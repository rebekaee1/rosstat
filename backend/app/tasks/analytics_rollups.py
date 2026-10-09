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
import json
from types import SimpleNamespace
from uuid import uuid4
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import BigInteger, Column, Index, Integer, MetaData, Table, and_, case, cast, delete, func, or_, select, text
from sqlalchemy.schema import CreateIndex, CreateTable, DropTable

from app.config import settings
from app.database import analytics_session
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
from app.services import session_change_log
from app.services.analytics_period import msk_day, msk_day_expr
from app.services.goal_taxonomy import TIER_MACRO, TIER_MICRO, is_conversion, tier_for_event
from app.services.traffic_channel import classify_channel

logger = logging.getLogger(__name__)

SESSION_GAP_MIN = 30  # правило Метрики: разрыв ≥ 30 минут = новая сессия
# Окно одного прохода сессионизации (МСК-дни). 15-минутный прогон (2 суток)
# укладывается в одно окно; ночной 60-дневный — в ~20 окон с ограниченной памятью.
SESSIONIZE_WINDOW_DAYS = 3
_SESSION_EVENT_TYPES = ("pageview", "dwell", "click", "move")
# Потоковое чтение длинных окон (визиты Метрики, dwell) — строк за раз.
_STREAM_BATCH = 5_000
# Ключи raw_json визита, которые читает rollup_daily_traffic.
_TRAFFIC_JSON_KEYS = (
    "ym:s:deviceCategory", "ym:s:isNewUser", "ym:s:pageViews", "ym:s:bounce",
    # Признаки робота (visit_is_robot): визиты роботов в витрину не идут.
    "ym:s:browser", "ym:s:isRobot", "ym:s:isRobotPro",
)

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

def _session_epoch_us(column):
    """Exact fixture timestamps; julianday rounds a30min boundary incorrectly."""
    return (cast(func.strftime("%s", func.substr(column, 1, 19)), BigInteger) * 1_000_000
            + cast(func.substr(column, 21, 6), Integer))


def _session_time_between(column, start, end, minutes: int, dialect: str):
    """Inclusive logical-session margins; SQLite is only a hermetic fixture."""
    if dialect == "sqlite":
        margin = minutes * 60 * 1_000_000
        return and_(_session_epoch_us(column) >= _session_epoch_us(start) - margin,
                    _session_epoch_us(column) <= _session_epoch_us(end) + margin)
    margin = timedelta(minutes=minutes)
    return and_(column >= start - margin, column <= end + margin)


def _session_history_query(db, since: datetime, until: datetime, visitors=None):
    """Resolve logical ownership in SQL, including history of window visitors.

    A fixed30min halo cannot recover a long continuous chain or a delayed
    pageviewless tail. SQL examines older raw rows of visitors present in this
    window; Python never loads that history or an all-visitor dictionary.
    """
    dialect = db.bind.dialect.name
    key = func.coalesce(func.nullif(BehaviorEvent.visitor_id_hash, ""),
                        func.nullif(BehaviorEvent.session_id_hash, ""))
    window_visitors = select(key.label("visitor")).where(
        BehaviorEvent.occurred_at >= since, BehaviorEvent.occurred_at < until,
        BehaviorEvent.event_type.in_(_SESSION_EVENT_TYPES), key.isnot(None),
    ).distinct()
    order = (BehaviorEvent.occurred_at, BehaviorEvent.id)
    params = BehaviorEvent.params_json
    is_object = (func.json_type(params) == "object" if dialect == "sqlite"
                 else func.json_typeof(params) == "object")
    # Move/click payloads can contain large polylines. Project only six fields
    # consumed below, while retaining the distinction between dict and null.
    names = ("ref", "touch", "vw", "synthetic", "active_ms", "scroll_pct")
    pairs = []
    for name in names:
        pairs.extend((name, func.json_extract(params, "$." + name) if dialect == "sqlite" else params[name]))
    compact_json = (func.json_object(*pairs) if dialect == "sqlite"
                    else func.json_build_object(*pairs))
    projected = case((is_object, compact_json), else_=None).label("params_json")
    ordered = select(
        key.label("visitor"), BehaviorEvent.id, BehaviorEvent.session_id_hash,
        BehaviorEvent.event_type, BehaviorEvent.occurred_at, BehaviorEvent.page,
        BehaviorEvent.user_id, projected,
        func.lag(BehaviorEvent.occurred_at).over(partition_by=key, order_by=order).label("previous"),
    ).where(
        BehaviorEvent.event_type.in_(_SESSION_EVENT_TYPES),
        BehaviorEvent.occurred_at < until,
    )
    ordered = (ordered.where(key.in_(window_visitors)) if visitors is None else
               ordered.join(visitors, key == visitors.c.visitor))
    ordered = ordered.cte("session_events")
    gap = (_session_epoch_us(ordered.c.occurred_at) >= _session_epoch_us(ordered.c.previous) + SESSION_GAP_MIN * 60 * 1_000_000
           if dialect == "sqlite" else ordered.c.occurred_at >= ordered.c.previous + timedelta(minutes=SESSION_GAP_MIN))
    burst = func.sum(case((or_(ordered.c.previous.is_(None), gap), 1), else_=0)).over(
        partition_by=ordered.c.visitor, order_by=(ordered.c.occurred_at, ordered.c.id), rows=(None, 0),
    )
    bursts = select(ordered, burst.label("burst")).cte("session_bursts")
    burst_key = (bursts.c.visitor, bursts.c.burst)
    marked = select(
        bursts,
        func.min(bursts.c.occurred_at).over(partition_by=burst_key).label("burst_start"),
        func.max(case((bursts.c.event_type == "pageview", 1), else_=0)).over(partition_by=burst_key).label("has_pageview"),
    ).cte("session_burst_marks")
    logical_start = func.max(case((marked.c.has_pageview == 1, marked.c.burst_start), else_=None)).over(
        partition_by=marked.c.visitor, order_by=(marked.c.occurred_at, marked.c.id), rows=(None, 0),
    )
    return select(marked.c.visitor, marked.c.id, marked.c.session_id_hash,
        marked.c.event_type, marked.c.occurred_at, marked.c.page, marked.c.user_id,
        marked.c.params_json, logical_start.label("logical_start"))


