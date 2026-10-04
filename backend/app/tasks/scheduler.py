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
from app.core.cache import publish_committed_indicator_changes
from app.models import Indicator, IndicatorData, FetchLog, EconomicEvent
from app.services.rosstat_cpi_parser import get_parser
from app.services.rosstat_weekly_inflation_parser import WEEKLY_SEGMENT_CODES
from app.services.calculation_engine import calculation_engine
from app.services.forecast_pipeline import catch_up_empty_forecasts, retrain_indicator_forecast
from app.services.alerting import alert_etl_failure, alert_etl_summary, send_telegram
from app.services.staleness import (  # noqa: F401  (реэкспорт для тестов/внешних импортов)
    STALENESS_DEFAULT_DAYS,
    STALENESS_SLA_DAYS,
    StaleRow,
    build_report,
    find_stale,
    load_known_flagged,
    plan_staleness_message,
    store_known_flagged,
)
from app.services.base_parser import (
    DEGRADED_STATUSES,
    STATUS_FALLBACK_USED,
    STATUS_SUCCESS,
    storage_committed,
)

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


def _updated_source_codes(codes: list[str]) -> list[str]:
    """Include sibling rows written as a side effect of the primary ETL run."""
    expanded = dict.fromkeys(codes)
    if "inflation-weekly" in expanded:
        # RosstatWeeklyCpiParser._post_upsert writes these three series while
        # run_etl_for_indicator reports only the primary code to the scheduler.
        expanded.update(dict.fromkeys(WEEKLY_SEGMENT_CODES.values()))
    return list(expanded)


async def run_etl_for_indicator(indicator_code: str) -> bool:
    """Полный ETL для одного индикатора через PARSER_REGISTRY. Возвращает True если данные обновились."""
    changed, _status = await run_etl_for_indicator_status(indicator_code)
    return changed


def _fetch_changed(fetch_log: FetchLog) -> bool:
    """Ряд изменился в этом прогоне (для каскада derived / IndexNow).

    success — всегда изменение; fallback_used — если резервный снимок
    всё-таки добавил/обновил точки (статус про источник, не про дельту).
    """
    if fetch_log.status == STATUS_SUCCESS:
        return True
    if fetch_log.status == STATUS_FALLBACK_USED:
        return bool((fetch_log.records_added or 0) or (fetch_log.records_updated or 0))
    return False


class _CommittedETLCancelled(asyncio.CancelledError):
    """Propagate cancellation while retaining a successfully committed outcome."""

    def __init__(self, changed: bool, status: str | None):
        super().__init__("ETL cancelled after SQL commit")
        self.changed = changed
        self.status = status


async def _run_etl_with_timeout(code: str, timeout: float) -> tuple[bool, str | None]:
    """A per-indicator deadline must not hide a commit from the derived batch.

    wait_for translates child cancellation into TimeoutError with its cause.
    External cancellation of this caller still propagates as CancelledError.
    """
    try:
        return await asyncio.wait_for(run_etl_for_indicator_status(code), timeout=timeout)
    except asyncio.TimeoutError as exc:
        if isinstance(exc.__cause__, _CommittedETLCancelled):
            outcome = exc.__cause__
            logger.warning("ETL '%s': deadline reached after SQL commit; retaining changed outcome", code)
            return outcome.changed, outcome.status
        raise


