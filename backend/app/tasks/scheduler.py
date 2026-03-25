"""
ETL scheduler: ежедневный прогон **всех активных** индикаторов (`is_active=True`).

Включает Росстат (ИПЦ) и ЦБ (ключевая ставка и др.), каждый через свой `parser_type`
из `PARSER_REGISTRY`. При новых данных — upsert, при необходимости пересчёт прогноза, сброс кеша.
После ETL всех индикаторов — пересчёт производных через CalculationEngine.
"""

import logging
from datetime import datetime

from sqlalchemy import select

from app.database import async_session
from app.models import Indicator, FetchLog
from app.services.rosstat_cpi_parser import get_parser
from app.services.calculation_engine import calculation_engine

logger = logging.getLogger(__name__)


async def run_etl_for_indicator(indicator_code: str) -> bool:
    """Полный ETL для одного индикатора через PARSER_REGISTRY. Возвращает True если данные обновились."""
    async with async_session() as db:
        ind_q = await db.execute(select(Indicator).where(Indicator.code == indicator_code))
        indicator = ind_q.scalar_one_or_none()
        if not indicator:
            logger.error("Indicator '%s' not found", indicator_code)
            return False

        parser = get_parser(indicator.parser_type)
        if not parser:
            logger.error("Unknown parser_type '%s' for '%s'", indicator.parser_type, indicator_code)
            return False

        started_at = datetime.utcnow()
        fetch_log = FetchLog(indicator_id=indicator.id, status="running", started_at=started_at)
        db.add(fetch_log)
        await db.flush()

        await parser.run(db, indicator, fetch_log)
        return (fetch_log.records_added or 0) > 0


async def daily_update_job():
    """Плановая задача: обновить все активные индикаторы, затем пересчитать производные."""
    async with async_session() as db:
        active_q = await db.execute(
            select(Indicator).where(Indicator.is_active.is_(True)).order_by(Indicator.code)
        )
        active_indicators = active_q.scalars().all()

    codes = [i.code for i in active_indicators]
    logger.info(
        "Starting daily ETL: %d active indicator(s): %s",
        len(codes),
        ", ".join(codes) if codes else "(none)",
    )

    updated_codes: list[str] = []
    for indicator in active_indicators:
        try:
            had_new = await run_etl_for_indicator(indicator.code)
            if had_new:
                updated_codes.append(indicator.code)
        except Exception:
            logger.exception("Failed to update indicator '%s'", indicator.code)

    if updated_codes:
        async with async_session() as db:
            try:
                derived = await calculation_engine.run_for_updated_sources(db, updated_codes)
                await db.commit()
                if derived:
                    logger.info("CalculationEngine updated derived indicators: %s", derived)
            except Exception:
                logger.exception("CalculationEngine failed")

    logger.info("Daily ETL update complete.")
