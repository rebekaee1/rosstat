"""
Parsers for Rosstat Science & Education indicators (.xls files).

Source: rosstat.gov.ru/storage/mediabank/
Files:
  - Kadry_VO.xls → grad students (sheet '1'), doctoral students (sheet '4')
  - Nauka_1.xls → R&D organizations (sheet '1', row 6)
  - nauka_2.xls → R&D personnel (sheet '1', row 6)
  - innov_1_YYYY.xls → innovation activity level (sheet '1')
  - innov_2_YYYY.xls → tech innovation share (sheet '1')
  - innov-mp_1.xls → small business innovation (sheet '5')
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar

import xlrd
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


def _to_float(val) -> float | None:
    if val is None or val == "":
        return None
    s = str(val).strip().replace(",", ".").replace("\xa0", "").replace(" ", "")
    if s in ("", "…", "-", "...", "0"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_year_row_xls(ws, row_idx: int) -> list[tuple[int, int]]:
    """Extract (col_idx, year) pairs from a header row in .xls sheet."""
    pairs = []
    for col in range(ws.ncols):
        val = ws.cell_value(row_idx, col)
        if isinstance(val, float) and 1990 <= val <= 2100:
            pairs.append((col, int(val)))
        elif isinstance(val, str):
            m = re.match(r"(\d{4})", val.strip())
            if m:
                y = int(m.group(1))
                if 1990 <= y <= 2100:
                    pairs.append((col, y))
    return pairs


def parse_kadry_xls(content: bytes, sheet_idx: int) -> list[DataPoint]:
    """Parse Kadry_VO.xls → total count from specified sheet.

    Structure: years vertical in col 0, total count in col 1.
    Sheet 1 = grad students, Sheet 4 = doctoral students.
    """
    wb = xlrd.open_workbook(file_contents=content)
    ws = wb.sheet_by_index(sheet_idx)

    points = []
    seen_years: set[int] = set()
    for r in range(ws.nrows):
        year_val = ws.cell_value(r, 0)
        year = None
        if isinstance(year_val, float) and 1990 <= year_val <= 2100:
            year = int(year_val)
        elif isinstance(year_val, str):
            m = re.match(r"(\d{4})", year_val.strip())
            if m:
                y = int(m.group(1))
                if 1990 <= y <= 2100:
                    year = y

        if year is None or year in seen_years:
            continue

        val = _to_float(ws.cell_value(r, 1))
        if val is not None and val > 0:
            seen_years.add(year)
            points.append(DataPoint(date=date(year, 1, 1), value=round(val, 0)))

    return sorted(points, key=lambda p: p.date)


def parse_nauka_total_xls(content: bytes, sheet_name: str = "1") -> list[DataPoint]:
    """Parse Nauka_1.xls or nauka_2.xls → total from "всего" row."""
    wb = xlrd.open_workbook(file_contents=content)
    ws = None
    for s in wb.sheets():
        if s.name.strip() == sheet_name:
            ws = s
            break
    if ws is None:
        ws = wb.sheet_by_index(min(1, wb.nsheets - 1))

    year_row = None
    for r in range(min(10, ws.nrows)):
        years = _parse_year_row_xls(ws, r)
        if len(years) >= 3:
            year_row = r
            break

    if year_row is None:
        raise ValueError("Nauka: no year header found")

    years = _parse_year_row_xls(ws, year_row)

    total_row = None
    for r in range(year_row + 1, min(year_row + 5, ws.nrows)):
        cell = str(ws.cell_value(r, 0)).lower().strip()
        if "всего" in cell or "число" in cell or "численность" in cell:
            total_row = r
            break
    if total_row is None:
        total_row = year_row + 2

    points = []
    for col, year in years:
        if total_row < ws.nrows and col < ws.ncols:
            val = _to_float(ws.cell_value(total_row, col))
            if val is not None:
                points.append(DataPoint(date=date(year, 1, 1), value=round(val, 2)))

    return sorted(points, key=lambda p: p.date)


def parse_innov_russia_xls(content: bytes, sheet_name: str = "1") -> list[DataPoint]:
    """Parse innov_*.xls → Russia-level % from first data row after 'Российская Федерация'."""
    wb = xlrd.open_workbook(file_contents=content)
    ws = None
    for s in wb.sheets():
        if s.name.strip() == sheet_name:
            ws = s
            break
    if ws is None:
        ws = wb.sheet_by_index(min(1, wb.nsheets - 1))

    year_row = None
    for r in range(min(10, ws.nrows)):
        years = _parse_year_row_xls(ws, r)
        if len(years) >= 3:
            year_row = r
            break

    if year_row is None:
        raise ValueError("Innov: no year header found")

    years = _parse_year_row_xls(ws, year_row)

    russia_row = None
    for r in range(year_row + 1, min(year_row + 10, ws.nrows)):
        cell = str(ws.cell_value(r, 0)).lower().strip()
        if "российская" in cell or "всего" in cell or "итого" in cell:
            russia_row = r
            break
    if russia_row is None:
        russia_row = year_row + 2

    points = []
    for col, year in years:
        if russia_row < ws.nrows and col < ws.ncols:
            val = _to_float(ws.cell_value(russia_row, col))
            if val is not None:
                points.append(DataPoint(date=date(year, 1, 1), value=round(val, 2)))

    return sorted(points, key=lambda p: p.date)


def _try_download_xls(session, filename: str) -> bytes | None:
    url = BASE_URL + filename
    try:
        resp = session.get(url, timeout=60)
        if resp.status_code == 200 and len(resp.content) > 100:
            return resp.content
    except Exception:
        pass
    return None


SCIENCE_CONFIG = {
    "grad-students": {
        "files": ["Kadry_VO.xls"],
        "parser": "kadry",
        "sheet_idx": 1,
    },
    "doctoral-students": {
        "files": ["Kadry_VO.xls"],
        "parser": "kadry",
        "sheet_idx": 4,
    },
    "rd-organizations": {
        "files": ["Nauka_1.xls"],
        "parser": "nauka_total",
    },
    "rd-personnel": {
        "files": ["nauka_2.xls"],
        "parser": "nauka_total",
    },
    "innovation-activity": {
        "files": [f"innov_1_{y}.xls" for y in range(2026, 2020, -1)],
        "parser": "innov_russia",
    },
    "tech-innovation-share": {
        "files": [f"innov_2_{y}.xls" for y in range(2026, 2020, -1)],
        "parser": "innov_russia",
    },
    "small-business-innovation": {
        "files": ["innov-mp_1.xls"],
        "parser": "innov_russia",
        "sheet": "5",
    },
}


class RosstatScienceParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_science"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        cfg = indicator.model_config_json or {}
        sci_cfg = cfg.get("science_config") or SCIENCE_CONFIG.get(code)
        if not sci_cfg:
            raise ValueError(f"No science config for {code}")

        session = create_session()
        session.verify = settings.rosstat_ca_cert
        content = None
        used_file = ""
        for fn in sci_cfg["files"]:
            content = _try_download_xls(session, fn)
            if content:
                used_file = fn
                break

        if not content:
            raise ValueError(f"Science XLS not found for {code}: {sci_cfg['files']}")

        fetch_log.source_url = BASE_URL + used_file
        parser_type = sci_cfg.get("parser", "nauka_total")

        if parser_type == "kadry":
            sheet_idx = sci_cfg.get("sheet_idx", 0)
            points = parse_kadry_xls(content, sheet_idx)
        elif parser_type == "nauka_total":
            sheet = sci_cfg.get("sheet", "1")
            points = parse_nauka_total_xls(content, sheet)
        elif parser_type == "innov_russia":
            sheet = sci_cfg.get("sheet", "1")
            points = parse_innov_russia_xls(content, sheet)
        else:
            raise ValueError(f"Unknown science parser: {parser_type}")

        if not points:
            fetch_log.status = "no_new_data"
            fetch_log.records_added = 0
            fetch_log.completed_at = datetime.utcnow()
            await db.commit()
            return

        for p in points:
            await db.execute(upsert_indicator_data(indicator.id, p.date, p.value))
        await db.flush()

        fetch_log.status = "success"
        fetch_log.records_added = len(points)
        fetch_log.completed_at = datetime.utcnow()
        await db.commit()
        logger.info("%s: upserted %d points from %s", code, len(points), used_file)