async def run_etl_for_indicator_status(indicator_code: str) -> tuple[bool, str | None]:
    """Как `run_etl_for_indicator`, но возвращает ещё и итоговый fetch_log.status.

    Статус нужен ETL-summary: parsed_zero / fallback_used — проблемы, которые
    раньше прятались под no_new_data.
    """
    async with async_session() as db:
        ind_q = await db.execute(select(Indicator).where(Indicator.code == indicator_code))
        indicator = ind_q.scalar_one_or_none()
        if not indicator:
            logger.error("Indicator '%s' not found", indicator_code)
            return False, None

        parser = get_parser(indicator.parser_type)
        if not parser:
            logger.error("Unknown parser_type '%s' for '%s'", indicator.parser_type, indicator_code)
            return False, None

        indicator_id = indicator.id
        parser_type = indicator.parser_type  # rollback expires ORM attributes.

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
            return _fetch_changed(fetch_log), fetch_log.status
        except asyncio.CancelledError:
            if storage_committed(fetch_log):
                raise _CommittedETLCancelled(_fetch_changed(fetch_log), fetch_log.status) from None
            if fetch_log.status not in ("failed", "timeout"):
                await db.rollback()
                fetch_log.status = "timeout"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                to = etl_timeout_for(parser_type)
                fetch_log.error_message = f"ETL cancelled/timed out after {to}s"
                db.add(fetch_log)
                await db.commit()
            raise
        except Exception as e:
            if not storage_committed(fetch_log) and fetch_log.status not in ("failed", "timeout"):
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
    degraded: dict[str, list[str]] = {s: [] for s in DEGRADED_STATUSES}
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
            had_new, status = await _run_etl_with_timeout(code, timeout)
            if had_new:
                updated_codes.append(code)
            if status in degraded:
                degraded[status].append(code)
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
        source_codes = _updated_source_codes(updated_codes)
        ping_codes = list(source_codes)
        async with async_session() as db:
            try:
                derived = await calculation_engine.run_for_updated_sources(db, source_codes)
                await db.commit()
                await publish_committed_indicator_changes(derived)
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
    if any(degraded.values()):
        logger.warning(
            "Daily ETL degraded runs: %s",
            "; ".join(f"{s}={', '.join(c)}" for s, c in degraded.items() if c),
        )
    await alert_etl_summary(
        total_non_derived, len(updated_codes), failed_codes, duration, degraded=degraded,
    )
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
                await publish_committed_indicator_changes([ind.code])
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
    degraded_codes: list[str] = []
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
            had_new, status = await _run_etl_with_timeout(code, timeout)
            if had_new:
                updated_codes.append(code)
            if status in DEGRADED_STATUSES:
                degraded_codes.append(f"{code}:{status}")
        except Exception as e:
            # Н-15: late-pass подключён к тому же алертингу, что и daily.
            logger.exception("Late ETL failed for %s", code)
            failed_codes.append(code)
            await alert_etl_failure(code, str(e))
        finally:
            async with _lock:
                _running_locks.discard(code)

    if updated_codes:
        source_codes = _updated_source_codes(updated_codes)
        ping_codes = list(source_codes)
        async with async_session() as db:
            try:
                derived = await calculation_engine.run_for_updated_sources(db, source_codes)
                await db.commit()
                await publish_committed_indicator_changes(derived)
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
        "Late ETL pass for parser_type=%s done: %d updated, %d failed, %d degraded%s",
        parser_type, len(updated_codes), len(failed_codes), len(degraded_codes),
        f" ({', '.join(degraded_codes)})" if degraded_codes else "",
    )
    return {
        "total": len(codes),
        "updated": len(updated_codes),
        "failed": len(failed_codes),
        "degraded": len(degraded_codes),
    }


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

# Пороги SLA, классификация просрочек и формат сводки — app.services.staleness
# (здесь реэкспорт для обратной совместимости импортов).
_STALENESS_DEFAULT_DAYS = STALENESS_DEFAULT_DAYS


def calculation_engine_specs():
    """DERIVED_SPECS (dst_code → src_codes) для привязки производных к первоисточнику."""
    from app.services.calculation_engine import DERIVED_SPECS

    return DERIVED_SPECS


