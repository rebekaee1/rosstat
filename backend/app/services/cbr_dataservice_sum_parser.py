"""ETL: CBR DataService aggregate parser — sums multiple DataService elements by date.

Used for indicators composed of several monetary components (e.g. total
individual deposits = transferable + term + FX deposits).

Config in indicator.model_config_json:
{
  "dataservice_components": [
    {"publicationId": 5, "datasetId": 6, "element_id": 16, "date_offset_months": 0},
    {"publicationId": 5, "datasetId": 7, "element_id": 22, "date_offset_months": 0},
    {"publicationId": 5, "datasetId": 8, "element_id": 26, "date_offset_months": 0},
  ],
  "backfill_from_year": 2010
}
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date, datetime
from typing import ClassVar

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.cbr_dataservice_parser import fetch_dataservice
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)


class CbrDataServiceSumParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_dataservice_sum"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            cfg = indicator.model_config_json or {}
            components = cfg.get("dataservice_components")
            if not components or not isinstance(components, list):
                fetch_log.status = "failed"
                fetch_log.error_message = "Missing 'dataservice_components' in model_config_json"
                fetch_log.completed_at = datetime.utcnow()
                await db.commit()
                return

            year_from = int(cfg.get("backfill_from_year", 2010))
            year_to = date.today().year

            sums: dict[date, float] = defaultdict(float)
            for comp in components:
                date_offset = int(comp.get("date_offset_months", 0))
                points = await asyncio.to_thread(
                    fetch_dataservice,
                    comp["publicationId"],
                    comp["datasetId"],
                    comp.get("measureId"),
                    comp.get("element_id"),
                    year_from,
                    year_to,
                    date_offset,
                )
                for dt, val in points:
                    sums[dt] += val

            fetch_log.source_url = f"cbr.ru/dataservice (sum of {len(components)} components)"

            if not sums:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "DataService returned 0 matching rows across components"
                fetch_log.completed_at = datetime.utcnow()
                await db.commit()
                return

            count_before = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            for dt in sorted(sums):
                stmt = (
                    pg_insert(IndicatorData)
                    .values(indicator_id=indicator.id, date=dt, value=round(sums[dt], 2))
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
            logger.info("DataServiceSum '%s': +%d rows (total %d)", code, records_added, count_after)

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
