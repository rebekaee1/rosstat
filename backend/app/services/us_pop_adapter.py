"""U.S. Census Bureau population estimates adapter for the world data plane.

Official-first source (ADR-0012): U.S. Census Bureau, Population Estimates
Program (PEP). Wire format stays inside this module; product layers see
``WorldSourceAdapter`` only.

Verified live 2026-08-27:

- The Census **Data API** (``https://api.census.gov/data/{vintage}/pep/...``)
  now requires an API key for every data query: unauthenticated requests are
  redirected to a "Missing Key" HTML page. Metadata endpoints are exempt, but
  they are useless without the data query. No key is configured in this
  project, so the API path is not used.
- The same Population Estimates are published as free CSV datasets on the
  Census FTP2 server (no key, no auth). Two files cover the requested depth:
    * Vintage 2020 evaluation series, 2010-2020 national totals:
      ``https://www2.census.gov/programs-surveys/popest/datasets/
      2010-2020/national/totals/nst-est2020-alldata.csv``
    * Current-vintage annual series, 2020-2025:
      ``https://www2.census.gov/programs-surveys/popest/datasets/
      2020-2025/state/totals/NST-EST2025-ALLDATA.csv``
      (the "national totals" sibling path 404s; the state file ships the
      national row as ``SUMLEV=010``).
- Both files are wide tables: one row per geography, one column per year
  (``POPESTIMATE{year}``). Values are July 1 resident population estimates,
  persons. The two vintages must never be merged within one year: each
  vintage revises its whole series, so overlapping years (2020) are taken
  from the newer vintage (last wins in ``parse_census_pop_csv``).

Public fields must not mention API keys, vintages or file names.
Attribution: «Бюро переписи населения США» (RU) / "U.S. Census Bureau" (EN).
Observation-year policy: population is a stock measured on July 1 of each
year; the latest vintage year is a legitimate closed observation, no year
cut-off is applied on top of what the source publishes.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Mapping, Sequence

import httpx

from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

PROVIDER = "census"
DATASET_ID = "popest"
PUBLIC_SOURCE_NAME = "Бюро переписи населения США"
PUBLIC_SOURCE_NAME_EN = "U.S. Census Bureau"
PUBLIC_SOURCE_URL = (
    "https://www.census.gov/data/tables/time-series/demo/popest/"
    "2020s-national-total.html"
)
PUBLIC_UNIT = "PERSONS"
PUBLIC_UNIT_RU = "человек"

# Vintage 2020 evaluation estimates: April 1, 2010 to July 1, 2020.
HIST_CSV_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/"
    "2010-2020/national/totals/nst-est2020-alldata.csv"
)
# Latest completed vintage: April 1, 2020 to July 1, 2025. National row
# lives in the state file under SUMLEV=010.
LATEST_CSV_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/"
    "2020-2025/state/totals/NST-EST2025-ALLDATA.csv"
)

# National row in both layouts.
_SUMLEV_NATIONAL = "010"
_POP_COLUMN_PREFIX = "POPESTIMATE"

_UA = "ForecastEconomy/1.0 (+https://forecasteconomy.com)"

NATIONAL_ROWS_URLS: tuple[str, ...] = (HIST_CSV_URL, LATEST_CSV_URL)

SERIES_CODE = "us-population-census"


def make_census_series_ref() -> WorldSeriesRef:
    return WorldSeriesRef(
        provider=PROVIDER,
        dataset_id=DATASET_ID,
        series_id=SERIES_CODE,
        country_code="US",
        frequency="annual",
        unit_code=PUBLIC_UNIT,
        dimensions={"series": SERIES_CODE},
        title="United States resident population",
        source_url=PUBLIC_SOURCE_URL,
    )


def _population_columns(fieldnames: Sequence[str]) -> dict[int, str]:
    """POPESTIMATE<year> columns → {year: column name}."""
    out: dict[int, str] = {}
    for name in fieldnames:
        column = (name or "").strip()
        if not column.upper().startswith(_POP_COLUMN_PREFIX):
            continue
        raw_year = column[len(_POP_COLUMN_PREFIX):]
        if raw_year.isdigit() and len(raw_year) == 4:
            year = int(raw_year)
            if 1900 <= year <= 2100:
                out[year] = column
    return out


def parse_census_pop_csv(text: str) -> dict[date, float]:
    """Чистый разбор CSV PEP → {1 июля года: человек}.

    Несколько файлов подаются пачкой (vintage 2020 + текущий vintage):
    национальная строка берётся из каждого, годы объединяются, при
    пересечении побеждает поздний файл (свежий vintage). Файлы одного
    vintage перезаписывают друг друга целиком — их нельзя смешивать
    частично, каждый vintage пересматривает весь ряд.
    """
    merged: dict[int, float] = {}
    for block in _split_csv_documents(text):
        national = _national_row(block)
        if national is None:
            continue
        reader = csv.DictReader(io.StringIO(national))
        if reader.fieldnames is None:
            continue
        row = next(iter(reader), None)
        if row is None:
            continue
        for year, column in _population_columns(reader.fieldnames).items():
            raw = (row.get(column) or "").strip().replace(",", "")
            try:
                value = float(raw)
            except ValueError:
                continue
            if value > 0:
                merged[year] = value
    return {date(year, 7, 1): value for year, value in sorted(merged.items())}


def _split_csv_documents(text: str) -> list[str]:
    """CSV-файлы подаются склеенными (HIST + LATEST) одним текстом."""
    if "SUMLEV" not in text or text.count("SUMLEV") <= 1:
        return [text]
    marker = "SUMLEV"
    parts: list[str] = []
    index = text.find(marker)
    while index != -1:
        end = text.find(marker, index + len(marker))
        parts.append(text[index:] if end == -1 else text[index:end])
        index = end
    return [part for part in (p.strip("\r\n") for p in parts) if part]


def _national_row(block: str) -> str | None:
    """Блок CSV, сведённый к национальной строке (SUMLEV=010) + заголовок."""
    lines = block.splitlines()
    header_index = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("SUMLEV")),
        None,
    )
    if header_index is None:
        return None
    header = lines[header_index]
    body = [
        line
        for line in lines[header_index + 1:]
        if line.strip() and line.split(",")[0].strip().strip('"') == _SUMLEV_NATIONAL
    ]
    if not body:
        return None
    return "\r\n".join([header, body[0]])


def _payload_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fetch_census_csv(url: str) -> str:
    with httpx.Client(
        timeout=60.0,
        headers={"User-Agent": _UA, "Accept": "text/csv,*/*"},
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


class UsCensusPopAdapter:
    """WorldSourceAdapter for U.S. Census Bureau resident population."""

    provider = PROVIDER
    public_source_name = PUBLIC_SOURCE_NAME

    def __init__(self, *, fetch_csv=None, urls: Sequence[str] | None = None) -> None:
        self._fetch_csv = fetch_csv or _fetch_census_csv
        self._urls = tuple(urls or NATIONAL_ROWS_URLS)

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        yield WorldDatasetVersion(
            provider=PROVIDER,
            dataset_id=DATASET_ID,
            title="Population Estimates Program",
            metadata_url=PUBLIC_SOURCE_URL,
        )

    async def list_series(
        self,
        dataset: WorldDatasetVersion | None,
    ) -> AsyncIterator[WorldSeriesRef]:
        if dataset is not None and dataset.dataset_id != DATASET_ID:
            return
        yield make_census_series_ref()

    async def fetch_series(
        self,
        series: WorldSeriesRef,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorldSeriesPayload:
        fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
        text = "".join(self._fetch_csv(url) for url in self._urls)
        points = parse_census_pop_csv(text)
        observations = [
            WorldObservation(period=period, value=value)
            for period, value in points.items()
            if (date_from is None or period >= date_from)
            and (date_to is None or period <= date_to)
        ]
        return WorldSeriesPayload(
            ref=series,
            observations=observations,
            fetched_at=fetched_at,
            source_hash=_payload_hash(text),
        )

    def fetch_national_points(self) -> list[tuple[date, float]]:
        """Все национальные годовые точки (vintages merged) — для ingest."""
        text = "".join(self._fetch_csv(url) for url in self._urls)
        return list(parse_census_pop_csv(text).items())
