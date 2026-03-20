"""
ETL scheduler: daily check for new Rosstat data.
On new data: parse, upsert to DB, retrain forecast, invalidate cache.
"""

import logging
from datetime import datetime

from sqlalchemy import select

from app.database import async_session
from app.models import Indicator, FetchLog
from app.services.rosstat_cpi_parser import get_parser

logger = logging.getLogger(__name__)


async def run_etl_for_indicator(indicator_code: str):
    """Полный ETL для одного индикатора через PARSER_REGISTRY."""
    async with async_session() as db:
        ind_q = await db.execute(select(Indicator).where(Indicator.code == indicator_code))
        indicator = ind_q.scalar_one_or_none()
        if not indicator:
            logger.error("Indicator '%s' not found", indicator_code)
            return

        parser = get_parser(indicator.parser_type)
        if not parser:
            logger.error("Unknown parser_type '%s' for '%s'", indicator.parser_type, indicator_code)
            return

        started_at = datetime.utcnow()
        fetch_log = FetchLog(indicator_id=indicator.id, status="running", started_at=started_at)
        db.add(fetch_log)
        await db.flush()

        await parser.run(db, indicator, fetch_log)


async def daily_update_job():
    """Плановая задача: обновить все активные индикаторы."""
    logger.info("Starting daily ETL update...")

    async with async_session() as db:
        active_q = await db.execute(
            select(Indicator).where(Indicator.is_active.is_(True))
        )
        active_indicators = active_q.scalars().all()

    for indicator in active_indicators:
        try:
            await run_etl_for_indicator(indicator.code)
        except Exception:
            logger.exception("Failed to update indicator '%s'", indicator.code)

    logger.info("Daily ETL update complete.")
