"""Bank of Korea ECOS Open API adapter.

Official REST (API key required)::

    https://ecos.bok.or.kr/api/StatisticSearch/{apiKey}/json/en/{start}/{end}/
        {statCode}/{cycle}/{startTime}/{endTime}/{itemCode1}/…

Register at https://ecos.bok.or.kr/api/ — set ``RUSTATS_ECOS_API_KEY``.
Without the key ``create_adapter`` raises ``AdapterUnavailable``.
The portal ``sample`` key returns ≤10 rows and is **not** accepted for ingest
unless ``RUSTATS_ECOS_ALLOW_SAMPLE=1``.

``WorldSeriesRef.dataset_id`` = ECOS ``STAT_CODE`` (e.g. ``722Y001``).
``series_id`` = item path ``item1`` or ``item1/item2`` (e.g. ``I61BC/I28B``).
Cycle is derived from platform frequency (D/M/Q/A).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
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

ECOS_API_BASE = "https://ecos.bok.or.kr/api"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_COUNTRY_CODE = "KR"
ENV_API_KEY = "RUSTATS_ECOS_API_KEY"
ENV_ALLOW_SAMPLE = "RUSTATS_ECOS_ALLOW_SAMPLE"
_DEFAULT_DATE_FROM = date(1990, 1, 1)
_PAGE_SIZE = 1000
_USER_AGENT = "ForecastEconomy/1.0 (+https://forecasteconomy.com; national-core)"


class EcosBokError(RuntimeError):
    """Raised when ECOS returns RESULT.CODE error or unusable payload."""


@dataclass(frozen=True)
class EcosSeriesSpec:
    series_id: str
    dataset_id: str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "monthly"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


# Confirmed with ECOS sample key 2026-08-12 (codes/windows OK; full history needs real key).
DEFAULT_ECOS_SERIES: tuple[EcosSeriesSpec, ...] = (
    EcosSeriesSpec(
        series_id="0",
        dataset_id="901Y009",
        title="Consumer Price Index (all items, 2020=100)",
        unit_code="INDEX",
        frequency="monthly",
    ),
    EcosSeriesSpec(
        series_id="I61BC/I28B",
        dataset_id="901Y027",
        title="Unemployment rate (seasonally adjusted)",
        unit_code="PERCENT",
        frequency="monthly",
    ),
    EcosSeriesSpec(
        series_id="1400",
        dataset_id="200Y104",
        title="Real GDP at market prices (SA, chained 2020)",
        unit_code="KRW_BN",
        frequency="quarterly",
    ),
    EcosSeriesSpec(
        series_id="10101",
        dataset_id="200Y101",
        title="Nominal GDP (current prices, annual)",
        unit_code="KRW_BN",
        frequency="annual",
    ),
    EcosSeriesSpec(
        series_id="0101000",
        dataset_id="722Y001",
        title="Bank of Korea Base Rate",
        unit_code="PERCENT",
        frequency="daily",
    ),
    EcosSeriesSpec(
        series_id="0000001",
        dataset_id="731Y001",
        title="Won per United States Dollar (Basic Exchange Rate)",
        unit_code="KRW_PER_USD",
        frequency="daily",
        dimensions={"quote": "KRW", "base": "USD"},
    ),
    EcosSeriesSpec(
        series_id="000000",
        dataset_id="301Y013",
        title="Current account",
        unit_code="USD_MN",
        frequency="monthly",
    ),
    EcosSeriesSpec(
        series_id="99",
        dataset_id="732Y001",
        title="International reserves (total)",
        unit_code="USD_THOU",
        frequency="monthly",
    ),
)


def resolve_api_key(explicit: str | None = None) -> str | None:
    text = (explicit if explicit is not None else os.environ.get(ENV_API_KEY, "")).strip()
    return text or None


def allow_sample_key() -> bool:
    return os.environ.get(ENV_ALLOW_SAMPLE, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


def frequency_to_cycle(freq: str | None) -> str:
    key = (freq or "monthly").strip().lower()
    return {
        "daily": "D",
        "monthly": "M",
        "quarterly": "Q",
        "annual": "A",
        "yearly": "A",
        "weekly": "SM",
    }.get(key, "M")


def format_ecos_time(d: date, *, cycle: str) -> str:
    c = (cycle or "M").upper()
    if c == "D":
        return d.strftime("%Y%m%d")
    if c == "M":
        return d.strftime("%Y%m")
    if c == "Q":
        q = (d.month - 1) // 3 + 1
        return f"{d.year}Q{q}"
    if c == "A":
        return f"{d.year:04d}"
    return d.strftime("%Y%m")


def parse_ecos_time(raw: str, *, cycle: str) -> date:
    text = (raw or "").strip()
    if not text:
        raise EcosBokError("Empty ECOS TIME")
    c = (cycle or "M").upper()
    try:
        if c == "D" and len(text) >= 8:
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        if c == "M" and len(text) >= 6:
            return date(int(text[:4]), int(text[4:6]), 1)
        if c == "Q":
            # 2026Q1 or 202601 (rare)
            if "Q" in text.upper():
                y, _, q = text.upper().partition("Q")
                return date(int(y), (int(q) - 1) * 3 + 1, 1)
            if len(text) >= 6:
                return date(int(text[:4]), (int(text[4:6]) - 1) * 3 + 1, 1)
        if c == "A" and len(text) >= 4:
            return date(int(text[:4]), 1, 1)
        # Fallback heuristics
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) >= 8:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        if len(digits) >= 6:
            return date(int(digits[:4]), int(digits[4:6]), 1)
        if len(digits) == 4:
            return date(int(digits), 1, 1)
    except ValueError as exc:
        raise EcosBokError(f"Unparseable ECOS TIME: {raw!r}") from exc
    raise EcosBokError(f"Unparseable ECOS TIME: {raw!r}")


def split_item_path(series_id: str) -> list[str]:
    text = (series_id or "").strip()
    if not text:
        raise EcosBokError("Empty ECOS item / series_id")
    parts = [p.strip() for p in text.split("/") if p.strip()]
    if not parts:
        raise EcosBokError(f"Empty ECOS item path: {series_id!r}")
    return parts


def parse_ecos_search_payload(
    payload: Mapping[str, Any],
    *,
    cycle: str,
) -> list[WorldObservation]:
    if "RESULT" in payload and isinstance(payload["RESULT"], Mapping):
        result = payload["RESULT"]
        code = str(result.get("CODE") or "")
        if code and not code.upper().startswith("INFO-000"):
            # INFO-200 = no data; ERROR-* = hard fail
            if code.upper().startswith("ERROR") or code.upper().startswith("INFO-200"):
                raise EcosBokError(
                    f"ECOS {code}: {result.get('MESSAGE') or result!r}"
                )
    block = payload.get("StatisticSearch")
    if not isinstance(block, Mapping):
        raise EcosBokError(f"ECOS StatisticSearch missing: {payload!r}"[:300])
    rows = block.get("row")
    if rows is None:
        raise EcosBokError("ECOS StatisticSearch.row missing")
    if isinstance(rows, Mapping):
        rows = [rows]
    if not isinstance(rows, list) or not rows:
        raise EcosBokError("ECOS StatisticSearch.row empty")

    observations: list[WorldObservation] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise EcosBokError(f"ECOS row[{index}] is not an object")
        raw_value = row.get("DATA_VALUE")
        if raw_value is None or raw_value == "":
            continue
        try:
            value = float(str(raw_value).replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise EcosBokError(
                f"ECOS row[{index}] non-numeric DATA_VALUE: {raw_value!r}"
            ) from exc
        period = parse_ecos_time(str(row.get("TIME") or ""), cycle=cycle)
        observations.append(WorldObservation(period=period, value=value))
    if not observations:
        raise EcosBokError("ECOS rows had no numeric DATA_VALUE")
    by_period: dict[date, float] = {}
    for obs in observations:
        by_period[obs.period] = obs.value
    return [WorldObservation(period=p, value=v) for p, v in sorted(by_period.items())]


def statistic_search_url(
    *,
    api_key: str,
    stat_code: str,
    cycle: str,
    start_time: str,
    end_time: str,
    item_codes: Sequence[str],
    start_index: int = 1,
    end_index: int = _PAGE_SIZE,
    lang: str = "en",
    base_url: str = ECOS_API_BASE,
) -> str:
    """Build StatisticSearch path (key and codes stay unquoted path segments)."""
    filled = [str(c).strip() for c in item_codes if str(c).strip()]
    if not filled:
        raise EcosBokError("ECOS item_codes required")
    segs = [
        "StatisticSearch",
        api_key,
        "json",
        lang,
        str(int(start_index)),
        str(int(end_index)),
        stat_code,
        cycle,
        start_time,
        end_time,
        *filled,
    ]
    return base_url.rstrip("/") + "/" + "/".join(segs)


def _specs_from_national(series_specs: Sequence[Any] | None) -> list[EcosSeriesSpec]:
    out: list[EcosSeriesSpec] = []
    for row in series_specs or ():
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider not in {"ecos", "bok_ecos"}:
            continue
        sid = str(getattr(row, "series_id", "") or "").strip()
        did = str(getattr(row, "dataset_id", "") or "").strip()
        if not sid or not did:
            continue
        out.append(
            EcosSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=getattr(row, "name_en", None) or getattr(row, "name_ru", None),
                unit_code=str(getattr(row, "unit", None) or "UNIT"),
                frequency=str(getattr(row, "frequency", None) or "monthly"),
                dimensions=dict(getattr(row, "dimensions", None) or {}),
                source_url=getattr(row, "source_url", None),
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    api_key: str | None = None,
    **kwargs: Any,
) -> "EcosBokAdapter":
    from app.services.world_national_ingest import AdapterUnavailable

    resolved = resolve_api_key(api_key)
    if not resolved:
        raise AdapterUnavailable(
            f"ecos adapter requires {ENV_API_KEY} "
            "(register at https://ecos.bok.or.kr/api/)"
        )
    if resolved.lower() == "sample" and not allow_sample_key():
        raise AdapterUnavailable(
            f"ECOS key 'sample' is capped at 10 rows; set a real {ENV_API_KEY} "
            f"or {ENV_ALLOW_SAMPLE}=1 for probe-only"
        )
    curated = _specs_from_national(series_specs)
    return EcosBokAdapter(curated or None, api_key=resolved, **kwargs)


class EcosBokAdapter:
    """``WorldSourceAdapter`` for Bank of Korea ECOS Open API."""

    provider = "ecos"
    public_source_name = "Bank of Korea"

    def __init__(
        self,
        series: Sequence[EcosSeriesSpec] | None = None,
        *,
        api_key: str,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = ECOS_API_BASE,
        country_code: str = DEFAULT_COUNTRY_CODE,
        page_size: int = _PAGE_SIZE,
    ) -> None:
        if not (api_key or "").strip():
            raise EcosBokError(f"ECOS api_key required ({ENV_API_KEY})")
        curated = tuple(series) if series is not None else DEFAULT_ECOS_SERIES
        if not curated:
            raise EcosBokError("EcosBokAdapter requires at least one curated series")
        self._api_key = api_key.strip()
        self._series = curated
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._page_size = max(1, int(page_size))
        self._by_dataset: dict[str, list[EcosSeriesSpec]] = {}
        self._by_series_key: dict[tuple[str, str], EcosSeriesSpec] = {}
        for spec in self._series:
            sid = str(spec.series_id).strip()
            did = str(spec.dataset_id).strip()
            normalized = EcosSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=(spec.frequency or "monthly").strip().lower() or "monthly",
                dimensions=dict(spec.dimensions),
                source_url=spec.source_url,
            )
            self._by_dataset.setdefault(did, []).append(normalized)
            self._by_series_key[(did, sid)] = normalized

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=members[0].title,
                metadata_url=f"https://ecos.bok.or.kr/#/SearchStat/{dataset_id}",
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = (dataset.dataset_id or "").strip()
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise EcosBokError(f"No curated ECOS series for {dataset_id!r}")
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
            raise EcosBokError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        dataset_id = (series.dataset_id or "").strip()
        series_id = (series.series_id or "").strip()
        frequency = (series.frequency or "monthly").strip().lower() or "monthly"
        cycle = frequency_to_cycle(
            (series.dimensions or {}).get("cycle") or frequency
        )
        start = date_from or _DEFAULT_DATE_FROM
        end = date_to or date.today()
        if end < start:
            raise EcosBokError(
                f"date_to {end.isoformat()} is before date_from {start.isoformat()}"
            )
        item_codes = split_item_path(series_id)
        fetched_at = datetime.now(timezone.utc)
        observations = await asyncio.to_thread(
            self._fetch_all_pages_sync,
            stat_code=dataset_id,
            cycle=cycle,
            start_time=format_ecos_time(start, cycle=cycle),
            end_time=format_ecos_time(end, cycle=cycle),
            item_codes=item_codes,
        )
        revision = (
            f"{observations[0].period.isoformat()}"
            f"/{observations[-1].period.isoformat()}"
            f"#{len(observations)}"
        )
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "stat": dataset_id,
                    "items": item_codes,
                    "cycle": cycle,
                    "n": len(observations),
                    "first": observations[0].period.isoformat(),
                    "last": observations[-1].period.isoformat(),
                    "last_value": observations[-1].value,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return WorldSeriesPayload(
            ref=series,
            observations=observations,
            fetched_at=fetched_at,
            revision_token=revision,
            source_hash=source_hash,
        )

    def _fetch_all_pages_sync(
        self,
        *,
        stat_code: str,
        cycle: str,
        start_time: str,
        end_time: str,
        item_codes: Sequence[str],
    ) -> list[WorldObservation]:
        collected: list[WorldObservation] = []
        start_index = 1
        total: int | None = None
        while True:
            end_index = start_index + self._page_size - 1
            url = statistic_search_url(
                api_key=self._api_key,
                stat_code=stat_code,
                cycle=cycle,
                start_time=start_time,
                end_time=end_time,
                item_codes=item_codes,
                start_index=start_index,
                end_index=end_index,
                base_url=self._base_url,
            )
            payload = self._get_json(url)
            if total is None:
                block = payload.get("StatisticSearch")
                if isinstance(block, Mapping):
                    try:
                        total = int(block.get("list_total_count") or 0)
                    except (TypeError, ValueError):
                        total = None
            page = parse_ecos_search_payload(payload, cycle=cycle)
            collected.extend(page)
            if total is not None and end_index >= total:
                break
            if len(page) < self._page_size:
                break
            start_index = end_index + 1
            if start_index > 100_000:
                raise EcosBokError("ECOS pagination exceeded safety limit")

        by_period: dict[date, float] = {}
        for obs in collected:
            by_period[obs.period] = obs.value
        out = [WorldObservation(period=p, value=v) for p, v in sorted(by_period.items())]
        if not out:
            raise EcosBokError(
                f"ECOS {stat_code}/{ '/'.join(item_codes)} returned no observations"
            )
        return out

    def _get_json(self, url: str) -> dict[str, Any]:
        try:
            response = self._session.get(
                url,
                timeout=self._timeout,
                headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
            )
        except requests.RequestException as exc:
            raise EcosBokError(f"ECOS GET failed: {exc}") from exc
        if response.status_code >= 400:
            raise EcosBokError(
                f"ECOS HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise EcosBokError(f"ECOS non-JSON: {response.text[:300]}") from exc
        if not isinstance(payload, dict):
            raise EcosBokError(f"ECOS payload must be object, got {type(payload)!r}")
        return payload

    def _series_ref(self, spec: EcosSeriesSpec) -> WorldSeriesRef:
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=str(spec.dataset_id).strip(),
            series_id=str(spec.series_id).strip(),
            country_code=self._country_code,
            frequency=(spec.frequency or "monthly").strip().lower() or "monthly",
            unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url
            or f"https://ecos.bok.or.kr/#/SearchStat/{spec.dataset_id}",
        )


# Prefer create_adapter so missing RUSTATS_ECOS_API_KEY → AdapterUnavailable.
