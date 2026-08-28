"""U.S. Bureau of Economic Analysis (BEA) Data API adapter.

Docs: https://apps.bea.gov/API/docs/index.htm

NIPA example::

    GET https://apps.bea.gov/api/data/
        ?UserID=<RUSTATS_BEA_API_KEY>
        &method=GetData
        &DataSetName=NIPA
        &TableName=T10106
        &Frequency=Q
        &Year=ALL
        &ResultFormat=JSON

The API requires a free registration key. Without ``RUSTATS_BEA_API_KEY``
construction / fetch raises ``AdapterUnavailable``. Prefer FRED series
``GDPC1`` (BEA real GDP via St. Louis Fed) for the national-core passport
when the key is absent.
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

BEA_API_URL = "https://apps.bea.gov/api/data/"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_COUNTRY_CODE = "US"
_ENV_API_KEY = "RUSTATS_BEA_API_KEY"


class BeaApiError(RuntimeError):
    """Raised when BEA returns an unusable payload."""


@dataclass(frozen=True)
class BeaSeriesSpec:
    """One BEA GetData slice.

    ``series_id`` encodes ``{TableName}:{LineNumber}`` (e.g. ``T10106:1`` for
    real GDP line 1). ``dataset_id`` is the BEA DataSetName (e.g. ``NIPA``).
    """

    series_id: str
    dataset_id: str = "NIPA"
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "quarterly"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None
    table_name: str | None = None
    line_number: str | None = None
    bea_frequency: str = "Q"


DEFAULT_BEA_SERIES: tuple[BeaSeriesSpec, ...] = (
    BeaSeriesSpec(
        series_id="T10106:1",
        dataset_id="NIPA",
        table_name="T10106",
        line_number="1",
        title="Real Gross Domestic Product (NIPA table 1.1.6, line 1)",
        unit_code="USD_BN_CHAINED",
        frequency="quarterly",
        bea_frequency="Q",
    ),
)


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip().upper()
    if not text:
        raise BeaApiError("Empty BEA series id")
    return text


def parse_series_id(series_id: str) -> tuple[str, str]:
    """Split ``T10106:1`` → (table, line)."""
    sid = normalize_series_id(series_id)
    if ":" not in sid:
        raise BeaApiError(
            f"BEA series_id must be TABLE:LINE (e.g. T10106:1), got {series_id!r}"
        )
    table, line = sid.split(":", 1)
    table = table.strip()
    line = line.strip()
    if not table or not line:
        raise BeaApiError(f"BEA series_id malformed: {series_id!r}")
    return table, line


def parse_bea_time(raw: str, *, frequency: str) -> date:
    """Parse BEA TimePeriod: ``2024Q2``, ``2024M06``, ``2024``."""
    text = (raw or "").strip().upper()
    freq = (frequency or "").strip().upper()
    if not text:
        raise BeaApiError("Empty BEA TimePeriod")
    if "Q" in text and len(text) >= 6:
        year = int(text[:4])
        q = int(text.split("Q", 1)[1])
        if q < 1 or q > 4:
            raise BeaApiError(f"Bad BEA quarter: {raw!r}")
        return date(year, (q - 1) * 3 + 1, 1)
    if "M" in text and len(text) >= 6:
        year = int(text[:4])
        month = int(text.split("M", 1)[1])
        return date(year, month, 1)
    if len(text) == 4 and text.isdigit():
        return date(int(text), 1, 1)
    # Fallback ISO.
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise BeaApiError(f"Unparseable BEA TimePeriod: {raw!r} (freq={freq})") from exc


def parse_bea_data_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    line_number: str,
    frequency: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[WorldObservation]:
    line = str(line_number).strip()
    observations: list[WorldObservation] = []
    for index, row in enumerate(rows):
        row_line = str(row.get("LineNumber") or row.get("LineNumber".lower()) or "").strip()
        if row_line and row_line != line:
            continue
        raw_time = str(row.get("TimePeriod") or row.get("TimePeriod".lower()) or "")
        raw_value = row.get("DataValue")
        if raw_value is None or raw_value == "":
            continue
        # BEA often formats with commas: "21,234.5"
        try:
            value = float(str(raw_value).replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise BeaApiError(
                f"BEA DataValue non-numeric at row {index}: {raw_value!r}"
            ) from exc
        period = parse_bea_time(raw_time, frequency=frequency)
        if date_from is not None and period < date_from:
            continue
        if date_to is not None and period > date_to:
            continue
        observations.append(WorldObservation(period=period, value=value))

    if not observations:
        raise BeaApiError(f"BEA rows had no values for line {line}")
    observations.sort(key=lambda item: item.period)
    return observations


def _api_key_from_env() -> str | None:
    raw = (os.environ.get(_ENV_API_KEY) or "").strip()
    return raw or None


def _specs_from_national(series_specs: Sequence[Any]) -> list[BeaSeriesSpec]:
    out: list[BeaSeriesSpec] = []
    for row in series_specs:
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider != "bea":
            continue
        sid = normalize_series_id(str(getattr(row, "series_id", "") or ""))
        table, line = parse_series_id(sid)
        did = str(getattr(row, "dataset_id", "") or "").strip() or "NIPA"
        freq = getattr(row, "frequency", None)
        unit = getattr(row, "unit", None) or getattr(row, "unit_code", None) or "UNIT"
        title = getattr(row, "name_en", None) or getattr(row, "title", None)
        dims = dict(getattr(row, "dimensions", None) or {})
        bea_freq = str(dims.get("bea_frequency") or {"quarterly": "Q", "monthly": "M", "annual": "A"}.get(
            str(freq or "quarterly").lower(), "Q"
        ))
        out.append(
            BeaSeriesSpec(
                series_id=sid,
                dataset_id=did,
                table_name=table,
                line_number=line,
                title=str(title) if title else None,
                unit_code=str(unit).strip().upper() or "UNIT",
                frequency=str(freq).strip().lower() if freq else "quarterly",
                dimensions=dims,
                source_url=getattr(row, "source_url", None),
                bea_frequency=bea_freq,
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    **kwargs: Any,
) -> "BeaApiAdapter":
    curated: Sequence[BeaSeriesSpec] | None = None
    if series_specs is not None:
        mapped = _specs_from_national(series_specs)
        curated = mapped if mapped else None
    return BeaApiAdapter(curated, **kwargs)


class BeaApiAdapter:
    """``WorldSourceAdapter`` for BEA Data API (key required)."""

    provider = "bea"
    public_source_name = "U.S. Bureau of Economic Analysis"

    def __init__(
        self,
        series: Sequence[BeaSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = BEA_API_URL,
        api_key: str | None = None,
        country_code: str = DEFAULT_COUNTRY_CODE,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_BEA_SERIES
        if not curated:
            raise BeaApiError("BeaApiAdapter requires at least one curated BeaSeriesSpec")
        resolved = api_key if api_key is not None else _api_key_from_env()
        self._api_key = (resolved or "").strip() or None
        if not self._api_key:
            from app.services.world_national_ingest import AdapterUnavailable

            raise AdapterUnavailable(
                f"BEA Data API requires {_ENV_API_KEY} "
                "(no keyless public GetData endpoint)"
            )
        self._series = curated
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._by_dataset: dict[str, list[BeaSeriesSpec]] = {}
        self._by_series_id: dict[str, BeaSeriesSpec] = {}
        for spec in self._series:
            sid = normalize_series_id(spec.series_id)
            table, line = parse_series_id(sid)
            did = (spec.dataset_id or "NIPA").strip() or "NIPA"
            normalized = BeaSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=(spec.frequency or "quarterly").strip().lower() or "quarterly",
                dimensions=dict(spec.dimensions),
                source_url=spec.source_url,
                table_name=spec.table_name or table,
                line_number=spec.line_number or line,
                bea_frequency=(spec.bea_frequency or "Q").strip().upper() or "Q",
            )
            self._by_dataset.setdefault(did, []).append(normalized)
            self._by_series_id[sid] = normalized

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=members[0].title,
                metadata_url="https://apps.bea.gov/API/docs/index.htm",
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = (dataset.dataset_id or "").strip()
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise BeaApiError(f"No curated BEA series for dataset_id={dataset_id!r}")
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
            raise BeaApiError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        if not self._api_key:
            from app.services.world_national_ingest import AdapterUnavailable

            raise AdapterUnavailable(f"BEA Data API requires {_ENV_API_KEY}")

        series_id = normalize_series_id(series.series_id)
        spec = self._by_series_id.get(series_id)
        table, line = parse_series_id(series_id)
        if spec is not None:
            table = spec.table_name or table
            line = spec.line_number or line
            bea_freq = spec.bea_frequency
            dataset_name = spec.dataset_id
            freq = spec.frequency
        else:
            bea_freq = "Q"
            dataset_name = series.dataset_id or "NIPA"
            freq = series.frequency

        fetched_at = datetime.now(timezone.utc)
        observations = await asyncio.to_thread(
            self._fetch_sync,
            dataset_name=dataset_name,
            table_name=table,
            line_number=line,
            bea_frequency=bea_freq,
            frequency=freq,
            date_from=date_from,
            date_to=date_to,
        )
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

    def _fetch_sync(
        self,
        *,
        dataset_name: str,
        table_name: str,
        line_number: str,
        bea_frequency: str,
        frequency: str,
        date_from: date | None,
        date_to: date | None,
    ) -> list[WorldObservation]:
        params = {
            "UserID": self._api_key,
            "method": "GetData",
            "DataSetName": dataset_name,
            "TableName": table_name,
            "Frequency": bea_frequency,
            "Year": "ALL",
            "ResultFormat": "JSON",
        }
        try:
            response = self._session.get(
                self._base_url,
                params=params,
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
        except requests.RequestException as exc:
            raise BeaApiError(f"BEA GET failed: {exc}") from exc
        if response.status_code >= 400:
            raise BeaApiError(
                f"BEA HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise BeaApiError(
                f"BEA returned non-JSON: {response.text[:300]}"
            ) from exc

        root = payload.get("BEAAPI") if isinstance(payload, Mapping) else None
        if not isinstance(root, Mapping):
            raise BeaApiError(f"BEA payload missing BEAAPI: {str(payload)[:200]}")
        results = root.get("Results")
        if isinstance(results, Mapping) and results.get("Error"):
            raise BeaApiError(f"BEA error: {results.get('Error')!r}")
        # Some error shapes nest under BEAAPI.Error
        if root.get("Error"):
            raise BeaApiError(f"BEA error: {root.get('Error')!r}")
        data = None
        if isinstance(results, Mapping):
            data = results.get("Data")
        if not isinstance(data, list) or not data:
            raise BeaApiError(f"BEA Results.Data empty for {table_name}")
        rows = [r for r in data if isinstance(r, Mapping)]
        return parse_bea_data_rows(
            rows,
            line_number=line_number,
            frequency=frequency,
            date_from=date_from,
            date_to=date_to,
        )

    def _series_ref(self, spec: BeaSeriesSpec) -> WorldSeriesRef:
        sid = normalize_series_id(spec.series_id)
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=(spec.dataset_id or "NIPA").strip() or "NIPA",
            series_id=sid,
            country_code=self._country_code,
            frequency=(spec.frequency or "quarterly").strip().lower() or "quarterly",
            unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url or "https://www.bea.gov/data",
        )


ADAPTER = BeaApiAdapter
