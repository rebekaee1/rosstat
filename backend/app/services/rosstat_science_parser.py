"""
Parsers for Rosstat Science & Education indicators (.xls files).

Catalog pages (устойчивый discovery имён файлов):
  - https://rosstat.gov.ru/statistics/science — наука и инновации
    * Nauka_1.xls — число организаций, выполнявших НИР
    * nauka_2.xls — численность персонала, занятого НИР
    * innov_1_{YYYY}.xls — уровень инновационной активности
    * innov_2_{YYYY}.xls — удельный вес организаций с технологическими инновациями
    * Innov_mp_1.xls (ранее innov-mp_1.xls) — инновации малых предприятий
  - https://rosstat.gov.ru/statistics/education — образование
    * Kadry-VO.xls (ранее Kadry_VO.xls) — аспиранты / докторанты

Fallback: прямые probe-имена, если страница раздела временно недоступна.
Методологический пол инноваций (Осло 3→4): min_year=2018 в SCIENCE_CONFIG.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar

import xlrd
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Indicator, FetchLog
from app.services.base_parser import BaseParser
from app.services.http_client import create_session
from app.services.rosstat_sdds_fetcher import resolve_mediabank_file

logger = logging.getLogger(__name__)

SCIENCE_CATALOG_URL = "https://rosstat.gov.ru/statistics/science"
EDUCATION_CATALOG_URL = "https://rosstat.gov.ru/statistics/education"
BASE_URL = "https://rosstat.gov.ru/storage/mediabank/"


@dataclass
class DataPoint:
    date: date
    value: float


def _to_float(val) -> float | None:
    if val is None or val == "":
        return None
    s = str(val).strip().replace("\u2212", "-").replace(",", ".").replace("\xa0", "").replace(" ", "")
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
    """Parse Kadry_VO / Kadry-VO.xls → total count from specified sheet.

    Structure: years vertical in col 0, total count in col 1.
    Sheet 1 = grad students, Sheet 4 = doctoral students.
    """
    wb = xlrd.open_workbook(file_contents=content)
    try:
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
    finally:
        wb.release_resources()

    return sorted(points, key=lambda p: p.date)


def parse_nauka_total_xls(content: bytes, sheet_name: str = "1") -> list[DataPoint]:
    """Parse Nauka_1.xls or nauka_2.xls → total from "всего" row."""
    wb = xlrd.open_workbook(file_contents=content)
    try:
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
            logger.warning(
                "Nauka: keyword row not found after row %d, falling back to row %d",
                year_row,
                year_row + 2,
            )
            total_row = year_row + 2

        points = []
        for col, year in years:
            if total_row < ws.nrows and col < ws.ncols:
                val = _to_float(ws.cell_value(total_row, col))
                if val is not None:
                    points.append(DataPoint(date=date(year, 1, 1), value=round(val, 2)))
    finally:
        wb.release_resources()

    return sorted(points, key=lambda p: p.date)


def parse_innov_russia_xls(content: bytes, sheet_name: str = "1") -> list[DataPoint]:
    """Parse innov_*.xls → Russia-level % from first data row after 'Российская Федерация'."""
    wb = xlrd.open_workbook(file_contents=content)
    try:
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
            logger.warning(
                "Innov: keyword row not found after row %d, falling back to row %d",
                year_row,
                year_row + 2,
            )
            russia_row = year_row + 2

        points = []
        for col, year in years:
            if russia_row < ws.nrows and col < ws.ncols:
                val = _to_float(ws.cell_value(russia_row, col))
                if val is not None:
                    points.append(DataPoint(date=date(year, 1, 1), value=round(val, 2)))
    finally:
        wb.release_resources()

    return sorted(points, key=lambda p: p.date)


def _year_fallbacks(template: str) -> list[str]:
    current_year = datetime.now().year
    return [template.format(y=y) for y in range(current_year + 1, current_year - 7, -1)]


SCIENCE_CONFIG = {
    "grad-students": {
        "catalog_urls": [EDUCATION_CATALOG_URL],
        "name_patterns": [r"(?i)Kadry[-_]VO\.xls"],
        "fallback_filenames": ["Kadry-VO.xls", "Kadry_VO.xls"],
        "parser": "kadry",
        "sheet_idx": 1,
    },
    "doctoral-students": {
        "catalog_urls": [EDUCATION_CATALOG_URL],
        "name_patterns": [r"(?i)Kadry[-_]VO\.xls"],
        "fallback_filenames": ["Kadry-VO.xls", "Kadry_VO.xls"],
        "parser": "kadry",
        "sheet_idx": 4,
    },
    "rd-organizations": {
        "catalog_urls": [SCIENCE_CATALOG_URL],
        "name_patterns": [r"(?i)Nauka_1\.xls"],
        "fallback_filenames": ["Nauka_1.xls"],
        "parser": "nauka_total",
    },
    "rd-personnel": {
        "catalog_urls": [SCIENCE_CATALOG_URL],
        "name_patterns": [r"(?i)nauka_2\.xls"],
        "fallback_filenames": ["nauka_2.xls"],
        "parser": "nauka_total",
    },
    # Методологический разрыв Росстата (Руководство Осло 3-я → 4-я редакция,
    # приказ № 788): с перерасчёта за 2017 показатели инноваций считаются по
    # новой методике и НЕсопоставимы со старым рядом (≤2016/2017 ~7-10%, новый
    # ~20-24% у tech-innovation). Старые значения за 2017 у нас остались по
    # 3-й редакции — обрезаем ряд до первого полного года новой методики (2018),
    # чтобы график не показывал ложный вертикальный «обрыв». См. data_sources.md.
    "innovation-activity": {
        "catalog_urls": [SCIENCE_CATALOG_URL],
        "name_patterns": [r"(?i)innov_1_(\d{4})\.xls"],
        "fallback_filenames_template": "innov_1_{y}.xls",
        "parser": "innov_russia",
        "min_year": 2018,
    },
    "tech-innovation-share": {
        "catalog_urls": [SCIENCE_CATALOG_URL],
        "name_patterns": [r"(?i)innov_2_(\d{4})\.xls"],
        "fallback_filenames_template": "innov_2_{y}.xls",
        "parser": "innov_russia",
        "min_year": 2018,
    },
    "small-business-innovation": {
        "catalog_urls": [SCIENCE_CATALOG_URL],
        "name_patterns": [r"(?i)Innov[_-]mp_1\.xls", r"(?i)innov-mp_1\.xls"],
        "fallback_filenames": ["Innov_mp_1.xls", "innov-mp_1.xls"],
        "parser": "innov_russia",
        "sheet": "5",
    },
}


class RosstatScienceParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_science"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        code = indicator.code
        sci_cfg = cfg.get("science_config") or SCIENCE_CONFIG.get(code)
        if not sci_cfg:
            raise ValueError(f"No science config for {code}")

        fallback = list(sci_cfg.get("fallback_filenames") or [])
        if not fallback and "fallback_filenames_template" in sci_cfg:
            fallback = _year_fallbacks(sci_cfg["fallback_filenames_template"])
        # legacy keys from older configs
        if not fallback and sci_cfg.get("files"):
            fallback = list(sci_cfg["files"])
        if not fallback and sci_cfg.get("files_template"):
            fallback = _year_fallbacks(sci_cfg["files_template"])

        catalog_urls = list(sci_cfg.get("catalog_urls") or [SCIENCE_CATALOG_URL])
        name_patterns = list(sci_cfg.get("name_patterns") or [])
        if not name_patterns and fallback:
            name_patterns = [re.escape(fallback[0])]

        session = create_session()
        try:
            session.verify = settings.rosstat_ca_cert
            content, used_url = resolve_mediabank_file(
                catalog_urls=catalog_urls,
                name_patterns=name_patterns,
                fallback_filenames=fallback,
                session=session,
            )
        finally:
            session.close()

        parser_kind = sci_cfg.get("parser", "nauka_total")
        if parser_kind == "kadry":
            points = parse_kadry_xls(content, sci_cfg.get("sheet_idx", 0))
        elif parser_kind == "nauka_total":
            points = parse_nauka_total_xls(content, sci_cfg.get("sheet", "1"))
        elif parser_kind == "innov_russia":
            points = parse_innov_russia_xls(content, sci_cfg.get("sheet", "1"))
        else:
            raise ValueError(f"Unknown science parser: {parser_kind}")

        min_year = sci_cfg.get("min_year")
        if min_year:
            points = [p for p in points if p.date.year >= min_year]

        return points, used_url

    def _validate(self, points: list, cfg: dict) -> list:
        valid = [
            p for p in points
            if isinstance(p.value, (int, float)) and not math.isnan(p.value)
        ]
        if len(valid) < len(points):
            logger.warning(
                "Filtered out %d invalid (NaN/non-numeric) science values",
                len(points) - len(valid),
            )
        return valid
