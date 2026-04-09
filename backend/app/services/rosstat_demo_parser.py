"""
Parsers for Rosstat demographic data:
- demo21_YYYY.xlsx → births, deaths, birth rate, death rate
- demo14.xlsx → working-age population
- Sp_2.1_YYYY.xlsx → pensioners

All files: rosstat.gov.ru/storage/mediabank/
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

import openpyxl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Indicator, IndicatorData, FetchLog
from app.services.http_client import create_session
from app.services.base_parser import BaseParser
from app.services.upsert import upsert_indicator_data

logger = logging.getLogger(__name__)

BASE_URL = "https://rosstat.gov.ru/storage/mediabank/"


@dataclass
class DataPoint:
    date: date
    value: float


def _extract_year(cell) -> int | None:
    if cell is None:
        return None
    s = str(cell).strip()
    m = re.match(r"(\d{4})", s)
    if m:
        y = int(m.group(1))
        if 1900 <= y <= 2100:
            return y
    return None


def _to_float(cell) -> float | None:
    if cell is None:
        return None
    s = str(cell).strip().replace(",", ".").replace("\xa0", "").replace(" ", "")
    if s in ("", "…", "-", "..."):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def parse_demo21_xlsx(content: bytes) -> dict[str, list[DataPoint]]:
    """Parse demo21_YYYY.xlsx → births, deaths, birth_rate, death_rate."""
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows_data = [list(row) for row in ws.iter_rows(values_only=True)]
    wb.close()

    births, deaths, birth_rate, death_rate = [], [], [], []

    for row in rows_data:
        if not row or len(row) < 7:
            continue
        year = _extract_year(row[0])
        if year is None or year < 1990:
            continue

        d = date(year, 1, 1)
        b = _to_float(row[1])
        de = _to_float(row[2])
        br = _to_float(row[4])
        dr = _to_float(row[5])

        if b is not None:
            births.append(DataPoint(date=d, value=round(b / 1000, 1)))
        if de is not None:
            deaths.append(DataPoint(date=d, value=round(de / 1000, 1)))
        if br is not None:
            birth_rate.append(DataPoint(date=d, value=br))
        if dr is not None:
            death_rate.append(DataPoint(date=d, value=dr))

    return {
        "births": sorted(births, key=lambda p: p.date),
        "deaths": sorted(deaths, key=lambda p: p.date),
        "birth-rate": sorted(birth_rate, key=lambda p: p.date),
        "death-rate": sorted(death_rate, key=lambda p: p.date),
    }


def parse_demo14_xlsx(content: bytes) -> list[DataPoint]:
    """Parse demo14.xlsx → working-age population (тыс. чел.) from row 25."""
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows_data = [list(row) for row in ws.iter_rows(values_only=True)]
    wb.close()

    if len(rows_data) < 26:
        raise ValueError(f"demo14: expected >= 26 rows, got {len(rows_data)}")

    year_row = rows_data[5]
    working_age_row = None
    for i in range(20, min(30, len(rows_data))):
        cell = str(rows_data[i][0] or "").lower().replace("\xa0", " ").strip()
        if "трудоспособном" in cell and "моложе" not in cell and "старше" not in cell:
            working_age_row = rows_data[i]
            break

    if working_age_row is None:
        raise ValueError("demo14: working-age row not found")

    points = []
    for col_idx in range(1, min(len(year_row), len(working_age_row))):
        year = _extract_year(year_row[col_idx])
        if year is None or year < 1990:
            continue
        val = _to_float(working_age_row[col_idx])
        if val is not None:
            points.append(DataPoint(date=date(year, 1, 1), value=round(val / 1000, 2)))

    return sorted(points, key=lambda p: p.date)


def parse_pensioners_xlsx(content: bytes) -> list[DataPoint]:
    """Parse Sp_2.1_YYYY.xlsx → total pensioners (тыс. чел.)."""
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    sheets = wb.sheetnames
    ws = None
    for name in sheets:
        if "РФ" in name or "2014" in name:
            ws = wb[name]
            break
    if ws is None:
        ws = wb.worksheets[-1]

    rows_data = [list(row) for row in ws.iter_rows(values_only=True)]
    wb.close()

    if len(rows_data) < 5:
        raise ValueError(f"Pensioners: expected >= 5 rows, got {len(rows_data)}")

    year_row = None
    data_row = None
    for i in range(min(10, len(rows_data))):
        row = rows_data[i]
        years_found = sum(1 for c in row[1:15] if _extract_year(c) is not None)
        if years_found >= 3:
            year_row = row
            if i + 1 < len(rows_data):
                data_row = rows_data[i + 1]
            break

    if year_row is None or data_row is None:
        raise ValueError("Pensioners: year/data row not found")

    points = []
    for col_idx in range(1, min(len(year_row), len(data_row))):
        year = _extract_year(year_row[col_idx])
        if year is None:
            continue
        val = _to_float(data_row[col_idx])
        if val is not None:
            points.append(DataPoint(date=date(year, 1, 1), value=round(val, 1)))

    return sorted(points, key=lambda p: p.date)


DEMO_FILES = {
    "births": ("demo21", "births"),
    "deaths": ("demo21", "deaths"),
    "birth-rate": ("demo21", "birth-rate"),
    "death-rate": ("demo21", "death-rate"),
    "working-age-population": ("demo14", None),
    "pensioners": ("pensioners", None),
}


def _try_download(session, filename: str) -> bytes | None:
    url = BASE_URL + filename
    try:
        resp = session.get(url, timeout=60)
        if resp.status_code == 200 and resp.content[:4] == b"PK\x03\x04":
            return resp.content
    except Exception:
        pass
    return None


class RosstatDemoParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_demo"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        cfg = indicator.model_config_json or {}
        file_type = cfg.get("demo_file", "demo21")

        session = create_session()
        session.verify = settings.rosstat_ca_cert

        if file_type == "demo21":
            filenames = [f"demo21_{y}.xlsx" for y in range(2026, 2020, -1)]
            content = None
            used_url = ""
            for fn in filenames:
                content = _try_download(session, fn)
                if content:
                    used_url = BASE_URL + fn
                    break
            if not content:
                raise ValueError(f"demo21 XLSX not found (tried {filenames})")

            fetch_log.source_url = used_url
            result = parse_demo21_xlsx(content)
            series_key = cfg.get("demo_series", code)
            points = result.get(series_key, [])

        elif file_type == "demo14":
            content = _try_download(session, "demo14.xlsx")
            if not content:
                raise ValueError("demo14.xlsx not found")
            fetch_log.source_url = BASE_URL + "demo14.xlsx"
            points = parse_demo14_xlsx(content)

        elif file_type == "pensioners":
            filenames = [f"Sp_2.1_{y}.xlsx" for y in range(2026, 2020, -1)]
            content = None
            for fn in filenames:
                content = _try_download(session, fn)
                if content:
                    fetch_log.source_url = BASE_URL + fn
                    break
            if not content:
                raise ValueError(f"Pensioners XLSX not found")
            points = parse_pensioners_xlsx(content)

        else:
            raise ValueError(f"Unknown demo_file type: {file_type}")

        if not points:
            fetch_log.status = "no_new_data"
            fetch_log.records_added = 0
            return

        count = await upsert_indicator_data(db, indicator.id, [(p.date, p.value) for p in points])
        fetch_log.status = "success"
        fetch_log.records_added = count
        logger.info("%s: upserted %d points from %s", code, count, file_type)
