"""OLAP-слой ClickHouse: производная копия Postgres (ADR-0010, этап 4).

Роль: «любая метрика × любое измерение» за миллисекунды для вкладки BI
«Срезы» и срезов-аномалий Пульса. Ни одного нового пути записи: Postgres —
единственный источник истины, сайт/сбор/auth не знают о CH. Слой можно
снести и налить заново полным ресинком (`resync()`), поэтому том
clickhouse_data в бэкапы не входит.

Синк — APScheduler каждые 15 минут (main.py): батчи по id-курсору
(курсоры в state-Redis DB 1), события append-only. raw_metrika_visits —
перезаливка последних 2 суток, ReplacingMergeTree дедуплицирует по visit_id.
Идемпотентный DDL выполняется на старте каждого прогона (CREATE TABLE IF NOT
EXISTS) — новая таблица появляется без ручных миграций CH.

Деградация: CH упал → синк пишет warning и молчит, сайт не замечает,
«Срезы» отвечают «слой недоступен», после подъёма синк догоняет по курсорам.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import (
    BehaviorEvent,
    BehaviorSession,
    FrontendEvent,
    IdentityLink,
    RawMetrikaVisit,
    ServerSession,
)

logger = logging.getLogger(__name__)

_CURSOR_KEY = "fe:ch:cursor:{table}"
_LAST_SYNC_KEY = "fe:ch:last_sync_at"
_BATCH = 20_000

# DDL: MergeTree, партиции по месяцу, ORDER BY под типовые срезы.
_DDL = [
    """CREATE TABLE IF NOT EXISTS behavior_events (
        id Int64, event_type LowCardinality(String), session_id_hash String,
        visitor_id_hash String, user_id String, authed UInt8,
        page String, element_path String, element_text String,
        is_dead UInt8, is_rage UInt8, params String,
        occurred_at DateTime
    ) ENGINE = MergeTree PARTITION BY toYYYYMM(occurred_at)
      ORDER BY (occurred_at, visitor_id_hash)""",
    """CREATE TABLE IF NOT EXISTS frontend_events (
        id Int64, event_name LowCardinality(String), session_id_hash String,
        visitor_id_hash String, user_id String, authed UInt8,
        url String, params String, occurred_at DateTime
    ) ENGINE = MergeTree PARTITION BY toYYYYMM(occurred_at)
      ORDER BY (occurred_at, visitor_id_hash)""",
    """CREATE TABLE IF NOT EXISTS behavior_sessions (
        session_id_hash String, visitor_id_hash String, ym_client_id String,
        user_id String, authed UInt8, started_at DateTime, entry_page String,
        referrer_host String, channel LowCardinality(String),
        utm_source String, utm_campaign String,
        country String, geo_region String, city String,
        browser LowCardinality(String), os LowCardinality(String),
        device_type LowCardinality(String), language String,
        is_webdriver UInt8
    ) ENGINE = ReplacingMergeTree PARTITION BY toYYYYMM(started_at)
      ORDER BY (session_id_hash)""",
    """CREATE TABLE IF NOT EXISTS server_sessions (
        id Int64, day Date, visitor_id_hash String, user_id String,
        started_at DateTime, duration_ms Int64, active_ms Int64,
        pageviews Int32, clicks Int32, max_scroll_pct Int32,
        entry_page String, exit_page String,
        channel LowCardinality(String), device LowCardinality(String),
        is_new_visitor UInt8, is_engaged UInt8,
        micro_goals Int32, macro_goals Int32, is_bot UInt8,
        bot_score Int32, is_internal UInt8
    ) ENGINE = ReplacingMergeTree PARTITION BY toYYYYMM(day)
      ORDER BY (visitor_id_hash, started_at)""",
    """CREATE TABLE IF NOT EXISTS raw_metrika_visits (
        visit_id String, client_id_hash String, visit_date Date,
        start_time DateTime, start_url String, traffic_source LowCardinality(String),
        search_engine String, duration_seconds Int32, has_goal UInt8,
        device LowCardinality(String), browser String, os String, is_new UInt8
    ) ENGINE = ReplacingMergeTree PARTITION BY toYYYYMM(visit_date)
      ORDER BY (visit_id)""",
    """CREATE TABLE IF NOT EXISTS identity_links (
        user_id String, visitor_id_hash String, first_seen DateTime, last_seen DateTime
    ) ENGINE = ReplacingMergeTree ORDER BY (user_id, visitor_id_hash)""",
]


def _client():
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        database=settings.clickhouse_db,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        connect_timeout=5,
        send_receive_timeout=30,
    )


def _dt(v: datetime | None) -> datetime:
    return v or datetime(1970, 1, 1)


async def _cursor_get(table: str) -> int:
    from app.core.cache import get_state_redis
    r = await get_state_redis()
    raw = await r.get(_CURSOR_KEY.format(table=table))
    return int(raw) if raw else 0


async def _cursor_set(table: str, value: int) -> None:
    from app.core.cache import get_state_redis
    r = await get_state_redis()
    await r.set(_CURSOR_KEY.format(table=table), str(value))


async def last_sync_age_minutes() -> int | None:
    from app.core.cache import get_state_redis
    r = await get_state_redis()
    raw = await r.get(_LAST_SYNC_KEY)
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)
    except ValueError:
        return None
    return int((datetime.now(timezone.utc).replace(tzinfo=None) - ts).total_seconds() / 60)


async def _sync_events(db, ch) -> int:
    """behavior_events + frontend_events: append-only по id-курсору."""
    total = 0
    cursor = await _cursor_get("behavior_events")
    while True:
        rows = (await db.execute(
            select(BehaviorEvent).where(BehaviorEvent.id > cursor)
            .order_by(BehaviorEvent.id).limit(_BATCH)
        )).scalars().all()
        if not rows:
            break
        ch.insert(
            "behavior_events",
            [[
                r.id, r.event_type or "", r.session_id_hash or "", r.visitor_id_hash or "",
                r.user_id or "", 1 if r.authed else 0, r.page or "", r.element_path or "",
                r.element_text or "", 1 if r.is_dead else 0, 1 if r.is_rage else 0,
                json.dumps(r.params_json or {}, ensure_ascii=False), _dt(r.occurred_at),
            ] for r in rows],
            column_names=[
                "id", "event_type", "session_id_hash", "visitor_id_hash", "user_id",
                "authed", "page", "element_path", "element_text", "is_dead", "is_rage",
                "params", "occurred_at",
            ],
        )
        cursor = rows[-1].id
        total += len(rows)
        await _cursor_set("behavior_events", cursor)
        if len(rows) < _BATCH:
            break

    cursor = await _cursor_get("frontend_events")
    while True:
        rows = (await db.execute(
            select(FrontendEvent).where(FrontendEvent.id > cursor)
            .order_by(FrontendEvent.id).limit(_BATCH)
        )).scalars().all()
        if not rows:
            break
        ch.insert(
            "frontend_events",
            [[
                r.id, r.event_name or "", r.session_id_hash or "", r.visitor_id_hash or "",
                r.user_id or "", 1 if r.authed else 0, r.url or "",
                json.dumps(r.params_json or {}, ensure_ascii=False), _dt(r.occurred_at),
            ] for r in rows],
            column_names=[
                "id", "event_name", "session_id_hash", "visitor_id_hash", "user_id",
                "authed", "url", "params", "occurred_at",
            ],
        )
        cursor = rows[-1].id
        total += len(rows)
        await _cursor_set("frontend_events", cursor)
        if len(rows) < _BATCH:
            break
    return total


async def _sync_replacing(db, ch, days: int = 2) -> int:
    """Идемпотентные слои: последние N суток перезаливкой (Replacing-дедуп)."""
    from app.services.analytics_marts import (
        business_goal_ids,
        visit_browser,
        visit_device,
        visit_field,
        visit_has_business_goal,
        visit_os,
    )

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    total = 0
    # has_goal в CH — только business-tier цели (этап 2б BI 2.1).
    biz_ids = await business_goal_ids(db)

    sessions = (await db.execute(
        select(BehaviorSession).where(BehaviorSession.started_at >= since)
    )).scalars().all()
    if sessions:
        ch.insert(
            "behavior_sessions",
            [[
                s.session_id_hash, s.visitor_id_hash or "", s.ym_client_id or "", s.user_id or "",
                1 if s.authed else 0, _dt(s.started_at), s.entry_page or "", s.referrer_host or "",
                s.channel or "", s.utm_source or "", s.utm_campaign or "",
                s.country or "", s.geo_region or "", s.city or "",
                s.browser or "", s.os or "", s.device_type or "", s.language or "",
                1 if s.is_webdriver else 0,
            ] for s in sessions],
            column_names=[
                "session_id_hash", "visitor_id_hash", "ym_client_id", "user_id", "authed",
                "started_at", "entry_page", "referrer_host", "channel", "utm_source",
                "utm_campaign", "country", "geo_region", "city", "browser", "os",
                "device_type", "language", "is_webdriver",
            ],
        )
        total += len(sessions)

    srv = (await db.execute(
        select(ServerSession).where(ServerSession.started_at >= since)
    )).scalars().all()
    if srv:
        ch.insert(
            "server_sessions",
            [[
                s.id, s.day, s.visitor_id_hash, s.user_id or "", _dt(s.started_at),
                int(s.duration_ms or 0), int(s.active_ms or 0), int(s.pageviews or 0),
                int(s.clicks or 0), int(s.max_scroll_pct or 0), s.entry_page or "",
                s.exit_page or "", s.channel or "", s.device or "",
                1 if s.is_new_visitor else 0, 1 if s.is_engaged else 0,
                int(s.micro_goals or 0), int(s.macro_goals or 0), 1 if s.is_bot else 0,
                int(s.bot_score or 0), 1 if s.is_internal else 0,
            ] for s in srv],
            column_names=[
                "id", "day", "visitor_id_hash", "user_id", "started_at", "duration_ms",
                "active_ms", "pageviews", "clicks", "max_scroll_pct", "entry_page",
                "exit_page", "channel", "device", "is_new_visitor", "is_engaged",
                "micro_goals", "macro_goals", "is_bot",
                "bot_score", "is_internal",
            ],
        )
        total += len(srv)

    visits = (await db.execute(
        select(RawMetrikaVisit).where(RawMetrikaVisit.visit_date >= since.date())
    )).scalars().all()
    if visits:
        ch.insert(
            "raw_metrika_visits",
            [[
                v.visit_id, v.client_id_hash or "", v.visit_date or datetime(1970, 1, 1).date(),
                _dt(v.start_time), v.start_url or "", v.traffic_source or "",
                v.search_engine or "", int(v.duration_seconds or 0),
                1 if visit_has_business_goal(v, biz_ids) else 0,
                visit_device(v), visit_browser(v), visit_os(v),
                1 if visit_field(v, "ym:s:isNewUser") == "1" else 0,
            ] for v in visits],
            column_names=[
                "visit_id", "client_id_hash", "visit_date", "start_time", "start_url",
                "traffic_source", "search_engine", "duration_seconds", "has_goal",
                "device", "browser", "os", "is_new",
            ],
        )
        total += len(visits)

    links = (await db.execute(select(IdentityLink))).scalars().all()
    if links:
        ch.insert(
            "identity_links",
            [[l.user_id, l.visitor_id_hash, _dt(l.first_seen), _dt(l.last_seen)] for l in links],
            column_names=["user_id", "visitor_id_hash", "first_seen", "last_seen"],
        )
        total += len(links)
    return total


def _ensure_schema(ch) -> None:
    for ddl in _DDL:
        ch.command(ddl)


async def clickhouse_sync_job() -> None:
    """15-минутный синк. Все CH-вызовы — в thread executor (клиент синхронный)."""
    if not settings.clickhouse_enabled:
        return
    loop = asyncio.get_running_loop()
    try:
        ch = await loop.run_in_executor(None, _client)
        await loop.run_in_executor(None, _ensure_schema, ch)
    except Exception as exc:  # noqa: BLE001 — мягкая деградация
        logger.warning("ClickHouse unavailable, sync skipped: %s", exc)
        return
    try:
        async with async_session() as db:
            n_events = await _sync_events(db, ch)
            n_repl = await _sync_replacing(db, ch)
        from app.core.cache import get_state_redis
        r = await get_state_redis()
        await r.set(_LAST_SYNC_KEY, datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
        if n_events or n_repl:
            logger.info("ClickHouse sync: %d event rows, %d replacing rows", n_events, n_repl)
    except Exception:
        logger.exception("ClickHouse sync failed")
    finally:
        try:
            await loop.run_in_executor(None, ch.close)
        except Exception:  # noqa: BLE001
            pass


async def resync() -> None:
    """Полный ресинк с нуля: сброс курсоров + очистка таблиц CH + вся история."""
    loop = asyncio.get_running_loop()
    ch = await loop.run_in_executor(None, _client)
    try:
        # DROP+CREATE (не TRUNCATE): ресинк подхватывает и изменения схемы
        # (новые колонки вроде bot_score/is_internal) без ручных ALTER.
        for table in ("behavior_events", "frontend_events", "behavior_sessions",
                      "server_sessions", "raw_metrika_visits", "identity_links"):
            await loop.run_in_executor(None, ch.command, f"DROP TABLE IF EXISTS {table}")
        await loop.run_in_executor(None, _ensure_schema, ch)
        for table in ("behavior_events", "frontend_events"):
            await _cursor_set(table, 0)
        async with async_session() as db:
            n_events = await _sync_events(db, ch)
            # Бутстрап: replacing-слои льём всей историей, не 2-дневным окном.
            n_repl = await _sync_replacing(db, ch, days=3650)
        from app.core.cache import get_state_redis
        r = await get_state_redis()
        await r.set(_LAST_SYNC_KEY, datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
        logger.info("ClickHouse resync: %d event rows, %d replacing rows", n_events, n_repl)
    finally:
        try:
            await loop.run_in_executor(None, ch.close)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Запросы для вкладки «Срезы» (белый список измерений — SQL-инъекции исключены)
# ---------------------------------------------------------------------------

SLICE_METRICS = {
    "sessions": ("server_sessions", "count()"),
    "visitors": ("server_sessions", "uniq(visitor_id_hash)"),
    "pageviews": ("behavior_events", "countIf(event_type = 'pageview')"),
    "clicks": ("behavior_events", "countIf(event_type = 'click')"),
    "engaged_sessions": ("server_sessions", "countIf(is_engaged = 1)"),
    "micro_goals": ("server_sessions", "sum(micro_goals)"),
    "macro_goals": ("server_sessions", "sum(macro_goals)"),
    "metrika_visits": ("raw_metrika_visits", "count()"),
    "metrika_goal_visits": ("raw_metrika_visits", "countIf(has_goal = 1)"),
}

SLICE_DIMENSIONS = {
    "server_sessions": {
        "day": "toString(day)", "channel": "channel", "device": "device",
        "is_new": "toString(is_new_visitor)", "entry_page": "entry_page",
        "hour": "toString(toHour(started_at))",
    },
    "behavior_events": {
        "day": "toString(toDate(occurred_at))", "page": "page",
        "hour": "toString(toHour(occurred_at))", "event_type": "event_type",
    },
    "raw_metrika_visits": {
        "day": "toString(visit_date)", "traffic_source": "traffic_source",
        "device": "device", "browser": "browser", "os": "os",
        "search_engine": "search_engine", "is_new": "toString(is_new)",
        "hour": "toString(toHour(start_time))",
    },
}


async def run_slice(metric: str, dims: list[str], days: int = 30, limit: int = 1000) -> dict[str, Any]:
    """Конструктор среза: метрика × 1-2 измерения × период → строки."""
    if metric not in SLICE_METRICS:
        raise ValueError(f"Unknown metric: {metric}")
    table, expr = SLICE_METRICS[metric]
    allowed = SLICE_DIMENSIONS.get(table, {})
    sel_dims = [d for d in dims if d in allowed][:2]
    time_col = {"server_sessions": "day", "behavior_events": "toDate(occurred_at)",
                "raw_metrika_visits": "visit_date"}[table]

    # Пустое значение измерения → «(не определён)» прямо в SQL (этап 3б).
    dim_exprs = [
        f"if(empty({allowed[d]}), '(не определён)', {allowed[d]}) AS {d}"
        for d in sel_dims
    ]
    group = ", ".join(sel_dims) if sel_dims else ""
    # FINAL обязателен для ReplacingMergeTree: без него перезалитые окна
    # читаются с дублями до фонового merge (аудит 2026-07-06: +64% строк).
    final = " FINAL" if table in ("server_sessions", "raw_metrika_visits", "behavior_sessions") else ""
    # Срезы по нашим сессиям — только люди и не своя активность (этапы 3/3б).
    extra_where = " AND is_bot = 0 AND is_internal = 0" if table == "server_sessions" else ""
    sql = (
        f"SELECT {', '.join(dim_exprs + [expr + ' AS value'])} FROM {table}{final} "
        f"WHERE {time_col} >= today() - {int(days)}{extra_where} "
        + (f"GROUP BY {group} ORDER BY value DESC " if group else "")
        + f"LIMIT {int(limit)}"
    )
    loop = asyncio.get_running_loop()

    def _run():
        ch = _client()
        try:
            res = ch.query(sql)
            return res.column_names, res.result_rows
        finally:
            ch.close()

    cols, rows = await loop.run_in_executor(None, _run)
    return {
        "metric": metric, "dimensions": sel_dims, "days": days, "sql": sql,
        "columns": list(cols),
        "rows": [list(r) for r in rows],
    }
