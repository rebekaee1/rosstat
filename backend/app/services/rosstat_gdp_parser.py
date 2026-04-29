"""ETL: Росстат National Accounts XLSX → IndicatorData.

Файл: SDDS national accounts_{year}.xlsx
Лист: "National Accounts"
Строки (0-indexed in code, 1-indexed in XLSX):
  Row 1: заголовки кварталов (Qn-YYYY или Qn-YYYY**)
  Row 3: GDP in current prices (billion rubles)
  Row 4: Final consumption
  Row 5: Household consumption expenditure
  Row 6: Government consumption expenditure
  Row 9: Gross fixed capital formation
  Row 12: Exports of goods and services
  Row 13: Imports of goods and services

Индикаторы:
  gdp-nominal        — row 3 (gdp_row_index=2)
  gdp-consumption    — row 5 (gdp_row_index=4)
  gdp-government     — row 6 (gdp_row_index=5)
  gdp-investment     — row 9 (gdp_row_index=8)

Файл: VVP_kvartal_s_1995-2025.xlsx (rosstat.gov.ru)
  gdp-real           — sheet 9, GDP at 2021 constant prices
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import ClassVar

import openpyxl
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.upsert import bulk_upsert
from app.services.data_validator import validate_points
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.services.rosstat_sdds_fetcher import fetch_sdds_xlsx, fetch_rosstat_static_xlsx
from app.core.cache import cache_invalidate_indicator

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


class RosstatGdpParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_sdds_gdp"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            cfg = indicator.model_config_json or {}
            if cfg.get("gdp_source") == "official_quarterly":
                content, final_url = await asyncio.to_thread(fetch_rosstat_static_xlsx, "gdp_quarterly")
                fetch_log.source_url = final_url[:500]
                sheet_name = str(cfg.get("gdp_sheet", "9"))
                points = await asyncio.to_thread(parse_rosstat_gdp_quarter_grid_xlsx, content, sheet_name)
            else:
                content, final_url = await asyncio.to_thread(fetch_sdds_xlsx, "gdp")
                fetch_log.source_url = final_url[:500]
                row_index = int(cfg.get("gdp_row_index", 2))
                points = await asyncio.to_thread(parse_gdp_xlsx, content, row_index)

            points = validate_points(points, cfg)

            if not points:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "Parser returned 0 data points"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.commit()
                return

            records_added, records_updated = await bulk_upsert(db, indicator.id, points)
            logger.info(
                "Upserted %d new, %d updated for '%s'",
                records_added, records_updated, code,
            )
            fetch_log.records_added = records_added

            steps = int(cfg.get("forecast_steps", 0) or 0)
            if steps > 0 and (records_added > 0 or records_updated > 0):
                await retrain_indicator_forecast(db, indicator)

            if records_added > 0 or records_updated > 0:
                await cache_invalidate_indicator(code)

            fetch_log.status = "success" if (records_added > 0 or records_updated > 0) else "no_new_data"
            fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()

        except Exception as e:
            logger.exception("ETL failed for '%s'", code)
            await db.rollback()
            fetch_log.status = "failed"
            fetch_log.error_message = str(e)[:500]
            fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(fetch_log)
            await db.commit()
