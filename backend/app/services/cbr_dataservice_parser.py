"""ETL: универсальный парсер REST API CBR DataService → IndicatorData.

Подходит для:
- Ипотечные ставки (publicationId=14, datasetId=29, element_id=36)
- Автокредиты (publicationId=14, datasetId=28, measureId=2, element_id=11)
- Ставки по депозитам ФЛ (publicationId=18, datasetId=37, measureId=2, element_id=7)

Конфигурация хранится в indicator.model_config_json:
{
  "dataservice": {
    "publicationId": 14,
    "datasetId": 29,
    "measureId": null,
    "element_id": 36
  },
  "backfill_from_year": 2017
}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import ClassVar

import requests
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

CBR_DATASERVICE_URL = "http://www.cbr.ru/dataservice/data"

MONTH_MAP = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}


def _parse_ds_date(dt_str: str, iso_date: str | None, date_offset_months: int = -1) -> date | None:
    """Parse date from DataService response.

    date_offset_months: -1 for rate data (Feb = data for Jan), 0 for monetary (date is actual).
    """
    if iso_date:
        try:
            d = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            y, m = d.year, d.month
            m += date_offset_months
            while m <= 0:
                m += 12
                y -= 1
            while m > 12:
                m -= 12
                y += 1
            return date(y, m, 1)
        except (ValueError, TypeError):
            pass
    if dt_str:
        trimmed = dt_str.strip()
        parts = trimmed.lower().split()
        if len(parts) == 2:
            month_name, year_str = parts
            month = MONTH_MAP.get(month_name)
            if month:
                try:
                    return date(int(year_str), month, 1)
                except (ValueError, TypeError):
                    pass
        # DD.MM.YYYY format
        dot_parts = trimmed.split(".")
        if len(dot_parts) == 3:
            try:
                dd, mm, yy = int(dot_parts[0]), int(dot_parts[1]), int(dot_parts[2])
                return date(yy, mm, dd)
            except (ValueError, TypeError):
                pass
    return None


def fetch_dataservice(
    publication_id: int, dataset_id: int,
    measure_id: int | None, element_id: int | None,
    year_from: int, year_to: int,
    date_offset_months: int = -1,
) -> list[tuple[date, float]]:
    """Fetch from CBR DataService REST API."""
    params: dict = {
        "publicationId": publication_id,
        "datasetId": dataset_id,
        "y1": year_from,
        "y2": year_to,
    }
    if measure_id is not None:
        params["measureId"] = measure_id

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)",
        "Accept": "application/json",
    })
    resp = session.get(CBR_DATASERVICE_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    raw_data = data.get("RawData") or []
    results: list[tuple[date, float]] = []
    for row in raw_data:
        if element_id is not None:
            eid = row.get("element_id") or row.get("colId")
            if eid != element_id:
                continue
        val = row.get("obs_val")
        if val is None:
            continue
        dt = _parse_ds_date(row.get("dt", ""), row.get("date"), date_offset_months)
        if dt:
            results.append((dt, round(float(val), 4)))

    results.sort(key=lambda x: x[0])
    by_date: dict[date, float] = {}
    for d, v in results:
        by_date[d] = v
    return sorted(by_date.items())


class CbrDataServiceParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_dataservice_json"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            cfg = indicator.model_config_json or {}
            ds_cfg = cfg.get("dataservice")
            if not ds_cfg:
                fetch_log.status = "failed"
                fetch_log.error_message = "Missing 'dataservice' in model_config_json"
                fetch_log.completed_at = datetime.utcnow()
                await db.commit()
                return

            pub_id = ds_cfg["publicationId"]
            ds_id = ds_cfg["datasetId"]
            measure_id = ds_cfg.get("measureId")
            element_id = ds_cfg.get("element_id")
            date_offset = int(ds_cfg.get("date_offset_months", -1))
            year_from = int(cfg.get("backfill_from_year", 2017))
            year_to = date.today().year

            points = await asyncio.to_thread(
                fetch_dataservice, pub_id, ds_id, measure_id, element_id, year_from, year_to, date_offset,
            )
            fetch_log.source_url = f"cbr.ru/dataservice/data?pub={pub_id}&ds={ds_id}&el={element_id}"

            if not points:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "DataService returned 0 matching rows"
                fetch_log.completed_at = datetime.utcnow()
                await db.commit()
                return

            value_divisor = float(cfg.get("value_divisor", 1))

            count_before = (await db.execute(
                select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            for dt, val in points:
                stored_val = round(val / value_divisor, 4) if value_divisor != 1 else val
                stmt = (
                    pg_insert(IndicatorData)
                    .values(indicator_id=indicator.id, date=dt, value=stored_val)
                    .on_conflict_do_nothing(constraint="uq_indicator_date")
                )
                await db.execute(stmt)

            await db.flush()
            count_after = (await db.execute(
                select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            records_added = count_after - count_before
            fetch_log.records_added = records_added
            logger.info("DataService '%s': +%d rows (total %d)", code, records_added, count_after)

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
