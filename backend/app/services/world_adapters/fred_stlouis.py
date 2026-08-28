"""Federal Reserve Bank of St. Louis FRED adapter (official).

Primary transport is the public graph CSV (no API key)::

    GET https://fred.stlouisfed.org/graph/fredgraph.csv
        ?id={SERIES_ID}
        &cosd=YYYY-MM-DD   # optional start
        &coed=YYYY-MM-DD   # optional end

Optional JSON Observations API when ``RUSTATS_FRED_API_KEY`` is set::

    GET https://api.stlouisfed.org/fred/series/observations
        ?series_id=…&api_key=…&file_type=json

FRED redistributes official BLS / BEA / Fed / Census series; provenance on
each passport row points at the FRED series page. Keyless CSV is preferred;
missing API key never blocks CSV mode.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
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

FRED_GRAPH_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_API_BASE = "https://api.stlouisfed.org/fred"
FRED_SERIES_PAGE = "https://fred.stlouisfed.org/series"
DEFAULT_TIMEOUT_SEC = 180
DEFAULT_COUNTRY_CODE = "US"
_ENV_API_KEY = "RUSTATS_FRED_API_KEY"
_DEFAULT_DATE_FROM = date(1900, 1, 1)


class FredStLouisError(RuntimeError):
    """Raised when FRED returns an unusable payload or HTTP error."""


@dataclass(frozen=True)
class FredSeriesSpec:
    """Curated FRED series. ``dataset_id`` defaults to ``series_id``."""

    series_id: str
    dataset_id: str | None = None
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "monthly"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


# Confirmed live passport series (CSV graph endpoint, 2026-08-12).
DEFAULT_FRED_SERIES: tuple[FredSeriesSpec, ...] = (
    FredSeriesSpec(
        series_id="CPIAUCSL",
        title="Consumer Price Index for All Urban Consumers: All Items (SA)",
        unit_code="INDEX",
        frequency="monthly",
        dimensions={"origin": "bls"},
    ),
    FredSeriesSpec(
        series_id="UNRATE",
        title="Unemployment Rate (SA)",
        unit_code="PERCENT",
        frequency="monthly",
        dimensions={"origin": "bls"},
    ),
    FredSeriesSpec(
        series_id="PAYEMS",
        title="All Employees, Total Nonfarm (SA)",
        unit_code="THOUSANDS",
        frequency="monthly",
        dimensions={"origin": "bls"},
    ),
    FredSeriesSpec(
        series_id="GDPC1",
        title="Real Gross Domestic Product (SAAR, billions of chained 2017 USD)",
        unit_code="USD_BN_CHAINED",
        frequency="quarterly",
        dimensions={"origin": "bea"},
    ),
    FredSeriesSpec(
        series_id="RSAFS",
        title="Advance Retail Sales: Retail Trade (SA, millions of USD)",
        unit_code="USD_MN",
        frequency="monthly",
        dimensions={"origin": "census"},
    ),
    FredSeriesSpec(
        series_id="FEDFUNDS",
        title="Federal Funds Effective Rate (monthly average)",
        unit_code="PERCENT",
        frequency="monthly",
        dimensions={"origin": "fed"},
    ),
    FredSeriesSpec(
        series_id="DTWEXBGS",
        title="Trade Weighted U.S. Dollar Index: Broad, Goods and Services",
        unit_code="INDEX",
        frequency="daily",
        dimensions={"origin": "fed"},
    ),
    FredSeriesSpec(
        series_id="DEXUSEU",
        title="U.S. / Euro Foreign Exchange Rate",
        unit_code="USD_PER_EUR",
        frequency="daily",
        dimensions={"origin": "fed", "quote": "EUR", "base": "USD"},
    ),
    FredSeriesSpec(
        series_id="INDPRO",
        title="Industrial Production: Total Index (SA, 2017=100)",
        unit_code="INDEX",
        frequency="monthly",
        dimensions={"origin": "fed"},
    ),
)


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip().upper()
    if not text:
        raise FredStLouisError("Empty FRED series id")
    return text


def normalize_dataset_id(raw: str | None, *, series_id: str) -> str:
    text = (raw or "").strip()
    return text or series_id


def series_page_url(series_id: str) -> str:
    return f"{FRED_SERIES_PAGE}/{normalize_series_id(series_id)}"


def graph_csv_url(
    series_id: str,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    base_url: str = FRED_GRAPH_CSV,
) -> str:
    """Build the public CSV URL (params applied by the HTTP client)."""
    sid = normalize_series_id(series_id)
    # Stable identity URL without date window (window is a fetch param).
    _ = (date_from, date_to, base_url)
    return f"{FRED_GRAPH_CSV}?id={sid}"


def parse_observation_date(raw: str) -> date:
    text = (raw or "").strip()
    if not text:
        raise FredStLouisError("Empty FRED observation date")
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise FredStLouisError(f"Unparseable FRED observation date: {raw!r}") from exc


def parse_fred_csv(
    text: str,
    *,
    series_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[WorldObservation]:
    """Parse ``fredgraph.csv`` body: header ``observation_date,<SERIES>``."""
    sid = normalize_series_id(series_id)
    if not (text or "").strip():
        raise FredStLouisError(f"FRED CSV empty for {sid}")

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise FredStLouisError(f"FRED CSV has no header for {sid}") from exc

    if len(header) < 2:
        raise FredStLouisError(f"FRED CSV header too short for {sid}: {header!r}")

    date_col = 0
    value_col = 1
    # Prefer exact series column if present; else second column.
    for index, name in enumerate(header):
        if normalize_series_id(name) == sid:
            value_col = index
            break

    observations: list[WorldObservation] = []
    for row_index, row in enumerate(reader, start=2):
        if not row or len(row) <= max(date_col, value_col):
            continue
        raw_date = (row[date_col] or "").strip()
        raw_value = (row[value_col] or "").strip()
        if not raw_date:
            continue
        # FRED uses "." for missing observations.
        if not raw_value or raw_value == ".":
            continue
        try:
            period = parse_observation_date(raw_date)
        except FredStLouisError:
            raise
        if date_from is not None and period < date_from:
            continue
        if date_to is not None and period > date_to:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise FredStLouisError(
                f"FRED CSV row {row_index} non-numeric for {sid}: {raw_value!r}"
            ) from exc
        observations.append(WorldObservation(period=period, value=value))

    if not observations:
        raise FredStLouisError(f"FRED CSV had no numeric values for {sid}")
    observations.sort(key=lambda item: item.period)
    return observations


def parse_fred_api_observations(
    payload: Mapping[str, Any],
    *,
    series_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[WorldObservation]:
    """Parse FRED JSON ``observations`` list."""
    sid = normalize_series_id(series_id)
    raw_obs = payload.get("observations")
    if not isinstance(raw_obs, list) or not raw_obs:
        raise FredStLouisError(f"FRED API observations missing/empty for {sid}")

    observations: list[WorldObservation] = []
    for index, item in enumerate(raw_obs):
        if not isinstance(item, Mapping):
            raise FredStLouisError(f"observations[{index}] is not an object")
        period = parse_observation_date(str(item.get("date") or ""))
        if date_from is not None and period < date_from:
            continue
        if date_to is not None and period > date_to:
            continue
        raw_value = item.get("value")
        if raw_value is None or raw_value == "" or raw_value == ".":
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise FredStLouisError(
                f"observations[{index}].value non-numeric: {raw_value!r}"
            ) from exc
        observations.append(WorldObservation(period=period, value=value))

    if not observations:
        raise FredStLouisError(f"FRED API had no numeric values for {sid}")
    observations.sort(key=lambda item: item.period)
    return observations


def _api_key_from_env() -> str | None:
    raw = (os.environ.get(_ENV_API_KEY) or "").strip()
    return raw or None


def _specs_from_national(series_specs: Sequence[Any]) -> list[FredSeriesSpec]:
    out: list[FredSeriesSpec] = []
    for row in series_specs:
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider != "fred":
            continue
        sid = normalize_series_id(str(getattr(row, "series_id", "") or ""))
        did = str(getattr(row, "dataset_id", "") or "").strip() or sid
        freq = getattr(row, "frequency", None)
        unit = getattr(row, "unit", None) or getattr(row, "unit_code", None) or "UNIT"
        dims = dict(getattr(row, "dimensions", None) or {})
        title = getattr(row, "name_en", None) or getattr(row, "name_ru", None) or getattr(
            row, "title", None
        )
        out.append(
            FredSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=str(title) if title else None,
                unit_code=str(unit).strip().upper() or "UNIT",
                frequency=str(freq).strip().lower() if freq else "monthly",
                dimensions=dims,
                source_url=getattr(row, "source_url", None),
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    **kwargs: Any,
) -> "FredStLouisAdapter":
    """Factory for ``world_national_ingest.resolve_adapter``."""
    curated: Sequence[FredSeriesSpec] | None = None
    if series_specs is not None:
        mapped = _specs_from_national(series_specs)
        curated = mapped if mapped else None
    return FredStLouisAdapter(curated, **kwargs)


class FredStLouisAdapter:
    """``WorldSourceAdapter`` for FRED (St. Louis Fed)."""

    provider = "fred"
    public_source_name = "Federal Reserve Bank of St. Louis"

    def __init__(
        self,
        series: Sequence[FredSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        csv_base_url: str = FRED_GRAPH_CSV,
        api_base_url: str = FRED_API_BASE,
        api_key: str | None = None,
        prefer_api: bool = False,
        country_code: str = DEFAULT_COUNTRY_CODE,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_FRED_SERIES
        if not curated:
            raise FredStLouisError(
                "FredStLouisAdapter requires at least one curated FredSeriesSpec"
            )
        self._series = curated
        self._session = session or requests.Session()
        self._timeout = timeout
        self._csv_base_url = csv_base_url.rstrip("?")
        self._api_base_url = api_base_url.rstrip("/")
        resolved_key = (api_key if api_key is not None else _api_key_from_env()) or None
        self._api_key = resolved_key
        self._prefer_api = prefer_api and bool(resolved_key)
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._by_dataset: dict[str, list[FredSeriesSpec]] = {}
        self._by_series_id: dict[str, FredSeriesSpec] = {}
        for spec in self._series:
            sid = normalize_series_id(spec.series_id)
            did = normalize_dataset_id(spec.dataset_id, series_id=sid)
            normalized = FredSeriesSpec(
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
                metadata_url=series_page_url(members[0].series_id),
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = (dataset.dataset_id or "").strip()
        members = self._by_dataset.get(dataset_id)
        if not members:
            # Allow lookup by series id when dataset_id == series_id.
            spec = self._by_series_id.get(normalize_series_id(dataset_id))
            if spec is None:
                raise FredStLouisError(
                    f"No curated FRED series for dataset_id={dataset_id!r}"
                )
            members = [spec]
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
            raise FredStLouisError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        series_id = normalize_series_id(series.series_id)
        fetched_at = datetime.now(timezone.utc)

        if self._prefer_api:
            if not self._api_key:
                from app.services.world_national_ingest import AdapterUnavailable

                raise AdapterUnavailable(
                    f"FRED JSON API requested but {_ENV_API_KEY} is not set"
                )
            observations = await asyncio.to_thread(
                self._fetch_via_api_sync,
                series_id,
                date_from=date_from,
                date_to=date_to,
            )
        else:
            observations = await asyncio.to_thread(
                self._fetch_via_csv_sync,
                series_id,
                date_from=date_from,
                date_to=date_to,
            )

        revision = None
        if observations:
            revision = (
                f"{observations[0].period.isoformat()}"
                f"/{observations[-1].period.isoformat()}"
                f"#{len(observations)}"
            )
        source_hash = hashlib.sha256(
            json.dumps(
                {
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
        if not series.source_url:
            ref = WorldSeriesRef(
                provider=series.provider,
                dataset_id=series.dataset_id,
                series_id=series.series_id,
                country_code=series.country_code,
                frequency=series.frequency,
                unit_code=series.unit_code,
                dimensions=dict(series.dimensions),
                title=series.title,
                source_url=series_page_url(series_id),
            )

        return WorldSeriesPayload(
            ref=ref,
            observations=observations,
            fetched_at=fetched_at,
            revision_token=revision,
            source_hash=source_hash,
        )

    # ------------------------------------------------------------------ sync HTTP

    def _get_text(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = self._session.get(
                    url,
                    params=dict(params or {}),
                    timeout=self._timeout,
                    headers={"Accept": "text/csv,text/plain,*/*"},
                )
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "FRED GET %s attempt %s failed: %s", url, attempt + 1, exc
                )
                continue
            if response.status_code >= 400:
                raise FredStLouisError(
                    f"FRED GET {url} HTTP {response.status_code}: {response.text[:300]}"
                )
            return response.text
        raise FredStLouisError(f"FRED GET {url} failed: {last_exc}") from last_exc

    def _get_json(self, url: str, *, params: Mapping[str, str] | None = None) -> Any:
        try:
            response = self._session.get(
                url,
                params=dict(params or {}),
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
        except requests.RequestException as exc:
            raise FredStLouisError(f"FRED GET {url} failed: {exc}") from exc
        if response.status_code >= 400:
            raise FredStLouisError(
                f"FRED GET {url} HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise FredStLouisError(
                f"FRED GET {url} returned non-JSON: {response.text[:300]}"
            ) from exc

    def _fetch_via_csv_sync(
        self,
        series_id: str,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[WorldObservation]:
        params: dict[str, str] = {"id": normalize_series_id(series_id)}
        if date_from is not None:
            params["cosd"] = date_from.isoformat()
        if date_to is not None:
            params["coed"] = date_to.isoformat()
        text = self._get_text(self._csv_base_url, params=params)
        return parse_fred_csv(
            text,
            series_id=series_id,
            date_from=date_from,
            date_to=date_to,
        )

    def _fetch_via_api_sync(
        self,
        series_id: str,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[WorldObservation]:
        if not self._api_key:
            from app.services.world_national_ingest import AdapterUnavailable

            raise AdapterUnavailable(
                f"FRED JSON API requires {_ENV_API_KEY}"
            )
        params: dict[str, str] = {
            "series_id": normalize_series_id(series_id),
            "api_key": self._api_key,
            "file_type": "json",
            "sort_order": "asc",
        }
        start = date_from or _DEFAULT_DATE_FROM
        end = date_to or date.today()
        params["observation_start"] = start.isoformat()
        params["observation_end"] = end.isoformat()
        url = f"{self._api_base_url}/series/observations"
        payload = self._get_json(url, params=params)
        if not isinstance(payload, Mapping):
            raise FredStLouisError(
                f"FRED API payload must be an object, got {type(payload)!r}"
            )
        return parse_fred_api_observations(
            payload,
            series_id=series_id,
            date_from=date_from,
            date_to=date_to,
        )

    def _series_ref(self, spec: FredSeriesSpec) -> WorldSeriesRef:
        sid = normalize_series_id(spec.series_id)
        did = normalize_dataset_id(spec.dataset_id, series_id=sid)
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=did,
            series_id=sid,
            country_code=self._country_code,
            frequency=(spec.frequency or "monthly").strip().lower() or "monthly",
            unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url or series_page_url(sid),
        )


ADAPTER = FredStLouisAdapter
FredAdapter = FredStLouisAdapter
