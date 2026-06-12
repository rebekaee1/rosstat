"""
ETL scheduler: ежедневный прогон **всех активных** индикаторов (`is_active=True`).

Включает Росстат (ИПЦ) и ЦБ (ключевая ставка и др.), каждый через свой `parser_type`
из `PARSER_REGISTRY`. При новых данных — upsert, при необходимости пересчёт прогноза, сброс кеша.
После ETL всех индикаторов — пересчёт производных через CalculationEngine.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.database import async_session
from app.models import Indicator, FetchLog, EconomicEvent
from app.services.rosstat_cpi_parser import get_parser
from app.services.calculation_engine import calculation_engine
from app.services.alerting import alert_etl_failure, alert_etl_summary

ETL_TIMEOUT_SECONDS = 300
# Тяжёлые парсеры: cold-start может идти минуты; steady-state weekly — секунды.
ETL_TIMEOUT_BY_PARSER: dict[str, int] = {
    "rosstat_weekly_cpi": 600,
}

logger = logging.getLogger(__name__)


def etl_timeout_for(parser_type: str) -> int:
    return ETL_TIMEOUT_BY_PARSER.get(parser_type, ETL_TIMEOUT_SECONDS)

_running_locks: set[str] = set()
_lock = asyncio.Lock()


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

        indicator_id = indicator.id

        started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        fetch_log = FetchLog(indicator_id=indicator_id, status="running", started_at=started_at)
        db.add(fetch_log)
        await db.commit()

        try:
            await parser.run(db, indicator, fetch_log)
            if fetch_log.status == "failed":
                raise RuntimeError(fetch_log.error_message or "Parser reported failure")
            return (fetch_log.records_added or 0) > 0
        except asyncio.CancelledError:
            if fetch_log.status not in ("failed", "timeout"):
                await db.rollback()
                fetch_log.status = "timeout"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                fetch_log.error_message = f"ETL cancelled/timed out after {ETL_TIMEOUT_SECONDS}s"
                db.add(fetch_log)
                await db.commit()
            raise
        except Exception as e:
            if fetch_log.status not in ("failed", "timeout"):
                await db.rollback()
                fetch_log.status = "failed"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                fetch_log.error_message = str(e)[:500]
                db.add(fetch_log)
                await db.commit()
            raise


async def daily_update_job():
    """Плановая задача: обновить все активные индикаторы, затем пересчитать производные."""
    async with async_session() as db:
        active_q = await db.execute(
            select(Indicator).where(Indicator.is_active.is_(True)).order_by(Indicator.code)
        )
        active_indicators = active_q.scalars().all()
        indicator_tasks = [
            {"code": ind.code, "parser_type": ind.parser_type}
            for ind in active_indicators
        ]

    codes = [t["code"] for t in indicator_tasks]
    logger.info(
        "Starting daily ETL: %d active indicator(s): %s",
        len(codes),
        ", ".join(codes) if codes else "(none)",
    )

    t0 = time.monotonic()
    updated_codes: list[str] = []
    failed_codes: list[str] = []
    for task in indicator_tasks:
        code = task["code"]
        if task["parser_type"] == "derived":
            continue

        async with _lock:
            if code in _running_locks:
                logger.info("Skipping %s — already running", code)
                continue
            _running_locks.add(code)
        parser_type = task["parser_type"]
        timeout = etl_timeout_for(parser_type)
        try:
            had_new = await asyncio.wait_for(
                run_etl_for_indicator(code),
                timeout=timeout,
            )
            if had_new:
                updated_codes.append(code)
        except asyncio.TimeoutError:
            msg = f"ETL timed out after {timeout}s"
            logger.error("Timeout for indicator '%s': %s", code, msg)
            failed_codes.append(code)
            await alert_etl_failure(code, msg)
        except Exception as e:
            logger.exception("Failed to update indicator '%s'", code)
            failed_codes.append(code)
            await alert_etl_failure(code, str(e))
        finally:
            async with _lock:
                _running_locks.discard(code)

    if updated_codes:
        ping_codes = list(updated_codes)
        async with async_session() as db:
            try:
                derived = await calculation_engine.run_for_updated_sources(db, updated_codes)
                await db.commit()
                if derived:
                    logger.info("CalculationEngine updated derived indicators: %s", derived)
                    ping_codes.extend(derived)
            except Exception:
                logger.exception("CalculationEngine failed")
        # IndexNow: сообщаем поисковикам об обновлённых карточках (source +
        # derived) сразу после ETL — робот узнаёт о свежих данных за минуты.
        try:
            from app.services.indexnow import ping_updated_indicators

            await ping_updated_indicators(ping_codes)
        except Exception:
            logger.exception("IndexNow ping failed (non-fatal)")

    await _promote_past_events()

    duration = time.monotonic() - t0
    total_non_derived = sum(1 for t in indicator_tasks if t["parser_type"] != "derived")
    await alert_etl_summary(total_non_derived, len(updated_codes), failed_codes, duration)
    logger.info("Daily ETL update complete in %.0fs.", duration)


async def run_etl_for_parser_type(parser_type: str) -> dict[str, int]:
    """Re-run ETL для всех активных индикаторов с конкретным `parser_type`.

    Used by `late_minfin_etl_job` to catch in-place CSV content updates that
    утренний `daily_update_job` пропустил (Minfin обновляет content того же
    URL в течение дня — см. enterprise_resilience.md::Minfin in-place CSV).
    """
    async with async_session() as db:
        ind_q = await db.execute(
            select(Indicator).where(
                Indicator.is_active.is_(True),
                Indicator.parser_type == parser_type,
            ).order_by(Indicator.code)
        )
        codes = [i.code for i in ind_q.scalars().all()]

    if not codes:
        logger.info("run_etl_for_parser_type(%r): no active indicators found", parser_type)
        return {"total": 0, "updated": 0, "failed": 0}

    logger.info("Late ETL pass for parser_type=%s: %d indicators", parser_type, len(codes))
    updated_codes: list[str] = []
    failed_codes: list[str] = []
    async with async_session() as db:
        type_q = await db.execute(
            select(Indicator.code, Indicator.parser_type).where(Indicator.code.in_(codes))
        )
        parser_by_code = dict(type_q.all())

    for code in codes:
        async with _lock:
            if code in _running_locks:
                logger.info("Skipping %s — already running", code)
                continue
            _running_locks.add(code)
        timeout = etl_timeout_for(parser_by_code.get(code, ""))
        try:
            had_new = await asyncio.wait_for(
                run_etl_for_indicator(code),
                timeout=timeout,
            )
            if had_new:
                updated_codes.append(code)
        except Exception:
            logger.exception("Late ETL failed for %s", code)
            failed_codes.append(code)
        finally:
            async with _lock:
                _running_locks.discard(code)

    if updated_codes:
        ping_codes = list(updated_codes)
        async with async_session() as db:
            try:
                derived = await calculation_engine.run_for_updated_sources(db, updated_codes)
                await db.commit()
                if derived:
                    logger.info(
                        "Late ETL pass updated derived indicators: %s", derived
                    )
                    ping_codes.extend(derived)
            except Exception:
                logger.exception("CalculationEngine failed in late pass")
        try:
            from app.services.indexnow import ping_updated_indicators

            await ping_updated_indicators(ping_codes)
        except Exception:
            logger.exception("IndexNow ping failed (non-fatal)")

    logger.info(
        "Late ETL pass for parser_type=%s done: %d updated, %d failed",
        parser_type, len(updated_codes), len(failed_codes),
    )
    return {"total": len(codes), "updated": len(updated_codes), "failed": len(failed_codes)}


async def late_minfin_etl_job():
    """Polluc 15:00 MSK pass — ловит in-place content updates Минфин-каталога.

    См. enterprise_resilience.md::Minfin in-place CSV update — URL CSV-файла
    остаётся стабильным после первой публикации (`data-YYYYMMDDTHHMM-…csv`),
    но Минфин дополняет content того же URL новыми месяцами в течение дня.
    Утренний `daily_update_job` (03:00 MSK по умолчанию) может пропустить
    обновление, если оно вышло позже утра. Этот second pass в 15:00 MSK —
    insurance.
    """
    await run_etl_for_parser_type("minfin_budget_csv")


async def _promote_past_events() -> None:
    """Bulk-update stale 'scheduled' events whose date has passed → 'released'."""
    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    async with async_session() as db:
        result = await db.execute(
            update(EconomicEvent)
            .where(
                EconomicEvent.status == "scheduled",
                EconomicEvent.scheduled_date < today,
            )
            .values(
                status="released",
                updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        count = result.rowcount
        await db.commit()
        if count:
            logger.info("Promoted %d stale calendar events: scheduled → released", count)
