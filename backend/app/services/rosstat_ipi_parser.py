"""ETL: Росстат SDDS Industrial Production Index XLSX → IndicatorData.

Файл: SDDS_industrial production index_{year}.xlsx
Лист: "IPI"
Строки:
  Row 1: заголовки дат (MM.YYYY)
  Row 2: Industrial Production Index (2023=100)
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
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.data_validator import validate_points
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.services.rosstat_sdds_fetcher import fetch_sdds_xlsx
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    date: date
    value: float


def _parse_header_date(header: str) -> date | None:
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


def parse_ipi_xlsx(content: bytes) -> list[DataPoint]:
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = wb.worksheets[0]

    rows_data: list[list] = []
    for row in ws.iter_rows(values_only=True):
        rows_data.append(list(row))
    wb.close()

    if len(rows_data) < 2:
        raise ValueError(f"IPI XLSX: expected >=2 rows, got {len(rows_data)}")

    dates: list[tuple[int, date]] = []
    for col_idx in range(2, len(rows_data[0])):
        header = rows_data[0][col_idx]
        d = _parse_header_date(str(header) if header else "")
        if d:
            dates.append((col_idx, d))

    if not dates:
        raise ValueError("IPI XLSX: no valid date headers found")

    ipi_row = rows_data[1]
    points: list[DataPoint] = []
    for col_idx, d in dates:
        val = ipi_row[col_idx] if col_idx < len(ipi_row) else None
        if val is not None:
            try:
                points.append(DataPoint(date=d, value=round(float(val), 2)))
            except (ValueError, TypeError):
                pass

    points.sort(key=lambda p: p.date)
    return points


class RosstatIpiParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_sdds_ipi"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            content, final_url = await asyncio.to_thread(fetch_sdds_xlsx, "ipi")
            fetch_log.source_url = final_url[:500]

            points = await asyncio.to_thread(parse_ipi_xlsx, content)

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
                stmt = (
                    pg_insert(IndicatorData)
                    .values(indicator_id=indicator.id, date=p.date, value=p.value)
                    .on_conflict_do_nothing(constraint="uq_indicator_date")
                )
                await db.execute(stmt)

            await db.flush()
            count_after = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            records_added = count_after - count_before
            fetch_log.records_added = records_added
            logger.info("IPI '%s': +%d rows (total %d)", code, records_added, count_after)

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
