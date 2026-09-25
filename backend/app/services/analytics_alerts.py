"""Realtime-аномалии: пороговые алерты 15-минутного цикла (этап 5 плана).

Вызывается из rollups_15min_job. Правила:
- трафик текущего часа < 40% того же часа прошлой недели (при базе ≥ 20);
- всплеск своих js_error/rejection за 15 минут (≥ 10), без kind=resource
  и без очевидных скриптов Метрики/РСЯ;
- тишина собственного сбора ≥ 45 минут при живом трафике за предыдущий час
  (порог выше одного 15-минутного цикла rollup; statement timeout пробы
  не считается тишиной);
- лаг повизитного сырья Метрики > 36 часов;
- лаг ClickHouse-синка > 1 часа (если слой включён).

Плюс суточная сверка доставки (`check_bot_calibration`, legacy имя):
сравнивает разные популяции (сырые Logs с роботами и собственные
небот-сессии без внутренних). Отклонение требует разбора состава,
но не доказывает ошибку антибота и не оправдывает подгонку весов.

Антиспам: не чаще одного алерта каждого типа в 2 часа (state-Redis DB 1 —
переживает FLUSHDB кэша). Канал доставки — общий send_telegram (архивируется
в telegram_outbox, как всё исходящее).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.config import settings
from app.database import analytics_session
from app.models import BehaviorEvent, RawMetrikaVisit

logger = logging.getLogger(__name__)

_MUTE_TTL = 2 * 3600  # один алерт типа — раз в 2 часа
# 15 минут совпадали с периодом rollup и пейджили на одну тихую четверть часа.
# 45 минут — три цикла: реальный обрыв всё ещё виден внутри часа.
COLLECTION_SILENCE_AFTER = timedelta(minutes=45)
_COLLECTION_PROBE_WINDOW = timedelta(hours=6)
# Водяной знак приёма behavior-батча. state-Redis переживает FLUSHDB кэша.
# max(ingested_at) без индекса на behavior_events упирается в statement_timeout.
BEHAVIOR_INGEST_WATERMARK = "fe:beh:last_ingest_unix"
# 85% на cgroup, который и так у потолка, — метроном каждые 2 часа.
# Эпизод: один алерт на вход выше 92%, снятие после отката ниже 80%.
MEMORY_ALERT_RATIO = 0.92
MEMORY_CLEAR_RATIO = 0.80
_MEMORY_STICKY_KEY = "fe:alerts:memory_pressure_episode"
_METRIKA_HOST_MARKERS = (
    "mc.yandex.",
    "mc.webvisor.",
    "webvisor.com",
    "yastatic.net",
    "an.yandex.",
    "adfox.ru",
    "yandexadexchange.net",
)


def _error_host(params: dict) -> str:
    src = str(params.get("src") or "")
    match = re.search(r"https?://([^/\s):]+)", src) or re.search(
        r"https?://([^/\s):]+)", str(params.get("stack") or "")
    )
    return match.group(1).lower() if match else ""


def js_error_counts_for_alert(params) -> bool:
    """Свои error/rejection. resource и скрипты Метрики/РСЯ — шум, не регресс."""
    payload = params if isinstance(params, dict) else {}
    if payload.get("kind") not in ("error", "rejection"):
        return False
    host = _error_host(payload)
    return not host or not any(marker in host for marker in _METRIKA_HOST_MARKERS)


def memory_pressure_episode(ratio: float | None, *, sticky: bool) -> str:
    """alert — первый вход в зону; clear — откат; hold — уже объявленный эпизод или норма."""
    if ratio is None:
        return "hold"
    if ratio >= MEMORY_ALERT_RATIO:
        return "hold" if sticky else "alert"
    if sticky and ratio < MEMORY_CLEAR_RATIO:
        return "clear"
    return "hold"


def collection_silence_due(
    *,
    last_seen: datetime | None,
    now: datetime,
    prev_hour_pageviews: int,
    probe_failed: bool,
) -> bool:
    """Таймаут или сбой пробы — не тишина. Пустая успешная проба при живом часе — тишина."""
    if probe_failed or prev_hour_pageviews < 10:
        return False
    if last_seen is None:
        return True
    return (now - last_seen) > COLLECTION_SILENCE_AFTER


def _is_statement_timeout(exc: BaseException) -> bool:
    seen: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in seen:
        seen.append(current)
        name = type(current).__name__.lower()
        text = str(current).lower()
        if (
            "querycanceled" in name
            or "canceling statement" in text
            or "statement timeout" in text
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


def _naive_utc(when: datetime) -> datetime:
    if when.tzinfo is None:
        return when
    return when.astimezone(timezone.utc).replace(tzinfo=None)


async def note_behavior_ingest(when: datetime) -> None:
    """Запомнить серверное время успешного приёма behavior-батча."""
    try:
        from app.core.cache import get_state_redis
        stamp = int(_naive_utc(when).replace(tzinfo=timezone.utc).timestamp())
        redis = await get_state_redis()
        await redis.set(BEHAVIOR_INGEST_WATERMARK, str(stamp), ex=7 * 24 * 3600)
    except Exception:  # noqa: BLE001
        logger.debug("behavior ingest watermark skipped", exc_info=True)


async def _read_ingest_watermark() -> datetime | None:
    try:
        from app.core.cache import get_state_redis
        redis = await get_state_redis()
        raw = await redis.get(BEHAVIOR_INGEST_WATERMARK)
        if not raw:
            return None
        return datetime.fromtimestamp(int(raw), tz=timezone.utc).replace(tzinfo=None)
    except Exception:  # noqa: BLE001
        return None


async def _last_collection_seen(db, now: datetime) -> tuple[datetime | None, bool]:
    """(момент, probe_failed). Сбой пробы не превращается в алерт тишины."""
    watermark = await _read_ingest_watermark()
    if watermark is not None:
        return watermark, False
    try:
        floor = now - _COLLECTION_PROBE_WINDOW
        seen = await db.scalar(
            select(func.max(BehaviorEvent.occurred_at)).where(
                BehaviorEvent.event_type == "pageview",
                BehaviorEvent.occurred_at >= floor,
            )
        )
        return seen, False
    except Exception as exc:  # noqa: BLE001
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            logger.debug("collection_silence rollback failed", exc_info=True)
        if _is_statement_timeout(exc):
            logger.warning("collection_silence probe hit statement timeout; alert suppressed")
        else:
            logger.warning("collection_silence probe failed; alert suppressed", exc_info=True)
        return None, True


async def _memory_sticky() -> bool:
    try:
        from app.core.cache import get_state_redis
        redis = await get_state_redis()
        return bool(await redis.get(_MEMORY_STICKY_KEY))
    except Exception:  # noqa: BLE001
        return False


async def _set_memory_sticky(active: bool) -> None:
    try:
        from app.core.cache import get_state_redis
        redis = await get_state_redis()
        if active:
            await redis.set(_MEMORY_STICKY_KEY, "1")
        else:
            await redis.delete(_MEMORY_STICKY_KEY)
    except Exception:  # noqa: BLE001
        logger.debug("memory_pressure sticky update skipped", exc_info=True)


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


async def _alert(alert_key: str, text: str) -> bool:
    if await _muted(alert_key):
        return False
    from app.services.alerting import send_telegram
    await send_telegram(f"⚠️ <b>Аномалия аналитики</b>\n{text}", kind="analytics_anomaly")
    logger.warning("Analytics anomaly alert: %s", alert_key)
    return True


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

        # 2. Всплеск своих JS-ошибок за 15 минут. resource и Метрика не считаются.
        kind = BehaviorEvent.params_json["kind"].as_string()
        error_rows = (await db.execute(
            select(BehaviorEvent.params_json).where(
                BehaviorEvent.event_type == "js_error",
                BehaviorEvent.occurred_at >= now - timedelta(minutes=15),
                kind.in_(("error", "rejection")),
            )
        )).scalars().all()
        errors_15m = sum(1 for params in error_rows if js_error_counts_for_alert(params))
        if errors_15m >= 10:
            await _alert("js_error_spike", f"Всплеск JS-ошибок: {errors_15m} за 15 минут.")

        # 3. Тишина собственного сбора при живом сайте.
        # Водяной знак приёма, иначе узкий max(occurred_at) по индексу
        # (event_type, occurred_at). max(ingested_at) по всей таблице
        # упирается в statement_timeout и не должен становиться алертом.
        last_ingest, probe_failed = await _last_collection_seen(db, now)
        prev_hour = await _count_pv(now - timedelta(hours=2), now - timedelta(hours=1))
        if collection_silence_due(
            last_seen=last_ingest,
            now=now,
            prev_hour_pageviews=prev_hour,
            probe_failed=probe_failed,
        ):
            if last_ingest is None:
                quiet = f"дольше {int(_COLLECTION_PROBE_WINDOW.total_seconds() // 60)} мин"
            else:
                quiet = f"{round((now - last_ingest).total_seconds() / 60)} мин"
            await _alert(
                "collection_silence",
                f"Собственный сбор молчит {quiet} "
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
    sticky = await _memory_sticky()
    episode = memory_pressure_episode(ratio, sticky=sticky)
    if episode == "clear":
        await _set_memory_sticky(False)
    elif episode == "alert" and ratio is not None:
        sent = await _alert(
            "memory_pressure",
            f"Память контейнера backend {round(ratio * 100)}% лимита "
            f"(порог {round(MEMORY_ALERT_RATIO * 100)}%).",
        )
        # Mute на 2 часа без sticky спрятал бы следующий шаг после TTL.
        # Sticky ставим только если алерт реально ушёл.
        if sent:
            await _set_memory_sticky(True)

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


BOT_CALIBRATION_TOLERANCE_PCT = 15  # сигнал для сверки, не критерий точности антибота


async def check_bot_calibration() -> dict | None:
    """Суточная сверка: небот-сессии против визитов Метрики за последний
    полный МСК-день. Это сверка доставки разных популяций, НЕ качество антибота.
    Raw Logs содержит роботов; подгонять к нему количество людей нельзя."""
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
            .where(ServerSession.day == last_metrika_day, ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
        ) or 0)

    if metrika_visits < 20:  # малая база — сверка статистически пуста
        return {"day": str(last_metrika_day), "metrika": metrika_visits, "ours": our_sessions, "skipped": True}

    ratio_pct = round(our_sessions / metrika_visits * 100)
    out = {"day": str(last_metrika_day), "metrika": metrika_visits, "ours": our_sessions, "ratio_pct": ratio_pct, "comparable_populations": False, "metrika_population": "all_raw_visits_including_robots", "own_population": "nonbot_noninternal_sessions"}
    if abs(ratio_pct - 100) > BOT_CALIBRATION_TOLERANCE_PCT:
        await _alert(
            "bot_calibration",
            f"Сверка сбора за {last_metrika_day}: наши небот-сессии {our_sessions} "
            f"против {metrika_visits} сырых визитов Метрики, включая роботов ({ratio_pct}%). "
            "Популяции различаются: проверить доставку и состав трафика, не подгонять веса антибота.",
        )
    logger.info("Bot calibration: %s", out)
    return out
