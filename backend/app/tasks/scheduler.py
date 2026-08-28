"""
ETL scheduler: ежедневный прогон **всех активных** индикаторов (`is_active=True`).

Включает Росстат (ИПЦ) и ЦБ (ключевая ставка и др.), каждый через свой `parser_type`
из `PARSER_REGISTRY`. При новых данных — upsert, при необходимости пересчёт прогноза, сброс кеша.
После ETL всех индикаторов — пересчёт производных через CalculationEngine.
"""

import asyncio
import logging
import time
from datetime import date, datetime, timezone

from sqlalchemy import func, select, update

from app.database import async_session
from app.models import Indicator, IndicatorData, FetchLog, EconomicEvent
from app.services.rosstat_cpi_parser import get_parser
from app.services.calculation_engine import calculation_engine
from app.services.forecast_pipeline import catch_up_empty_forecasts, retrain_indicator_forecast
from app.services.alerting import alert_etl_failure, alert_etl_summary, send_telegram

ETL_TIMEOUT_SECONDS = 300
# Тяжёлые парсеры: cold-start может идти минуты; steady-state weekly — секунды.
ETL_TIMEOUT_BY_PARSER: dict[str, int] = {
    "rosstat_weekly_cpi": 600,
    # Minfin: direct 503 → Tor SOCKS (+ artifact). Ночью Tor иногда >5 мин.
    "minfin_budget_csv": 600,
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
            # П-3: «данные изменились» = добавления И ревизии (status=success
            # ставится парсером при added/updated/pruned > 0). Раньше чистая
            # in-place ревизия (records_updated>0, added=0) не попадала в
            # updated_codes — при инкрементальном derived-пересчёте (П-2)
            # её зависимые остались бы stale.
            return fetch_log.status == "success"
        except asyncio.CancelledError:
            if fetch_log.status not in ("failed", "timeout"):
                await db.rollback()
                fetch_log.status = "timeout"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                to = etl_timeout_for(indicator.parser_type)
                fetch_log.error_message = f"ETL cancelled/timed out after {to}s"
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
            # Per-indicator TG не шлём: итог в alert_etl_summary (антидубль).
        except Exception as e:
            logger.exception("Failed to update indicator '%s'", code)
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
                    logger.info("CalculationEngine updated derived indicators: %s", derived)
                    ping_codes.extend(derived)
                    await _retrain_recalculated_derived(db, derived)
            except Exception as e:
                # Н-5: source обновился, derived stale — это витринная ложь,
                # а не внутренняя мелочь; в summary и алерт, не только в лог.
                logger.exception("CalculationEngine failed")
                failed_codes.append("derived-engine")
        # IndexNow: сообщаем поисковикам об обновлённых карточках (source +
        # derived) сразу после ETL — робот узнаёт о свежих данных за минуты.
        try:
            from app.services.indexnow import ping_updated_indicators

            await ping_updated_indicators(ping_codes)
        except Exception:
            logger.exception("IndexNow ping failed (non-fatal)")

    # Gap-fill: steps>0 без текущего прогноза (после seed/включения стратегии
    # или сбоя retrain). Идемпотентно — при полном покрытии no-op.
    await _catch_up_empty_forecasts_safe("daily_etl")

    await _promote_past_events()

    duration = time.monotonic() - t0
    total_non_derived = sum(1 for t in indicator_tasks if t["parser_type"] != "derived")
    await alert_etl_summary(total_non_derived, len(updated_codes), failed_codes, duration)
    logger.info("Daily ETL update complete in %.0fs.", duration)


async def _retrain_recalculated_derived(db, derived_codes: list[str]) -> None:
    """Ретрейн прогнозов пересчитанных derived-индикаторов — ПОСЛЕ движка.

    Порядок критичен. Source-каскад (`retrain_indicator_forecast` в конце ETL
    источника) ретрейнит `derived_from_source` siblings ДО того, как
    CalculationEngine досчитал их собственный факт: фильтр «только точки
    за пределами факта» работает по stale-факту, и прогноз derived-ряда
    получает точку на дату, которая минутой позже станет фактом. Фронт по
    collision-policy рисует её как прогноз — «факт Q1 идёт как прогноз»
    (инцидент 2026-08-05, семейство gdp-*-qoq/yoy). Поэтому после пересчёта
    движком ретрейним ВСЕ затронутые derived с активной стратегией — и
    self-modeled (`monthly_auto` на самом ряде), и `derived_from_source`
    (повторный прогон по свежему факту отрежет overlap; трансформы дешёвые).
    Каскад внутри retrain подтянет их собственные агрегаты/приросты.
    """
    if not derived_codes:
        return
    res = await db.execute(
        select(Indicator).where(Indicator.code.in_(derived_codes))
    )
    for ind in res.scalars().all():
        cfg = ind.model_config_json or {}
        strategy = cfg.get("forecast_strategy")
        steps = int(cfg.get("forecast_steps", 0) or 0)
        if steps > 0 and strategy:
            try:
                await retrain_indicator_forecast(db, ind)
                await db.commit()
                logger.info("Retrained derived forecast after recalc: %s", ind.code)
            except Exception as e:
                await db.rollback()
                # Н-6: старый прогноз молча остаётся current — алертим.
                logger.exception("Derived retrain after recalc failed: %s", ind.code)
                await alert_etl_failure(f"retrain:{ind.code}", str(e))


async def _catch_up_empty_forecasts_safe(context: str) -> list[str]:
    """Gap-fill пустых прогнозов; ошибки не роняют ETL/startup."""
    try:
        async with async_session() as db:
            filled = await catch_up_empty_forecasts(db)
            await db.commit()
            if filled:
                logger.info(
                    "Forecast catch-up (%s): retrained %d: %s",
                    context, len(filled), ", ".join(filled),
                )
            else:
                logger.info("Forecast catch-up (%s): nothing missing", context)
            return filled
    except Exception:
        logger.exception("Forecast catch-up (%s) aborted", context)
        return []


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
        except Exception as e:
            # Н-15: late-pass подключён к тому же алертингу, что и daily.
            logger.exception("Late ETL failed for %s", code)
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
                    logger.info(
                        "Late ETL pass updated derived indicators: %s", derived
                    )
                    ping_codes.extend(derived)
                    await _retrain_recalculated_derived(db, derived)
            except Exception as e:
                logger.exception("CalculationEngine failed in late pass")
                failed_codes.append("derived-engine")
                await alert_etl_failure("derived-engine", str(e))
        try:
            from app.services.indexnow import ping_updated_indicators

            await ping_updated_indicators(ping_codes)
        except Exception:
            logger.exception("IndexNow ping failed (non-fatal)")

    await _catch_up_empty_forecasts_safe(f"late_etl:{parser_type}")

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


async def late_fred_etl_job():
    """23:30 MSK pass — ловит same-day закрытия США на FRED.

    Вечерний полный ETL (20:00 MSK) раньше закрытия NYSE и типичной
    публикации H.15 / EIA на FRED. Без этого прогона оперативный срез на
    главной остаётся на предыдущем торговом дне до утреннего 06:00.
    """
    await run_etl_for_parser_type("fred_csv")


async def emiss_regional_job():
    """Обновление помесячных региональных витрин ЕМИСС (цены на топливо).

    Вне общего daily_update_job: regional bounded context (ADR-0008) живёт
    своим артефактом/сидером, а эта витрина — единственная «живая» помесячная
    (dataset 31448). Расписание в main.py, реализация —
    app.services.emiss_regional_parser.
    """
    from app.services.emiss_regional_parser import emiss_regional_job as _job

    await _job()



# ---------------------------------------------------------------------------
#  Staleness-мониторинг (Н-3): «источник молча умер» виден не через failed,
#  а через вечный no_new_data. Ежедневная сверка max(data.date) с SLA частоты.
# ---------------------------------------------------------------------------

# Пороги с запасом на лаг публикации источника (месячный ряд Росстата выходит
# через 4-6 недель после периода). Синхронизированы по духу с freshness-SLA
# страниц /today (`seo_today._STALE_AFTER_DAYS`), но мягче: здесь алерт
# оператору, там — честная рамка пользователю.
STALENESS_SLA_DAYS: dict[str, int] = {
    "daily": 7,
    "weekly": 21,
    "monthly": 75,
    "quarterly": 150,
    "annual": 550,
}
_STALENESS_DEFAULT_DAYS = 550  # irregular и незнакомые частоты


def find_stale(rows: list[tuple[str, str | None, date | None]],
               today: date | None = None) -> list[tuple[str, int]]:
    """Из (code, frequency, max_date) — [(code, возраст_дней)] сверх SLA.

    Чистая функция для тестируемости; ряды без точек пропускаются (их ловит
    startup catch-up, Н-9).
    """
    today = today or date.today()
    stale: list[tuple[str, int]] = []
    for code, frequency, max_date in rows:
        if max_date is None:
            continue
        sla = STALENESS_SLA_DAYS.get((frequency or "").lower(), _STALENESS_DEFAULT_DAYS)
        age = (today - max_date).days
        if age > sla:
            stale.append((code, age))
    return stale


async def staleness_check_job() -> list[tuple[str, int]]:
    """Ежедневная проверка свежести всех активных индикаторов + Telegram-алерт."""
    async with async_session() as db:
        q = await db.execute(
            select(Indicator.code, Indicator.frequency, func.max(IndicatorData.date))
            .outerjoin(IndicatorData, IndicatorData.indicator_id == Indicator.id)
            .where(Indicator.is_active.is_(True))
            .group_by(Indicator.id)
        )
        rows = [(code, freq, max_date) for code, freq, max_date in q.all()]

    # Н-14: meta-чек «алерты сломаны». Система шлёт минимум одно сообщение в
    # сутки (ETL-summary); если последней успешной отправки нет > 26 ч —
    # Telegram-канал, вероятно, мёртв. Алертить через него же бессмысленно —
    # маркер в лог уровнем ERROR (виден в docker logs / Loki).
    try:
        from app.models import TelegramOutbox
        async with async_session() as db:
            last_ok = await db.scalar(
                select(func.max(TelegramOutbox.sent_at))
                .where(TelegramOutbox.ok.is_(True))
            )
        if last_ok is not None:
            age_h = (datetime.now(timezone.utc).replace(tzinfo=None) - last_ok
                     ).total_seconds() / 3600
            if age_h > 26:
                logger.error(
                    "ALERTING CHANNEL DEAD? Последнее успешное Telegram-сообщение "
                    "%.0f ч назад — проверь токен/сеть (telegram_outbox)", age_h,
                )
    except Exception:
        logger.warning("Telegram outbox freshness check failed", exc_info=True)

    stale = find_stale(rows)
    if stale:
        from html import escape

        from app.services.alerting import STALENESS_MUTE_TTL, alert_muted

        stale.sort(key=lambda p: -p[1])
        # Хронический хвост (демография 1285 дн. и т.п.) — раз в неделю,
        # не каждый день один и тот же список из 340 кодов.
        if await alert_muted("staleness", STALENESS_MUTE_TTL):
            logger.info(
                "Staleness check muted (%d stale) — next digest in ≤%dd",
                len(stale), STALENESS_MUTE_TTL // 86400,
            )
        else:
            listing = "\n".join(
                f"• <code>{escape(code)}</code> — {age} дн. без новых точек"
                for code, age in stale[:25]
            )
            more = f"\n…и ещё {len(stale) - 25}" if len(stale) > 25 else ""
            await send_telegram(
                f"🟡 <b>Staleness check</b>\n{len(stale)} индикатор(ов) старше SLA "
                f"своей частоты:\n{listing}{more}",
                kind="staleness",
            )
        logger.warning("Staleness check: %d stale indicator(s): %s",
                       len(stale), ", ".join(c for c, _ in stale[:40]))
    else:
        logger.info("Staleness check: all %d active indicators fresh", len(rows))
    return stale


async def _promote_past_events() -> None:
    """Bulk-update stale 'scheduled' events whose date has passed → 'released'.

    Also enrich from IndicatorData (early publications still on a future
    scheduled_date) so upcoming API stops advertising already-released rows.
    """
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
        try:
            from app.services.calendar_sources.enrichment import (
                enrich_events_from_indicator_data,
            )
            enriched = await enrich_events_from_indicator_data(db)
            if enriched:
                logger.info("Calendar enrichment after promote: %d events", enriched)
        except Exception:
            logger.exception("Calendar enrichment from IndicatorData failed")