async def _prepare_session_history(db, since: datetime, until: datetime, temporary: list):
    """Indexed SQL ownership stages have fresh stats even for cold raw tables.

    Historical work lives in PostgreSQL temporary storage, not Python lists.
    ANALYZE touches only these private transaction-scoped stages.
    """
    visitors = Table("sessionize_visitors_" + uuid4().hex, MetaData(),
        Column("visitor", BehaviorEvent.visitor_id_hash.type, primary_key=True),
        prefixes=["TEMPORARY"], postgresql_on_commit="DROP")
    temporary.append(visitors)
    await db.execute(CreateTable(visitors))
    key = func.coalesce(func.nullif(BehaviorEvent.visitor_id_hash, ""),
                        func.nullif(BehaviorEvent.session_id_hash, ""))
    await db.execute(visitors.insert().from_select(["visitor"], select(key).where(
        BehaviorEvent.occurred_at >= since, BehaviorEvent.occurred_at < until,
        BehaviorEvent.event_type.in_(_SESSION_EVENT_TYPES), key.isnot(None),
    ).distinct()))
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("ANALYZE " + visitors.name))
    history = Table("sessionize_history_" + uuid4().hex, MetaData(),
        Column("visitor", BehaviorEvent.visitor_id_hash.type),
        *(Column(name, BehaviorEvent.__table__.c[name].type) for name in
          ("id", "session_id_hash", "event_type", "occurred_at", "page", "user_id", "params_json")),
        Column("logical_start", BehaviorEvent.occurred_at.type),
        prefixes=["TEMPORARY"], postgresql_on_commit="DROP")
    temporary.append(history)
    await db.execute(CreateTable(history))
    await db.execute(history.insert().from_select(
        [c.name for c in history.columns], _session_history_query(db, since, until, visitors)))
    await db.execute(CreateIndex(Index("ix_" + history.name, history.c.visitor, history.c.logical_start)))
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("ANALYZE " + history.name))
    return history


def _session_source_query(db, since: datetime, until: datetime, events=None):
    """Join compact logical-session bounds, goals and portraits in SQL."""
    dialect = db.bind.dialect.name
    if events is None:
        events = _session_history_query(db, since, until).cte("logical_session_events")
    keys = (events.c.visitor, events.c.logical_start)
    all_bounds = select(
        *keys, func.max(events.c.occurred_at).label("logical_end"),
    ).where(events.c.logical_start.isnot(None)).group_by(*keys).cte("all_session_bounds")
    day = msk_day_expr(all_bounds.c.logical_start, dialect)
    counts = select(
        all_bounds,
        func.count().over(partition_by=(all_bounds.c.visitor, day)).label("visitor_sessions"),
        func.min(all_bounds.c.logical_start).over(partition_by=all_bounds.c.visitor).label("first_start"),
    ).cte("session_day_counts")
    bounds = select(counts).where(counts.c.logical_end >= since).cte("touched_session_bounds")
    sids = select(*keys, events.c.session_id_hash).join(
        bounds, and_(events.c.visitor == bounds.c.visitor, events.c.logical_start == bounds.c.logical_start),
    ).where(events.c.session_id_hash.isnot(None), events.c.session_id_hash != "").distinct().cte("logical_session_client_ids")
    from app.services.goal_taxonomy import explicit_events
    micro_names = sorted(name for name in explicit_events() if tier_for_event(name) == TIER_MICRO)
    macro_names = sorted(name for name in explicit_events() if tier_for_event(name) == TIER_MACRO)
    goals = select(
        sids.c.visitor, sids.c.logical_start,
        func.sum(case((FrontendEvent.event_name.in_(micro_names), 1), else_=0)).label("micro_goals"),
        func.sum(case((FrontendEvent.event_name.in_(macro_names), 1), else_=0)).label("macro_goals"),
    ).join(bounds, and_(sids.c.visitor == bounds.c.visitor, sids.c.logical_start == bounds.c.logical_start)).join(
        FrontendEvent, and_(FrontendEvent.session_id_hash == sids.c.session_id_hash,
            _session_time_between(FrontendEvent.occurred_at, bounds.c.logical_start, bounds.c.logical_end, 5, dialect)),
    ).group_by(sids.c.visitor, sids.c.logical_start).cte("logical_session_goals")
    fallback = select(BehaviorSession.session_id_hash).where(
        BehaviorSession.visitor_id_hash == bounds.c.visitor,
        and_(
            BehaviorSession.started_at <= bounds.c.logical_end,
            (_session_epoch_us(BehaviorSession.started_at) >= _session_epoch_us(bounds.c.logical_start) - 86_400_000_000
             if dialect == "sqlite" else BehaviorSession.started_at >= bounds.c.logical_start - timedelta(days=1)),
        ),
    ).order_by(BehaviorSession.started_at.desc(), BehaviorSession.session_id_hash).limit(1).correlate(bounds).scalar_subquery()
    earlier = select(ServerSession.id).where(
        ServerSession.visitor_id_hash == bounds.c.visitor, ServerSession.started_at < bounds.c.first_start,
    ).exists()
    details = select(bounds, fallback.label("fallback_sid"),
        and_(bounds.c.logical_start == bounds.c.first_start, ~earlier).label("is_new_visitor"),
    ).cte("session_attribution").prefix_with("MATERIALIZED", dialect="postgresql")
    return select(
        events, details.c.logical_end, details.c.visitor_sessions, details.c.is_new_visitor,
        details.c.fallback_sid, func.coalesce(goals.c.micro_goals, 0).label("micro_goals"),
        func.coalesce(goals.c.macro_goals, 0).label("macro_goals"),
    ).join(details, and_(events.c.visitor == details.c.visitor, events.c.logical_start == details.c.logical_start)).outerjoin(
        goals, and_(goals.c.visitor == details.c.visitor, goals.c.logical_start == details.c.logical_start),
    ).order_by(events.c.visitor, events.c.logical_start, events.c.occurred_at, events.c.id)


