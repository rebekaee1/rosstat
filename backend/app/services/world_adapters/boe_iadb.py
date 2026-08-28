"""Bank of England Interactive Statistical Database (IADB) CSV adapter.

Official CSV export (no public JSON REST for headline rates)::

    https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp
        ?csv.x=yes
        &Datefrom=01/Jan/YYYY
        &Dateto=DD/Mon/YYYY
        &SeriesCodes={CODE}
        &CSVF=TN
        &UsingCodes=Y
        &VPD=Y
        &VFD=N

Confirmed live passport series:

- ``IUDBEDR`` — Official Bank Rate (business daily)
- ``XUDLUSS`` — USD per GBP spot (US$ per £1, business daily)

``WorldSeriesRef.dataset_id`` may equal the series code. ``series_id`` is the
IADB SeriesCodes mnemonic. Country code is ``UK``.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from io import StringIO
from typing import Any, AsyncIterator, Mapping, Sequence

import requests

from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

logger = logging.getLogger(__name__)

BOE_IADB_CSV_URL = (
    "https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp"
)
BOE_DATABASE_INDEX = "https://www.bankofengland.co.uk/boeapps/database/"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_COUNTRY_CODE = "UK"
# IADB HTML-errors / hangs on very long windows from this environment; 2000+
# is enough for passport charts and confirmed live for IUDBEDR / XUDLUSS.
_DEFAULT_DATE_FROM = date(2000, 1, 1)
_FALLBACK_DATE_FROM = (date(2010, 1, 1), date(2020, 1, 1))

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

_MONTH_ABBR: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_DMY_MON = re.compile(r"^(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})$")
_DMY_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


class BoeIadbError(RuntimeError):
    """Raised when BoE IADB CSV is missing, blocked, or unusable."""


@dataclass(frozen=True)
class BoeSeriesSpec:
    """Curated BoE IADB SeriesCodes mnemonic."""

    series_id: str
    dataset_id: str | None = None
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "daily"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


DEFAULT_BOE_SERIES: tuple[BoeSeriesSpec, ...] = (
    BoeSeriesSpec(
        series_id="IUDBEDR",
        dataset_id="IUDBEDR",
        title="Official Bank Rate",
        unit_code="PERCENT",
        frequency="daily",
    ),
    BoeSeriesSpec(
        series_id="XUDLUSS",
        dataset_id="XUDLUSS",
        title="USD per GBP spot exchange rate",
        unit_code="USD_PER_GBP",
        frequency="daily",
        dimensions={"quote": "USD", "base": "GBP"},
    ),
)


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip().upper()
    if not text:
        raise BoeIadbError("Empty BoE series id")
    return text


def normalize_dataset_id(raw: str | None, *, series_id: str) -> str:
    text = (raw or "").strip().upper()
    return text or series_id


def format_boe_date_param(period: date) -> str:
    """BoE query params use ``DD/Mon/YYYY`` (e.g. ``01/Jan/2020``)."""
    months = (
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    )
    return f"{period.day:02d}/{months[period.month - 1]}/{period.year}"


def observations_url(
    series_id: str,
    *,
    base_url: str = BOE_IADB_CSV_URL,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str:
    """Build a documented IADB CSV URL (for source_url / debugging)."""
    sid = normalize_series_id(series_id)
    start = date_from or _DEFAULT_DATE_FROM
    end = date_to or date.today()
    params = (
        f"csv.x=yes"
        f"&Datefrom={format_boe_date_param(start)}"
        f"&Dateto={format_boe_date_param(end)}"
        f"&SeriesCodes={sid}"
        f"&CSVF=TN"
        f"&UsingCodes=Y"
        f"&VPD=Y"
        f"&VFD=N"
    )
    return f"{base_url.rstrip('/')}?{params}"


def parse_boe_date(raw: str) -> date:
    """Parse BoE CSV dates (``02 Jan 2020``, ``02/01/2020``, ISO)."""
    text = (raw or "").strip()
    if not text:
        raise BoeIadbError("Empty BoE observation date")

    mon = _DMY_MON.match(text)
    if mon:
        day_s, month_raw, year_s = mon.groups()
        month = _MONTH_ABBR.get(month_raw[:3].lower())
        if month is None:
            raise BoeIadbError(f"Unparseable BoE month in date: {raw!r}")
        try:
            return date(int(year_s), month, int(day_s))
        except ValueError as exc:
            raise BoeIadbError(f"Unparseable BoE date: {raw!r}") from exc

    slash = _DMY_SLASH.match(text)
    if slash:
        day_s, month_s, year_s = slash.groups()
        try:
            return date(int(year_s), int(month_s), int(day_s))
        except ValueError as exc:
            raise BoeIadbError(f"Unparseable BoE slash date: {raw!r}") from exc

    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text[:10])
        except ValueError as exc:
            raise BoeIadbError(f"Unparseable BoE ISO date: {raw!r}") from exc

    raise BoeIadbError(f"Unparseable BoE date: {raw!r}")


def parse_boe_iadb_csv(
    text: str,
    *,
    series_id: str,
) -> list[WorldObservation]:
    """Parse IADB ``CSVF=TN`` body: header ``DATE,<SERIES>`` then rows."""
    sid = normalize_series_id(series_id)
    body = (text or "").lstrip("\ufeff").strip()
    if not body:
        raise BoeIadbError(f"BoE IADB CSV empty for {sid}")
    lowered = body[:500].lower()
    if "<html" in lowered or "access denied" in lowered or "forbidden" in lowered:
        raise BoeIadbError(f"BoE IADB returned HTML/blocked page for {sid}")

    reader = csv.reader(StringIO(body))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise BoeIadbError(f"BoE IADB CSV has no header for {sid}") from exc

    header_norm = [h.strip().upper() for h in header]
    if not header_norm or header_norm[0] not in {"DATE", "DATE CHANGED", "DATECHANGED"}:
        # Some exports still start with DATE; otherwise require series column.
        if sid not in header_norm:
            raise BoeIadbError(
                f"BoE IADB CSV header missing DATE/{sid}: {header!r}"
            )

    try:
        series_idx = header_norm.index(sid)
    except ValueError as exc:
        # Single-series TN export is usually DATE,SERIES — take column 1.
        if len(header_norm) >= 2:
            series_idx = 1
        else:
            raise BoeIadbError(
                f"BoE IADB CSV missing column for {sid}: {header!r}"
            ) from exc

    observations: list[WorldObservation] = []
    for index, row in enumerate(reader):
        if not row or all(not (cell or "").strip() for cell in row):
            continue
        if len(row) <= series_idx:
            continue
        raw_date = (row[0] or "").strip()
        raw_value = (row[series_idx] or "").strip()
        if not raw_date or not raw_value:
            continue
        if raw_value.upper() in {"NA", "N/A", ".", "..", "-"}:
            continue
        try:
            value = float(raw_value.replace(",", ""))
        except ValueError as exc:
            raise BoeIadbError(
                f"BoE IADB row {index} non-numeric value for {sid}: {raw_value!r}"
            ) from exc
        observations.append(
            WorldObservation(period=parse_boe_date(raw_date), value=value)
        )

    if not observations:
        raise BoeIadbError(f"BoE IADB CSV had no numeric values for {sid}")
    observations.sort(key=lambda item: item.period)
    return observations


def _specs_from_national(series_specs: Sequence[Any]) -> list[BoeSeriesSpec]:
    out: list[BoeSeriesSpec] = []
    for row in series_specs:
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider not in {"boe", "boe_iadb"}:
            continue
        sid = normalize_series_id(str(getattr(row, "series_id", "") or ""))
        did = normalize_dataset_id(
            str(getattr(row, "dataset_id", "") or "") or None,
            series_id=sid,
        )
        freq = getattr(row, "frequency", None) or "daily"
        unit = getattr(row, "unit", None) or getattr(row, "unit_code", None) or "UNIT"
        title = (
            getattr(row, "name_en", None)
            or getattr(row, "name_ru", None)
            or getattr(row, "title", None)
        )
        out.append(
            BoeSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=str(title) if title else None,
                unit_code=str(unit).strip().upper() or "UNIT",
                frequency=str(freq).strip().lower() or "daily",
                dimensions=dict(getattr(row, "dimensions", None) or {}),
                source_url=getattr(row, "source_url", None),
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    **kwargs: Any,
) -> BoeIadbAdapter:
    curated: Sequence[BoeSeriesSpec] | None = None
    if series_specs is not None:
        mapped = _specs_from_national(series_specs)
        curated = mapped if mapped else None
    return BoeIadbAdapter(curated, **kwargs)


class BoeIadbAdapter:
    """``WorldSourceAdapter`` for Bank of England IADB CSV exports."""

    provider = "boe_iadb"
    public_source_name = "Bank of England"

    def __init__(
        self,
        series: Sequence[BoeSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        csv_url: str = BOE_IADB_CSV_URL,
        country_code: str = DEFAULT_COUNTRY_CODE,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_BOE_SERIES
        if not curated:
            raise BoeIadbError(
                "BoeIadbAdapter requires at least one curated BoeSeriesSpec"
            )
        self._session = session or requests.Session()
        self._timeout = timeout
        self._csv_url = csv_url
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE

        self._by_dataset: dict[str, list[BoeSeriesSpec]] = {}
        self._by_series_id: dict[str, BoeSeriesSpec] = {}
        for spec in curated:
            sid = normalize_series_id(spec.series_id)
            did = normalize_dataset_id(spec.dataset_id, series_id=sid)
            normalized = BoeSeriesSpec(
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
                metadata_url=BOE_DATABASE_INDEX,
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = normalize_dataset_id(dataset.dataset_id, series_id=dataset.dataset_id)
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise BoeIadbError(
                f"No curated BoE series for dataset_id={dataset.dataset_id!r}"
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
            raise BoeIadbError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        series_id = normalize_series_id(series.series_id)
        start = date_from or _DEFAULT_DATE_FROM
        end = date_to or date.today()
        if end < start:
            raise BoeIadbError(
                f"date_to {end.isoformat()} is before date_from {start.isoformat()}"
            )
        fetched_at = datetime.now(timezone.utc)

        # Caller-supplied window is tried as-is; default passport fetch may
        # shorten the start date if IADB returns an HTML error page.
        candidates = [start]
        if date_from is None:
            for fallback in _FALLBACK_DATE_FROM:
                if fallback > start and fallback not in candidates:
                    candidates.append(fallback)

        last_error: Exception | None = None
        observations: list[WorldObservation] | None = None
        for candidate_start in candidates:
            try:
                text = await asyncio.to_thread(
                    self._get_csv_sync,
                    series_id,
                    start_date=candidate_start,
                    end_date=end,
                )
                observations = parse_boe_iadb_csv(text, series_id=series_id)
                if candidate_start != start:
                    logger.warning(
                        "BoE IADB %s: using shortened window from %s (requested %s)",
                        series_id,
                        candidate_start.isoformat(),
                        start.isoformat(),
                    )
                break
            except BoeIadbError as exc:
                last_error = exc
                msg = str(exc).lower()
                retryable = (
                    "html" in msg
                    or "blocked" in msg
                    or "empty" in msg
                    or "timed out" in msg
                    or "timeout" in msg
                )
                if not retryable or candidate_start == candidates[-1]:
                    raise
                logger.warning(
                    "BoE IADB %s window from %s failed (%s); retrying shorter",
                    series_id,
                    candidate_start.isoformat(),
                    exc,
                )
        if observations is None:
            assert last_error is not None
            raise last_error
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
        return WorldSeriesPayload(
            ref=series,
            observations=observations,
            fetched_at=fetched_at,
            revision_token=revision,
            source_hash=source_hash,
        )

    def _get_csv_sync(
        self,
        series_id: str,
        *,
        start_date: date,
        end_date: date,
    ) -> str:
        sid = normalize_series_id(series_id)
        params = {
            "csv.x": "yes",
            "Datefrom": format_boe_date_param(start_date),
            "Dateto": format_boe_date_param(end_date),
            "SeriesCodes": sid,
            "CSVF": "TN",
            "UsingCodes": "Y",
            "VPD": "Y",
            "VFD": "N",
        }
        try:
            response = self._session.get(
                self._csv_url,
                params=params,
                timeout=self._timeout,
                headers={
                    "Accept": "text/csv,text/plain,*/*",
                    "User-Agent": _USER_AGENT,
                    "Referer": BOE_DATABASE_INDEX,
                },
            )
        except requests.RequestException as exc:
            raise BoeIadbError(
                f"BoE IADB GET {self._csv_url} failed: {exc}"
            ) from exc
        if response.status_code >= 400:
            raise BoeIadbError(
                f"BoE IADB GET HTTP {response.status_code}: {response.text[:300]}"
            )
        content_type = (response.headers.get("Content-Type") or "").lower()
        text = response.content.decode("utf-8-sig", errors="replace")
        if "text/html" in content_type and "DATE" not in text[:200].upper():
            raise BoeIadbError(
                f"BoE IADB returned HTML instead of CSV for {sid} "
                f"(status={response.status_code})"
            )
        return text

    def _series_ref(self, spec: BoeSeriesSpec) -> WorldSeriesRef:
        sid = normalize_series_id(spec.series_id)
        did = normalize_dataset_id(spec.dataset_id, series_id=sid)
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=did,
            series_id=sid,
            country_code=self._country_code,
            frequency=(spec.frequency or "daily").strip().lower() or "daily",
            unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url or observations_url(sid, base_url=self._csv_url),
        )


ADAPTER = BoeIadbAdapter
