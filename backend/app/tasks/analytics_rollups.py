"""Вычислительный фундамент аналитики (ADR-0010, этап 2 плана «Аналитика 2.0»).

Каждые 15 минут (`rollups_15min_job`): серверная сессионизация последних
2 суток + инкремент rollup-таблиц + пороговые алерты-аномалии. Раз в сутки
ночью (`rollups_daily_job`): пересчёт длинного хвоста истории + синк словаря
целей Метрики из Management API.

Почему серверные сессии: клиентский session_id — техническая единица батчей
(sessionStorage живёт до закрытия вкладки). Метрика считает визитом
последовательность с разрывом < 30 минут — чтобы сверка «наши сессии vs
визиты Метрики» была корректна по определению, применяем то же правило на
сервере, поверх постоянного visitor_id.

Все операции идемпотентны: пересчитываемое окно очищается и наполняется
заново (delete + bulk insert в одной транзакции).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case, delete, func, select

from app.config import settings
from app.database import async_session
from app.models import (
    BehaviorEvent,
    BehaviorSession,
    DailyGoal,
    DailyPage,
    DailyTraffic,
    FrontendEvent,
    MetrikaGoal,
    RawMetrikaVisit,
    ServerSession,
)
from app.services.goal_taxonomy import TIER_MACRO, TIER_MICRO, tier_for_event

logger = logging.getLogger(__name__)

SESSION_GAP_MIN = 30  # правило Метрики: разрыв ≥ 30 минут = новая сессия

# lastTrafficSource Метрики → наши каналы (traffic_channel.CHANNELS)
METRIKA_SOURCE_TO_CHANNEL = {
    "organic": "search",
    "direct": "direct",
    "ad": "ad",
    "referral": "referral",
    "internal": "internal",
    "social": "social",
    "messenger": "social",
    "email": "campaign",
    "recommend": "referral",
    "saved": "direct",
    "undefined": "direct",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Серверная сессионизация
# ---------------------------------------------------------------------------

async def sessionize(db, since: datetime) -> int:
    """Пересчитать server_sessions для окна [since, now). Возвращает число сессий.

    Визитор без visitor_id (старые данные до 2026-07-06) сессионизируется по
    session_id_hash — исторические ряды не проваливаются в ноль.
    """
    rows = (await db.execute(
        select(
            BehaviorEvent.visitor_id_hash,
            BehaviorEvent.session_id_hash,
            BehaviorEvent.event_type,
            BehaviorEvent.occurred_at,
            BehaviorEvent.page,
            BehaviorEvent.user_id,
            BehaviorEvent.params_json,
        )
        .where(
            BehaviorEvent.occurred_at >= since,
            BehaviorEvent.event_type.in_(("pageview", "dwell", "click")),
        )
        .order_by(BehaviorEvent.occurred_at)
    )).all()

    # Портреты сессий: канал/устройство/бот-признак + ym/visitor склейка.
    portraits = {
        p.session_id_hash: p
        for p in (await db.execute(
            select(BehaviorSession).where(BehaviorSession.started_at >= since - timedelta(days=1))
        )).scalars()
    }

    # Бизнес-события окна: цели по tier'ам, привязка по session_id_hash.
    goal_rows = (await db.execute(
        select(FrontendEvent.session_id_hash, FrontendEvent.event_name, FrontendEvent.occurred_at)
        .where(FrontendEvent.occurred_at >= since, FrontendEvent.session_id_hash.isnot(None))
    )).all()
    goals_by_session: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for sid, name, ts in goal_rows:
        goals_by_session[sid].append((ts, name))

    by_visitor: dict[str, list] = defaultdict(list)
    for r in rows:
        key = r.visitor_id_hash or r.session_id_hash
        if key:
            by_visitor[key].append(r)

    # «Новизна»: первый ли это визит посетителя за всю историю.
    known_visitors: set[str] = set(
        (await db.execute(
            select(ServerSession.visitor_id_hash).where(ServerSession.started_at < since).distinct()
        )).scalars()
    )

    gap = timedelta(minutes=SESSION_GAP_MIN)
    sessions: list[dict[str, Any]] = []
    for visitor, evs in by_visitor.items():
        chunk: list = []
        for ev in evs:
            if chunk and ev.occurred_at - chunk[-1].occurred_at >= gap:
                sessions.append(_finalize_session(visitor, chunk, portraits, goals_by_session, known_visitors))
                known_visitors.add(visitor)
                chunk = []
            chunk.append(ev)
        if chunk:
            sessions.append(_finalize_session(visitor, chunk, portraits, goals_by_session, known_visitors))
            known_visitors.add(visitor)

    await db.execute(delete(ServerSession).where(ServerSession.started_at >= since))
    if sessions:
        await db.execute(ServerSession.__table__.insert(), sessions)
    await db.commit()
    return len(sessions)


def _finalize_session(visitor, evs, portraits, goals_by_session, known_visitors) -> dict[str, Any]:
    started, ended = evs[0].occurred_at, evs[-1].occurred_at
    pageviews = sum(1 for e in evs if e.event_type == "pageview")
    clicks = sum(1 for e in evs if e.event_type == "click")
    active_ms = 0
    max_scroll = 0
    for e in evs:
        if e.event_type == "dwell" and isinstance(e.params_json, dict):
            p = e.params_json
            active_ms += int(p.get("active_ms") or 0)
            max_scroll = max(max_scroll, int(p.get("scroll_pct") or 0))

    portrait = None
    for e in evs:
        if e.session_id_hash and e.session_id_hash in portraits:
            portrait = portraits[e.session_id_hash]
            break

    micro = macro = 0
    session_ids = {e.session_id_hash for e in evs if e.session_id_hash}
    for sid in session_ids:
        for ts, name in goals_by_session.get(sid, ()):  # только внутри окна сессии
            if started - timedelta(minutes=5) <= ts <= ended + timedelta(minutes=5):
                tier = tier_for_event(name)
                if tier == TIER_MICRO:
                    micro += 1
                elif tier == TIER_MACRO:
                    macro += 1

    engaged = active_ms > 15_000 or max_scroll > 50 or pageviews >= 2
    user_id = next((e.user_id for e in evs if e.user_id), None)
    return {
        "day": started.date(),
        "visitor_id_hash": visitor,
        "user_id": user_id,
        "started_at": started,
        "ended_at": ended,
        "duration_ms": int((ended - started).total_seconds() * 1000),
        "active_ms": active_ms,
        "pageviews": pageviews,
        "clicks": clicks,
        "max_scroll_pct": max_scroll,
        "entry_page": next((e.page for e in evs if e.page), None),
        "exit_page": next((e.page for e in reversed(evs) if e.page), None),
        "channel": portrait.channel if portrait else None,
        "device": portrait.device_type if portrait else None,
        "is_new_visitor": visitor not in known_visitors,
        "is_engaged": engaged,
        "micro_goals": micro,
        "macro_goals": macro,
        "is_bot": bool(portrait.is_webdriver) if portrait and portrait.is_webdriver is not None else False,
        "computed_at": _utcnow(),
    }


# ---------------------------------------------------------------------------
# Rollup'ы
# ---------------------------------------------------------------------------

def _visit_raw(v: RawMetrikaVisit, key: str) -> str:
    return ((v.raw_json or {}).get(key) or "").strip()


def _metrika_device(v: RawMetrikaVisit) -> str:
    from app.services.analytics_marts import METRIKA_DEVICE
    raw = _visit_raw(v, "ym:s:deviceCategory")
    return METRIKA_DEVICE.get(raw, raw or "")


def _metrika_channel(v: RawMetrikaVisit) -> str:
    return METRIKA_SOURCE_TO_CHANNEL.get((v.traffic_source or "").strip().lower(), "direct")


async def rollup_daily_traffic(db, since_day: date) -> int:
    """день × канал × устройство × новизна из raw_metrika_visits (визиты Метрики)."""
    from app.services.analytics_marts import visit_has_goals

    visits = (await db.execute(
        select(RawMetrikaVisit).where(RawMetrikaVisit.visit_date >= since_day)
    )).scalars().all()

    agg: dict[tuple, dict[str, Any]] = {}
    visitors: dict[tuple, set] = defaultdict(set)
    for v in visits:
        if not v.visit_date:
            continue
        key = (v.visit_date, _metrika_channel(v), _metrika_device(v), _visit_raw(v, "ym:s:isNewUser") == "1")
        a = agg.setdefault(key, {"visits": 0, "pageviews": 0, "goal_visits": 0, "total_duration_sec": 0, "bounces": 0})
        a["visits"] += 1
        try:
            a["pageviews"] += int(_visit_raw(v, "ym:s:pageViews") or 0)
        except ValueError:
            pass
        a["goal_visits"] += 1 if visit_has_goals(v) else 0
        a["total_duration_sec"] += int(v.duration_seconds or 0)
        a["bounces"] += 1 if _visit_raw(v, "ym:s:bounce") == "1" else 0
        if v.client_id_hash:
            visitors[key].add(v.client_id_hash)

    await db.execute(delete(DailyTraffic).where(DailyTraffic.day >= since_day))
    rows = [
        {
            "day": day, "channel": ch, "device": dev, "is_new": is_new,
            "visitors": len(visitors.get((day, ch, dev, is_new), ())),
            "computed_at": _utcnow(), **a,
        }
        for (day, ch, dev, is_new), a in agg.items()
    ]
    if rows:
        await db.execute(DailyTraffic.__table__.insert(), rows)
    await db.commit()
    return len(rows)


async def rollup_daily_goals(db, since_day: date) -> int:
    """день × событие (SQL GROUP BY по frontend_events; tier из таксономии)."""
    since_dt = datetime.combine(since_day, datetime.min.time())
    rows = (await db.execute(
        select(
            func.date(FrontendEvent.occurred_at).label("day"),
            FrontendEvent.event_name,
            func.count().label("cnt"),
            func.count(func.distinct(FrontendEvent.session_id_hash)).label("sessions"),
            func.sum(case((FrontendEvent.authed.is_(True), 1), else_=0)).label("authed_cnt"),
        )
        .where(FrontendEvent.occurred_at >= since_dt)
        .group_by(func.date(FrontendEvent.occurred_at), FrontendEvent.event_name)
    )).all()

    await db.execute(delete(DailyGoal).where(DailyGoal.day >= since_day))
    out = []
    for day, name, cnt, sessions, authed_cnt in rows:
        d = date.fromisoformat(day) if isinstance(day, str) else day
        out.append({
            "day": d, "event_name": name, "tier": tier_for_event(name),
            "count": int(cnt), "sessions": int(sessions or 0),
            "authed_count": int(authed_cnt or 0), "computed_at": _utcnow(),
        })
    if out:
        await db.execute(DailyGoal.__table__.insert(), out)
    await db.commit()
    return len(out)


async def rollup_daily_pages(db, since_day: date) -> int:
    """день × страница из behavior_events: просмотры, dwell, dead-клики."""
    since_dt = datetime.combine(since_day, datetime.min.time())

    pv = (await db.execute(
        select(
            func.date(BehaviorEvent.occurred_at).label("day"),
            BehaviorEvent.page,
            func.count().label("views"),
            func.count(func.distinct(func.coalesce(BehaviorEvent.visitor_id_hash, BehaviorEvent.session_id_hash))).label("visitors"),
        )
        .where(BehaviorEvent.occurred_at >= since_dt, BehaviorEvent.event_type == "pageview", BehaviorEvent.page.isnot(None))
        .group_by(func.date(BehaviorEvent.occurred_at), BehaviorEvent.page)
    )).all()

    dead = dict(((str(day), page), int(cnt)) for day, page, cnt in (await db.execute(
        select(func.date(BehaviorEvent.occurred_at), BehaviorEvent.page, func.count())
        .where(BehaviorEvent.occurred_at >= since_dt, BehaviorEvent.event_type == "click",
               BehaviorEvent.is_dead.is_(True), BehaviorEvent.page.isnot(None))
        .group_by(func.date(BehaviorEvent.occurred_at), BehaviorEvent.page)
    )).all())

    # dwell: params_json → стримим только нужные колонки окна (объём дней мал)
    dwell_rows = (await db.execute(
        select(BehaviorEvent.occurred_at, BehaviorEvent.page, BehaviorEvent.params_json)
        .where(BehaviorEvent.occurred_at >= since_dt, BehaviorEvent.event_type == "dwell", BehaviorEvent.page.isnot(None))
    )).all()
    dwell: dict[tuple, dict[str, int]] = defaultdict(lambda: {"ms": 0, "active": 0, "scroll_sum": 0, "n": 0})
    for ts, page, params in dwell_rows:
        if not isinstance(params, dict):
            continue
        d = dwell[(ts.date().isoformat(), page)]
        d["ms"] += int(params.get("ms") or 0)
        d["active"] += int(params.get("active_ms") or 0)
        d["scroll_sum"] += int(params.get("scroll_pct") or 0)
        d["n"] += 1

    await db.execute(delete(DailyPage).where(DailyPage.day >= since_day))
    out = []
    for day, page, views, visitors in pv:
        key = (str(day), page)
        dw = dwell.get(key)
        d = date.fromisoformat(day) if isinstance(day, str) else day
        out.append({
            "day": d, "page": page[:500], "views": int(views), "visitors": int(visitors or 0),
            "total_dwell_ms": dw["ms"] if dw else 0,
            "total_active_ms": dw["active"] if dw else 0,
            "avg_scroll_pct": round(dw["scroll_sum"] / dw["n"], 1) if dw and dw["n"] else None,
            "dead_clicks": dead.get(key, 0),
            "computed_at": _utcnow(),
        })
    if out:
        await db.execute(DailyPage.__table__.insert(), out)
    await db.commit()
    return len(out)


# ---------------------------------------------------------------------------
# Словарь целей Метрики (Management API)
# ---------------------------------------------------------------------------

async def sync_metrika_goals(db) -> int:
    """goal_id → имя/событие/tier. Числа goals_json становятся читаемыми."""
    if not settings.yandex_metrika_read_token:
        return 0
    from app.services.yandex_metrika_management import MetrikaManagementClient

    counter_id = (settings.analytics_allowed_counter_ids or "").split(",")[0].strip()
    if not counter_id:
        return 0
    try:
        resp = await MetrikaManagementClient().goals(counter_id)
        goals = (resp.data or {}).get("goals") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Metrika goals sync failed: %s", exc)
        return 0

    stored = 0
    for g in goals:
        gid = g.get("id")
        if not gid:
            continue
        # Для JS-целей (action) имя события лежит в conditions[].url.
        event_name = None
        for cond in g.get("conditions") or []:
            if cond.get("type") == "exact" or g.get("type") == "action":
                event_name = (cond.get("url") or "")[:120] or None
                break
        existing = await db.get(MetrikaGoal, int(gid))
        values = {
            "name": (g.get("name") or "")[:300] or None,
            "event_name": event_name,
            "tier": tier_for_event(event_name) if event_name else None,
            "synced_at": _utcnow(),
        }
        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            db.add(MetrikaGoal(goal_id=int(gid), **values))
        stored += 1
    await db.commit()
    logger.info("Metrika goals dict synced: %d goals", stored)
    return stored


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

async def run_rollups(days: int = 2) -> dict[str, int]:
    """Общий прогон: сессионизация + все rollup'ы для окна N дней."""
    since_dt = _utcnow() - timedelta(days=days)
    since_day = since_dt.date()
    async with async_session() as db:
        n_sessions = await sessionize(db, since_dt)
        n_traffic = await rollup_daily_traffic(db, since_day)
        n_goals = await rollup_daily_goals(db, since_day)
        n_pages = await rollup_daily_pages(db, since_day)
    return {"sessions": n_sessions, "traffic": n_traffic, "goals": n_goals, "pages": n_pages}


async def rollups_15min_job() -> None:
    """Инкремент последних 2 суток + пороговые алерты. Каждые 15 минут."""
    try:
        stats = await run_rollups(days=2)
        logger.info("Rollups 15min: %s", stats)
    except Exception:
        logger.exception("Rollups 15min failed")
    try:
        from app.services.analytics_alerts import check_anomalies
        await check_anomalies()
    except Exception:
        logger.exception("Anomaly check failed")


async def rollups_daily_job() -> None:
    """Ночной пересчёт хвоста истории (60 дней) + синк словаря целей."""
    try:
        stats = await run_rollups(days=60)
        logger.info("Rollups daily: %s", stats)
    except Exception:
        logger.exception("Rollups daily failed")
    try:
        async with async_session() as db:
            await sync_metrika_goals(db)
    except Exception:
        logger.exception("Metrika goals sync failed")
