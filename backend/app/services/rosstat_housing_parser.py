"""ETL: Росстат SDDS Housing Market Price Indices XLSX → IndicatorData.

Файл: SDDS_housing market price indices_{year}_.xlsx
Лист: "Additional indicators"
Строки:
  Row 1: заголовки кварталов (Q1-YYYY)
  Row 2: Primary housing market price indices (2010=100)
  Row 3: Secondary housing market price indices (2010=100)
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
from app.services.rosstat_sdds_fetcher import fetch_sdds_xlsx
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

_Q_RE = re.compile(r"^Q(\d)-(\d{4})")
QUARTER_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}


@dataclass
class DataPoint:
    date: date
    value: float


def _parse_quarter_header(header: str) -> date | None:
    if not header or not isinstance(header, str):
        return None
    m = _Q_RE.match(header.strip())
    if not m:
        return None
    q, y = int(m.group(1)), int(m.group(2))
    if 1 <= q <= 4 and 1990 <= y <= 2100:
        return date(y, QUARTER_MONTH[q], 1)
    return None


INDICATOR_ROW_MAP: dict[str, int] = {
    "housing-price-primary": 1,
    "housing-price-secondary": 2,
}


def parse_housing_xlsx(content: bytes) -> dict[str, list[DataPoint]]:
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        ws = wb.worksheets[0]
        rows_data: list[list] = []
        for row in ws.iter_rows(values_only=True):
            rows_data.append(list(row))
    finally:
        wb.close()

    if len(rows_data) < 3:
        raise ValueError(f"Housing XLSX: expected >=3 rows, got {len(rows_data)}")

    dates: list[tuple[int, date]] = []
    for col_idx in range(2, len(rows_data[0])):
        header = rows_data[0][col_idx]
        d = _parse_quarter_header(str(header) if header else "")
        if d:
            dates.append((col_idx, d))

    if not dates:
        raise ValueError("Housing XLSX: no valid quarter headers found")

    result: dict[str, list[DataPoint]] = {}
    for series_key, row_idx in INDICATOR_ROW_MAP.items():
        data_row = rows_data[row_idx]
        points: list[DataPoint] = []
        for col_idx, d in dates:
            val = data_row[col_idx] if col_idx < len(data_row) else None
            if val is not None:
                try:
                    points.append(DataPoint(date=d, value=round(float(val), 2)))
                except (ValueError, TypeError):
                    pass
        result[series_key] = sorted(points, key=lambda p: p.date)

    return result


class RosstatHousingParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_sdds_housing"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            content, final_url = await asyncio.to_thread(fetch_sdds_xlsx, "housing")
            fetch_log.source_url = final_url[:500]

            all_series = await asyncio.to_thread(parse_housing_xlsx, content)

            series_key = code
            if series_key not in all_series:
                fetch_log.status = "failed"
                fetch_log.error_message = f"No series mapping for '{code}'"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.commit()
                return

            points = all_series[series_key]

            cfg = indicator.model_config_json or {}
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
