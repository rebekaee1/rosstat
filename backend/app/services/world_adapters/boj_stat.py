"""Bank of Japan Time-Series Data Search API adapter.

Official API (no key, public since 2026-02-18)::

    https://www.stat-search.boj.or.jp/api/v1/getDataCode
    https://www.stat-search.boj.or.jp/api/v1/getMetadata

Manual: https://www.stat-search.boj.or.jp/info/api_manual_en.pdf

``WorldSeriesRef.dataset_id`` is the BoJ DB name (``FM01``, ``FM08``, ``IR01``,
``MD01``, ``MD02``). ``series_id`` is the short series code **without** the
``DB'`` prefix (e.g. ``STRDCLUCON``, not ``FM01'STRDCLUCON``). Daily/monthly
date windows use ``YYYYMM``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Mapping, Sequence

import requests

from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

logger = logging.getLogger(__name__)

BOJ_API_BASE = "https://www.stat-search.boj.or.jp/api/v1"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_COUNTRY_CODE = "JP"
_DEFAULT_DATE_FROM = date(1900, 1, 1)
_USER_AGENT = "ForecastEconomy/1.0 (+https://forecasteconomy.com; national-core)"


class BojStatError(RuntimeError):
    """Raised when BoJ Time-Series API returns an error or unusable payload."""


@dataclass(frozen=True)
class BojSeriesSpec:
    """Curated BoJ series: ``dataset_id`` = DB name, ``series_id`` = short code."""

    series_id: str
    dataset_id: str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "daily"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


# Confirmed live 2026-08-12 (getDataCode HTTP 200).
DEFAULT_BOJ_SERIES: tuple[BojSeriesSpec, ...] = (
    BojSeriesSpec(
        series_id="STRDCLUCON",
        dataset_id="FM01",
        title="Call Rate, Uncollateralized Overnight, Average (Daily)",
        unit_code="PERCENT",
        frequency="daily",
    ),
    BojSeriesSpec(
        series_id="MADR1Z@D",
        dataset_id="IR01",
        title="The Basic Discount Rate and Basic Loan Rate",
        unit_code="PERCENT",
        frequency="daily",
    ),
    BojSeriesSpec(
        series_id="FXERD04",
        dataset_id="FM08",
        title="US.Dollar/Yen Spot Rate at 17:00 in JST, Tokyo Market",
        unit_code="JPY_PER_USD",
        frequency="daily",
        dimensions={"quote": "JPY", "base": "USD"},
    ),
    BojSeriesSpec(
        series_id="MABS1AN11",
        dataset_id="MD01",
        title="Monetary Base/Average Amounts Outstanding",
        unit_code="JPY",
        frequency="monthly",
    ),
    BojSeriesSpec(
        series_id="MAM1NAM2M2MO",
        dataset_id="MD02",
        title="M2/Average Amounts Outstanding/Money Stock",
        unit_code="JPY",
        frequency="monthly",
    ),
    BojSeriesSpec(
        series_id="MAM1NAM3M3MO",
        dataset_id="MD02",
        title="M3/Average Amounts Outstanding/Money Stock",
        unit_code="JPY",
        frequency="monthly",
    ),
)


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise BojStatError("Empty BoJ series id")
    # Accept accidental full codes like FM01'STRDCLUCON → STRDCLUCON.
    if "'" in text:
        text = text.split("'", 1)[1].strip()
    if not text:
        raise BojStatError(f"Empty BoJ series id after stripping DB prefix: {raw!r}")
    return text


def normalize_dataset_id(raw: str) -> str:
    text = (raw or "").strip().upper()
    if not text:
        raise BojStatError("Empty BoJ dataset (DB) id")
    return text


def frequency_to_boj(freq: str | None) -> str:
    key = (freq or "daily").strip().lower()
    return {
        "daily": "D",
        "weekly": "W",
        "monthly": "M",
        "quarterly": "Q",
        "annual": "CY",
        "yearly": "CY",
    }.get(key, "D")


def format_boj_period(d: date, *, frequency: str) -> str:
    """BoJ startDate/endDate: daily/weekly/monthly → YYYYMM; quarter → YYYYQQ; year → YYYY."""
    freq = (frequency or "daily").strip().lower()
    if freq in {"annual", "yearly"}:
        return f"{d.year:04d}"
    if freq == "quarterly":
        q = (d.month - 1) // 3 + 1
        return f"{d.year:04d}{q:02d}"
    return f"{d.year:04d}{d.month:02d}"


def parse_boj_survey_date(raw: Any, *, frequency: str) -> date:
    """Parse BoJ SURVEY_DATES integers/strings into calendar dates."""
    text = str(raw).strip()
    if not text or text.lower() in {"none", "null"}:
        raise BojStatError(f"Empty BoJ survey date: {raw!r}")
    digits = "".join(ch for ch in text if ch.isdigit())
    freq = (frequency or "daily").strip().lower()
    try:
        if freq in {"annual", "yearly"} and len(digits) >= 4:
            return date(int(digits[:4]), 1, 1)
        if freq == "quarterly" and len(digits) >= 6:
            year = int(digits[:4])
            q = int(digits[4:6])
            if q < 1 or q > 4:
                raise ValueError("quarter out of range")
            return date(year, (q - 1) * 3 + 1, 1)
        if len(digits) >= 8:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        if len(digits) >= 6:
            return date(int(digits[:4]), int(digits[4:6]), 1)
        if len(digits) == 4:
            return date(int(digits), 1, 1)
    except ValueError as exc:
        raise BojStatError(f"Unparseable BoJ survey date: {raw!r}") from exc
    raise BojStatError(f"Unparseable BoJ survey date: {raw!r}")


def parse_boj_resultset(
    payload: Mapping[str, Any],
    *,
    series_id: str,
    frequency: str,
) -> tuple[str | None, list[WorldObservation]]:
    """Extract one series from getDataCode JSON RESULTSET."""
    sid = normalize_series_id(series_id)
    status = payload.get("STATUS")
    if status not in (200, "200", None):
        raise BojStatError(
            f"BoJ STATUS={status!r}: {payload.get('MESSAGE') or payload!r}"
        )
    rows = payload.get("RESULTSET")
    if not isinstance(rows, list) or not rows:
        raise BojStatError(f"BoJ RESULTSET empty for {sid}")

    match: Mapping[str, Any] | None = None
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if normalize_series_id(str(row.get("SERIES_CODE") or "")) == sid:
            match = row
            break
    if match is None:
        # Single-series request may omit needing a filter, but still require code match.
        if len(rows) == 1 and isinstance(rows[0], Mapping):
            match = rows[0]
        else:
            raise BojStatError(f"BoJ RESULTSET has no series {sid}")

    title = str(match.get("NAME_OF_TIME_SERIES") or "") or None
    values_block = match.get("VALUES")
    if not isinstance(values_block, Mapping):
        raise BojStatError(f"BoJ series {sid} missing VALUES block")
    survey_dates = values_block.get("SURVEY_DATES") or []
    values = values_block.get("VALUES") or []
    if not isinstance(survey_dates, list) or not isinstance(values, list):
        raise BojStatError(f"BoJ series {sid} VALUES malformed")
    if len(survey_dates) != len(values):
        raise BojStatError(
            f"BoJ series {sid} date/value length mismatch "
            f"{len(survey_dates)}!={len(values)}"
        )

    observations: list[WorldObservation] = []
    for raw_date, raw_value in zip(survey_dates, values):
        if raw_value is None or raw_value == "":
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise BojStatError(
                f"BoJ series {sid} non-numeric value: {raw_value!r}"
            ) from exc
        period = parse_boj_survey_date(raw_date, frequency=frequency)
        observations.append(WorldObservation(period=period, value=value))

    if not observations:
        raise BojStatError(f"BoJ series {sid} had no numeric observations")
    observations.sort(key=lambda item: item.period)
    return title, observations


def data_code_url(*, base_url: str = BOJ_API_BASE) -> str:
    return f"{base_url.rstrip('/')}/getDataCode"


def metadata_url(*, base_url: str = BOJ_API_BASE) -> str:
    return f"{base_url.rstrip('/')}/getMetadata"


def _specs_from_national(series_specs: Sequence[Any] | None) -> list[BojSeriesSpec]:
    out: list[BojSeriesSpec] = []
    for row in series_specs or ():
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider != "boj":
            continue
        sid = str(getattr(row, "series_id", "") or "").strip()
        did = str(getattr(row, "dataset_id", "") or "").strip()
        if not sid or not did:
            continue
        out.append(
            BojSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=getattr(row, "name_en", None) or getattr(row, "name_ru", None),
                unit_code=str(getattr(row, "unit", None) or "UNIT"),
                frequency=str(getattr(row, "frequency", None) or "daily"),
                dimensions=dict(getattr(row, "dimensions", None) or {}),
                source_url=getattr(row, "source_url", None),
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    **kwargs: Any,
) -> "BojStatAdapter":
    curated = _specs_from_national(series_specs)
    return BojStatAdapter(curated or None, **kwargs)


class BojStatAdapter:
    """``WorldSourceAdapter`` for Bank of Japan Time-Series API."""

    provider = "boj"
    public_source_name = "Bank of Japan"

    def __init__(
        self,
        series: Sequence[BojSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = BOJ_API_BASE,
        country_code: str = DEFAULT_COUNTRY_CODE,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_BOJ_SERIES
        if not curated:
            raise BojStatError("BojStatAdapter requires at least one curated series")
        self._series = curated
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._by_dataset: dict[str, list[BojSeriesSpec]] = {}
        self._by_series_id: dict[str, BojSeriesSpec] = {}
        for spec in self._series:
            sid = normalize_series_id(spec.series_id)
            did = normalize_dataset_id(spec.dataset_id)
            normalized = BojSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=(spec.frequency or "daily").strip().lower() or "daily",
                dimensions=dict(spec.dimensions),
                source_url=spec.source_url,
            )
            self._by_dataset.setdefault(did, []).append(normalized)
            self._by_series_id[sid] = normalized

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=members[0].title,
                metadata_url=f"{metadata_url(base_url=self._base_url)}?format=json&lang=en&db={dataset_id}",
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = normalize_dataset_id(dataset.dataset_id)
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise BojStatError(f"No curated BoJ series for dataset_id={dataset_id!r}")
        for spec in members:
            yield self._series_ref(spec)

    async def fetch_series(
        self,
        series: WorldSeriesRef,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorldSeriesPayload:
        if series.provider != self.provider:
            raise BojStatError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        series_id = normalize_series_id(series.series_id)
        dataset_id = normalize_dataset_id(series.dataset_id)
        frequency = (series.frequency or "daily").strip().lower() or "daily"
        start = date_from or _DEFAULT_DATE_FROM
        end = date_to or date.today()
        if end < start:
            raise BojStatError(
                f"date_to {end.isoformat()} is before date_from {start.isoformat()}"
            )
        fetched_at = datetime.now(timezone.utc)
        payload = await asyncio.to_thread(
            self._get_data_code_sync,
            dataset_id=dataset_id,
            series_id=series_id,
            frequency=frequency,
            start=start,
            end=end,
        )
        title, observations = parse_boj_resultset(
            payload, series_id=series_id, frequency=frequency
        )
        if date_from is not None or date_to is not None:
            lo = date_from or _DEFAULT_DATE_FROM
            hi = date_to or date.today()
            observations = [o for o in observations if lo <= o.period <= hi]
            if not observations:
                raise BojStatError(
                    f"BoJ series {series_id} empty after date filter "
                    f"{lo.isoformat()}..{hi.isoformat()}"
                )

        revision = (
            f"{observations[0].period.isoformat()}"
            f"/{observations[-1].period.isoformat()}"
            f"#{len(observations)}"
        )
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "db": dataset_id,
                    "series": series_id,
                    "n": len(observations),
                    "first": observations[0].period.isoformat(),
                    "last": observations[-1].period.isoformat(),
                    "last_value": observations[-1].value,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        ref = series
        if title and not series.title:
            ref = WorldSeriesRef(
                provider=series.provider,
                dataset_id=series.dataset_id,
                series_id=series.series_id,
                country_code=series.country_code,
                frequency=series.frequency,
                unit_code=series.unit_code,
                dimensions=dict(series.dimensions),
                title=title,
                source_url=series.source_url,
            )
        return WorldSeriesPayload(
            ref=ref,
            observations=observations,
            fetched_at=fetched_at,
            revision_token=revision,
            source_hash=source_hash,
        )

    def _get_json(self, url: str, *, params: Mapping[str, str]) -> dict[str, Any]:
        try:
            response = self._session.get(
                url,
                params=dict(params),
                timeout=self._timeout,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "User-Agent": _USER_AGENT,
                },
            )
        except requests.RequestException as exc:
            raise BojStatError(f"BoJ GET {url} failed: {exc}") from exc
        if response.status_code >= 400:
            raise BojStatError(
                f"BoJ GET {url} HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise BojStatError(
                f"BoJ GET {url} non-JSON: {response.text[:300]}"
            ) from exc
        if not isinstance(payload, dict):
            raise BojStatError(f"BoJ payload must be object, got {type(payload)!r}")
        return payload

    def _get_data_code_sync(
        self,
        *,
        dataset_id: str,
        series_id: str,
        frequency: str,
        start: date,
        end: date,
    ) -> dict[str, Any]:
        params = {
            "format": "json",
            "lang": "en",
            "db": dataset_id,
            "code": series_id,
            "startDate": format_boj_period(start, frequency=frequency),
            "endDate": format_boj_period(end, frequency=frequency),
        }
        return self._get_json(data_code_url(base_url=self._base_url), params=params)

    def _series_ref(self, spec: BojSeriesSpec) -> WorldSeriesRef:
        sid = normalize_series_id(spec.series_id)
        did = normalize_dataset_id(spec.dataset_id)
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=did,
            series_id=sid,
            country_code=self._country_code,
            frequency=(spec.frequency or "daily").strip().lower() or "daily",
            unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url
            or (
                f"{data_code_url(base_url=self._base_url)}"
                f"?format=json&lang=en&db={did}&code={sid}"
            ),
        )


ADAPTER = BojStatAdapter
