"""Japan e-Stat API 3.0 adapter (Statistics Bureau / MIC portal).

Official REST::

    https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData

Requires free application ID (``appId``). Set env ``RUSTATS_ESTAT_APP_ID``.
Without the key ``create_adapter`` raises ``AdapterUnavailable``.

``WorldSeriesRef.dataset_id`` = ``statsDataId``.
``series_id`` = stable passport suffix key (not necessarily an e-Stat code).
Narrowing filters live in ``dimensions`` (``cdCat01``, ``cdArea``, …) and are
passed through as query parameters.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
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

ESTAT_JSON_BASE = "https://api.e-stat.go.jp/rest/3.0/app/json"
DEFAULT_TIMEOUT_SEC = 90
DEFAULT_COUNTRY_CODE = "JP"
ENV_APP_ID = "RUSTATS_ESTAT_APP_ID"
_DEFAULT_DATE_FROM = date(1900, 1, 1)
_USER_AGENT = "ForecastEconomy/1.0 (+https://forecasteconomy.com; national-core)"
_TIME_RE = re.compile(
    r"^(?P<y>\d{4})"
    r"(?:[-./]?(?P<m>\d{1,2}))?"
    r"(?:[-./]?(?P<d>\d{1,2}))?"
    r"(?:[Qq](?P<q>[1-4]))?$"
)


class EstatApiError(RuntimeError):
    """Raised when e-Stat returns an error STATUS or unusable payload."""


@dataclass(frozen=True)
class EstatSeriesSpec:
    series_id: str
    dataset_id: str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "monthly"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


# Curated passport stubs (statsDataId from e-Stat catalogue; live fetch needs appId).
DEFAULT_ESTAT_SERIES: tuple[EstatSeriesSpec, ...] = (
    EstatSeriesSpec(
        series_id="cpi-all-items",
        dataset_id="0003427113",
        title="Consumer Price Index (all items)",
        unit_code="INDEX",
        frequency="monthly",
        dimensions={"cdArea": "00000"},
        source_url="https://www.e-stat.go.jp/en/stat-search/files?toukei=00200573",
    ),
    EstatSeriesSpec(
        series_id="unemployment-rate",
        dataset_id="0003143513",
        title="Unemployment rate (Labour Force Survey)",
        unit_code="PERCENT",
        frequency="monthly",
        source_url="https://www.e-stat.go.jp/en/stat-search/files?toukei=00200531",
    ),
    EstatSeriesSpec(
        series_id="gdp-real",
        dataset_id="0003411572",
        title="GDP (national accounts)",
        unit_code="JPY_BN",
        frequency="quarterly",
        source_url="https://www.e-stat.go.jp/en/stat-search/files?toukei=00100409",
    ),
)


def resolve_app_id(explicit: str | None = None) -> str | None:
    text = (explicit if explicit is not None else os.environ.get(ENV_APP_ID, "")).strip()
    return text or None


def normalize_stats_data_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise EstatApiError("Empty e-Stat statsDataId")
    return text


def parse_estat_time(raw: str, *, frequency: str) -> date:
    text = (raw or "").strip()
    if not text:
        raise EstatApiError("Empty e-Stat time code")
    # Common forms: 202401, 2024Q1, 2024-01, 2024.
    q_match = re.match(r"^(\d{4})\s*[Qq]([1-4])$", text)
    if q_match:
        year = int(q_match.group(1))
        q = int(q_match.group(2))
        return date(year, (q - 1) * 3 + 1, 1)
    digits = "".join(ch for ch in text if ch.isdigit())
    freq = (frequency or "monthly").strip().lower()
    try:
        if len(digits) >= 8:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        if len(digits) >= 6:
            return date(int(digits[:4]), int(digits[4:6]), 1)
        if len(digits) == 4:
            month = 1
            if freq == "quarterly":
                # Rare bare year for annual NA tables.
                month = 1
            return date(int(digits), month, 1)
    except ValueError as exc:
        raise EstatApiError(f"Unparseable e-Stat time: {raw!r}") from exc
    raise EstatApiError(f"Unparseable e-Stat time: {raw!r}")


def _result_status(payload: Mapping[str, Any]) -> tuple[int | None, str | None]:
    root = payload.get("GET_STATS_DATA") or payload.get("GET_STATS_LIST") or payload
    if not isinstance(root, Mapping):
        return None, None
    result = root.get("RESULT")
    if not isinstance(result, Mapping):
        return None, None
    status = result.get("STATUS")
    try:
        status_int = int(status) if status is not None else None
    except (TypeError, ValueError):
        status_int = None
    msg = result.get("ERROR_MSG") or result.get("ERROR_DETAIL") or result.get("DATE")
    return status_int, str(msg) if msg else None


def parse_estat_observations(
    payload: Mapping[str, Any],
    *,
    frequency: str,
) -> list[WorldObservation]:
    status, msg = _result_status(payload)
    if status is None:
        raise EstatApiError(f"e-Stat payload missing RESULT: {payload!r}"[:400])
    if status == 100:
        raise EstatApiError(
            f"e-Stat authentication failed (STATUS 100). "
            f"Set {ENV_APP_ID}. Detail: {msg}"
        )
    if status != 0:
        raise EstatApiError(f"e-Stat STATUS={status}: {msg}")

    root = payload.get("GET_STATS_DATA")
    if not isinstance(root, Mapping):
        raise EstatApiError("e-Stat GET_STATS_DATA missing")
    statistical = root.get("STATISTICAL_DATA")
    if not isinstance(statistical, Mapping):
        raise EstatApiError("e-Stat STATISTICAL_DATA missing")
    data_inf = statistical.get("DATA_INF")
    if not isinstance(data_inf, Mapping):
        raise EstatApiError("e-Stat DATA_INF missing")
    values = data_inf.get("VALUE")
    if values is None:
        raise EstatApiError("e-Stat VALUE missing")
    if isinstance(values, Mapping):
        values = [values]
    if not isinstance(values, list):
        raise EstatApiError(f"e-Stat VALUE must be list, got {type(values)!r}")

    observations: list[WorldObservation] = []
    for index, cell in enumerate(values):
        if not isinstance(cell, Mapping):
            raise EstatApiError(f"VALUE[{index}] is not an object")
        raw_time = cell.get("@time") or cell.get("time") or cell.get("@TIME")
        raw_value = cell.get("$") if "$" in cell else cell.get("value")
        if raw_value is None or raw_value == "" or str(raw_value).strip() in {"*", "-"}:
            continue
        try:
            value = float(str(raw_value).replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise EstatApiError(
                f"VALUE[{index}] non-numeric: {raw_value!r}"
            ) from exc
        period = parse_estat_time(str(raw_time or ""), frequency=frequency)
        observations.append(WorldObservation(period=period, value=value))

    if not observations:
        raise EstatApiError("e-Stat VALUE had no numeric observations")
    # Keep latest value per period (tables sometimes repeat).
    by_period: dict[date, float] = {}
    for obs in observations:
        by_period[obs.period] = obs.value
    return [WorldObservation(period=p, value=v) for p, v in sorted(by_period.items())]


def _specs_from_national(series_specs: Sequence[Any] | None) -> list[EstatSeriesSpec]:
    out: list[EstatSeriesSpec] = []
    for row in series_specs or ():
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider != "estat":
            continue
        sid = str(getattr(row, "series_id", "") or "").strip()
        did = str(getattr(row, "dataset_id", "") or "").strip()
        if not sid or not did:
            continue
        out.append(
            EstatSeriesSpec(
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
    app_id: str | None = None,
    **kwargs: Any,
) -> "EstatApiAdapter":
    from app.services.world_national_ingest import AdapterUnavailable

    resolved = resolve_app_id(app_id)
    if not resolved:
        raise AdapterUnavailable(
            f"estat adapter requires {ENV_APP_ID} "
            "(free appId from https://www.e-stat.go.jp/api/)"
        )
    curated = _specs_from_national(series_specs)
    return EstatApiAdapter(curated or None, app_id=resolved, **kwargs)


class EstatApiAdapter:
    """``WorldSourceAdapter`` for Japan e-Stat REST 3.0."""

    provider = "estat"
    public_source_name = "Statistics Bureau of Japan (e-Stat)"

    def __init__(
        self,
        series: Sequence[EstatSeriesSpec] | None = None,
        *,
        app_id: str,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = ESTAT_JSON_BASE,
        country_code: str = DEFAULT_COUNTRY_CODE,
    ) -> None:
        if not (app_id or "").strip():
            raise EstatApiError(f"e-Stat appId required ({ENV_APP_ID})")
        curated = tuple(series) if series is not None else DEFAULT_ESTAT_SERIES
        if not curated:
            raise EstatApiError("EstatApiAdapter requires at least one curated series")
        self._app_id = app_id.strip()
        self._series = curated
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._by_dataset: dict[str, list[EstatSeriesSpec]] = {}
        self._by_series_id: dict[str, EstatSeriesSpec] = {}
        for spec in self._series:
            sid = str(spec.series_id).strip()
            did = normalize_stats_data_id(spec.dataset_id)
            normalized = EstatSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=(spec.frequency or "monthly").strip().lower() or "monthly",
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
                metadata_url=(
                    f"{self._base_url}/getStatsData?appId=***"
                    f"&statsDataId={dataset_id}&limit=1"
                ),
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = normalize_stats_data_id(dataset.dataset_id)
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise EstatApiError(f"No curated e-Stat series for {dataset_id!r}")
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
            raise EstatApiError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        dataset_id = normalize_stats_data_id(series.dataset_id)
        frequency = (series.frequency or "monthly").strip().lower() or "monthly"
        curated = self._by_series_id.get(str(series.series_id).strip())
        dims = dict(series.dimensions or {})
        if curated:
            for key, value in curated.dimensions.items():
                dims.setdefault(key, value)
        fetched_at = datetime.now(timezone.utc)
        payload = await asyncio.to_thread(
            self._get_stats_data_sync,
            dataset_id=dataset_id,
            dimensions=dims,
        )
        observations = parse_estat_observations(payload, frequency=frequency)
        lo = date_from or _DEFAULT_DATE_FROM
        hi = date_to or date.today()
        observations = [o for o in observations if lo <= o.period <= hi]
        if not observations:
            raise EstatApiError(
                f"e-Stat {dataset_id}/{series.series_id} empty after date filter"
            )

        revision = (
            f"{observations[0].period.isoformat()}"
            f"/{observations[-1].period.isoformat()}"
            f"#{len(observations)}"
        )
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "statsDataId": dataset_id,
                    "series": series.series_id,
                    "dims": dims,
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

    def _get_stats_data_sync(
        self,
        *,
        dataset_id: str,
        dimensions: Mapping[str, str],
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "appId": self._app_id,
            "statsDataId": dataset_id,
            "metaGetFlg": "N",
            "cntGetFlg": "N",
            "sectionHeaderFlg": "1",
        }
        for key, value in dimensions.items():
            k = str(key).strip()
            v = str(value).strip()
            if k and v:
                params[k] = v
        url = f"{self._base_url}/getStatsData"
        try:
            response = self._session.get(
                url,
                params=params,
                timeout=self._timeout,
                headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
            )
        except requests.RequestException as exc:
            raise EstatApiError(f"e-Stat GET failed: {exc}") from exc
        if response.status_code >= 400:
            raise EstatApiError(
                f"e-Stat HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise EstatApiError(f"e-Stat non-JSON: {response.text[:300]}") from exc
        if not isinstance(payload, dict):
            raise EstatApiError(f"e-Stat payload must be object, got {type(payload)!r}")
        return payload

    def _series_ref(self, spec: EstatSeriesSpec) -> WorldSeriesRef:
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=normalize_stats_data_id(spec.dataset_id),
            series_id=str(spec.series_id).strip(),
            country_code=self._country_code,
            frequency=(spec.frequency or "monthly").strip().lower() or "monthly",
            unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url
            or f"https://www.e-stat.go.jp/stat-search/database?statdisp_id={spec.dataset_id}",
        )


# Prefer create_adapter so missing RUSTATS_ESTAT_APP_ID → AdapterUnavailable.
# Do not export ADAPTER class alias (would bypass the key gate).
