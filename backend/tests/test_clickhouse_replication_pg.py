"""Late-commit replication through two real PostgreSQL writer transactions.

Only explicit isolated loopback fe_f01_* PostgreSQL is accepted; each test owns
one UUID schema. Initial tests use an observed sink, then optional real CH
acceptance exercises logical deduplication separately from physical inserts.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from urllib.parse import urlsplit
from uuid import uuid4

import fakeredis.aioredis
import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateIndex, CreateSchema, CreateTable, DropSchema

from app.core import cache
from app.models import BehaviorEvent, FrontendEvent, ServerSessionChange
from app.services import clickhouse_sync as sync
from test_world_national_reconcile_pg import _validated_pg_url


@asynccontextmanager
async def event_database(monkeypatch):
    raw = os.environ.get("F01_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set explicit isolated F01_TEST_DATABASE_URL")
    parts = urlsplit(raw)
    url = _validated_pg_url(raw)
    if url.port in {None, 5432} or parts.query or parts.fragment:
        pytest.fail("Event test PostgreSQL requires nondefault loopback port without query/fragment")
    schema = f"f06_test_{uuid4().hex}"
    engine = create_async_engine(url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}})
    created = False
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        async with engine.begin() as db:
            await db.execute(CreateSchema(schema))
        created = True
        async with engine.begin() as db:
            for model in (BehaviorEvent, FrontendEvent, ServerSessionChange):
                await db.execute(CreateTable(model.__table__))
                for index in model.__table__.indexes:
                    await db.execute(CreateIndex(index))
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(sync, "analytics_session", sessions)
        monkeypatch.setattr(cache, "_state_redis", redis)
        yield sessions, redis
    finally:
        try:
            if created:
                async with engine.begin() as db:
                    await db.execute(DropSchema(schema, cascade=True))
        finally:
            await redis.aclose()
            await engine.dispose()


class ObservedSink:
    def __init__(self):
        self.rows = {"behavior_events": [], "frontend_events": []}

    def insert(self, table, rows, column_names):
        self.rows[table].extend(dict(zip(column_names, row, strict=True)) for row in rows)

    def command(self, sql):
        pass

    def close(self):
        pass


def source_event(model):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if model is BehaviorEvent:
        return model(event_type="pageview", page="/fixture", visitor_id_hash="fixture-visitor", occurred_at=now)
    return model(event_name="fixture_goal", url="/fixture", visitor_id_hash="fixture-visitor", occurred_at=now)


@pytest.mark.parametrize("model", [BehaviorEvent, FrontendEvent])
def test_lower_allocated_id_commits_after_higher_id_and_is_eventually_replicated(monkeypatch, model):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, _):
            sink = ObservedSink()
            async with sessions() as late:
                low = source_event(model)
                late.add(low)
                await late.flush()  # Real sequence allocation/row, still uncommitted.
                async with sessions() as early:
                    high = source_event(model)
                    early.add(high)
                    await early.commit()
                assert low.id < high.id
                try:
                    await sync._sync_events(sink)
                except DBAPIError as exc:
                    # A bounded safe barrier may defer this noncritical copy.
                    assert getattr(exc.orig, "sqlstate", None) == "55P03"
                await late.commit()
            await sync._sync_events(sink)
            assert {row["id"] for row in sink.rows[model.__tablename__]} == {low.id, high.id}
    asyncio.run(scenario())


@pytest.mark.parametrize("model", [BehaviorEvent, FrontendEvent])
def test_legacy_cursor_is_not_reused_for_historical_repair(monkeypatch, model):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            async with sessions() as db:
                db.add_all([source_event(model), source_event(model)])
                await db.commit()
            await redis.set(f"fe:ch:cursor:{model.__tablename__}", "999999")
            sink = ObservedSink()
            await sync._sync_events(sink)
            assert {row["id"] for row in sink.rows[model.__tablename__]} == {1, 2}
    asyncio.run(scenario())


def test_replay_budget_persists_progress_and_continues_next_job(monkeypatch):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            async with sessions() as db:
                db.add_all([source_event(BehaviorEvent) for _ in range(5)])
                await db.commit()
            monkeypatch.setattr(sync, "_BATCH", 2)
            monkeypatch.setattr(sync, "_EVENT_BATCHES_PER_TABLE", 1, raising=False)
            sink = ObservedSink()
            assert await sync._sync_events(sink) == 2
            assert len(sink.rows["behavior_events"]) == 2
            assert await sync._sync_events(sink) == 2
            assert await sync._sync_events(sink) == 1
            assert await sync._sync_events(sink) == 0
            assert {row["id"] for row in sink.rows["behavior_events"]} == {1, 2, 3, 4, 5}
    asyncio.run(scenario())


@pytest.mark.parametrize("sequence_setting", ["CACHE 20", "CYCLE", "INCREMENT BY -1 MINVALUE -999999"])
def test_unsafe_sequence_configuration_never_advances_cursor(monkeypatch, sequence_setting):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            async with sessions() as db:
                db.add(source_event(BehaviorEvent))
                await db.commit()
                sequence = await db.scalar(text("SELECT pg_get_serial_sequence('behavior_events', 'id')"))
                # Name comes solely from owned synthetic schema metadata, never a request.
                await db.execute(text(f"ALTER SEQUENCE {sequence} {sequence_setting}"))
                await db.commit()
            sink = ObservedSink()
            with pytest.raises(RuntimeError, match="sequence"):
                await sync._sync_events(sink)
            assert await redis.get(sync._CURSOR_KEY.format(table="behavior_events")) is None
            assert sink.rows["behavior_events"] == []
    asyncio.run(scenario())


def test_non_read_committed_source_is_rejected_before_publication(monkeypatch):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            async with sessions() as db:
                db.add(source_event(BehaviorEvent))
                await db.commit()
            engine = sessions.kw["bind"]
            unsafe = async_sessionmaker(engine.execution_options(isolation_level="REPEATABLE READ"), expire_on_commit=False)
            monkeypatch.setattr(sync, "analytics_session", unsafe)
            sink = ObservedSink()
            with pytest.raises(RuntimeError, match="READ COMMITTED"):
                await sync._sync_events(sink)
            assert await redis.get(sync._CURSOR_KEY.format(table="behavior_events")) is None
            assert sink.rows["behavior_events"] == []
    asyncio.run(scenario())


def test_job_heartbeat_waits_for_complete_bounded_replay(monkeypatch):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            async with sessions() as db:
                db.add_all([source_event(BehaviorEvent) for _ in range(5)])
                await db.commit()
            monkeypatch.setattr(sync, "_BATCH", 2)
            monkeypatch.setattr(sync, "_EVENT_BATCHES_PER_TABLE", 1, raising=False)
            monkeypatch.setattr(sync.settings, "clickhouse_enabled", True)
            sink = ObservedSink()
            monkeypatch.setattr(sync, "_client", lambda: sink)
            monkeypatch.setattr(sync, "_ensure_schema", lambda ch: None)

            async def no_replacing(ch):
                return 0
            monkeypatch.setattr(sync, "_sync_replacing", no_replacing)
            await sync.clickhouse_sync_job()
            assert await redis.get(sync._LAST_SYNC_KEY) is None
            await sync.clickhouse_sync_job()
            assert await redis.get(sync._LAST_SYNC_KEY) is None
            await sync.clickhouse_sync_job()
            assert await sync.last_sync_age_minutes() == 0
            assert (await sync.event_sync_progress())["behavior_events"]["caught_up"] is True
    asyncio.run(scenario())


def test_busy_writer_publishes_deferred_progress_without_fresh_heartbeat(monkeypatch):
    from app.api.admin_bi import slices_meta

    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            async with sessions() as late:
                late.add(source_event(BehaviorEvent))
                await late.flush()
                monkeypatch.setattr(sync.settings, "clickhouse_enabled", True)
                sink = ObservedSink()
                monkeypatch.setattr(sync, "_client", lambda: sink)
                monkeypatch.setattr(sync, "_ensure_schema", lambda ch: None)

                async def no_replacing(ch):
                    return 0
                monkeypatch.setattr(sync, "_sync_replacing", no_replacing)
                await sync.clickhouse_sync_job()
                assert await redis.get(sync._LAST_SYNC_KEY) is None
                meta = await slices_meta(_admin=None)
                progress = meta["sync_progress"]
                assert progress["behavior_events"] == {"cursor": 0, "ceiling": None, "caught_up": False, "deferred": True}
                assert progress["frontend_events"]["caught_up"] is True
                await late.commit()
            await sync.clickhouse_sync_job()
            assert await sync.last_sync_age_minutes() == 0
            assert (await sync.event_sync_progress())["behavior_events"]["caught_up"] is True
    asyncio.run(scenario())


def test_legacy_success_timestamp_does_not_mark_revision_replay_fresh(monkeypatch):
    async def scenario():
        async with event_database(monkeypatch) as (_, redis):
            await redis.set("fe:ch:last_sync_at", datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
            assert await sync.last_sync_age_minutes() is None
            assert await sync.event_sync_progress() == {}
    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["drop_default", "drop_sequence"])
def test_missing_default_or_sequence_fails_closed(monkeypatch, change):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            async with sessions() as db:
                db.add(source_event(BehaviorEvent))
                await db.commit()
                if change == "drop_default":
                    await db.execute(text("ALTER TABLE behavior_events ALTER COLUMN id DROP DEFAULT"))
                else:
                    sequence = await db.scalar(text("SELECT pg_get_serial_sequence('behavior_events', 'id')"))
                    await db.execute(text(f"DROP SEQUENCE {sequence} CASCADE"))
                await db.commit()
            sink = ObservedSink()
            with pytest.raises(RuntimeError, match="sequence"):
                await sync._sync_events(sink)
            assert sink.rows["behavior_events"] == []
            assert await redis.get(sync._CURSOR_KEY.format(table="behavior_events")) is None
    asyncio.run(scenario())


def test_sequence_reset_below_committed_ids_fails_closed(monkeypatch):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            async with sessions() as db:
                db.add_all([source_event(BehaviorEvent) for _ in range(3)])
                await db.commit()
                await db.execute(text("SELECT setval(pg_get_serial_sequence('behavior_events', 'id'), 1, true)"))
                await db.commit()
            sink = ObservedSink()
            with pytest.raises(RuntimeError, match="sequence"):
                await sync._sync_events(sink)
            assert sink.rows["behavior_events"] == []
            assert await redis.get(sync._CURSOR_KEY.format(table="behavior_events")) is None
    asyncio.run(scenario())


def test_deferred_resync_clears_old_success_and_keeps_revision_incomplete(monkeypatch):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            await redis.set(sync._LAST_SYNC_KEY, "2020-01-01T00:00:00")
            await redis.set(sync._EVENT_PROGRESS_KEY, '{"obsolete": {"caught_up": true}}')
            await sync._cursor_set("behavior_events", 999999)
            sink = ObservedSink()
            monkeypatch.setattr(sync, "_client", lambda: sink)
            monkeypatch.setattr(sync, "_ensure_schema", lambda client: None)
            async with sessions() as late:
                late.add(source_event(BehaviorEvent))
                await late.flush()
                with pytest.raises(RuntimeError, match="incomplete"):
                    await sync.resync()
                assert await redis.get(sync._LAST_SYNC_KEY) is None
                assert await sync._cursor_get("behavior_events") == 0
                progress = await sync.event_sync_progress()
                assert "obsolete" not in progress
                assert progress["behavior_events"] == {"cursor": 0, "ceiling": None, "caught_up": False, "deferred": True}
                await late.rollback()
    asyncio.run(scenario())


def test_job_does_not_publish_success_if_maintenance_begins_during_copy(monkeypatch):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            async with sessions() as db:
                db.add(source_event(BehaviorEvent))
                await db.commit()
            monkeypatch.setattr(sync.settings, "clickhouse_enabled", True)
            sink = ObservedSink()
            monkeypatch.setattr(sync, "_client", lambda: sink)
            monkeypatch.setattr(sync, "_ensure_schema", lambda client: None)

            async def maintenance_started(client):
                await redis.set("fe:ch:resync_pending:v2", "1")
                return 0

            monkeypatch.setattr(sync, "_sync_replacing", maintenance_started)
            await sync.clickhouse_sync_job()
            assert (await sync.event_sync_progress())["behavior_events"]["caught_up"] is True
            assert sink.rows["behavior_events"][0]["id"] == 1
            assert await redis.get(sync._LAST_SYNC_KEY) is None
            assert await sync.resync_pending() is True
    asyncio.run(scenario())
