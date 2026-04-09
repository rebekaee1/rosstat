"""
ETL scheduler: ежедневный прогон **всех активных** индикаторов (`is_active=True`).

Включает Росстат (ИПЦ) и ЦБ (ключевая ставка и др.), каждый через свой `parser_type`
из `PARSER_REGISTRY`. При новых данных — upsert, при необходимости пересчёт прогноза, сброс кеша.
После ETL всех индикаторов — пересчёт производных через CalculationEngine.
"""

import asyncio
import logging
import time
from datetime import datetime

from sqlalchemy import select

from app.database import async_session
from app.models import Indicator, FetchLog
from app.services.rosstat_cpi_parser import get_parser
from app.services.calculation_engine import calculation_engine
from app.services.alerting import alert_etl_failure, alert_etl_summary

ETL_TIMEOUT_SECONDS = 300

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

    t0 = time.monotonic()
    updated_codes: list[str] = []
    failed_codes: list[str] = []
    for indicator in active_indicators:
        if indicator.parser_type == "derived":
            continue
        try:
            had_new = await asyncio.wait_for(
                run_etl_for_indicator(indicator.code),
                timeout=ETL_TIMEOUT_SECONDS,
            )
            if had_new:
                updated_codes.append(indicator.code)
        except asyncio.TimeoutError:
            msg = f"ETL timed out after {ETL_TIMEOUT_SECONDS}s"
            logger.error("Timeout for indicator '%s': %s", indicator.code, msg)
            failed_codes.append(indicator.code)
            alert_etl_failure(indicator.code, msg)
        except Exception as e:
            logger.exception("Failed to update indicator '%s'", indicator.code)
            failed_codes.append(indicator.code)
            alert_etl_failure(indicator.code, str(e))

    if updated_codes:
        async with async_session() as db:
            try:
                derived = await calculation_engine.run_for_updated_sources(db, updated_codes)
                await db.commit()
                if derived:
                    logger.info("CalculationEngine updated derived indicators: %s", derived)
            except Exception:
                logger.exception("CalculationEngine failed")

    duration = time.monotonic() - t0
    total_non_derived = sum(1 for i in active_indicators if i.parser_type != "derived")
    alert_etl_summary(total_non_derived, len(updated_codes), failed_codes, duration)
    logger.info("Daily ETL update complete in %.0fs.", duration)
