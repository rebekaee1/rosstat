"""U.S. Bureau of Labor Statistics Public Data API adapter.

Docs: https://www.bls.gov/developers/

Timeseries endpoint::

    POST https://api.bls.gov/publicAPI/v2/timeseries/data/
    JSON body: {"seriesid": ["CUSR0000SA0"], "startyear": "2015", "endyear": "2026",
                "registrationkey": "<optional>"}

Keyless calls are rate-limited and may be blocked by edge filters. When the
request cannot proceed without a key, raise ``AdapterUnavailable`` pointing at
``RUSTATS_BLS_API_KEY``. Prefer FRED redistributions of BLS series for the
national-core passport when the key is absent.
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

BLS_V2_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_COUNTRY_CODE = "US"
_ENV_API_KEY = "RUSTATS_BLS_API_KEY"


class BlsApiError(RuntimeError):
    """Raised when BLS returns an unusable payload."""


@dataclass(frozen=True)
class BlsSeriesSpec:
    series_id: str
    dataset_id: str | None = None
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "monthly"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


# Canonical BLS ids mirroring FRED passport counterparts (for keyed use).
DEFAULT_BLS_SERIES: tuple[BlsSeriesSpec, ...] = (
    BlsSeriesSpec(
        series_id="CUSR0000SA0",
        dataset_id="CU",
        title="CPI-U All Items SA",
        unit_code="INDEX",
        frequency="monthly",
    ),
    BlsSeriesSpec(
        series_id="LNS14000000",
        dataset_id="LN",
        title="Unemployment Rate SA",
        unit_code="PERCENT",
        frequency="monthly",
    ),
    BlsSeriesSpec(
        series_id="CES0000000001",
        dataset_id="CE",
        title="All Employees, Total Nonfarm SA",
        unit_code="THOUSANDS",
        frequency="monthly",
    ),
)


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip().upper()
    if not text:
        raise BlsApiError("Empty BLS series id")
    return text


def normalize_dataset_id(raw: str | None, *, series_id: str) -> str:
    text = (raw or "").strip()
    return text or series_id


def _api_key_from_env() -> str | None:
    raw = (os.environ.get(_ENV_API_KEY) or "").strip()
    return raw or None


def parse_bls_period(year: str | int, period: str) -> date | None:
    """Map BLS ``period`` (M01–M12, Q01–Q04, A01) + year to a period date."""
    y = int(year)
    p = (period or "").strip().upper()
    if p.startswith("M") and len(p) == 3 and p[1:].isdigit():
        month = int(p[1:])
        if 1 <= month <= 12:
            return date(y, month, 1)
    if p.startswith("Q") and len(p) == 3 and p[1:].isdigit():
        q = int(p[1:])
        if 1 <= q <= 4:
            return date(y, (q - 1) * 3 + 1, 1)
    if p in {"A01", "A"}:
        return date(y, 1, 1)
    return None


def parse_bls_series_payload(
    series_block: Mapping[str, Any],
    *,
    series_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[WorldObservation]:
    sid = normalize_series_id(series_id)
    raw_data = series_block.get("data")
    if not isinstance(raw_data, list) or not raw_data:
        raise BlsApiError(f"BLS series {sid} has no data[]")

    observations: list[WorldObservation] = []
    for index, item in enumerate(raw_data):
        if not isinstance(item, Mapping):
            raise BlsApiError(f"BLS data[{index}] is not an object")
        period = parse_bls_period(str(item.get("year") or ""), str(item.get("period") or ""))
        if period is None:
            continue
        if date_from is not None and period < date_from:
            continue
        if date_to is not None and period > date_to:
            continue
        raw_value = item.get("value")
        if raw_value is None or raw_value == "":
            continue
        try:
            value = float(str(raw_value).replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise BlsApiError(
                f"BLS data[{index}].value non-numeric: {raw_value!r}"
            ) from exc
        observations.append(WorldObservation(period=period, value=value))

    if not observations:
        raise BlsApiError(f"BLS series {sid} had no numeric observations")
    observations.sort(key=lambda item: item.period)
    return observations


def _specs_from_national(series_specs: Sequence[Any]) -> list[BlsSeriesSpec]:
    out: list[BlsSeriesSpec] = []
    for row in series_specs:
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider != "bls":
            continue
        sid = normalize_series_id(str(getattr(row, "series_id", "") or ""))
        did = str(getattr(row, "dataset_id", "") or "").strip() or sid
        freq = getattr(row, "frequency", None)
        unit = getattr(row, "unit", None) or getattr(row, "unit_code", None) or "UNIT"
        title = getattr(row, "name_en", None) or getattr(row, "title", None)
        out.append(
            BlsSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=str(title) if title else None,
                unit_code=str(unit).strip().upper() or "UNIT",
                frequency=str(freq).strip().lower() if freq else "monthly",
                dimensions=dict(getattr(row, "dimensions", None) or {}),
                source_url=getattr(row, "source_url", None),
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    **kwargs: Any,
) -> "BlsApiAdapter":
    curated: Sequence[BlsSeriesSpec] | None = None
    if series_specs is not None:
        mapped = _specs_from_national(series_specs)
        curated = mapped if mapped else None
    return BlsApiAdapter(curated, **kwargs)


class BlsApiAdapter:
    """``WorldSourceAdapter`` for BLS Public Data API v2."""

    provider = "bls"
    public_source_name = "U.S. Bureau of Labor Statistics"

    def __init__(
        self,
        series: Sequence[BlsSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = BLS_V2_URL,
        api_key: str | None = None,
        country_code: str = DEFAULT_COUNTRY_CODE,
        require_key: bool = False,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_BLS_SERIES
        if not curated:
            raise BlsApiError("BlsApiAdapter requires at least one curated BlsSeriesSpec")
        self._series = curated
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url
        resolved = api_key if api_key is not None else _api_key_from_env()
        self._api_key = (resolved or "").strip() or None
        self._require_key = require_key or False
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._by_dataset: dict[str, list[BlsSeriesSpec]] = {}
        self._by_series_id: dict[str, BlsSeriesSpec] = {}
        for spec in self._series:
            sid = normalize_series_id(spec.series_id)
            did = normalize_dataset_id(spec.dataset_id, series_id=sid)
            normalized = BlsSeriesSpec(
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

        if self._require_key and not self._api_key:
            from app.services.world_national_ingest import AdapterUnavailable

            raise AdapterUnavailable(
                f"BLS adapter requires {_ENV_API_KEY} (public keyless access unavailable)"
            )

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=members[0].title,
                metadata_url="https://www.bls.gov/developers/",
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = (dataset.dataset_id or "").strip()
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise BlsApiError(f"No curated BLS series for dataset_id={dataset_id!r}")
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
            raise BlsApiError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        series_id = normalize_series_id(series.series_id)
        fetched_at = datetime.now(timezone.utc)
        try:
            observations = await asyncio.to_thread(
                self._fetch_sync,
                series_id,
                date_from=date_from,
                date_to=date_to,
            )
        except BlsApiError as exc:
            if not self._api_key:
                from app.services.world_national_ingest import AdapterUnavailable

                raise AdapterUnavailable(
                    f"BLS keyless fetch failed for {series_id}; "
                    f"set {_ENV_API_KEY}. Underlying: {exc}"
                ) from exc
            raise

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
        series_id: str,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[WorldObservation]:
        end_year = (date_to or date.today()).year
        start_year = (date_from or date(end_year - 10, 1, 1)).year
        # BLS v2 allows at most 20 years per request without registration;
        # with key up to 20 years still typical — clamp window.
        if end_year - start_year > 19:
            start_year = end_year - 19
        body: dict[str, Any] = {
            "seriesid": [normalize_series_id(series_id)],
            "startyear": str(start_year),
            "endyear": str(end_year),
        }
        if self._api_key:
            body["registrationkey"] = self._api_key

        try:
            response = self._session.post(
                self._base_url,
                json=body,
                timeout=self._timeout,
                headers={"Content-Type": "application/json"},
            )
        except requests.RequestException as exc:
            raise BlsApiError(f"BLS POST failed: {exc}") from exc

        if response.status_code >= 400:
            raise BlsApiError(
                f"BLS HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise BlsApiError(
                f"BLS returned non-JSON: {response.text[:300]}"
            ) from exc

        if not isinstance(payload, Mapping):
            raise BlsApiError(f"BLS payload must be an object, got {type(payload)!r}")
        status = str(payload.get("status") or "")
        if status and status.lower() != "request_succeeded":
            messages = payload.get("message") or payload.get("Results") or status
            raise BlsApiError(f"BLS status={status!r}: {messages!r}")

        results = payload.get("Results") or {}
        series_list = results.get("series") if isinstance(results, Mapping) else None
        if not isinstance(series_list, list) or not series_list:
            raise BlsApiError(f"BLS Results.series missing for {series_id}")
        block = series_list[0]
        if not isinstance(block, Mapping):
            raise BlsApiError("BLS series block is not an object")
        return parse_bls_series_payload(
            block,
            series_id=series_id,
            date_from=date_from,
            date_to=date_to,
        )

    def _series_ref(self, spec: BlsSeriesSpec) -> WorldSeriesRef:
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
            source_url=spec.source_url or "https://www.bls.gov/data/",
        )


ADAPTER = BlsApiAdapter
