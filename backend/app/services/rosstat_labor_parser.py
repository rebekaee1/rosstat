"""ETL: Росстат SDDS Labor Market XLSX → IndicatorData.

Файл: SDDS_labor market_{year}.xlsx
Лист: "labor market"
Строки:
  Row 1: заголовки дат (MM.YYYY)
  Row 2: Economically active population (mln)
  Row 3: Employed (mln)
  Row 4: Unemployed (mln)
  Row 5: Unemployed, officially registered (mln)
  Row 6: Average monthly accrued wages (rubles)

Индикаторы:
  unemployment — rate = row4 / row2 * 100
  wages-nominal — row6 (прямое значение в рублях)
"""

from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
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


@dataclass
class DataPoint:
    date: date
    value: float


ROW_LABELS: dict[str, int] = {
    "active": 2,
    "employed": 3,
    "unemployed": 4,
    "unemployed_registered": 5,
    "wages": 6,
}


def _parse_header_date(header: str) -> date | None:
    """Parse 'MM.YYYY' header to first-of-month date."""
    if not header or not isinstance(header, str):
        return None
    parts = header.strip().split(".")
    if len(parts) != 2:
        return None
    try:
        month, year = int(parts[0]), int(parts[1])
        if 1 <= month <= 12 and 1990 <= year <= 2100:
            return date(year, month, 1)
    except (ValueError, TypeError):
        pass
    return None


def parse_labor_xlsx(content: bytes) -> dict[str, list[DataPoint]]:
    """Parse SDDS labor market XLSX.

    Returns dict with keys: 'unemployment_rate', 'wages_nominal',
    'labor_force', 'employment'.
    """
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = wb.worksheets[0]

    rows_data: list[list] = []
    for row in ws.iter_rows(values_only=True):
        rows_data.append(list(row))
    wb.close()

    if len(rows_data) < 6:
        raise ValueError(f"Labor XLSX: expected >=6 rows, got {len(rows_data)}")

    dates: list[tuple[int, date]] = []
    for col_idx in range(2, len(rows_data[0])):
        header = rows_data[0][col_idx]
        d = _parse_header_date(str(header) if header else "")
        if d:
            dates.append((col_idx, d))

    if not dates:
        raise ValueError("Labor XLSX: no valid date headers found")

    unemployment_rate: list[DataPoint] = []
    wages_nominal: list[DataPoint] = []
    labor_force: list[DataPoint] = []
    employment: list[DataPoint] = []

    active_row = rows_data[ROW_LABELS["active"] - 1]
    employed_row = rows_data[ROW_LABELS["employed"] - 1]
    unemployed_row = rows_data[ROW_LABELS["unemployed"] - 1]
    wages_row = rows_data[ROW_LABELS["wages"] - 1]

    for col_idx, d in dates:
        active_val = active_row[col_idx] if col_idx < len(active_row) else None
        employed_val = employed_row[col_idx] if col_idx < len(employed_row) else None
        unemp_val = unemployed_row[col_idx] if col_idx < len(unemployed_row) else None

        if active_val is not None:
            try:
                active_f = float(active_val)
                labor_force.append(DataPoint(date=d, value=round(active_f, 2)))
                if unemp_val is not None:
                    unemp_f = float(unemp_val)
                    if active_f > 0:
                        rate = round(unemp_f / active_f * 100, 2)
                        unemployment_rate.append(DataPoint(date=d, value=rate))
            except (ValueError, TypeError):
                pass

        if employed_val is not None:
            try:
                employment.append(DataPoint(date=d, value=round(float(employed_val), 2)))
            except (ValueError, TypeError):
                pass

        wage_val = wages_row[col_idx] if col_idx < len(wages_row) else None
        if wage_val is not None:
            try:
                wages_nominal.append(DataPoint(date=d, value=round(float(wage_val), 2)))
            except (ValueError, TypeError):
                pass

    return {
        "unemployment_rate": sorted(unemployment_rate, key=lambda p: p.date),
        "wages_nominal": sorted(wages_nominal, key=lambda p: p.date),
        "labor_force": sorted(labor_force, key=lambda p: p.date),
        "employment": sorted(employment, key=lambda p: p.date),
    }


INDICATOR_SERIES_MAP: dict[str, str] = {
    "unemployment": "unemployment_rate",
    "wages-nominal": "wages_nominal",
    "labor-force": "labor_force",
    "employment": "employment",
}


class RosstatLaborParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_sdds_labor"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            content, final_url = await asyncio.to_thread(fetch_sdds_xlsx, "labor")
            fetch_log.source_url = final_url[:500]

            all_series = await asyncio.to_thread(parse_labor_xlsx, content)

            series_key = INDICATOR_SERIES_MAP.get(code)
            if not series_key:
                fetch_log.status = "failed"
                fetch_log.error_message = f"No series mapping for '{code}'"
                fetch_log.completed_at = datetime.utcnow()
                await db.commit()
                return

            points = all_series.get(series_key, [])

            cfg = indicator.model_config_json or {}
            points = validate_points(points, cfg)

            if not points:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "Parser returned 0 data points"
                fetch_log.completed_at = datetime.utcnow()
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
            logger.info("Labor '%s': +%d rows (total %d)", code, records_added, count_after)

            steps = int(cfg.get("forecast_steps", 0) or 0)
            if steps > 0 and records_added > 0:
                await retrain_indicator_forecast(db, indicator)

            if records_added > 0:
                await cache_invalidate_indicator(code)

            fetch_log.status = "success" if records_added > 0 else "no_new_data"
            fetch_log.completed_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            logger.exception("ETL failed for '%s'", code)
            fetch_log.status = "failed"
            fetch_log.error_message = str(e)[:500]
            fetch_log.completed_at = datetime.utcnow()
            await db.commit()