async def staleness_check_job() -> list[tuple[str, int]]:
    """Ежедневная проверка свежести всех активных индикаторов + Telegram-алерт."""
    async with async_session() as db:
        # Последний прогон парсера (fetch_log): отличает «источник молчит»
        # (читаем без ошибок) от «парсер сломан» (failed/parsed_zero/…).
        last_status = (
            select(FetchLog.status)
            .where(FetchLog.indicator_id == Indicator.id)
            .order_by(FetchLog.started_at.desc())
            .limit(1)
            .correlate(Indicator)
            .scalar_subquery()
        )
        last_fetch_at = (
            select(func.max(FetchLog.started_at))
            .where(FetchLog.indicator_id == Indicator.id)
            .correlate(Indicator)
            .scalar_subquery()
        )
        q = await db.execute(
            select(
                Indicator.code, Indicator.frequency, func.max(IndicatorData.date),
                Indicator.parser_type, Indicator.source,
                last_status.label("last_status"), last_fetch_at.label("last_fetch_at"),
            )
            .outerjoin(IndicatorData, IndicatorData.indicator_id == Indicator.id)
            .where(Indicator.is_active.is_(True))
            .group_by(Indicator.id)
        )
        stale_rows = [
            StaleRow(
                code=code, frequency=freq, max_date=max_date,
                parser_type=parser_type or "", source=source or "",
                last_status=status, last_fetch_at=fetched_at,
            )
            for code, freq, max_date, parser_type, source, status, fetched_at in q.all()
        ]
        rows = [(r.code, r.frequency, r.max_date) for r in stale_rows]

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

    from app.services.process_metrics import (
        fd_pressure_high,
        fd_soft_limit,
        process_open_fds,
    )

    n_fd = process_open_fds()
    fd_limit = fd_soft_limit()
    logger.info(
        "Staleness check: process open_fds=%s limit=%s",
        n_fd,
        fd_limit or "unknown",
    )

    stale = find_stale(rows)
    fd_line = f"\nfd {n_fd}/{fd_limit or '?'}"
    sent = False
    if stale:
        from app.services.alerting import STALENESS_MUTE_TTL, alert_muted

        derived_sources = {s.dst_code: s.src_codes for s in calculation_engine_specs()}
        report = build_report(
            stale_rows, derived_sources,
            today=date.today(), now=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        known = await load_known_flagged()
        # Раз в неделю — полная сводка по группам; в остальные дни — только
        # новые просрочки (хронический хвост не повторяем).
        weekly_due = not await alert_muted("staleness_weekly", STALENESS_MUTE_TTL)
        message = plan_staleness_message(
            report, known, weekly_due=weekly_due, fd_line=fd_line,
        )
        await store_known_flagged(report.flagged_codes)
        if message:
            await send_telegram(message, kind="staleness")
            sent = True
        else:
            logger.info(
                "Staleness check: nothing new to report (%d stale: attention=%d "
                "frozen=%d derived_follow=%d within_lag=%d)",
                len(stale), len(report.attention), len(report.frozen),
                report.derived_follow, report.within_lag,
            )
        logger.warning(
            "Staleness check: %d stale (attention=%d frozen=%d derived_follow=%d "
            "within_lag=%d); attention: %s",
            len(stale), len(report.attention), len(report.frozen),
            report.derived_follow, report.within_lag,
            ", ".join(f"{i.code}:{i.age}" for i in report.attention[:40]),
        )
    else:
        logger.info("Staleness check: all %d active indicators fresh", len(rows))

    if fd_pressure_high():
        logger.error(
            "FD pressure high: open_fds=%s limit=%s",
            n_fd,
            fd_limit or "unknown",
        )
        if not sent:
            await send_telegram(
                f"🟡 <b>Staleness check</b>\nОткрытых файловых дескрипторов "
                f"{n_fd} из {fd_limit or '?'} (больше 80% soft ulimit).",
                kind="staleness",
            )
    return stale


async def _promote_past_events() -> None:
    """Repair legacy elapsed-date promotions, then confirm from published data."""
    async with async_session() as db:
        result = await db.execute(
            update(EconomicEvent)
            .where(
                EconomicEvent.status == "released",
                EconomicEvent.actual_value.is_(None),
            )
            .values(status="scheduled", updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        await db.commit()
        if result.rowcount:
            logger.info("Removed %d unconfirmed calendar release statuses", result.rowcount)
        try:
            from app.services.calendar_sources.enrichment import (
                enrich_events_from_indicator_data,
            )
            enriched = await enrich_events_from_indicator_data(db)
            if enriched:
                logger.info("Calendar enrichment after promote: %d events", enriched)
        except Exception:
            logger.exception("Calendar enrichment from IndicatorData failed")