class _SessionAccumulator:
    """Constant-size sufficient statistics; no raw event list or SID set."""
    def __init__(self, event, portraits):
        self.visitor = event.visitor
        self.started = event.logical_start
        self.ended = event.logical_end
        self.is_new = event.is_new_visitor
        self.visitor_sessions = event.visitor_sessions
        self.goals = (event.micro_goals, event.macro_goals)
        self.fallback = portraits.get(event.fallback_sid)
        self.own = None
        self.first_pv = None
        self.entry = self.exit = self.user_id = None
        self.counts = defaultdict(int)
        self.active_ms = self.scroll = self.synthetic = 0
        self.admin_page = False

    def add(self, event, portraits):
        self.counts[event.event_type] += 1
        params = event.params_json
        if isinstance(params, str):
            params = json.loads(params)
        if isinstance(params, dict):
            if event.event_type == "dwell":
                self.active_ms += int(params.get("active_ms") or 0)
                self.scroll = max(self.scroll, int(params.get("scroll_pct") or 0))
            if event.event_type == "click" and params.get("synthetic"):
                self.synthetic += 1
            if event.event_type == "pageview" and self.first_pv is None:
                self.first_pv = params
        candidate = portraits.get(event.session_id_hash)
        if self.own is None and candidate is not None and candidate.started_at <= self.ended:
            self.own = candidate
        if event.page:
            self.entry = self.entry or event.page
            self.exit = event.page
            self.admin_page |= event.page.startswith("/admin")
        self.user_id = self.user_id or event.user_id

    def finish(self, admin_users, admin_visitors):
        # A fixed-size adapter keeps the established finalizer/score semantics.
        def event(kind, *, page=None, params=None, weight=1, sid=None, user=None, ended=False):
            return SimpleNamespace(event_type=kind, occurred_at=self.ended if ended else self.started,
                                   page=page, params_json=params, weight=weight, session_id_hash=sid, user_id=user)
        sid = self.own.session_id_hash if self.own else None
        evs = [event("boundary", page=self.entry, sid=sid, user=self.user_id),
               event("pageview", params=self.first_pv, weight=self.counts["pageview"]),
               event("click", params={"synthetic": True}, weight=self.synthetic),
               event("click", weight=self.counts["click"] - self.synthetic),
               event("move", weight=self.counts["move"]),
               event("dwell", params={"active_ms": self.active_ms, "scroll_pct": self.scroll}),
               event("boundary", page=self.exit, ended=True)]
        row = _finalize_session(self.visitor, evs, {sid: self.own} if self.own else {}, {},
            set() if self.is_new else {self.visitor}, self.visitor_sessions,
            fallback_portrait=self.fallback, goal_counts=self.goals)
        row["is_internal"] = self.admin_page or self.visitor in admin_visitors or self.user_id in admin_users
        return row


