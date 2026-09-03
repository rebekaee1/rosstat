"""Realtime-аномалии: пороговые алерты 15-минутного цикла (этап 5 плана).

Вызывается из rollups_15min_job. Правила:
- трафик текущего часа < 40% того же часа прошлой недели (при базе ≥ 20);
- всплеск js_error за 15 минут (≥ 10);
- тишина собственного сбора ≥ 15 минут при живом трафике за предыдущий час;
- лаг повизитного сырья Метрики > 36 часов;
- лаг ClickHouse-синка > 1 часа (если слой включён).

Плюс суточная калибровка антибота (`check_bot_calibration`, из ночного
rollups_daily_job): небот-сессии за последний полный день с повизиткой
Метрики должны попадать в коридор ±15% к её визитам — вылет означает, что
веса bot_score разъехались с реальностью (см. services/bot_score.py).

Антиспам: не чаще одного алерта каждого типа в 2 часа (state-Redis DB 1 —
переживает FLUSHDB кэша). Канал доставки — общий send_telegram (архивируется
в telegram_outbox, как всё исходящее).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.config import settings
from app.database import analytics_session
from app.models import BehaviorEvent, RawMetrikaVisit

logger = logging.getLogger(__name__)

_MUTE_TTL = 2 * 3600  # один алерт типа — раз в 2 часа


async def _muted(alert_key: str) -> bool:
    try:
        from app.core.cache import get_state_redis
        r = await get_state_redis()
        key = f"fe:alerts:mute:{alert_key}"
        if await r.get(key):
            return True
        await r.set(key, "1", ex=_MUTE_TTL)
        return False
    except Exception:  # noqa: BLE001 — редис недоступен: лучше замолчать, чем упасть
        return True


async def _alert(alert_key: str, text: str) -> None:
    if await _muted(alert_key):
        return
    from app.services.alerting import send_telegram
    await send_telegram(f"⚠️ <b>Аномалия аналитики</b>\n{text}", kind="analytics_anomaly")
    logger.warning("Analytics anomaly alert: %s", alert_key)


async def check_anomalies() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with analytics_session() as db:
        hour_start = now.replace(minute=0, second=0, microsecond=0)

        async def _count_pv(a: datetime, b: datetime) -> int:
            return int(await db.scalar(
                select(func.count()).select_from(BehaviorEvent).where(
                    BehaviorEvent.event_type == "pageview",
                    BehaviorEvent.occurred_at >= a,
                    BehaviorEvent.occurred_at < b,
                )
            ) or 0)

        # 1. Трафик часа против того же часа прошлой недели.
        cur = await _count_pv(hour_start, now)
        base = await _count_pv(hour_start - timedelta(days=7), now - timedelta(days=7))
        if base >= 20 and cur < base * 0.4 and (now - hour_start) >= timedelta(minutes=30):
            await _alert(
                "traffic_drop",
                f"Трафик часа упал: {cur} просмотров против {base} в тот же час "
                f"неделю назад ({round(cur / base * 100)}%).",
            )

        # 2. Всплеск JS-ошибок за 15 минут.
        errors_15m = int(await db.scalar(
            select(func.count()).select_from(BehaviorEvent).where(
                BehaviorEvent.event_type == "js_error",
                BehaviorEvent.occurred_at >= now - timedelta(minutes=15),
            )
        ) or 0)
        if errors_15m >= 10:
            await _alert("js_error_spike", f"Всплеск JS-ошибок: {errors_15m} за 15 минут.")

        # 3. Тишина собственного сбора при живом сайте.
        last_ingest = await db.scalar(select(func.max(BehaviorEvent.ingested_at)))
        prev_hour = await _count_pv(now - timedelta(hours=2), now - timedelta(hours=1))
        if last_ingest and prev_hour >= 10 and (now - last_ingest) > timedelta(minutes=15):
            await _alert(
                "collection_silence",
                f"Собственный сбор молчит {round((now - last_ingest).total_seconds() / 60)} мин "
                f"при живом трафике (час назад было {prev_hour} просмотров).",
            )

        # 4. Лаг повизитного сырья Метрики.
        last_visit = await db.scalar(select(func.max(RawMetrikaVisit.ingested_at)))
        if last_visit and (now - last_visit) > timedelta(hours=36):
            await _alert(
                "metrika_lag",
                f"Повизитное сырьё Метрики не обновлялось "
                f"{round((now - last_visit).total_seconds() / 3600)} ч (порог 36 ч).",
            )

    # 5. Лаг ClickHouse-синка (вне сессии БД — свой слой).
    if settings.clickhouse_enabled:
        try:
            from app.services.clickhouse_sync import last_sync_age_minutes
            age = await last_sync_age_minutes()
            if age is not None and age > 60:
                await _alert("clickhouse_lag", f"ClickHouse-синк отстаёт на {age} мин (порог 60).")
        except Exception:  # noqa: BLE001
            pass

    await _check_host_pressure()


async def _check_host_pressure() -> None:
    """Память cgroup, насыщение пула, idle in transaction — инцидент 2026-09-03."""
    from app.database import pool_stats
    from app.services.process_metrics import memory_pressure_ratio
    from sqlalchemy import text as sql_text

    ratio = memory_pressure_ratio()
    if ratio is not None and ratio >= 0.85:
        await _alert(
            "memory_pressure",
            f"Память контейнера backend {round(ratio * 100)}% лимита (порог 85%).",
        )

    public = pool_stats("public")
    analytics = pool_stats("analytics")
    pub_cap = public["size"] + settings.db_max_overflow
    an_cap = analytics["size"] + settings.analytics_db_max_overflow
    if pub_cap and public["checkedout"] >= pub_cap:
        await _alert(
            "db_pool_saturation",
            f"Публичный пул БД исчерпан: {public['checkedout']}/{pub_cap}.",
        )
    if an_cap and analytics["checkedout"] >= an_cap:
        await _alert(
            "db_pool_saturation",
            f"Аналитический пул БД исчерпан: {analytics['checkedout']}/{an_cap}.",
        )

    try:
        async with analytics_session() as db:
            idle = int(await db.scalar(sql_text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE state = 'idle in transaction' "
                "AND now() - state_change > interval '2 minutes'"
            )) or 0)
        if idle > 0:
            await _alert(
                "idle_in_tx",
                f"{idle} сессий Postgres idle in transaction дольше 2 минут.",
            )
    except Exception:  # noqa: BLE001
        logger.debug("idle_in_tx check skipped", exc_info=True)


BOT_CALIBRATION_TOLERANCE_PCT = 15  # коридор ±15% к визитам Метрики


async def check_bot_calibration() -> dict | None:
    """Суточная сверка: небот-сессии против визитов Метрики за последний
    полный МСК-день, по которому уже есть повизитка (лаг Logs API — сутки).
    Возвращает измерение для логов/тестов; вылет из коридора — алерт."""
    from app.models import ServerSession
    from app.services.analytics_period import msk_day

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with analytics_session() as db:
        # Последний день, за который у Метрики есть данные (кроме сегодня —
        # день не закрыт, сравнение бессмысленно).
        last_metrika_day = await db.scalar(
            select(func.max(RawMetrikaVisit.visit_date))
            .where(RawMetrikaVisit.visit_date < msk_day(now))
        )
        if not last_metrika_day:
            return None
        metrika_visits = int(await db.scalar(
            select(func.count()).select_from(RawMetrikaVisit)
            .where(RawMetrikaVisit.visit_date == last_metrika_day)
        ) or 0)
        our_sessions = int(await db.scalar(
            select(func.count()).select_from(ServerSession)
            .where(ServerSession.day == last_metrika_day, ServerSession.is_bot.is_(False))
        ) or 0)

    if metrika_visits < 20:  # малая база — сверка статистически пуста
        return {"day": str(last_metrika_day), "metrika": metrika_visits, "ours": our_sessions, "skipped": True}

    ratio_pct = round(our_sessions / metrika_visits * 100)
    out = {"day": str(last_metrika_day), "metrika": metrika_visits, "ours": our_sessions, "ratio_pct": ratio_pct}
    if abs(ratio_pct - 100) > BOT_CALIBRATION_TOLERANCE_PCT:
        await _alert(
            "bot_calibration",
            f"Антибот-калибровка за {last_metrika_day}: наши небот-сессии {our_sessions} "
            f"против {metrika_visits} визитов Метрики ({ratio_pct}%) — вне коридора "
            f"±{BOT_CALIBRATION_TOLERANCE_PCT}%. Проверить веса bot_score.",
        )
    logger.info("Bot calibration: %s", out)
    return out
