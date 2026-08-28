"""Reserve Bank of Australia statistical tables adapter.

Official CSVs: ``https://www.rba.gov.au/statistics/tables/csv/{filename}``
(index: https://www.rba.gov.au/statistics/tables/).

RBA does not publish a public JSON REST API for F-tables. Tables are static
CSV files with a label-driven metadata block (Title / Description / Frequency /
Units / Source / Publication date / Series ID) followed by dated observation
rows. Dates appear as ``DD-Mon-YYYY`` or ``DD/MM/YYYY``.

Confirmed live passport series:

- ``F1`` / ``FIRMMCRTD`` — Cash Rate Target (business daily)
- ``F11.1`` / ``FXRUSD`` — AUD/USD daily exchange rate
- ``F11.1`` / ``FXRTWI`` — Trade-weighted Index (May 1970 = 100)

``WorldSeriesRef.dataset_id`` is the RBA table id (e.g. ``F1``, ``F11.1``);
``series_id`` is the RBA Series ID mnemonic. Country code is always ``AU``.
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
from typing import AsyncIterator, Mapping, Sequence

import requests

from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

logger = logging.getLogger(__name__)

RBA_CSV_BASE = "https://www.rba.gov.au/statistics/tables/csv"
RBA_TABLES_INDEX = "https://www.rba.gov.au/statistics/tables/"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_COUNTRY_CODE = "AU"
_DEFAULT_DATE_FROM = date(1900, 1, 1)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

# Official table id → CDN filename under /statistics/tables/csv/.
_KNOWN_CSV_FILENAMES: dict[str, str] = {
    "F1": "f1-data.csv",
    "F1.1": "f1.1-data.csv",
    "F11": "f11-data.csv",
    "F11.1": "f11.1-data.csv",
}

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

_LABEL_TO_FIELD: dict[str, str] = {
    "title": "title",
    "description": "description",
    "frequency": "frequency",
    "type": "type",
    "units": "units",
    "source": "source",
    "publication date": "publication_date",
    "series id": "series_id",
    "mnemonic": "series_id",
}

_DMY_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_DMY_MON = re.compile(r"^(\d{1,2})-([A-Za-z]{3,9})-(\d{4})$")


class RbaStatsError(RuntimeError):
    """Raised when an RBA CSV is missing, malformed, or unusable."""


@dataclass(frozen=True)
class RbaSeriesSpec:
    """Curated RBA Series ID inside one statistical table."""

    series_id: str
    dataset_id: str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "daily"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None
    csv_filename: str | None = None


# Confirmed live passport series (business daily → platform ``daily``).
DEFAULT_RBA_SERIES: tuple[RbaSeriesSpec, ...] = (
    RbaSeriesSpec(
        series_id="FIRMMCRTD",
        dataset_id="F1",
        title="Cash Rate Target",
        unit_code="PERCENT",
        frequency="daily",
        csv_filename="f1-data.csv",
    ),
    RbaSeriesSpec(
        series_id="FXRUSD",
        dataset_id="F11.1",
        title="AUD/USD",
        unit_code="USD",
        frequency="daily",
        dimensions={"quote": "USD", "base": "AUD"},
        csv_filename="f11.1-data.csv",
    ),
    RbaSeriesSpec(
        series_id="FXRTWI",
        dataset_id="F11.1",
        title="Trade-weighted Index",
        unit_code="INDEX",
        frequency="daily",
        csv_filename="f11.1-data.csv",
    ),
)


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip().upper()
    if not text:
        raise RbaStatsError("Empty RBA series id")
    return text


def normalize_table_id(raw: str) -> str:
    text = (raw or "").strip().upper()
    if not text:
        raise RbaStatsError("Empty RBA table id")
    return text


def csv_filename_for_table(table_id: str, *, override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    tid = normalize_table_id(table_id)
    known = _KNOWN_CSV_FILENAMES.get(tid)
    if known:
        return known
    return f"{tid.lower()}-data.csv"


def table_csv_url(
    table_id: str,
    *,
    base_url: str = RBA_CSV_BASE,
    csv_filename: str | None = None,
) -> str:
    filename = csv_filename_for_table(table_id, override=csv_filename)
    return f"{base_url.rstrip('/')}/{filename}"


def parse_rba_date(raw: str) -> date:
    """Parse RBA observation dates (``DD-Mon-YYYY``, ``DD/MM/YYYY``, ISO)."""
    text = (raw or "").strip()
    if not text:
        raise RbaStatsError("Empty RBA observation date")

    slash = _DMY_SLASH.match(text)
    if slash:
        day_s, month_s, year_s = slash.groups()
        try:
            return date(int(year_s), int(month_s), int(day_s))
        except ValueError as exc:
            raise RbaStatsError(f"Unparseable RBA date: {raw!r}") from exc

    mon = _DMY_MON.match(text)
    if mon:
        day_s, month_raw, year_s = mon.groups()
        month = _MONTH_ABBR.get(month_raw[:3].lower())
        if month is None:
            raise RbaStatsError(f"Unparseable RBA month in date: {raw!r}")
        try:
            return date(int(year_s), month, int(day_s))
        except ValueError as exc:
            raise RbaStatsError(f"Unparseable RBA date: {raw!r}") from exc

    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise RbaStatsError(f"Unparseable RBA observation date: {raw!r}") from exc


def _looks_like_date(cell: str) -> bool:
    text = (cell or "").strip()
    if not text:
        return False
    if _DMY_SLASH.match(text) or _DMY_MON.match(text):
        return True
    try:
        date.fromisoformat(text[:10])
        return len(text) >= 8 and text[0].isdigit()
    except ValueError:
        return False


def parse_rba_csv_series(
    body: str | bytes,
    *,
    series_id: str,
) -> tuple[str | None, list[WorldObservation]]:
    """Extract one Series ID column from an RBA statistical-table CSV.

    Returns ``(series_title, observations)``. Blank / non-numeric cells are
    skipped (weekend gaps, discontinued columns).
    """
    sid = normalize_series_id(series_id)
    if isinstance(body, bytes):
        text = body.decode("utf-8-sig", errors="replace")
    else:
        text = body
    if not text.strip():
        raise RbaStatsError(f"Empty RBA CSV for series {sid}")

    reader = csv.reader(StringIO(text))
    rows: list[list[str]] = [list(row) for row in reader]
    if not rows:
        raise RbaStatsError(f"RBA CSV had no rows for series {sid}")

    table_title = (rows[0][0].strip() if rows[0] else "") or None
    n_cols = max((len(r) for r in rows), default=0)
    by_field: dict[str, list[str]] = {}
    data_start = None

    for row_idx in range(1, len(rows)):
        row = rows[row_idx]
        if not row:
            continue
        label_raw = (row[0] or "").strip()
        label = label_raw.lower()
        if label and _looks_like_date(label):
            data_start = row_idx
            break
        if not label:
            continue
        field_name = _LABEL_TO_FIELD.get(label)
        if field_name is None:
            continue
        padded = [(row[i].strip() if i < len(row) else "") for i in range(n_cols)]
        by_field[field_name] = padded

    series_row = by_field.get("series_id")
    if not series_row:
        raise RbaStatsError(
            f"RBA CSV missing Series ID row for {sid} "
            f"(found metadata: {sorted(by_field)})"
        )

    col_idx = None
    for i in range(1, len(series_row)):
        if (series_row[i] or "").strip().upper() == sid:
            col_idx = i
            break
    if col_idx is None:
        raise RbaStatsError(f"RBA CSV has no column for series id {sid}")

    title_row = by_field.get("title") or []
    series_title = None
    if col_idx < len(title_row) and title_row[col_idx]:
        series_title = title_row[col_idx]

    if data_start is None:
        # Fallback: first row after Series ID whose col0 looks like a date.
        series_row_idx = next(
            (
                i
                for i, row in enumerate(rows)
                if row and (row[0] or "").strip().lower() in {"series id", "mnemonic"}
            ),
            None,
        )
        start_guess = (series_row_idx + 1) if series_row_idx is not None else 1
        for row_idx in range(start_guess, len(rows)):
            row = rows[row_idx]
            if row and _looks_like_date((row[0] or "").strip()):
                data_start = row_idx
                break
    if data_start is None:
        raise RbaStatsError(f"RBA CSV has no observation rows for {sid}")

    observations: list[WorldObservation] = []
    for row_idx in range(data_start, len(rows)):
        row = rows[row_idx]
        if not row:
            continue
        raw_date = (row[0] or "").strip()
        if not raw_date:
            continue
        if not _looks_like_date(raw_date):
            # Trailing notes block after the data section.
            continue
        period = parse_rba_date(raw_date)
        raw_value = row[col_idx].strip() if col_idx < len(row) else ""
        if raw_value == "" or raw_value.upper() in {"NA", "N/A", "-", ".."}:
            continue
        try:
            value = float(raw_value.replace(",", ""))
        except ValueError as exc:
            raise RbaStatsError(
                f"RBA CSV non-numeric value for {sid} on {raw_date!r}: {raw_value!r}"
            ) from exc
        observations.append(WorldObservation(period=period, value=value))

    if not observations:
        raise RbaStatsError(f"RBA CSV had no numeric values for {sid}")
    observations.sort(key=lambda item: item.period)
    return series_title or table_title, observations


class RbaStatsAdapter:
    """``WorldSourceAdapter`` for Reserve Bank of Australia statistical CSVs."""

    provider = "rba"
    public_source_name = "Reserve Bank of Australia"

    def __init__(
        self,
        series: Sequence[RbaSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        csv_base_url: str = RBA_CSV_BASE,
        country_code: str = DEFAULT_COUNTRY_CODE,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_RBA_SERIES
        if not curated:
            raise RbaStatsError(
                "RbaStatsAdapter requires at least one curated RbaSeriesSpec"
            )
        self._series = curated
        self._session = session or requests.Session()
        self._timeout = timeout
        self._csv_base_url = csv_base_url.rstrip("/")
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._csv_cache: dict[str, str] = {}
        self._by_dataset: dict[str, list[RbaSeriesSpec]] = {}
        self._by_series_id: dict[str, RbaSeriesSpec] = {}
        for spec in self._series:
            sid = normalize_series_id(spec.series_id)
            did = normalize_table_id(spec.dataset_id)
            normalized = RbaSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=(spec.frequency or "daily").strip().lower() or "daily",
                dimensions=dict(spec.dimensions),
                source_url=spec.source_url,
                csv_filename=spec.csv_filename,
            )
            self._by_dataset.setdefault(did, []).append(normalized)
            self._by_series_id[sid] = normalized

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            title = members[0].title
            if len(members) > 1:
                title = f"RBA Table {dataset_id}"
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=title,
                metadata_url=RBA_TABLES_INDEX,
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = normalize_table_id(dataset.dataset_id)
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise RbaStatsError(
                f"No curated RBA series for dataset_id={dataset_id!r}"
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
            raise RbaStatsError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        series_id = normalize_series_id(series.series_id)
        dataset_id = normalize_table_id(series.dataset_id)
        fetched_at = datetime.now(timezone.utc)

        curated = self._by_series_id.get(series_id)
        csv_filename = curated.csv_filename if curated else None
        url = table_csv_url(
            dataset_id,
            base_url=self._csv_base_url,
            csv_filename=csv_filename,
        )

        body = await asyncio.to_thread(self._get_csv_sync, url)
        title, observations = await asyncio.to_thread(
            parse_rba_csv_series, body, series_id=series_id
        )

        start = date_from or _DEFAULT_DATE_FROM
        end = date_to or date.today()
        if date_from is not None or date_to is not None:
            if end < start:
                raise RbaStatsError(
                    f"date_to {end.isoformat()} is before date_from {start.isoformat()}"
                )
            observations = [
                item for item in observations if start <= item.period <= end
            ]
            if not observations:
                raise RbaStatsError(
                    f"RBA series {series_id} has no observations in "
                    f"{start.isoformat()}..{end.isoformat()}"
                )

        revision = (
            f"{observations[0].period.isoformat()}"
            f"/{observations[-1].period.isoformat()}"
            f"#{len(observations)}"
        )
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "table": dataset_id,
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
                source_url=series.source_url or url,
            )

        return WorldSeriesPayload(
            ref=ref,
            observations=observations,
            fetched_at=fetched_at,
            revision_token=revision,
            source_hash=source_hash,
        )

    # ------------------------------------------------------------------ sync HTTP

    def _get_csv_sync(self, url: str) -> str:
        cached = self._csv_cache.get(url)
        if cached is not None:
            return cached
        try:
            response = self._session.get(
                url,
                timeout=self._timeout,
                headers={
                    "Accept": "text/csv,text/plain,*/*",
                    "User-Agent": _USER_AGENT,
                    "Referer": RBA_TABLES_INDEX,
                    "Accept-Language": "en-AU,en;q=0.9",
                },
            )
        except requests.RequestException as exc:
            raise RbaStatsError(f"RBA GET {url} failed: {exc}") from exc
        if response.status_code >= 400:
            raise RbaStatsError(
                f"RBA GET {url} HTTP {response.status_code}: {response.text[:300]}"
            )
        # Akamai sometimes returns HTML 403 with 200 in misconfigured proxies —
        # reject obvious HTML error pages.
        content_type = (response.headers.get("Content-Type") or "").lower()
        text = response.content.decode("utf-8-sig", errors="replace")
        if "text/html" in content_type and "Series ID" not in text[:2000]:
            raise RbaStatsError(
                f"RBA GET {url} returned HTML instead of CSV "
                f"(status={response.status_code})"
            )
        if "Series ID" not in text and "Mnemonic" not in text:
            raise RbaStatsError(
                f"RBA GET {url} payload missing Series ID / Mnemonic row"
            )
        self._csv_cache[url] = text
        return text

    def _series_ref(self, spec: RbaSeriesSpec) -> WorldSeriesRef:
        sid = normalize_series_id(spec.series_id)
        did = normalize_table_id(spec.dataset_id)
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
            or table_csv_url(
                did,
                base_url=self._csv_base_url,
                csv_filename=spec.csv_filename,
            ),
        )


# Preferred discovery aliases for world_national_ingest.resolve_adapter.
RbaAdapter = RbaStatsAdapter
ADAPTER = RbaStatsAdapter