async def sessionize(db, since: datetime, until: datetime | None = None) -> int:
    """Recompute touched logical sessions; return starts owned by [since,until).

    SQL resolves historical continuity for window visitors. Python uses source
    and write batches of at most 5k rows, portrait lookup keys of at most 10k
    SIDs and one compact accumulator, even for a chain spanning many windows.
    Existing admin identity sets are separate allocations, not covered by this
    batch bound. Left-owner rows are repaired atomically with this window;
    their day remains the original MSK start day.
    F05b: при RUSTATS_CLICKHOUSE_ENABLED исчезнувшие/новые/изменённые ключи
    сессий пишутся в `server_session_changes` в той же транзакции.
    """
    from app.services.analytics_marts import admin_identity
    stop = until or _utcnow()
    if stop <= since:
        return 0
    stage = Table("sessionize_stage_" + uuid4().hex, MetaData(),
                  *(Column(c.name, c.type, nullable=c.nullable) for c in ServerSession.__table__.columns if c.name != "id"),
                  prefixes=["TEMPORARY"], postgresql_on_commit="DROP")
    temporary = [stage]
    # F05b: «как было» нужно только для журнала изменений CH-копии.
    track = session_change_log.enabled()
    previous = session_change_log.snapshot_table("sessionize_prev_" + uuid4().hex) if track else None
    try:
        await db.execute(CreateTable(stage))
        if track:
            temporary.append(previous)
            await db.execute(CreateTable(previous))
        history = await _prepare_session_history(db, since, stop, temporary)
        admin_users, admin_visitors = await admin_identity(db)
        result = await db.stream(_session_source_query(db, since, stop, history).execution_options(yield_per=_STREAM_BATCH))
        current = None
        output = []
        owned = 0
        try:
            async for part in result.partitions(_STREAM_BATCH):
                needed = {sid for event in part for sid in (event.session_id_hash, event.fallback_sid) if sid}
                portraits = {p.session_id_hash: p for p in (await db.execute(select(
                    BehaviorSession.session_id_hash, BehaviorSession.started_at, BehaviorSession.channel, BehaviorSession.referrer,
                    BehaviorSession.utm_source, BehaviorSession.utm_medium, BehaviorSession.yclid,
                    BehaviorSession.device_type, BehaviorSession.is_webdriver, BehaviorSession.ua_raw,
                    BehaviorSession.touch, BehaviorSession.screen_w, BehaviorSession.screen_h, BehaviorSession.cpu_cores,
                    BehaviorSession.site_locale,
                ).where(BehaviorSession.session_id_hash.in_(needed)))).all()} if needed else {}
                for event in part:
                    key = (event.visitor, event.logical_start)
                    if current is None or (current.visitor, current.started) != key:
                        if current is not None:
                            output.append(current.finish(admin_users, admin_visitors))
                            owned += current.started >= since
                        current = _SessionAccumulator(event, portraits)
                    current.add(event, portraits)
                    if len(output) >= _STREAM_BATCH:
                        await db.execute(stage.insert(), output)
                        output.clear()
            if current is not None:
                output.append(current.finish(admin_users, admin_visitors))
                owned += current.started >= since
            if output:
                await db.execute(stage.insert(), output)
        finally:
            await result.close()
        # Delete old splits and repair left ownership, without erasing unrelated
        # visitors or later sessions beyond this explicit source cutoff.
        carried = select(stage.c.visitor_id_hash, func.min(stage.c.started_at).label("first_start")).where(
            stage.c.started_at < since,
        ).group_by(stage.c.visitor_id_hash).subquery()
        in_window = and_(ServerSession.started_at >= since, ServerSession.started_at < stop)
        matches = and_(ServerSession.visitor_id_hash == carried.c.visitor_id_hash,
                       ServerSession.started_at >= carried.c.first_start)
        if db.bind.dialect.name == "sqlite":
            matches = select(carried.c.visitor_id_hash).where(matches).exists()
        left_owner = and_(ServerSession.started_at < since, matches)
        if track:
            # Два отдельных INSERT…SELECT: у left_owner неявный FROM carried (PG).
            await session_change_log.snapshot(db, previous, in_window)
            await session_change_log.snapshot(db, previous, left_owner)
        await db.execute(delete(ServerSession).where(in_window))
        await db.execute(delete(ServerSession).where(left_owner))
        columns = [c.name for c in stage.columns]
        await db.execute(ServerSession.__table__.insert().from_select(columns, select(*stage.columns)))
        if track:
            # F05b: исчезнувшие/новые/изменённые ключи — в ту же транзакцию.
            await session_change_log.record_window_changes(db, previous, stage)
        # asyncpg retains the exhausted server portal until transaction end.
        # PostgreSQL closes it before ON COMMIT DROP; explicit DROP of the
        # streamed history table would fail with ObjectInUseError here.
        if db.bind.dialect.name == "sqlite":
            for table in reversed(temporary):
                await db.execute(DropTable(table))
        await db.commit()
        return owned
    except BaseException:
        await db.rollback()
        # PostgreSQL rolls back CREATE/ON COMMIT DROP itself. SQLite's DDL
        # fixture may retain its temporary table on a reused pooled connection.
        if db.bind.dialect.name == "sqlite":
            try:
                for table in reversed(temporary):
                    await db.execute(DropTable(table, if_exists=True))
                await db.commit()
            except Exception:
                await db.rollback()
        raise



