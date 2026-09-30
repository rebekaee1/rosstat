"""OLAP-слой ClickHouse: производная копия Postgres (ADR-0010, этап 4).

Роль: «любая метрика × любое измерение» за миллисекунды для вкладки BI
«Срезы» и срезов-аномалий Пульса. Ни одного нового пути записи: Postgres —
единственный источник истины, сайт/сбор/auth не знают о CH. Слой можно
снести и налить заново полным ресинком (`resync()`), поэтому том
clickhouse_data в бэкапы не входит.

Синк — APScheduler каждые 15 минут (main.py): ограниченные батчи по
v2 id-курсору в state-Redis. SHARE NOWAIT фиксирует безопасный committed
ceiling при READ COMMITTED и возрастающей uncached sequence; занятая
таблица откладывается. Старые курсоры не используются: история постепенно
перечитывается для восстановления прежних пропусков. Повторная вставка в
MergeTree может физически дублировать события; публичные срезы считают
уникальные id. raw_metrika_visits —
перезаливка последних 2 суток, ReplacingMergeTree дедуплицирует по visit_id.
Идемпотентный DDL выполняется на старте каждого прогона (CREATE TABLE IF NOT
EXISTS) — новая таблица появляется без ручных миграций CH; для колонок,
добавленных в уже существующую таблицу, — `_COLUMN_GUARDS` (ALTER TABLE ADD
COLUMN IF NOT EXISTS), иначе дрейф схемы виден только после ручного `resync()`.

Деградация: CH упал → синк пишет warning и молчит, сайт не замечает,
«Срезы» отвечают «слой недоступен», после подъёма синк догоняет по курсорам.
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.database import analytics_session
from app.models import (
    BehaviorEvent,
    BehaviorSession,
    FrontendEvent,
    IdentityLink,
    RawMetrikaVisit,
    ServerSession,
)

logger = logging.getLogger(__name__)

_CURSOR_KEY = "fe:ch:cursor:v2:{table}"
_LAST_SYNC_KEY = "fe:ch:last_sync_at:v2"
_EVENT_PROGRESS_KEY = "fe:ch:events-progress:v2"
_RESYNC_PENDING_KEY = "fe:ch:resync_pending:v2"
_BATCH = 20_000
# Ограничение одного обычного прогона: не больше 80k строк каждой таблицы.
# Полный historical replay продолжается по сохранённому курсору следующих jobs.
_EVENT_BATCHES_PER_TABLE = 4
# Перезаливаемые слои (сессии/визиты окна) — потоком по столько строк.
_REPLACING_BATCH = 5_000

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

# Дрейф схемы: `CREATE TABLE IF NOT EXISTS` не подтягивает новые колонки в уже
# существующую таблицу — если `_DDL` выше пополнился полем после того, как
# таблица создана на проде, синк падает "Unrecognized column" до ручного
# `resync()`. Единственное место, которое трогаем при добавлении колонки в
# существующую таблицу (2026-07-08: bot_score/is_internal подвисли в
# server_sessions именно так).
_COLUMN_GUARDS = [
    ("server_sessions", "bot_score", "Int32"),
    ("server_sessions", "is_internal", "UInt8"),
]


def _client(*, send_receive_timeout: int = 30):
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        database=settings.clickhouse_db,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        connect_timeout=5,
        send_receive_timeout=send_receive_timeout,
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


async def event_sync_progress() -> dict[str, Any]:
    """Captured committed ceilings and bounded-copy progress, not wall-clock completeness."""
    from app.core.cache import get_state_redis
    redis = await get_state_redis()
    raw = await redis.get(_EVENT_PROGRESS_KEY)
    return json.loads(raw) if raw else {}


async def resync_pending() -> bool:
    """Durable known-maintenance state; cleared only after a complete resync."""
    from app.core.cache import get_state_redis
    redis = await get_state_redis()
    return bool(await redis.get(_RESYNC_PENDING_KEY))


async def _event_ceiling(model) -> int:
    """Take a short INSERT barrier; release PG before Redis or CH I/O.

    INSERT defaults allocate IDs only under the table's ROW EXCLUSIVE lock.
    SHARE NOWAIT therefore either observes all preceding writer commits or
    defers immediately, without queuing behind an open telemetry transaction.
    A newly arriving writer can briefly wait while the acquired barrier reads
    metadata/max(id). This relies on ascending CACHE 1, noncycling automatic
    IDs and READ COMMITTED; manual lower-ID writes/sequence resets are outside
    the append contract, and detectable schema/config mismatches fail closed.
    """
    table = model.__tablename__
    if table not in ("behavior_events", "frontend_events"):
        raise ValueError("Unknown event replication source")
    async with analytics_session() as db:
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            connection = await db.connection()
            if await connection.get_isolation_level() != "READ COMMITTED":
                raise RuntimeError("Event replication requires READ COMMITTED")
            await db.execute(text(f"LOCK TABLE {table} IN SHARE MODE NOWAIT"))
            info = (await db.execute(text("""
                SELECT pg_get_expr(d.adbin, d.adrelid) AS id_default,
                       a.attidentity, s.seqcache, s.seqcycle, s.seqincrement,
                       s.seqmin, s.seqrelid::oid AS sequence_oid
                FROM pg_attribute a
                LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                LEFT JOIN pg_sequence s ON s.seqrelid = pg_get_serial_sequence(:table, 'id')::regclass
                WHERE a.attrelid = to_regclass(:table) AND a.attname = 'id'
            """), {"table": table})).mappings().one()
            identity = info["attidentity"] in ("a", "d")
            default = re.fullmatch(r"nextval\('([^']+)'::regclass\)", info["id_default"] or "")
            default_oid = await db.scalar(text("SELECT to_regclass(:name)::oid"), {"name": default[1]}) if default else None
            if (
                not (identity or default_oid == info["sequence_oid"] and default_oid is not None)
                or info["seqcache"] != 1 or info["seqcycle"]
                or info["seqincrement"] != 1 or info["seqmin"] < 1
            ):
                raise RuntimeError(f"Unsafe {table} sequence/default for event replication")
        # READ COMMITTED obtains this statement's snapshot after the barrier.
        ceiling = int(await db.scalar(select(func.max(model.id))) or 0)
        if db.bind is not None and db.bind.dialect.name == "postgresql" and ceiling:
            allocated = await db.scalar(text("SELECT pg_sequence_last_value(CAST(:sequence_oid AS oid)::regclass)"), {"sequence_oid": info["sequence_oid"]})
            if allocated is None or allocated < ceiling:
                raise RuntimeError(f"Unsafe {table} sequence reset below committed IDs")
        return ceiling


async def _ceiling_or_deferred(model) -> int | None:
    try:
        return await _event_ceiling(model)
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) != "55P03":
            raise
        logger.info("ClickHouse event source deferred: active %s writer", model.__tablename__)
        return None


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


async def _ch_insert(ch, table: str, rows: list, column_names: list[str]) -> None:
    """Сетевой insert в CH — только в thread executor.

    Клиент clickhouse_connect синхронный: вызов прямо из корутины держал event
    loop scheduler'а на всё время HTTP-вставки, и соседние джобы ловили
    «Timeout reading from redis-state» (инцидент 2026-09-28/29).
    """
    await asyncio.get_running_loop().run_in_executor(
        None, functools.partial(ch.insert, table, rows, column_names=column_names)
    )


_EVENT_COLUMNS = [
    "id", "event_type", "session_id_hash", "visitor_id_hash", "user_id",
    "authed", "page", "element_path", "element_text", "is_dead", "is_rage",
    "params", "occurred_at",
]
_FRONTEND_COLUMNS = [
    "id", "event_name", "session_id_hash", "visitor_id_hash", "user_id",
    "authed", "url", "params", "occurred_at",
]


async def _sync_events(ch) -> int:
    """behavior_events + frontend_events: batch колонок → close PG → insert CH.

    Выбираются колонки, не ORM-сущности: 20k ORM-объектов с identity map
    весили на порядок больше кортежей.
    """
    total = 0
    progress = {}
    cursor = await _cursor_get("behavior_events")
    ceiling = await _ceiling_or_deferred(BehaviorEvent)
    for _ in range(_EVENT_BATCHES_PER_TABLE):
        if ceiling is None or cursor >= ceiling:
            break
        async with analytics_session() as db:
            rows = (await db.execute(
                select(
                    BehaviorEvent.id, BehaviorEvent.event_type,
                    BehaviorEvent.session_id_hash, BehaviorEvent.visitor_id_hash,
                    BehaviorEvent.user_id, BehaviorEvent.authed, BehaviorEvent.page,
                    BehaviorEvent.element_path, BehaviorEvent.element_text,
                    BehaviorEvent.is_dead, BehaviorEvent.is_rage,
                    BehaviorEvent.params_json, BehaviorEvent.occurred_at,
                ).where(BehaviorEvent.id > cursor, BehaviorEvent.id <= ceiling)
                .order_by(BehaviorEvent.id).limit(_BATCH)
            )).all()
        if not rows:
            break
        payload = [[
            r.id, r.event_type or "", r.session_id_hash or "", r.visitor_id_hash or "",
            r.user_id or "", 1 if r.authed else 0, r.page or "", r.element_path or "",
            r.element_text or "", 1 if r.is_dead else 0, 1 if r.is_rage else 0,
            json.dumps(r.params_json or {}, ensure_ascii=False), _dt(r.occurred_at),
        ] for r in rows]
        n = len(rows)
        cursor = rows[-1].id
        del rows
        await _ch_insert(ch, "behavior_events", payload, _EVENT_COLUMNS)
        total += n
        await _cursor_set("behavior_events", cursor)
        if n < _BATCH:
            break
    progress["behavior_events"] = {"cursor": cursor, "ceiling": ceiling, "caught_up": ceiling is not None and cursor >= ceiling, "deferred": ceiling is None}

    cursor = await _cursor_get("frontend_events")
    ceiling = await _ceiling_or_deferred(FrontendEvent)
    for _ in range(_EVENT_BATCHES_PER_TABLE):
        if ceiling is None or cursor >= ceiling:
            break
        async with analytics_session() as db:
            rows = (await db.execute(
                select(
                    FrontendEvent.id, FrontendEvent.event_name,
                    FrontendEvent.session_id_hash, FrontendEvent.visitor_id_hash,
                    FrontendEvent.user_id, FrontendEvent.authed, FrontendEvent.url,
                    FrontendEvent.params_json, FrontendEvent.occurred_at,
                ).where(FrontendEvent.id > cursor, FrontendEvent.id <= ceiling)
                .order_by(FrontendEvent.id).limit(_BATCH)
            )).all()
        if not rows:
            break
        payload = [[
            r.id, r.event_name or "", r.session_id_hash or "", r.visitor_id_hash or "",
            r.user_id or "", 1 if r.authed else 0, r.url or "",
            json.dumps(r.params_json or {}, ensure_ascii=False), _dt(r.occurred_at),
        ] for r in rows]
        n = len(rows)
        cursor = rows[-1].id
        del rows
        await _ch_insert(ch, "frontend_events", payload, _FRONTEND_COLUMNS)
        total += n
        await _cursor_set("frontend_events", cursor)
        if n < _BATCH:
            break
    progress["frontend_events"] = {"cursor": cursor, "ceiling": ceiling, "caught_up": ceiling is not None and cursor >= ceiling, "deferred": ceiling is None}
    from app.core.cache import get_state_redis
    redis = await get_state_redis()
    await redis.set(_EVENT_PROGRESS_KEY, json.dumps(progress))
    return total


# Ключи raw_json визита, которые нужны CH (устройство/браузер/ОС/новизна).
# На Postgres вынимаются в SQL: полный raw_json визита ~1,3 КБ × 35k строк.
_VISIT_JSON_KEYS = (
    "ym:s:deviceCategory", "ym:s:browser", "ym:s:operatingSystemRoot", "ym:s:isNewUser",
)


class _VisitLite:
    """Минимальный визит для хелперов analytics_marts (goals_json + raw_json)."""
    __slots__ = ("goals_json", "raw_json")

    def __init__(self, goals_json, raw_json):
        self.goals_json = goals_json
        self.raw_json = raw_json or {}


def _json_text(col, key: str):
    indexed = col[key]
    as_string = getattr(indexed, "as_string", None)
    return as_string() if callable(as_string) else indexed.astext


async def _stream_partitions(stmt, size: int):
    """Серверный курсор: в памяти одновременно не больше `size` строк."""
    async with analytics_session() as db:
        result = await db.stream(stmt.execution_options(yield_per=size))
        async for part in result.partitions(size):
            yield part


_SESSION_COLUMNS = [
    "session_id_hash", "visitor_id_hash", "ym_client_id", "user_id", "authed",
    "started_at", "entry_page", "referrer_host", "channel", "utm_source",
    "utm_campaign", "country", "geo_region", "city", "browser", "os",
    "device_type", "language", "is_webdriver",
]
_SERVER_SESSION_COLUMNS = [
    "id", "day", "visitor_id_hash", "user_id", "started_at", "duration_ms",
    "active_ms", "pageviews", "clicks", "max_scroll_pct", "entry_page",
    "exit_page", "channel", "device", "is_new_visitor", "is_engaged",
    "micro_goals", "macro_goals", "is_bot",
    "bot_score", "is_internal",
]
_VISIT_COLUMNS = [
    "visit_id", "client_id_hash", "visit_date", "start_time", "start_url",
    "traffic_source", "search_engine", "duration_seconds", "has_goal",
    "device", "browser", "os", "is_new",
]


async def _sync_replacing(ch, days: int = 2) -> int:
    """Идемпотентные слои: последние N суток перезаливкой (Replacing-дедуп).

    Потоково, пачками `_REPLACING_BATCH`: раньше все сессии и визиты окна
    (~130k ORM-объектов при бот-шторме) материализовались разом и процесс
    scheduler упирался в лимит памяти контейнера.
    """
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
    async with analytics_session() as db:
        biz_ids = await business_goal_ids(db)
        dialect = db.bind.dialect.name if db.bind is not None else ""

    async for part in _stream_partitions(
        select(
            BehaviorSession.session_id_hash, BehaviorSession.visitor_id_hash,
            BehaviorSession.ym_client_id, BehaviorSession.user_id, BehaviorSession.authed,
            BehaviorSession.started_at, BehaviorSession.entry_page,
            BehaviorSession.referrer_host, BehaviorSession.channel,
            BehaviorSession.utm_source, BehaviorSession.utm_campaign,
            BehaviorSession.country, BehaviorSession.geo_region, BehaviorSession.city,
            BehaviorSession.browser, BehaviorSession.os, BehaviorSession.device_type,
            BehaviorSession.language, BehaviorSession.is_webdriver,
        ).where(BehaviorSession.started_at >= since),
        _REPLACING_BATCH,
    ):
        await _ch_insert(ch, "behavior_sessions", [[
            s.session_id_hash, s.visitor_id_hash or "", s.ym_client_id or "", s.user_id or "",
            1 if s.authed else 0, _dt(s.started_at), s.entry_page or "", s.referrer_host or "",
            s.channel or "", s.utm_source or "", s.utm_campaign or "",
            s.country or "", s.geo_region or "", s.city or "",
            s.browser or "", s.os or "", s.device_type or "", s.language or "",
            1 if s.is_webdriver else 0,
        ] for s in part], _SESSION_COLUMNS)
        total += len(part)

    async for part in _stream_partitions(
        select(
            ServerSession.id, ServerSession.day, ServerSession.visitor_id_hash,
            ServerSession.user_id, ServerSession.started_at, ServerSession.duration_ms,
            ServerSession.active_ms, ServerSession.pageviews, ServerSession.clicks,
            ServerSession.max_scroll_pct, ServerSession.entry_page, ServerSession.exit_page,
            ServerSession.channel, ServerSession.device, ServerSession.is_new_visitor,
            ServerSession.is_engaged, ServerSession.micro_goals, ServerSession.macro_goals,
            ServerSession.is_bot, ServerSession.bot_score, ServerSession.is_internal,
        ).where(ServerSession.started_at >= since),
        _REPLACING_BATCH,
    ):
        await _ch_insert(ch, "server_sessions", [[
            s.id, s.day, s.visitor_id_hash, s.user_id or "", _dt(s.started_at),
            int(s.duration_ms or 0), int(s.active_ms or 0), int(s.pageviews or 0),
            int(s.clicks or 0), int(s.max_scroll_pct or 0), s.entry_page or "",
            s.exit_page or "", s.channel or "", s.device or "",
            1 if s.is_new_visitor else 0, 1 if s.is_engaged else 0,
            int(s.micro_goals or 0), int(s.macro_goals or 0), 1 if s.is_bot else 0,
            int(s.bot_score or 0), 1 if s.is_internal else 0,
        ] for s in part], _SERVER_SESSION_COLUMNS)
        total += len(part)

    base = [
        RawMetrikaVisit.visit_id, RawMetrikaVisit.client_id_hash,
        RawMetrikaVisit.visit_date, RawMetrikaVisit.start_time,
        RawMetrikaVisit.start_url, RawMetrikaVisit.traffic_source,
        RawMetrikaVisit.search_engine, RawMetrikaVisit.duration_seconds,
        RawMetrikaVisit.goals_json,
    ]
    if dialect == "postgresql":
        extra = [
            _json_text(RawMetrikaVisit.raw_json, k).label(f"jk{i}")
            for i, k in enumerate(_VISIT_JSON_KEYS)
        ]
    else:
        extra = [RawMetrikaVisit.raw_json]
    n_base = len(base)
    async for part in _stream_partitions(
        select(*base, *extra).where(RawMetrikaVisit.visit_date >= since.date()),
        _REPLACING_BATCH,
    ):
        payload = []
        for row in part:
            if dialect == "postgresql":
                blob = {k: row[n_base + i] for i, k in enumerate(_VISIT_JSON_KEYS)
                        if row[n_base + i]}
            else:
                blob = row[n_base]
            v = _VisitLite(row.goals_json, blob)
            payload.append([
                row.visit_id, row.client_id_hash or "",
                row.visit_date or datetime(1970, 1, 1).date(),
                _dt(row.start_time), row.start_url or "", row.traffic_source or "",
                row.search_engine or "", int(row.duration_seconds or 0),
                1 if visit_has_business_goal(v, biz_ids) else 0,
                visit_device(v), visit_browser(v), visit_os(v),
                1 if visit_field(v, "ym:s:isNewUser") == "1" else 0,
            ])
        await _ch_insert(ch, "raw_metrika_visits", payload, _VISIT_COLUMNS)
        total += len(part)

    async with analytics_session() as db:
        links = (await db.execute(select(
            IdentityLink.user_id, IdentityLink.visitor_id_hash,
            IdentityLink.first_seen, IdentityLink.last_seen,
        ))).all()
    if links:
        await _ch_insert(
            ch, "identity_links",
            [[l.user_id, l.visitor_id_hash, _dt(l.first_seen), _dt(l.last_seen)] for l in links],
            ["user_id", "visitor_id_hash", "first_seen", "last_seen"],
        )
        total += len(links)
    return total


def _ensure_schema(ch) -> None:
    for ddl in _DDL:
        ch.command(ddl)
    for table, column, col_type in _COLUMN_GUARDS:
        ch.command(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}")


async def clickhouse_sync_job() -> None:
    """15-минутный синк. Все CH-вызовы — в thread executor (клиент синхронный)."""
    if not settings.clickhouse_enabled:
        return
    loop = asyncio.get_running_loop()
    try:
        if await resync_pending():
            logger.info("ClickHouse sync deferred: incomplete operator resync")
            return
        ch = await loop.run_in_executor(None, _client)
        await loop.run_in_executor(None, _ensure_schema, ch)
    except Exception as exc:  # noqa: BLE001 — мягкая деградация
        logger.warning("ClickHouse unavailable, sync skipped: %s", exc)
        return
    try:
        n_events = await _sync_events(ch)
        n_repl = await _sync_replacing(ch)
        from app.core.cache import get_state_redis
        r = await get_state_redis()
        progress = await event_sync_progress()
        if progress and all(part["caught_up"] for part in progress.values()) and not await resync_pending():
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
    """Explicit full rebuild, streaming repeated bounded pages until caught up.

    Unlike an ordinary job this operator action traverses the whole history.
    A busy PostgreSQL writer defers completion rather than advertising a fresh
    heartbeat over a partial rebuild. Durable resync_pending blocks ordinary
    jobs and slice reads until a successful operator retry. Coordinate this
    action with the scheduler: the marker is not a cross-process fencing lease.
    """
    loop = asyncio.get_running_loop()
    ch = await loop.run_in_executor(None, _client)
    try:
        from app.core.cache import get_state_redis
        r = await get_state_redis()
        await r.set(_RESYNC_PENDING_KEY, "1")
        await r.delete(_LAST_SYNC_KEY, _EVENT_PROGRESS_KEY)
        # Reset both before the first destructive operation. Failure midway
        # must never leave an empty CH event table paired with an old cursor.
        for table in ("behavior_events", "frontend_events"):
            await _cursor_set(table, 0)
        # DROP+CREATE (не TRUNCATE): ресинк подхватывает и изменения схемы
        # (новые колонки вроде bot_score/is_internal) без ручных ALTER.
        for table in ("behavior_events", "frontend_events", "behavior_sessions",
                      "server_sessions", "raw_metrika_visits", "identity_links"):
            await loop.run_in_executor(None, ch.command, f"DROP TABLE IF EXISTS {table}")
        await loop.run_in_executor(None, _ensure_schema, ch)
        n_events = 0
        while True:
            n_events += await _sync_events(ch)
            progress = await event_sync_progress()
            if progress and all(part["caught_up"] for part in progress.values()):
                break
            if any(part["deferred"] for part in progress.values()):
                raise RuntimeError("ClickHouse resync incomplete: active PostgreSQL event writer")
        n_repl = await _sync_replacing(ch, days=3650)
        await r.set(_LAST_SYNC_KEY, datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
        await r.delete(_RESYNC_PENDING_KEY)
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
    "pageviews": ("behavior_events", "uniqExactIf(id, event_type = 'pageview')"),
    "clicks": ("behavior_events", "uniqExactIf(id, event_type = 'click')"),
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


_SLICE_TIMEOUT_SEC = 20


async def run_slice(metric: str, dims: list[str], days: int = 30, limit: int = 1000) -> dict[str, Any]:
    """Конструктор среза: метрика × 1-2 измерения × период → строки.

    Только ClickHouse, без Postgres. Таймаут — чтобы зависший CH не держал
    воркер; вызывающий код (BI «Срезы», Пульс) ловит исключение сам.
    """
    if metric not in SLICE_METRICS:
        raise ValueError(f"Unknown metric: {metric}")
    if await resync_pending():
        raise RuntimeError("Слой данных временно недоступен: обслуживание")
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
        ch = _client(send_receive_timeout=_SLICE_TIMEOUT_SEC)
        try:
            res = ch.query(sql)
            return list(res.column_names), res.result_rows
        finally:
            ch.close()

    try:
        cols, rows = await asyncio.wait_for(
            loop.run_in_executor(None, _run),
            timeout=_SLICE_TIMEOUT_SEC + 5,
        )
    except TimeoutError as exc:
        raise RuntimeError("ClickHouse slice timed out") from exc
    return {
        "metric": metric, "dimensions": sel_dims, "days": days, "sql": sql,
        "columns": cols,
        "rows": [dict(zip(cols, r, strict=False)) for r in rows],
    }
