"""ONS time-series JSON adapter (Office for National Statistics).

Official public pages expose a stable JSON payload under::

    https://www.ons.gov.uk/{uri_path}/data

where ``uri_path`` looks like
``economy/inflationandpriceindices/timeseries/d7bt/mm23``.

``WorldSeriesRef.dataset_id`` is the ONS source dataset id (``MM23``, ``LMS``,
``QNA``, …). ``series_id`` is the CDID (``D7BT``, ``MGSX``, …). The relative
path is carried in ``dimensions["uri_path"]`` (or curated ``OnsSeriesSpec``).

No API key. Country code for national-core series is ``UK``.
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

ONS_SITE_BASE = "https://www.ons.gov.uk"
DEFAULT_TIMEOUT_SEC = 90
DEFAULT_COUNTRY_CODE = "UK"

_MONTH_NAME: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_PERIOD_QUARTER = re.compile(r"^(\d{4})\s*Q([1-4])$", re.IGNORECASE)
_PERIOD_YEAR = re.compile(r"^(\d{4})$")
_PERIOD_MONTH_TOKEN = re.compile(
    r"^(\d{4})\s+([A-Za-z]{3,9})$"
)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


class OnsTimeseriesError(RuntimeError):
    """Raised when ONS time-series JSON is missing or unusable."""


@dataclass(frozen=True)
class OnsSeriesSpec:
    """Curated ONS CDID inside one source dataset."""

    series_id: str
    dataset_id: str
    uri_path: str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "monthly"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


# Confirmed live passport seed (CPI all items index, 2015=100).
DEFAULT_ONS_SERIES: tuple[OnsSeriesSpec, ...] = (
    OnsSeriesSpec(
        series_id="D7BT",
        dataset_id="MM23",
        uri_path="economy/inflationandpriceindices/timeseries/d7bt/mm23",
        title="CPI INDEX 00: ALL ITEMS 2015=100",
        unit_code="INDEX",
        frequency="monthly",
    ),
)


def normalize_cdid(raw: str) -> str:
    text = (raw or "").strip().upper()
    if not text:
        raise OnsTimeseriesError("Empty ONS CDID (series_id)")
    return text


def normalize_dataset_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise OnsTimeseriesError("Empty ONS dataset_id")
    return text


def normalize_uri_path(raw: str) -> str:
    text = (raw or "").strip().lstrip("/")
    if text.endswith("/data"):
        text = text[: -len("/data")].rstrip("/")
    if not text:
        raise OnsTimeseriesError("Empty ONS uri_path")
    if "://" in text:
        raise OnsTimeseriesError(f"uri_path must be relative, got {raw!r}")
    return text


def timeseries_data_url(
    uri_path: str,
    *,
    base_url: str = ONS_SITE_BASE,
) -> str:
    path = normalize_uri_path(uri_path)
    return f"{base_url.rstrip('/')}/{path}/data"


def parse_ons_period(
    *,
    date_token: str | None = None,
    year: str | None = None,
    month: str | None = None,
    quarter: str | None = None,
) -> date:
    """Parse ONS year/month/quarter cells into a calendar date (period start)."""
    if year and month:
        month_key = str(month).strip().lower()
        month_num = _MONTH_NAME.get(month_key)
        if month_num is None:
            raise OnsTimeseriesError(f"Unparseable ONS month name: {month!r}")
        try:
            return date(int(str(year).strip()), month_num, 1)
        except ValueError as exc:
            raise OnsTimeseriesError(
                f"Unparseable ONS year/month: year={year!r} month={month!r}"
            ) from exc

    if year and quarter:
        q_raw = str(quarter).strip().upper().lstrip("Q")
        try:
            q = int(q_raw)
        except ValueError as exc:
            raise OnsTimeseriesError(f"Unparseable ONS quarter: {quarter!r}") from exc
        if q not in (1, 2, 3, 4):
            raise OnsTimeseriesError(f"ONS quarter out of range: {quarter!r}")
        try:
            return date(int(str(year).strip()), (q - 1) * 3 + 1, 1)
        except ValueError as exc:
            raise OnsTimeseriesError(
                f"Unparseable ONS year/quarter: year={year!r} quarter={quarter!r}"
            ) from exc

    if year and not month and not quarter and not date_token:
        try:
            return date(int(str(year).strip()), 1, 1)
        except ValueError as exc:
            raise OnsTimeseriesError(f"Unparseable ONS year: {year!r}") from exc

    text = (date_token or "").strip()
    if not text:
        raise OnsTimeseriesError("Empty ONS period")

    m = _PERIOD_QUARTER.match(text)
    if m:
        return date(int(m.group(1)), (int(m.group(2)) - 1) * 3 + 1, 1)

    m = _PERIOD_MONTH_TOKEN.match(text)
    if m:
        month_num = _MONTH_NAME.get(m.group(2).lower())
        if month_num is None:
            raise OnsTimeseriesError(f"Unparseable ONS period month: {text!r}")
        return date(int(m.group(1)), month_num, 1)

    m = _PERIOD_YEAR.match(text)
    if m:
        return date(int(m.group(1)), 1, 1)

    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text[:10])
        except ValueError as exc:
            raise OnsTimeseriesError(f"Unparseable ONS ISO period: {text!r}") from exc

    raise OnsTimeseriesError(f"Unparseable ONS period: {text!r}")


def _obs_from_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[WorldObservation]:
    out: list[WorldObservation] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise OnsTimeseriesError(f"ONS observations[{index}] is not an object")
        raw_value = row.get("value")
        if raw_value is None or raw_value == "":
            continue
        try:
            value = float(str(raw_value).replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise OnsTimeseriesError(
                f"ONS observations[{index}] non-numeric value: {raw_value!r}"
            ) from exc
        period = parse_ons_period(
            date_token=str(row.get("date") or "") or None,
            year=str(row.get("year") or "") or None,
            month=str(row.get("month") or "") or None,
            quarter=str(row.get("quarter") or "") or None,
        )
        out.append(WorldObservation(period=period, value=value))
    return out


def select_frequency_rows(
    payload: Mapping[str, Any],
    *,
    frequency: str,
) -> list[Mapping[str, Any]]:
    """Pick months/quarters/years array matching the passport frequency."""
    freq = (frequency or "").strip().lower()
    if freq == "monthly":
        keys = ("months", "quarters", "years")
    elif freq == "quarterly":
        keys = ("quarters", "months", "years")
    elif freq == "annual":
        keys = ("years", "quarters", "months")
    else:
        keys = ("months", "quarters", "years")

    for key in keys:
        raw = payload.get(key)
        if isinstance(raw, list) and raw:
            return [row for row in raw if isinstance(row, Mapping)]
    raise OnsTimeseriesError(
        f"ONS payload has no observations for frequency={frequency!r}"
    )


def parse_ons_timeseries_payload(
    payload: Mapping[str, Any],
    *,
    frequency: str,
    series_id: str | None = None,
) -> list[WorldObservation]:
    if not isinstance(payload, Mapping):
        raise OnsTimeseriesError(f"ONS payload must be an object, got {type(payload)!r}")

    desc = payload.get("description")
    if isinstance(desc, Mapping) and series_id:
        cdid = str(desc.get("cdid") or "").strip().upper()
        if cdid and cdid != normalize_cdid(series_id):
            raise OnsTimeseriesError(
                f"ONS CDID mismatch: expected {series_id!r}, payload has {cdid!r}"
            )

    rows = select_frequency_rows(payload, frequency=frequency)
    observations = _obs_from_rows(rows)
    if not observations:
        raise OnsTimeseriesError("ONS time-series had no numeric observations")
    observations.sort(key=lambda item: item.period)
    return observations


def _uri_path_from_spec_or_ref(
    *,
    curated: OnsSeriesSpec | None,
    series: WorldSeriesRef | None = None,
    dimensions: Mapping[str, str] | None = None,
    source_url: str | None = None,
) -> str:
    dims = dict(dimensions or {})
    if series is not None:
        dims.update(dict(series.dimensions or {}))
    for key in ("uri_path", "uri", "path"):
        if dims.get(key):
            return normalize_uri_path(dims[key])
    if curated and curated.uri_path:
        return normalize_uri_path(curated.uri_path)
    url = source_url or (series.source_url if series else None)
    if url:
        text = str(url).strip()
        prefix = ONS_SITE_BASE.rstrip("/") + "/"
        if text.startswith(prefix):
            text = text[len(prefix) :]
        return normalize_uri_path(text)
    sid = normalize_cdid(
        (series.series_id if series else None) or (curated.series_id if curated else "")
    )
    did = normalize_dataset_id(
        (series.dataset_id if series else None)
        or (curated.dataset_id if curated else "")
    )
    raise OnsTimeseriesError(
        f"ONS series {sid}/{did} missing dimensions.uri_path "
        f"(cannot build www.ons.gov.uk/…/data URL)"
    )


def _specs_from_national(series_specs: Sequence[Any]) -> list[OnsSeriesSpec]:
    out: list[OnsSeriesSpec] = []
    for row in series_specs:
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider != "ons":
            continue
        sid = normalize_cdid(str(getattr(row, "series_id", "") or ""))
        did = normalize_dataset_id(str(getattr(row, "dataset_id", "") or ""))
        dims = dict(getattr(row, "dimensions", None) or {})
        uri = dims.get("uri_path") or dims.get("uri") or dims.get("path")
        source_url = getattr(row, "source_url", None)
        if not uri and source_url:
            text = str(source_url).strip()
            prefix = ONS_SITE_BASE.rstrip("/") + "/"
            if text.startswith(prefix):
                uri = text[len(prefix) :]
            else:
                uri = text
        if not uri:
            raise OnsTimeseriesError(
                f"ONS national series {sid!r} needs dimensions.uri_path"
            )
        freq = getattr(row, "frequency", None) or "monthly"
        unit = getattr(row, "unit", None) or getattr(row, "unit_code", None) or "UNIT"
        title = (
            getattr(row, "name_en", None)
            or getattr(row, "name_ru", None)
            or getattr(row, "title", None)
        )
        out.append(
            OnsSeriesSpec(
                series_id=sid,
                dataset_id=did,
                uri_path=normalize_uri_path(str(uri)),
                title=str(title) if title else None,
                unit_code=str(unit).strip().upper() or "UNIT",
                frequency=str(freq).strip().lower() or "monthly",
                dimensions=dims,
                source_url=source_url,
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    **kwargs: Any,
) -> OnsTimeseriesAdapter:
    curated: Sequence[OnsSeriesSpec] | None = None
    if series_specs is not None:
        mapped = _specs_from_national(series_specs)
        curated = mapped if mapped else None
    return OnsTimeseriesAdapter(curated, **kwargs)


class OnsTimeseriesAdapter:
    """``WorldSourceAdapter`` for ONS www.ons.gov.uk time-series JSON."""

    provider = "ons"
    public_source_name = "Office for National Statistics"

    def __init__(
        self,
        series: Sequence[OnsSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = ONS_SITE_BASE,
        country_code: str = DEFAULT_COUNTRY_CODE,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_ONS_SERIES
        if not curated:
            raise OnsTimeseriesError(
                "OnsTimeseriesAdapter requires at least one curated OnsSeriesSpec"
            )
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE

        self._by_dataset: dict[str, list[OnsSeriesSpec]] = {}
        self._by_series_id: dict[str, OnsSeriesSpec] = {}
        for spec in curated:
            sid = normalize_cdid(spec.series_id)
            did = normalize_dataset_id(spec.dataset_id)
            uri = normalize_uri_path(spec.uri_path)
            dims = dict(spec.dimensions)
            dims.setdefault("uri_path", uri)
            normalized = OnsSeriesSpec(
                series_id=sid,
                dataset_id=did,
                uri_path=uri,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=(spec.frequency or "monthly").strip().lower() or "monthly",
                dimensions=dims,
                source_url=spec.source_url,
            )
            self._by_dataset.setdefault(did, []).append(normalized)
            self._by_series_id[sid] = normalized

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            title = members[0].title
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=title,
                metadata_url=timeseries_data_url(
                    members[0].uri_path, base_url=self._base_url
                ),
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = normalize_dataset_id(dataset.dataset_id)
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise OnsTimeseriesError(
                f"No curated ONS series for dataset_id={dataset.dataset_id!r}"
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
            raise OnsTimeseriesError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        series_id = normalize_cdid(series.series_id)
        curated = self._by_series_id.get(series_id)
        uri_path = _uri_path_from_spec_or_ref(
            curated=curated,
            series=series,
            dimensions=series.dimensions,
            source_url=series.source_url,
        )
        frequency = (
            (series.frequency or "").strip().lower()
            or (curated.frequency if curated else None)
            or "monthly"
        )
        fetched_at = datetime.now(timezone.utc)
        payload = await asyncio.to_thread(self._get_timeseries_sync, uri_path)
        observations = parse_ons_timeseries_payload(
            payload, frequency=frequency, series_id=series_id
        )
        if date_from is not None:
            observations = [o for o in observations if o.period >= date_from]
        if date_to is not None:
            observations = [o for o in observations if o.period <= date_to]
        if not observations:
            raise OnsTimeseriesError(
                f"ONS series {series_id} empty after date filter "
                f"({date_from}..{date_to})"
            )

        revision = (
            f"{observations[0].period.isoformat()}"
            f"/{observations[-1].period.isoformat()}"
            f"#{len(observations)}"
        )
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "cdid": series_id,
                    "uri": uri_path,
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

    def _get_timeseries_sync(self, uri_path: str) -> dict[str, Any]:
        url = timeseries_data_url(uri_path, base_url=self._base_url)
        try:
            response = self._session.get(
                url,
                timeout=self._timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": _USER_AGENT,
                },
            )
        except requests.RequestException as exc:
            raise OnsTimeseriesError(f"ONS GET {url} failed: {exc}") from exc
        body = (response.text or "").strip()
        if response.status_code >= 400:
            raise OnsTimeseriesError(
                f"ONS GET {url} HTTP {response.status_code}: {body[:300]}"
            )
        if not body:
            raise OnsTimeseriesError(f"ONS GET {url} returned empty body")
        try:
            payload = response.json()
        except ValueError as exc:
            raise OnsTimeseriesError(
                f"ONS GET {url} returned non-JSON: {body[:300]}"
            ) from exc
        if not isinstance(payload, dict):
            raise OnsTimeseriesError(
                f"ONS payload must be an object, got {type(payload)!r}"
            )
        return payload

    def _series_ref(self, spec: OnsSeriesSpec) -> WorldSeriesRef:
        sid = normalize_cdid(spec.series_id)
        did = normalize_dataset_id(spec.dataset_id)
        uri = normalize_uri_path(spec.uri_path)
        dims = dict(spec.dimensions)
        dims.setdefault("uri_path", uri)
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=did,
            series_id=sid,
            country_code=self._country_code,
            frequency=(spec.frequency or "monthly").strip().lower() or "monthly",
            unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
            dimensions=dims,
            title=spec.title,
            source_url=spec.source_url
            or timeseries_data_url(uri, base_url=self._base_url),
        )


ADAPTER = OnsTimeseriesAdapter