def _infer_from_pageviews(evs) -> tuple[str | None, str | None, bool]:
    """(channel, device, has_signal) из потока событий сессии — когда портрета
    нет вовсе (ретро до 2026-07-06 или потерянный session_start).

    behavior.js шлёт document.referrer в КАЖДОМ pageview (params.ref) —
    канал первого pageview честно классифицируется referrer'ом входа.
    Устройство — эвристика по touch/viewport первого pageview. Волна 2, п. 1.
    """
    first_pv = next(
        (e for e in evs
         if e.event_type == "pageview" and isinstance(e.params_json, dict)),
        None,
    )
    if first_pv is None:
        return None, None, False
    p = first_pv.params_json
    ref = str(p.get("ref") or "") or None
    channel = classify_channel(referrer=ref)
    touch = p.get("touch")
    vw = p.get("vw") if isinstance(p.get("vw"), (int, float)) else None
    device = None
    if touch is not None or vw is not None:
        if touch and (vw or 0) <= 820:
            device = "mobile"
        elif touch:
            device = "tablet"
        elif vw:
            device = "desktop"
    return channel, device, True


def _finalize_session(visitor, evs, portraits, goals_by_session, known_visitors,
                      visitor_sessions: int = 1, fallback_portrait=None, goal_counts=None) -> dict[str, Any]:
    from app.services.bot_score import BOT_THRESHOLD, SessionSignals, score_session

    started, ended = evs[0].occurred_at, evs[-1].occurred_at
    pageviews = sum(getattr(e, "weight", 1) for e in evs if e.event_type == "pageview")
    clicks = sum(getattr(e, "weight", 1) for e in evs if e.event_type == "click")
    moves = sum(getattr(e, "weight", 1) for e in evs if e.event_type == "move")
    synthetic_clicks = sum(
        getattr(e, "weight", 1) for e in evs
        if e.event_type == "click" and isinstance(e.params_json, dict) and e.params_json.get("synthetic")
    )
    active_ms = 0
    max_scroll = 0
    for e in evs:
        if e.event_type == "dwell" and isinstance(e.params_json, dict):
            p = e.params_json
            active_ms += int(p.get("active_ms") or 0)
            max_scroll = max(max_scroll, int(p.get("scroll_pct") or 0))

    own_portrait = None
    for e in evs:
        if e.session_id_hash and e.session_id_hash in portraits:
            own_portrait = portraits[e.session_id_hash]
            break
    # Портрет этой клиентской сессии потерян — берём последний портрет того же
    # посетителя (устройство/UA стабильны; канал — приближение, но лучше пустоты).
    portrait = own_portrait or fallback_portrait

    # Канал и устройство (волна 2, п. 1): собственный портрет — истина;
    # без него канал берём из referrer'а первого pageview ЭТОЙ сессии
    # (точнее, чем канал другой сессии посетителя), устройство — из
    # fallback-портрета либо эвристики touch/viewport. Честный остаток
    # без всяких признаков — «direct», НЕ пустота.
    if own_portrait is not None:
        channel = own_portrait.channel or classify_channel(
            referrer=own_portrait.referrer,
            utm_source=own_portrait.utm_source,
            utm_medium=own_portrait.utm_medium,
            yclid=own_portrait.yclid,
        )
        device = own_portrait.device_type
    else:
        ev_channel, ev_device, has_signal = _infer_from_pageviews(evs)
        if has_signal:
            channel = ev_channel
        elif fallback_portrait is not None:
            channel = fallback_portrait.channel or classify_channel(
                referrer=fallback_portrait.referrer,
                utm_source=fallback_portrait.utm_source,
                utm_medium=fallback_portrait.utm_medium,
                yclid=fallback_portrait.yclid,
            )
        else:
            channel = "direct"
        device = (fallback_portrait.device_type if fallback_portrait else None) or ev_device

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

    if goal_counts is not None:
        micro, macro = goal_counts

    engaged = active_ms > 15_000 or max_scroll > 50 or pageviews >= 2
    user_id = next((e.user_id for e in evs if e.user_id), None)

    bot = score_session(SessionSignals(
        pageviews=pageviews,
        clicks=clicks,
        moves=moves,
        active_ms=active_ms,
        max_scroll_pct=max_scroll,
        synthetic_clicks=synthetic_clicks,
        visitor_sessions=visitor_sessions,
        has_portrait=portrait is not None,
        is_webdriver=bool(portrait.is_webdriver) if portrait else False,
        ua_raw=portrait.ua_raw if portrait else None,
        device_type=portrait.device_type if portrait else None,
        touch=portrait.touch if portrait else None,
        screen_w=portrait.screen_w if portrait else None,
        screen_h=portrait.screen_h if portrait else None,
        cpu_cores=portrait.cpu_cores if portrait else None,
    ))
    return {
        "day": msk_day(started),  # день сессии — МСК (BI 2.1)
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
        "channel": channel,
        "device": device,
        # Язык сайта (круг 11): портрет сессии, иначе портрет того же посетителя.
        "site_locale": getattr(portrait, "site_locale", None) if portrait else None,
        "is_new_visitor": visitor not in known_visitors,
        "is_engaged": engaged,
        "micro_goals": micro,
        "macro_goals": macro,
        "is_bot": bot >= BOT_THRESHOLD,
        "bot_score": bot,
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
    """день × канал × устройство × новизна из raw_metrika_visits (визиты Метрики).

    goal_visits — только business-tier цели (этап 2б BI 2.1): авто-цели
    (скролл, показы, ошибки) конверсией не считаются. Визиты роботов
    (visit_is_robot, в т.ч. headless-браузеры) не считаются вовсе.
    """
    from app.services.analytics_marts import (
        business_goal_ids,
        visit_has_business_goal,
        visit_is_robot,
    )

    biz_ids = await business_goal_ids(db)
    # Только нужные колонки и, на Postgres, только нужные ключи raw_json
    # (~1 КБ на визит), потоком: ночное окно 60 дней — ~94k визитов.
    base = [
        RawMetrikaVisit.visit_date,
        RawMetrikaVisit.client_id_hash,
        RawMetrikaVisit.duration_seconds,
        RawMetrikaVisit.goals_json,
        RawMetrikaVisit.traffic_source,
    ]
    pg = db.bind is not None and db.bind.dialect.name == "postgresql"
    if pg:
        raw_cols = [
            RawMetrikaVisit.raw_json[key].as_string().label(f"jk{i}")
            for i, key in enumerate(_TRAFFIC_JSON_KEYS)
        ]
    else:
        raw_cols = [RawMetrikaVisit.raw_json]
    result = await db.stream(
        select(*base, *raw_cols)
        .where(RawMetrikaVisit.visit_date >= since_day)
        .execution_options(yield_per=_STREAM_BATCH)
    )

    agg: dict[tuple, dict[str, Any]] = {}
    visitors: dict[tuple, set] = defaultdict(set)
    try:
        async for part in result.partitions(_STREAM_BATCH):
            for row in part:
                visit_date, client_id_hash, duration_seconds, goals_json, traffic_source = row[:5]
                if not visit_date:
                    continue
                if pg:
                    raw_json = {
                        k: row[5 + i] for i, k in enumerate(_TRAFFIC_JSON_KEYS) if row[5 + i]
                    }
                else:
                    raw_json = row[5]
                stub = RawMetrikaVisit(
                    visit_date=visit_date,
                    client_id_hash=client_id_hash,
                    duration_seconds=duration_seconds,
                    goals_json=goals_json,
                    traffic_source=traffic_source,
                    raw_json=raw_json,
                )
                if visit_is_robot(stub):
                    continue
                key = (
                    visit_date, _metrika_channel(stub), _metrika_device(stub),
                    _visit_raw(stub, "ym:s:isNewUser") == "1",
                )
                a = agg.setdefault(key, {
                    "visits": 0, "pageviews": 0, "goal_visits": 0,
                    "total_duration_sec": 0, "bounces": 0,
                })
                a["visits"] += 1
                try:
                    a["pageviews"] += int(_visit_raw(stub, "ym:s:pageViews") or 0)
                except ValueError:
                    pass
                a["goal_visits"] += 1 if visit_has_business_goal(stub, biz_ids) else 0
                a["total_duration_sec"] += int(duration_seconds or 0)
                a["bounces"] += 1 if _visit_raw(stub, "ym:s:bounce") == "1" else 0
                if client_id_hash:
                    visitors[key].add(client_id_hash)
    finally:
        await result.close()

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
    """день × событие (SQL GROUP BY по frontend_events; день — МСК).

    E6 (круг 11): роботы и собственная активность владельца/админов исключены —
    так же, как в воронке и `mart_pwa_installs`. Сессионизация в `run_rollups`
    выполняется раньше, поэтому флаги `is_bot/is_internal` уже свежие.
    """
    from app.services.analytics_marts import human_event_conditions
    from app.services.analytics_period import msk_day_start_utc

    since_dt = msk_day_start_utc(since_day)
    day_expr = msk_day_expr(FrontendEvent.occurred_at, db.bind.dialect.name)
    human = await human_event_conditions(db, since_day, msk_day(_utcnow()))
    rows = (await db.execute(
        select(
            day_expr.label("day"),
            FrontendEvent.event_name,
            func.count().label("cnt"),
            func.count(func.distinct(FrontendEvent.session_id_hash)).label("sessions"),
            func.sum(case((FrontendEvent.authed.is_(True), 1), else_=0)).label("authed_cnt"),
        )
        .where(FrontendEvent.occurred_at >= since_dt, *human)
        .group_by(day_expr, FrontendEvent.event_name)
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


# События, для которых строим разрезы в `daily_goal_dims`: группы отчётов (скачивания,
# упоры в стену, сравнение, калькуляторы, поделились, избранное, подписки, язык).
_DIM_NAMES_CACHE: list[str] | None = None


def _dim_event_names() -> list[str]:
    global _DIM_NAMES_CACHE
    if _DIM_NAMES_CACHE is None:
        from app.services.goal_taxonomy import all_grouped_events

        _DIM_NAMES_CACHE = sorted(all_grouped_events())
    return _DIM_NAMES_CACHE


async def rollup_daily_goal_dims(db, since_day: date) -> int:
    """день × событие × разрез × значение (круг 11, зона H).

    Разрезы: `all` (итого), `site_locale` (по адресу события), `device`, `channel`,
    `country` (ru / foreign / unknown) — из портрета сессии, `surface` — из параметров.
    Роботы и собственная активность исключены (как в `daily_goals`). Объём мал: берутся
    только события групп отчётов, по индексу имя+время; читаются потоком пачками.
    """
    from app.models import DailyGoalDim
    from app.services.analytics_dims import UNKNOWN, country_group, site_locale_from_url, surface_from_url
    from app.services.analytics_marts import human_event_conditions
    from app.services.analytics_period import msk_day_start_utc

    since_dt = msk_day_start_utc(since_day)
    human = await human_event_conditions(db, since_day, msk_day(_utcnow()))
    surface_col = FrontendEvent.params_json["surface"].as_string()
    result = await db.stream(
        select(
            FrontendEvent.occurred_at, FrontendEvent.event_name, FrontendEvent.session_id_hash,
            FrontendEvent.url, surface_col,
            BehaviorSession.device_type, BehaviorSession.channel, BehaviorSession.country,
        )
        .select_from(FrontendEvent)
        .outerjoin(BehaviorSession, BehaviorSession.session_id_hash == FrontendEvent.session_id_hash)
        .where(FrontendEvent.event_name.in_(_dim_event_names()),
               FrontendEvent.occurred_at >= since_dt, *human)
        .execution_options(yield_per=_STREAM_BATCH)
    )
    agg: dict[tuple, list] = {}

    def bump(day: str, name: str, dim: str, value: str, sid: str | None) -> None:
        cell = agg.setdefault((day, name, dim, value[:120]), [0, set()])
        cell[0] += 1
        if sid:
            cell[1].add(sid)

    try:
        async for part in result.partitions(_STREAM_BATCH):
            for occurred_at, name, sid, url, surface, device, channel, country in part:
                day = msk_day(occurred_at).isoformat()
                bump(day, name, "all", "all", sid)
                bump(day, name, "site_locale", site_locale_from_url(url) or UNKNOWN, sid)
                bump(day, name, "device", device or UNKNOWN, sid)
                bump(day, name, "channel", channel or UNKNOWN, sid)
                bump(day, name, "country", country_group(country), sid)
                # Поверхность: параметр события, иначе по пути адреса.
                where = str(surface) if surface else surface_from_url(url)
                if where:
                    bump(day, name, "surface", where, sid)
    finally:
        await result.close()

    await db.execute(delete(DailyGoalDim).where(DailyGoalDim.day >= since_day))
    rows = [
        {"day": date.fromisoformat(day), "event_name": name, "dim": dim, "value": value,
         "count": cnt, "sessions": len(sessions), "computed_at": _utcnow()}
        for (day, name, dim, value), (cnt, sessions) in agg.items()
    ]
    if rows:
        await db.execute(DailyGoalDim.__table__.insert(), rows)
    await db.commit()
    return len(rows)


async def rollup_daily_pages(db, since_day: date) -> int:
    """день × страница из behavior_events: просмотры, dwell, dead-клики (день — МСК)."""
    from app.services.analytics_period import msk_day_start_utc

    since_dt = msk_day_start_utc(since_day)
    day_expr = msk_day_expr(BehaviorEvent.occurred_at, db.bind.dialect.name)

    pv = (await db.execute(
        select(
            day_expr.label("day"),
            BehaviorEvent.page,
            func.count().label("views"),
            func.count(func.distinct(func.coalesce(BehaviorEvent.visitor_id_hash, BehaviorEvent.session_id_hash))).label("visitors"),
        )
        .where(BehaviorEvent.occurred_at >= since_dt, BehaviorEvent.event_type == "pageview", BehaviorEvent.page.isnot(None),
               ~BehaviorEvent.page.like("/admin%"))
        .group_by(day_expr, BehaviorEvent.page)
    )).all()

    dead = dict(((str(day), page), int(cnt)) for day, page, cnt in (await db.execute(
        select(day_expr, BehaviorEvent.page, func.count())
        .where(BehaviorEvent.occurred_at >= since_dt, BehaviorEvent.event_type == "click",
               BehaviorEvent.is_dead.is_(True), BehaviorEvent.page.isnot(None),
               ~BehaviorEvent.page.like("/admin%"))
        .group_by(day_expr, BehaviorEvent.page)
    )).all())

    # dwell: params_json → потоком пачками (ночное окно 60 дней — сотни
    # тысяч dwell-событий; целиком в память не держим).
    dwell: dict[tuple, dict[str, int]] = defaultdict(lambda: {"ms": 0, "active": 0, "scroll_sum": 0, "n": 0})
    result = await db.stream(
        select(BehaviorEvent.occurred_at, BehaviorEvent.page, BehaviorEvent.params_json)
        .where(BehaviorEvent.occurred_at >= since_dt, BehaviorEvent.event_type == "dwell", BehaviorEvent.page.isnot(None),
               ~BehaviorEvent.page.like("/admin%"))
        .execution_options(yield_per=_STREAM_BATCH)
    )
    try:
        async for part in result.partitions(_STREAM_BATCH):
            for ts, page, params in part:
                if not isinstance(params, dict):
                    continue
                d = dwell[(msk_day(ts).isoformat(), page)]
                d["ms"] += int(params.get("ms") or 0)
                d["active"] += int(params.get("active_ms") or 0)
                d["scroll_sum"] += int(params.get("scroll_pct") or 0)
                d["n"] += 1
    finally:
        await result.close()

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
    """goal_id → имя/событие/tier. Числа goals_json становятся читаемыми.

    Строки НЕ удаляются: цель, исчезнувшая из счётчика (чистка 2026-07-06),
    помечается deleted=true — исторические goals_json продолжают резолвиться.
    Синк-гвард: активная action-цель Метрики обязана соответствовать
    macro/micro событию таксономии, иначе алерт (кто-то завёл цель руками
    мимо goal_taxonomy — расхождение источников истины).
    """
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
    live_ids: set[int] = set()
    stray_events: list[str] = []
    for g in goals:
        gid = g.get("id")
        if not gid:
            continue
        live_ids.add(int(gid))
        # Для JS-целей (action) имя события лежит в conditions[].url.
        event_name = None
        for cond in g.get("conditions") or []:
            if cond.get("type") == "exact" or g.get("type") == "action":
                event_name = (cond.get("url") or "")[:120] or None
                break
        if g.get("type") == "action" and event_name and not is_conversion(event_name):
            stray_events.append(event_name)
        existing = await db.get(MetrikaGoal, int(gid))
        values = {
            "name": (g.get("name") or "")[:300] or None,
            "event_name": event_name,
            "tier": tier_for_event(event_name) if event_name else None,
            "deleted": False,
            "synced_at": _utcnow(),
        }
        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            db.add(MetrikaGoal(goal_id=int(gid), **values))
        stored += 1

    # Soft-delete: словарная запись есть, в счётчике цели больше нет.
    if live_ids:
        await db.execute(
            MetrikaGoal.__table__.update()
            .where(MetrikaGoal.goal_id.notin_(live_ids), MetrikaGoal.deleted.is_(False))
            .values(deleted=True)
        )
    await db.commit()

    if stray_events:
        try:
            from app.services.analytics_alerts import _alert
            await _alert(
                "metrika_goals_stray",
                "Цели Метрики разошлись с goal_taxonomy (не macro/micro): "
                + ", ".join(sorted(set(stray_events))[:10]),
            )
        except Exception:  # noqa: BLE001
            logger.warning("Stray Metrika goals (не macro/micro): %s", stray_events)
    logger.info("Metrika goals dict synced: %d goals", stored)
    return stored


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

async def run_rollups(days: int = 2) -> dict[str, int]:
    """Общий прогон: сессионизация + все rollup'ы для окна N МСК-дней.
    Окно выравнивается по границе МСК-суток — пересчёт всегда затирает
    целые дни (идемпотентность delete+insert без «полудней» на стыке)."""
    from app.services.analytics_period import msk_day_start_utc

    since_day = msk_day(_utcnow() - timedelta(days=days))
    # Короткие сессии по фазам: одна длинная транзакция держала пул 20 мин
    # (инцидент 2026-09-03). Сессионизация длинного окна — по МСК-дням
    # окнами SESSIONIZE_WINDOW_DAYS, от старых к новым: новизна посетителя
    # в окне опирается на уже пересчитанные предыдущие окна.
    n_sessions = 0
    window_day = since_day
    today = msk_day(_utcnow())
    while True:
        next_day = window_day + timedelta(days=SESSIONIZE_WINDOW_DAYS)
        until = msk_day_start_utc(next_day) if next_day <= today else None
        async with analytics_session() as db:
            n_sessions += await sessionize(db, msk_day_start_utc(window_day), until=until)
        if until is None:
            break
        window_day = next_day
    async with analytics_session() as db:
        n_traffic = await rollup_daily_traffic(db, since_day)
    async with analytics_session() as db:
        n_goals = await rollup_daily_goals(db, since_day)
    n_dims = 0
    try:
        async with analytics_session() as db:
            n_dims = await rollup_daily_goal_dims(db, since_day)
    except Exception:
        # Разрезы для отчётов не должны останавливать основные роллапы.
        logger.exception("daily_goal_dims rollup failed")
    async with analytics_session() as db:
        n_pages = await rollup_daily_pages(db, since_day)
    n_signups = 0
    try:
        from app.services.signup_attribution import ensure_signup_attribution, refill_empty_attribution

        async with analytics_session() as db:
            n_signups = await ensure_signup_attribution(db)
            await refill_empty_attribution(db, since=_utcnow() - timedelta(days=3))
    except Exception:
        logger.exception("signup attribution failed")
    return {"sessions": n_sessions, "traffic": n_traffic, "goals": n_goals, "goal_dims": n_dims,
            "pages": n_pages, "signups": n_signups}


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
    """Ночной пересчёт хвоста истории (60 дней) + синк словаря целей
    + суточная калибровка антибота к визитам Метрики."""
    try:
        stats = await run_rollups(days=60)
        logger.info("Rollups daily: %s", stats)
    except Exception:
        logger.exception("Rollups daily failed")
    try:
        async with analytics_session() as db:
            await sync_metrika_goals(db)
    except Exception:
        logger.exception("Metrika goals sync failed")
    try:
        # Круг 11: добор атрибуции регистраций за всё время и уборка следов удалённых аккаунтов.
        from app.services.account_erasure import process_pending_erasures
        from app.services.signup_attribution import ensure_signup_attribution

        async with analytics_session() as db:
            await ensure_signup_attribution(db, since=_utcnow() - timedelta(days=3650), limit=1000)
        async with analytics_session() as db:
            logger.info("Analytics erasure: %s", await process_pending_erasures(db))
    except Exception:
        logger.exception("Signup attribution / erasure failed")
    try:
        from app.services.analytics_alerts import check_bot_calibration
        await check_bot_calibration()
    except Exception:
        logger.exception("Bot calibration check failed")
