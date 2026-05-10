"""ETL: Росстат National Accounts → IndicatorData.

Три источника, выбираются через `model_config_json.gdp_source`:

1. SDDS (default, deprecated по ADR-0004) — `gdp_source` отсутствует:
   Файл `SDDS national accounts_{year}.xlsx`, лист "National Accounts".
   row_index (0-based): 2 = GDP nominal, 4 = consumption, 5 = government, 8 = investment.

2. `gdp_source: "official_quarterly"` — `VVP_kvartal_s_1995-2025.xlsx` (rosstat.gov.ru):
   Quarter-grid layout (years row 2, quarters row 3, single value row 4).
   `gdp_sheet`: "2" = nominal current prices ОКВЭД2 (2011+),
                "9" = real в ценах 2021 г. (2011+).

3. `gdp_source: "official_use"` — `GDP-quarters-of-use-1995-4kv-2025.xls` (rosstat.gov.ru):
   Quarter-grid layout, multi-row (стек индикаторов на одном sheet).
   `gdp_sheet`: "1" = ОКВЭД2007 (1995-2010), "2" = ОКВЭД2 (2011+).
   `gdp_row_index` (0-based): 4 = ВВП, 7 = домохозяйства, 8 = госуправление, 11 = GFCF.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

import openpyxl
import xlrd
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.data_validator import validate_points
from app.services.rosstat_sdds_fetcher import fetch_sdds_xlsx, fetch_rosstat_static_xlsx

logger = logging.getLogger(__name__)

_Q_RE = re.compile(r"^Q(\d)-(\d{4})")
_YEAR_RE = re.compile(r"(\d{4})")


@dataclass
class DataPoint:
    date: date
    value: float


QUARTER_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}


def _parse_quarter_header(header: str) -> date | None:
    """Parse 'Q1-2011' or 'Q3-2025**' to end-of-quarter date."""
    if not header or not isinstance(header, str):
        return None
    m = _Q_RE.match(header.strip())
    if not m:
        return None
    q, y = int(m.group(1)), int(m.group(2))
    if 1 <= q <= 4 and 1990 <= y <= 2100:
        return date(y, QUARTER_MONTH[q], 1)
    return None


def _extract_year(cell) -> int | None:
    if cell is None:
        return None
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        year = int(cell)
    else:
        m = _YEAR_RE.match(str(cell).strip())
        if not m:
            return None
        year = int(m.group(1))
    return year if 1990 <= year <= 2100 else None


def parse_gdp_xlsx(content: bytes, row_index: int = 2) -> list[DataPoint]:
    """Parse SDDS national accounts XLSX → list of data points.

    row_index: 0-based index of the data row to extract.
    Default 2 = Row 3 (GDP nominal).
    """
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        ws = wb.worksheets[0]
        rows_data: list[list] = []
        for row in ws.iter_rows(values_only=True):
            rows_data.append(list(row))
    finally:
        wb.close()

    if len(rows_data) <= row_index:
        raise ValueError(f"GDP XLSX: expected >={row_index + 1} rows, got {len(rows_data)}")

    dates: list[tuple[int, date]] = []
    for col_idx in range(2, len(rows_data[0])):
        header = rows_data[0][col_idx]
        d = _parse_quarter_header(str(header) if header else "")
        if d:
            dates.append((col_idx, d))

    if not dates:
        raise ValueError("GDP XLSX: no valid quarter headers found")

    data_row = rows_data[row_index]
    points: list[DataPoint] = []

    for col_idx, d in dates:
        val = data_row[col_idx] if col_idx < len(data_row) else None
        if val is not None:
            try:
                points.append(DataPoint(date=d, value=round(float(val), 1)))
            except (ValueError, TypeError):
                pass

    points.sort(key=lambda p: p.date)
    return points


_QUARTER_NAME_TO_MONTH = {
    "i квартал": 3,
    "ii квартал": 6,
    "iii квартал": 9,
    "iv квартал": 12,
}


def parse_rosstat_gdp_quarter_grid_xlsx(content: bytes, sheet_name: str = "9") -> list[DataPoint]:
    """Parse official Rosstat GDP quarter grid.

    The Russian accounts file has years in row 3, quarters in row 4, values in row 5.
    Sheet 9 is GDP in 2021 constant prices, billion rubles.
    """
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        ws = wb[sheet_name]
        rows_data = [list(row) for row in ws.iter_rows(values_only=True)]
    finally:
        wb.close()

    if len(rows_data) < 5:
        raise ValueError(f"GDP official XLSX sheet {sheet_name}: expected >=5 rows, got {len(rows_data)}")

    year_row = rows_data[2]
    quarter_row = rows_data[3]
    value_row = rows_data[4]

    points: list[DataPoint] = []
    current_year: int | None = None
    for idx, quarter_cell in enumerate(quarter_row):
        maybe_year = _extract_year(year_row[idx] if idx < len(year_row) else None)
        if maybe_year is not None:
            current_year = maybe_year

        if current_year is None:
            continue

        quarter = str(quarter_cell or "").strip().lower()
        month = _QUARTER_NAME_TO_MONTH.get(quarter)
        if month is None:
            continue

        val = value_row[idx] if idx < len(value_row) else None
        if val is None:
            continue
        try:
            points.append(DataPoint(date=date(current_year, month, 1), value=round(float(val), 1)))
        except (ValueError, TypeError):
            pass

    points.sort(key=lambda p: p.date)
    return points


def parse_rosstat_gdp_use_xls(
    content: bytes,
    sheet_name: str = "2",
    value_row_index: int = 4,
) -> list[DataPoint]:
    """Parse legacy .xls `GDP-quarters-of-use-*.xls` (rosstat.gov.ru/statistics/accounts).

    Same year/quarter grid as `parse_rosstat_gdp_quarter_grid_xlsx` but the file is
    OLE2 binary (xlrd, not openpyxl) and the sheet hosts multiple stacked indicators
    (ВВП, конечное потребление, домохозяйства, госуправление, GFCF) — caller selects
    via `value_row_index` (0-based).

    Sheets: "1" = ОКВЭД2007 1995-2010 (methodology break vs sheet 2),
            "2" = ОКВЭД2 2011+ (current canonical for our 2011-onwards series).
    """
    wb = xlrd.open_workbook(file_contents=content)
    ws = wb.sheet_by_name(sheet_name)

    if ws.nrows <= max(4, value_row_index):
        raise ValueError(
            f"GDP use XLS sheet {sheet_name}: expected >= {value_row_index + 1} rows, got {ws.nrows}"
        )

    year_row = ws.row_values(2)
    quarter_row = ws.row_values(3)
    value_row = ws.row_values(value_row_index)

    points: list[DataPoint] = []
    current_year: int | None = None
    for idx, qcell in enumerate(quarter_row):
        maybe_year = _extract_year(year_row[idx] if idx < len(year_row) else None)
        if maybe_year is not None:
            current_year = maybe_year

        if current_year is None:
            continue

        quarter = str(qcell or "").strip().lower()
        month = _QUARTER_NAME_TO_MONTH.get(quarter)
        if month is None:
            continue

        val = value_row[idx] if idx < len(value_row) else None
        if val in (None, ""):
            continue
        try:
            points.append(DataPoint(date=date(current_year, month, 1), value=round(float(val), 1)))
        except (ValueError, TypeError):
            pass

    points.sort(key=lambda p: p.date)
    return points


class RosstatGdpParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_sdds_gdp"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        gdp_source = cfg.get("gdp_source")
        if gdp_source == "official_quarterly":
            content, final_url = await asyncio.to_thread(fetch_rosstat_static_xlsx, "gdp_quarterly")
            sheet_name = str(cfg.get("gdp_sheet", "9"))
            points = await asyncio.to_thread(parse_rosstat_gdp_quarter_grid_xlsx, content, sheet_name)
        elif gdp_source == "official_use":
            content, final_url = await asyncio.to_thread(fetch_rosstat_static_xlsx, "gdp_use_quarterly")
            sheet_name = str(cfg.get("gdp_sheet", "2"))
            row_index = int(cfg.get("gdp_row_index", 4))
            points = await asyncio.to_thread(parse_rosstat_gdp_use_xls, content, sheet_name, row_index)
        else:
            content, final_url = await asyncio.to_thread(fetch_sdds_xlsx, "gdp")
            row_index = int(cfg.get("gdp_row_index", 2))
            points = await asyncio.to_thread(parse_gdp_xlsx, content, row_index)
        return points, final_url

    def _validate(self, points: list, cfg: dict) -> list:
        return validate_points(points, cfg)
