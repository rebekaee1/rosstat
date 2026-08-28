"""Australian Bureau of Statistics (ABS) Data API adapter.

Official SDMX 2.1 REST (Data API, base since 2024-11-29)::

    https://data.api.abs.gov.au/rest/

User guide: https://www.abs.gov.au/statistics/application-programming-interfaces-apis/data-api-user-guide

Data::

    GET /rest/data/{agencyId},{dataflowId}[,{version}]/{dataKey}
        ?startPeriod=…&endPeriod=…&detail=dataonly|full
        &format=jsondata
        &dimensionAtObservation=TIME_PERIOD   (default)

Structure (optional catalogue probe)::

    GET /rest/dataflow/{agencyId}/{dataflowId}[/{version}]

``WorldSeriesRef.dataset_id`` is the dataflow id (``CPI``) or a full
``ABS,CPI`` / ``ABS,CPI,2.0.0`` token. ``series_id`` is the SDMX data key
(e.g. ``1.10001.10.50.Q`` — measure.index.adjustment.region.freq).

No API key is required (ABS removed keys in the 2024-11 REST cutover).
Country code for curated national-core series is ``AU``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
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

ABS_REST_BASE = "https://data.api.abs.gov.au/rest"
DEFAULT_TIMEOUT_SEC = 180
DEFAULT_AGENCY = "ABS"
DEFAULT_COUNTRY_CODE = "AU"
_DEFAULT_DATE_FROM = date(1978, 1, 1)

# SDMX FREQ code → platform frequency.
FREQ_CODE_MAP: dict[str, str] = {
    "A": "annual",
    "Y": "annual",
    "Q": "quarterly",
    "M": "monthly",
    "W": "weekly",
    "D": "daily",
    "B": "daily",
    "S": "quarterly",  # semi-annual → nearest supported cadence
    "H": "quarterly",
}

_PERIOD_QUARTER = re.compile(r"^(\d{4})-Q([1-4])$", re.IGNORECASE)
_PERIOD_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_PERIOD_YEAR = re.compile(r"^(\d{4})$")
_PERIOD_SEMESTER = re.compile(r"^(\d{4})-S([12])$", re.IGNORECASE)
_PERIOD_WEEK = re.compile(r"^(\d{4})-W(\d{2})$", re.IGNORECASE)


class AbsDataError(RuntimeError):
    """Raised when ABS Data API returns an unusable or empty payload."""


@dataclass(frozen=True)
class AbsSeriesSpec:
    """Curated series inside an ABS dataflow. ``series_id`` = SDMX data key."""

    series_id: str
    dataset_id: str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str | None = None
    agency_id: str = DEFAULT_AGENCY
    version: str | None = None
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


@dataclass(frozen=True)
class AbsDataflowSpec:
    """Curated ABS dataflow with one or more series keys."""

    dataflow_id: str
    title: str | None = None
    agency_id: str = DEFAULT_AGENCY
    version: str | None = None
    series: Sequence[AbsSeriesSpec] = field(default_factory=tuple)
    revision_token: str | None = None


# Confirmed live passport seed (All groups CPI, Australia, quarterly).
DEFAULT_ABS_SERIES: tuple[AbsSeriesSpec, ...] = (
    AbsSeriesSpec(
        series_id="1.10001.10.50.Q",
        dataset_id="CPI",
        title="Consumer Price Index — All groups CPI (Australia)",
        unit_code="INDEX",
        frequency="quarterly",
        dimensions={
            "MEASURE": "1",
            "INDEX": "10001",
            "TSEST": "10",
            "REGION": "50",
            "FREQ": "Q",
        },
    ),
)


def normalize_data_key(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise AbsDataError("Empty ABS SDMX data key (series_id)")
    return text


def parse_dataflow_ref(raw: str, *, default_agency: str = DEFAULT_AGENCY) -> tuple[str, str, str | None]:
    """Return ``(agency_id, dataflow_id, version|None)`` from a dataset token."""
    text = (raw or "").strip()
    if not text:
        raise AbsDataError("Empty ABS dataflow / dataset_id")
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) == 1:
        return default_agency.strip().upper() or DEFAULT_AGENCY, parts[0], None
    if len(parts) == 2:
        return parts[0].upper(), parts[1], None
    if len(parts) >= 3:
        return parts[0].upper(), parts[1], parts[2]
    raise AbsDataError(f"Invalid ABS dataflow ref: {raw!r}")


def dataflow_path_token(
    dataset_id: str,
    *,
    agency_id: str = DEFAULT_AGENCY,
    version: str | None = None,
) -> str:
    agency, flow, ver = parse_dataflow_ref(dataset_id, default_agency=agency_id)
    if version:
        ver = version
    if ver:
        return f"{agency},{flow},{ver}"
    return f"{agency},{flow}"


def canonical_dataset_id(dataset_id: str, *, agency_id: str = DEFAULT_AGENCY) -> str:
    """Stable dataset identity for WorldSeriesRef (dataflow id without version)."""
    _, flow, _ = parse_dataflow_ref(dataset_id, default_agency=agency_id)
    return flow


def map_freq_code(code: str | None) -> str:
    if code is None or str(code).strip() == "":
        raise AbsDataError("Missing ABS FREQ code")
    key = str(code).strip().upper()
    mapped = FREQ_CODE_MAP.get(key)
    if mapped is None:
        raise AbsDataError(f"Unsupported ABS FREQ code: {code!r}")
    return mapped


def infer_frequency_from_data_key(data_key: str) -> str | None:
    """Last segment of a typical ABS key is FREQ (A/Q/M/…)."""
    parts = normalize_data_key(data_key).split(".")
    if not parts:
        return None
    tail = parts[-1].strip().upper()
    if tail in FREQ_CODE_MAP:
        return FREQ_CODE_MAP[tail]
    return None


def parse_sdmx_period(raw: str, *, start: str | None = None) -> date:
    """Parse SDMX TIME_PERIOD id or structure ``start`` into a calendar date."""
    if start:
        text = str(start).strip()
        if text:
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                pass

    text = (raw or "").strip()
    if not text:
        raise AbsDataError("Empty TIME_PERIOD")

    if "T" in text or (len(text) >= 10 and text[4] == "-" and text[7] == "-"):
        try:
            return date.fromisoformat(text[:10])
        except ValueError as exc:
            raise AbsDataError(f"Unparseable TIME_PERIOD: {raw!r}") from exc

    m = _PERIOD_QUARTER.match(text)
    if m:
        year, quarter = int(m.group(1)), int(m.group(2))
        return date(year, (quarter - 1) * 3 + 1, 1)

    m = _PERIOD_SEMESTER.match(text)
    if m:
        year, sem = int(m.group(1)), int(m.group(2))
        return date(year, 1 if sem == 1 else 7, 1)

    m = _PERIOD_MONTH.match(text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)

    m = _PERIOD_YEAR.match(text)
    if m:
        return date(int(m.group(1)), 1, 1)

    m = _PERIOD_WEEK.match(text)
    if m:
        # Approximate: Monday of ISO week.
        return date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)

    raise AbsDataError(f"Unparseable TIME_PERIOD: {raw!r}")


def format_sdmx_period(period: date, frequency: str) -> str:
    freq = (frequency or "").strip().lower()
    if freq == "annual":
        return str(period.year)
    if freq == "quarterly":
        quarter = (period.month - 1) // 3 + 1
        return f"{period.year}-Q{quarter}"
    if freq == "monthly":
        return f"{period.year}-{period.month:02d}"
    if freq in {"daily", "weekly"}:
        return period.isoformat()
    # Fail closed for unknown cadence rather than inventing a period token.
    raise AbsDataError(f"Cannot format startPeriod for frequency={frequency!r}")


def data_url(
    dataset_id: str,
    data_key: str,
    *,
    base_url: str = ABS_REST_BASE,
    agency_id: str = DEFAULT_AGENCY,
    version: str | None = None,
) -> str:
    token = dataflow_path_token(dataset_id, agency_id=agency_id, version=version)
    key = normalize_data_key(data_key)
    return f"{base_url.rstrip('/')}/data/{token}/{key}"


def series_source_url(
    dataset_id: str,
    data_key: str,
    *,
    base_url: str = ABS_REST_BASE,
    agency_id: str = DEFAULT_AGENCY,
    version: str | None = None,
) -> str:
    return data_url(
        dataset_id,
        data_key,
        base_url=base_url,
        agency_id=agency_id,
        version=version,
    )


def parse_sdmx_json_observations(payload: Mapping[str, Any]) -> list[WorldObservation]:
    """Parse SDMX-JSON (``format=jsondata``) into typed observations.

    Expects ``dimensionAtObservation=TIME_PERIOD`` (ABS default): series keyed
    by dimension indices, observations keyed by TIME_PERIOD index.
    """
    if not isinstance(payload, Mapping):
        raise AbsDataError(f"ABS payload must be an object, got {type(payload)!r}")

    # Some ABS error bodies are JSON; others are plain text handled in HTTP layer.
    errors = payload.get("errors")
    if errors:
        raise AbsDataError(f"ABS Data API errors: {errors!r}")

    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise AbsDataError("ABS SDMX-JSON missing data object")

    datasets = data.get("dataSets")
    if not isinstance(datasets, list) or not datasets:
        raise AbsDataError("ABS SDMX-JSON dataSets empty")

    structures = data.get("structures")
    if not isinstance(structures, list) or not structures:
        raise AbsDataError("ABS SDMX-JSON structures empty")

    structure = structures[0]
    if not isinstance(structure, Mapping):
        raise AbsDataError("ABS SDMX-JSON structure[0] is not an object")

    obs_dims = (structure.get("dimensions") or {}).get("observation") or []
    if not isinstance(obs_dims, list) or not obs_dims:
        raise AbsDataError("ABS SDMX-JSON missing observation dimensions")
    time_dim = obs_dims[0]
    if not isinstance(time_dim, Mapping):
        raise AbsDataError("ABS TIME_PERIOD dimension missing")
    time_values = time_dim.get("values") or []
    if not isinstance(time_values, list) or not time_values:
        raise AbsDataError("ABS TIME_PERIOD values empty")

    dataset0 = datasets[0]
    if not isinstance(dataset0, Mapping):
        raise AbsDataError("ABS dataSets[0] is not an object")

    series_map = dataset0.get("series")
    # Flat / AllDimensions layout uses observations at dataset level.
    if not series_map:
        flat = dataset0.get("observations")
        if isinstance(flat, Mapping) and flat:
            return _observations_from_map(flat, time_values)
        raise AbsDataError("ABS dataSets[0] has no series/observations")

    if not isinstance(series_map, Mapping) or not series_map:
        raise AbsDataError("ABS series map empty")

    observations: list[WorldObservation] = []
    for series_key, series_body in series_map.items():
        if not isinstance(series_body, Mapping):
            raise AbsDataError(f"ABS series[{series_key!r}] is not an object")
        obs_map = series_body.get("observations")
        if not isinstance(obs_map, Mapping) or not obs_map:
            continue
        observations.extend(_observations_from_map(obs_map, time_values))

    if not observations:
        raise AbsDataError("ABS response had no numeric observations")
    observations.sort(key=lambda item: item.period)
    return observations


def _observations_from_map(
    obs_map: Mapping[str, Any],
    time_values: Sequence[Mapping[str, Any]],
) -> list[WorldObservation]:
    out: list[WorldObservation] = []
    for index_raw, cell in obs_map.items():
        try:
            index = int(index_raw)
        except (TypeError, ValueError) as exc:
            raise AbsDataError(
                f"ABS observation key not an int index: {index_raw!r}"
            ) from exc
        if index < 0 or index >= len(time_values):
            raise AbsDataError(
                f"ABS observation index {index} out of range "
                f"(TIME_PERIOD has {len(time_values)} values)"
            )
        period_meta = time_values[index]
        if not isinstance(period_meta, Mapping):
            raise AbsDataError(f"ABS TIME_PERIOD[{index}] is not an object")
        period = parse_sdmx_period(
            str(period_meta.get("id") or period_meta.get("name") or ""),
            start=str(period_meta.get("start") or "") or None,
        )
        value, status, decimals = _parse_obs_cell(cell, index=index)
        if value is None:
            continue
        out.append(
            WorldObservation(
                period=period,
                value=value,
                status=status,
                decimals=decimals,
            )
        )
    return out


def _parse_obs_cell(
    cell: Any, *, index: int
) -> tuple[float | None, str | None, int | None]:
    """SDMX-JSON observation cell: ``[value, status?, …]`` or scalar."""
    if cell is None or cell == "":
        return None, None, None
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        return float(cell), None, None
    if isinstance(cell, list):
        if not cell:
            return None, None, None
        raw_value = cell[0]
        if raw_value is None or raw_value == "":
            return None, None, None
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise AbsDataError(
                f"ABS observation[{index}] non-numeric value: {raw_value!r}"
            ) from exc
        status = None
        decimals: int | None = None
        if len(cell) > 1 and cell[1] not in (None, ""):
            status = str(cell[1])
        # Decimals often live in attributes; ignore unless numeric trailing hint.
        return value, status, decimals
    raise AbsDataError(f"ABS observation[{index}] unexpected cell: {cell!r}")


def _specs_from_national(
    series_specs: Sequence[Any],
) -> list[AbsSeriesSpec]:
    """Map national-core YAML rows (duck-typed) into AbsSeriesSpec."""
    out: list[AbsSeriesSpec] = []
    for row in series_specs:
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider != "abs":
            continue
        sid = normalize_data_key(str(getattr(row, "series_id", "") or ""))
        did = str(getattr(row, "dataset_id", "") or "").strip()
        if not did:
            raise AbsDataError(f"ABS national series {sid!r} missing dataset_id")
        freq = getattr(row, "frequency", None)
        unit = getattr(row, "unit", None) or getattr(row, "unit_code", None) or "UNIT"
        dims = dict(getattr(row, "dimensions", None) or {})
        title = getattr(row, "name_en", None) or getattr(row, "name_ru", None) or getattr(
            row, "title", None
        )
        out.append(
            AbsSeriesSpec(
                series_id=sid,
                dataset_id=canonical_dataset_id(did),
                title=str(title) if title else None,
                unit_code=str(unit).strip().upper() or "UNIT",
                frequency=str(freq).strip().lower() if freq else None,
                dimensions=dims,
                source_url=getattr(row, "source_url", None),
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    **kwargs: Any,
) -> AbsDataAdapter:
    """Factory for ``world_national_ingest.resolve_adapter``."""
    curated: Sequence[AbsSeriesSpec] | None = None
    if series_specs is not None:
        mapped = _specs_from_national(series_specs)
        curated = mapped if mapped else None
    return AbsDataAdapter(curated, **kwargs)


class AbsDataAdapter:
    """``WorldSourceAdapter`` for ABS Data API (SDMX 2.1 REST)."""

    provider = "abs"
    public_source_name = "Australian Bureau of Statistics"

    def __init__(
        self,
        series: Sequence[AbsSeriesSpec] | None = None,
        *,
        dataflows: Sequence[AbsDataflowSpec] | None = None,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = ABS_REST_BASE,
        country_code: str = DEFAULT_COUNTRY_CODE,
        agency_id: str = DEFAULT_AGENCY,
    ) -> None:
        curated = list(series or ())
        if dataflows:
            for flow in dataflows:
                for member in flow.series:
                    curated.append(
                        AbsSeriesSpec(
                            series_id=member.series_id,
                            dataset_id=flow.dataflow_id,
                            title=member.title or flow.title,
                            unit_code=member.unit_code,
                            frequency=member.frequency,
                            agency_id=flow.agency_id or member.agency_id,
                            version=flow.version or member.version,
                            dimensions=dict(member.dimensions),
                            source_url=member.source_url,
                        )
                    )
        if not curated:
            curated = list(DEFAULT_ABS_SERIES)

        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._agency_id = agency_id.strip().upper() or DEFAULT_AGENCY

        self._by_dataset: dict[str, list[AbsSeriesSpec]] = {}
        self._by_series_id: dict[str, AbsSeriesSpec] = {}
        for spec in curated:
            sid = normalize_data_key(spec.series_id)
            did = canonical_dataset_id(spec.dataset_id, agency_id=spec.agency_id)
            freq = (spec.frequency or infer_frequency_from_data_key(sid) or "").strip().lower()
            if not freq:
                raise AbsDataError(
                    f"ABS series {sid!r} needs frequency or FREQ suffix in data key"
                )
            normalized = AbsSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=freq,
                agency_id=(spec.agency_id or self._agency_id).strip().upper(),
                version=spec.version,
                dimensions=dict(spec.dimensions),
                source_url=spec.source_url,
            )
            self._by_dataset.setdefault(did, []).append(normalized)
            self._by_series_id[sid] = normalized

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            title = members[0].title
            agency = members[0].agency_id or self._agency_id
            version = members[0].version
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=title,
                revision_token=None,
                metadata_url=(
                    f"{self._base_url}/dataflow/{agency}/{dataset_id}"
                    + (f"/{version}" if version else "")
                ),
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = canonical_dataset_id(
            dataset.dataset_id, agency_id=self._agency_id
        )
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise AbsDataError(
                f"No curated ABS series for dataset_id={dataset.dataset_id!r}"
            )
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
            raise AbsDataError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        data_key = normalize_data_key(series.series_id)
        dataset_id = canonical_dataset_id(series.dataset_id, agency_id=self._agency_id)
        curated = self._by_series_id.get(data_key)
        agency = (curated.agency_id if curated else self._agency_id) or self._agency_id
        version = curated.version if curated else None
        frequency = (
            (series.frequency or "").strip().lower()
            or (curated.frequency if curated else None)
            or infer_frequency_from_data_key(data_key)
        )
        if not frequency:
            raise AbsDataError(
                f"Cannot determine frequency for ABS series {data_key!r}"
            )

        fetched_at = datetime.now(timezone.utc)
        params: dict[str, str] = {
            "format": "jsondata",
            "detail": "dataonly",
            "dimensionAtObservation": "TIME_PERIOD",
        }
        # Always bound the window: unbounded ABS LF/RT pulls frequently hang.
        start = date_from or _DEFAULT_DATE_FROM
        end = date_to or date.today()
        if end < start:
            raise AbsDataError(
                f"date_to {end.isoformat()} is before date_from {start.isoformat()}"
            )
        params["startPeriod"] = format_sdmx_period(start, frequency)
        params["endPeriod"] = format_sdmx_period(end, frequency)

        try:
            payload = await asyncio.to_thread(
                self._get_data_sync,
                dataset_id,
                data_key,
                agency_id=agency,
                version=version,
                params=params,
            )
        except AbsDataError as exc:
            # ABS Data API intermittently hangs on some LF/RT keys even with a
            # bounded window; lastNObservations is usually fast and enough for
            # a passport chart.
            msg = str(exc).lower()
            if "timed out" not in msg and "timeout" not in msg:
                raise
            fallback = {
                "format": "jsondata",
                "detail": "dataonly",
                "dimensionAtObservation": "TIME_PERIOD",
                "lastNObservations": "1200",
            }
            logger.warning(
                "ABS timeout on %s/%s — retry with lastNObservations=1200",
                dataset_id,
                data_key,
            )
            payload = await asyncio.to_thread(
                self._get_data_sync,
                dataset_id,
                data_key,
                agency_id=agency,
                version=version,
                params=fallback,
            )
        observations = parse_sdmx_json_observations(payload)
        revision = None
        prepared = None
        meta = payload.get("meta") if isinstance(payload, Mapping) else None
        if isinstance(meta, Mapping) and meta.get("prepared"):
            prepared = str(meta["prepared"])
            revision = prepared
        if revision is None and observations:
            revision = (
                f"{observations[0].period.isoformat()}"
                f"/{observations[-1].period.isoformat()}"
                f"#{len(observations)}"
            )
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "dataflow": dataset_id,
                    "key": data_key,
                    "n": len(observations),
                    "first": observations[0].period.isoformat(),
                    "last": observations[-1].period.isoformat(),
                    "last_value": observations[-1].value,
                    "prepared": prepared,
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

    # ------------------------------------------------------------------ sync HTTP

    def _get_data_sync(
        self,
        dataset_id: str,
        data_key: str,
        *,
        agency_id: str,
        version: str | None,
        params: Mapping[str, str],
    ) -> dict[str, Any]:
        url = data_url(
            dataset_id,
            data_key,
            base_url=self._base_url,
            agency_id=agency_id,
            version=version,
        )
        try:
            response = self._session.get(
                url,
                params=dict(params),
                timeout=self._timeout,
                headers={
                    "Accept": "application/vnd.sdmx.data+json, application/json;q=0.9"
                },
            )
        except requests.RequestException as exc:
            raise AbsDataError(f"ABS GET {url} failed: {exc}") from exc

        body = (response.text or "").strip()
        if response.status_code >= 400:
            raise AbsDataError(
                f"ABS GET {url} HTTP {response.status_code}: {body[:300]}"
            )
        if not body:
            raise AbsDataError(f"ABS GET {url} returned empty body")

        # ABS sometimes returns plain-text error tokens with HTTP 200.
        if body in {"NoRecordsFound", "No results found.", "Unauthorized"} or (
            body[0] not in "{[" and "NoRecordsFound" in body
        ):
            raise AbsDataError(f"ABS GET {url} error body: {body[:300]}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise AbsDataError(
                f"ABS GET {url} returned non-JSON: {body[:300]}"
            ) from exc
        if not isinstance(payload, dict):
            raise AbsDataError(
                f"ABS data payload must be an object, got {type(payload)!r}"
            )
        return payload

    def _series_ref(self, spec: AbsSeriesSpec) -> WorldSeriesRef:
        sid = normalize_data_key(spec.series_id)
        did = canonical_dataset_id(spec.dataset_id, agency_id=spec.agency_id)
        freq = (spec.frequency or infer_frequency_from_data_key(sid) or "").strip().lower()
        if not freq:
            raise AbsDataError(f"ABS series {sid!r} missing frequency")
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=did,
            series_id=sid,
            country_code=self._country_code,
            frequency=freq,
            unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url
            or series_source_url(
                did,
                sid,
                base_url=self._base_url,
                agency_id=spec.agency_id or self._agency_id,
                version=spec.version,
            ),
        )


ADAPTER = AbsDataAdapter
