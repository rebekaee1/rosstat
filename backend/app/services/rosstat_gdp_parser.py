"""ETL: Росстат SDDS National Accounts XLSX → IndicatorData.

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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.upsert import upsert_indicator_data
from app.services.data_validator import validate_points
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.services.rosstat_sdds_fetcher import fetch_sdds_xlsx
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

_Q_RE = re.compile(r"^Q(\d)-(\d{4})")


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


class RosstatGdpParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_sdds_gdp"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            content, final_url = await asyncio.to_thread(fetch_sdds_xlsx, "gdp")
            fetch_log.source_url = final_url[:500]

            cfg = indicator.model_config_json or {}
            row_index = int(cfg.get("gdp_row_index", 2))
            points = await asyncio.to_thread(parse_gdp_xlsx, content, row_index)

            points = validate_points(points, cfg)

            if not points:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "Parser returned 0 data points"
                fetch_log.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            count_before = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            for p in points:
                await db.execute(upsert_indicator_data(indicator.id, p.date, p.value))

            await db.flush()
            count_after = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            records_added = count_after - count_before
            fetch_log.records_added = records_added
            logger.info("GDP '%s': +%d rows (total %d)", code, records_added, count_after)

            steps = int(cfg.get("forecast_steps", 0) or 0)
            if steps > 0 and records_added > 0:
                await retrain_indicator_forecast(db, indicator)

            if records_added > 0:
                await cache_invalidate_indicator(code)

            fetch_log.status = "success" if records_added > 0 else "no_new_data"
            fetch_log.completed_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            logger.exception("ETL failed for '%s'", code)
            await db.rollback()
            fetch_log.status = "failed"
            fetch_log.error_message = str(e)[:500]
            fetch_log.completed_at = datetime.now(timezone.utc)
            db.add(fetch_log)
            await db.commit()
