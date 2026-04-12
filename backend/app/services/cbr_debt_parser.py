"""ETL: ЦБ РФ — внешний долг (debt_new.xlsx) → IndicatorData.

Источник: https://www.cbr.ru/vfs/statistics/credit_statistics/debt/debt_new.xlsx
Лист «2003-2026»:
  Row 4: даты (datetime) — квартальные, 2003-01-01, 2003-04-01, …
  Row 5: Всего (млн $)
"""

from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import ClassVar

import openpyxl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.http_client import create_session
from app.services.upsert import upsert_indicator_data
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

DEBT_URL = "https://www.cbr.ru/vfs/statistics/credit_statistics/debt/debt_new.xlsx"


@dataclass
class DataPoint:
    date: date
    value: float


def fetch_debt_xlsx() -> tuple[bytes, str]:
    session = create_session()
    try:
        resp = session.get(DEBT_URL, timeout=90)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "").lower()
        if "spreadsheet" not in ct and "openxml" not in ct and resp.status_code == 200:
            logger.warning("Debt unexpected content-type: %s", resp.headers.get("content-type"))
        if resp.content[:4] != b"PK\x03\x04":
            raise ValueError("Debt response is not XLSX")
        logger.info("Downloaded debt XLSX: %d KB", len(resp.content) // 1024)
        return resp.content, DEBT_URL
    finally:
        session.close()


def parse_debt_xlsx(content: bytes) -> list[DataPoint]:
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        ws = wb.worksheets[0]

        rows_data: list[list] = []
        for row in ws.iter_rows(values_only=True):
            rows_data.append(list(row))
    finally:
        wb.close()

    if len(rows_data) < 5:
        raise ValueError(f"Debt XLSX: expected >=5 rows, got {len(rows_data)}")

    date_row_idx = None
    for ri in range(min(10, len(rows_data))):
        for ci in range(1, min(5, len(rows_data[ri]))):
            val = rows_data[ri][ci]
            if isinstance(val, datetime):
                date_row_idx = ri
                break
        if date_row_idx is not None:
            break

    if date_row_idx is None:
        raise ValueError("Debt XLSX: no date row found")

    dates: list[tuple[int, date]] = []
    for ci in range(1, len(rows_data[date_row_idx])):
        val = rows_data[date_row_idx][ci]
        if isinstance(val, datetime):
            dates.append((ci, val.date()))
        elif isinstance(val, date):
            dates.append((ci, val))

    if not dates:
        raise ValueError("Debt XLSX: no valid dates")

    total_row_idx = None
    for i in range(date_row_idx + 1, min(date_row_idx + 5, len(rows_data))):
        cell = str(rows_data[i][0] or "").strip().lower()
        if "всего" in cell:
            total_row_idx = i
            break

    if total_row_idx is None:
        total_row_idx = date_row_idx + 1

    data_row = rows_data[total_row_idx]
    points: list[DataPoint] = []
    for ci, d in dates:
        val = data_row[ci] if ci < len(data_row) else None
        if val is not None:
            try:
                points.append(DataPoint(date=d, value=round(float(val), 2)))
            except (ValueError, TypeError):
                pass

    points.sort(key=lambda p: p.date)
    return points


class CbrDebtParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_debt_xlsx"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            content, final_url = await asyncio.to_thread(fetch_debt_xlsx)
            fetch_log.source_url = final_url[:500]

            points = await asyncio.to_thread(parse_debt_xlsx, content)

            cfg = indicator.model_config_json or {}

            if not points:
                logger.warning("No data points parsed for %s", code)
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "Debt parser returned 0 data points"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
            logger.info("Debt '%s': +%d rows (total %d)", code, records_added, count_after)

            steps = int(cfg.get("forecast_steps", 0) or 0)
            if steps > 0 and records_added > 0:
                await retrain_indicator_forecast(db, indicator)

            if records_added > 0:
                await cache_invalidate_indicator(code)

            fetch_log.status = "success" if records_added > 0 else "no_new_data"
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
