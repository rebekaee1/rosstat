"""Opt-in native ClickHouse acceptance; physical duplicates are permitted.

PG uses only a UUID schema; CH uses only a UUID database under an explicit
isolated loopback URL. No application settings or DSN is used as a fallback.
"""

import asyncio
from contextlib import asynccontextmanager
import os
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.core import cache
from app.models import BehaviorEvent, FrontendEvent
from app.services import clickhouse_sync as sync
from test_clickhouse_replication_pg import event_database, source_event


@asynccontextmanager
async def actual_state_redis(monkeypatch):
    raw = os.environ.get("F06_TEST_REDIS_URL")
    if not raw:
        pytest.skip("Set explicit isolated F06_TEST_REDIS_URL with reserved database 15")
    parts = urlsplit(raw)
    if (
        parts.scheme != "redis" or parts.hostname not in ("127.0.0.1", "localhost", "::1")
        or parts.port in (None, 6379) or parts.path != "/15"
        or parts.query or parts.fragment
    ):
        pytest.fail("F06 Redis requires isolated loopback nondefault port and reserved database 15")
    redis = Redis.from_url(raw, decode_responses=True)
    keys = [sync._CURSOR_KEY.format(table=table) for table in ("behavior_events", "frontend_events")]
    keys += [sync._EVENT_PROGRESS_KEY, sync._LAST_SYNC_KEY, "fe:ch:cursor:behavior_events", "fe:ch:resync_pending:v2"]
    try:
        await redis.ping()
        await redis.delete(*keys)
        monkeypatch.setattr(cache, "_state_redis", redis)
        yield redis
    finally:
        try:
            await redis.delete(*keys)
        finally:
            await redis.aclose()


@asynccontextmanager
async def actual_clickhouse(monkeypatch):
    raw = os.environ.get("F06_TEST_CLICKHOUSE_URL")
    if not raw:
        pytest.skip("Set explicit isolated F06_TEST_CLICKHOUSE_URL")
    parts = urlsplit(raw)
    if (
        parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost", "::1")
        or parts.port in (None, 8123, 9000) or parts.path != "/fe_analytics"
        or parts.query or parts.fragment
    ):
        pytest.fail("CH acceptance requires isolated loopback nondefault port and fe_analytics database")
    for key, value in (
        ("clickhouse_host", parts.hostname), ("clickhouse_port", parts.port),
        ("clickhouse_user", unquote(parts.username or "default")),
        ("clickhouse_password", unquote(parts.password or "")),
        ("clickhouse_db", "fe_analytics"),
    ):
        monkeypatch.setattr(sync.settings, key, value)
    database = f"fe_f06_test_{uuid4().hex}"
    owner = await asyncio.to_thread(sync._client)
    ch = None
    created = False
    try:
        await asyncio.to_thread(owner.command, f"CREATE DATABASE {database}")
        created = True
        monkeypatch.setattr(sync.settings, "clickhouse_db", database)
        ch = await asyncio.to_thread(sync._client)
        await asyncio.to_thread(sync._ensure_schema, ch)
        yield ch
    finally:
        if ch is not None:
            await asyncio.to_thread(ch.close)
        try:
            if created:
                await asyncio.to_thread(owner.command, f"DROP DATABASE {database}")
        finally:
            await asyncio.to_thread(owner.close)


@pytest.mark.parametrize("model", [BehaviorEvent, FrontendEvent])
def test_late_lower_id_is_once_in_logical_native_clickhouse_query(monkeypatch, model):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, _):
            async with actual_clickhouse(monkeypatch) as ch:
                async with sessions() as late:
                    low = source_event(model)
                    late.add(low)
                    await late.flush()
                    async with sessions() as early:
                        high = source_event(model)
                        early.add(high)
                        await early.commit()
                    await sync._sync_events(ch)  # Active writer safely deferred.
                    assert (await sync.event_sync_progress())[model.__tablename__]["deferred"] is True
                    await late.commit()
                await sync._sync_events(ch)
                result = await asyncio.to_thread(ch.query, f"SELECT uniqExact(id), count() FROM {model.__tablename__}")
                assert result.result_rows == [(2, 2)]
                assert await sync._sync_events(ch) == 0
    asyncio.run(scenario())


def test_redis_ack_failure_and_legacy_duplicates_do_not_inflate_actual_slice_metrics(monkeypatch):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, _):
            async with actual_clickhouse(monkeypatch) as ch:
                async with sessions() as db:
                    click = source_event(BehaviorEvent)
                    click.event_type = "click"
                    db.add_all([source_event(BehaviorEvent), source_event(BehaviorEvent), click])
                    await db.commit()
                set_cursor = sync._cursor_set
                failed = False

                async def fail_once(table, value):
                    nonlocal failed
                    if table == "behavior_events" and not failed:
                        failed = True
                        raise RuntimeError("synthetic Redis acknowledgement failed")
                    await set_cursor(table, value)

                monkeypatch.setattr(sync, "_cursor_set", fail_once)
                with pytest.raises(RuntimeError, match="acknowledgement"):
                    await sync._sync_events(ch)
                await sync._sync_events(ch)  # Replay the acknowledged CH rows.
                result = await asyncio.to_thread(ch.query, "SELECT count(), uniqExact(id) FROM behavior_events")
                assert result.result_rows == [(6, 3)]
                legacy = await asyncio.to_thread(ch.query, "SELECT " + ",".join(sync._EVENT_COLUMNS) + " FROM behavior_events WHERE id = 1 LIMIT 1")
                await sync._ch_insert(ch, "behavior_events", legacy.result_rows, sync._EVENT_COLUMNS)
                result = await asyncio.to_thread(ch.query, "SELECT count(), uniqExact(id) FROM behavior_events")
                assert result.result_rows == [(7, 3)]
                pageviews = await sync.run_slice("pageviews", ["page"], days=1)
                clicks = await sync.run_slice("clicks", ["page"], days=1)
                assert pageviews["rows"] == [{"page": "/fixture", "value": 2}]
                assert clicks["rows"] == [{"page": "/fixture", "value": 1}]
    asyncio.run(scenario())


def test_actual_pg_redis_ch_revision_cursor_and_retry(monkeypatch):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, _):
            async with actual_state_redis(monkeypatch) as redis:
                async with actual_clickhouse(monkeypatch) as ch:
                    async with sessions() as db:
                        db.add_all([source_event(BehaviorEvent), source_event(BehaviorEvent)])
                        await db.commit()
                    await redis.set("fe:ch:cursor:behavior_events", "999999")
                    original = redis.set
                    failed = False

                    async def fail_cursor_once(name, value, *args, **kwargs):
                        nonlocal failed
                        if name == sync._CURSOR_KEY.format(table="behavior_events") and not failed:
                            failed = True
                            raise ConnectionError("synthetic actual Redis cursor acknowledgement failure")
                        return await original(name, value, *args, **kwargs)

                    monkeypatch.setattr(redis, "set", fail_cursor_once)
                    with pytest.raises(ConnectionError, match="acknowledgement"):
                        await sync._sync_events(ch)
                    assert await redis.get(sync._CURSOR_KEY.format(table="behavior_events")) is None
                    assert await sync._sync_events(ch) == 2
                    assert await redis.get(sync._CURSOR_KEY.format(table="behavior_events")) == "2"
                    assert (await sync.event_sync_progress())["behavior_events"]["caught_up"] is True
                    result = await asyncio.to_thread(ch.query, "SELECT count(), uniqExact(id) FROM behavior_events")
                    assert result.result_rows == [(4, 2)]
                    assert (await sync.run_slice("pageviews", ["page"], days=1))["rows"] == [{"page": "/fixture", "value": 2}]
    asyncio.run(scenario())


def test_resync_rebuilds_all_bounded_pages_and_only_then_publishes_success(monkeypatch):
    async def scenario():
        async with event_database(monkeypatch) as (sessions, redis):
            async with actual_clickhouse(monkeypatch) as ch:
                async with sessions() as db:
                    db.add_all([source_event(BehaviorEvent) for _ in range(5)])
                    await db.commit()
                monkeypatch.setattr(sync, "_BATCH", 2)
                monkeypatch.setattr(sync, "_EVENT_BATCHES_PER_TABLE", 1)
                await redis.set(sync._LAST_SYNC_KEY, "2020-01-01T00:00:00")
                await redis.set(sync._EVENT_PROGRESS_KEY, '{"obsolete": {"caught_up": true}}')
                await sync._cursor_set("behavior_events", 999999)
                copy_events = sync._sync_events
                pages = []

                async def observed_page(client):
                    assert await redis.get(sync._LAST_SYNC_KEY) is None
                    count = await copy_events(client)
                    pages.append(count)
                    assert await redis.get(sync._LAST_SYNC_KEY) is None
                    return count

                replacing_windows = []

                async def no_replacing(client, days=2):
                    replacing_windows.append(days)
                    return 0

                monkeypatch.setattr(sync, "_sync_events", observed_page)
                monkeypatch.setattr(sync, "_sync_replacing", no_replacing)
                await sync.resync()
                assert pages == [2, 2, 1]
                assert replacing_windows == [3650]
                assert await sync.last_sync_age_minutes() == 0
                assert (await sync.event_sync_progress())["behavior_events"]["cursor"] == 5
                result = await asyncio.to_thread(ch.query, "SELECT count(), uniqExact(id) FROM behavior_events")
                assert result.result_rows == [(5, 5)]
    asyncio.run(scenario())


def test_interrupted_native_resync_blocks_ordinary_job_until_full_operator_repair(monkeypatch):
    from fastapi import HTTPException
    from app.api.admin_bi import slices_meta, slices_query

    async def scenario():
        async with event_database(monkeypatch) as (sessions, _):
            async with actual_state_redis(monkeypatch) as redis:
                async with actual_clickhouse(monkeypatch) as ch:
                    async with sessions() as db:
                        db.add_all([source_event(model) for model in (BehaviorEvent, FrontendEvent) for _ in range(5)])
                        await db.commit()
                    assert await sync._sync_events(ch) == 10
                    await redis.set(sync._LAST_SYNC_KEY, "2020-01-01T00:00:00")
                    real_client = sync._client
                    failed = False
                    opened = 0

                    class FaultingClient:
                        def __init__(self, native):
                            self.native = native

                        def command(self, sql):
                            nonlocal failed
                            if sql == "DROP TABLE IF EXISTS frontend_events" and not failed:
                                failed = True
                                raise RuntimeError("synthetic failure after first native DROP")
                            return self.native.command(sql)

                        def insert(self, table, rows, column_names):
                            return self.native.insert(table, rows, column_names=column_names)

                        def close(self):
                            self.native.close()

                    def faulting_client(**kwargs):
                        nonlocal opened
                        opened += 1
                        return FaultingClient(real_client(**kwargs))

                    replacing_windows = []

                    async def no_replacing(client, days=2):
                        replacing_windows.append(days)
                        return 0

                    monkeypatch.setattr(sync, "_client", faulting_client)
                    monkeypatch.setattr(sync, "_sync_replacing", no_replacing)
                    monkeypatch.setattr(sync.settings, "clickhouse_enabled", True)
                    with pytest.raises(RuntimeError, match="first native DROP"):
                        await sync.resync()
                    assert await sync._cursor_get("behavior_events") == 0
                    assert await sync._cursor_get("frontend_events") == 0
                    assert await redis.get("fe:ch:resync_pending:v2") == "1"
                    await sync.clickhouse_sync_job()
                    assert opened == 1  # No ordinary DDL/copy/heartbeat during maintenance.
                    assert await redis.get(sync._LAST_SYNC_KEY) is None
                    assert await asyncio.to_thread(ch.command, "EXISTS TABLE behavior_events") == 0
                    meta = await slices_meta(_admin=None)
                    assert meta["resync_pending"] is True
                    assert meta["available"] is False
                    assert meta["sync_progress"] == {}
                    with pytest.raises(RuntimeError, match="обслуживание"):
                        await sync.run_slice("pageviews", ["page"], days=1)
                    with pytest.raises(HTTPException) as response:
                        await slices_query(metric="pageviews", dims="page", days=1, _admin=None)
                    assert response.value.status_code == 503
                    assert opened == 1  # Consumer guards do not open partial CH tables.
                    await sync.resync()  # Explicit operator retry, injected fault now consumed.
                    assert await redis.get("fe:ch:resync_pending:v2") is None
                    assert await sync.last_sync_age_minutes() == 0
                    assert replacing_windows == [3650]
                    for table in ("behavior_events", "frontend_events"):
                        result = await asyncio.to_thread(ch.query, f"SELECT count(), uniqExact(id) FROM {table}")
                        assert result.result_rows == [(5, 5)]
                        assert await sync._cursor_get(table) == 5
                    assert (await slices_meta(_admin=None))["resync_pending"] is False
    asyncio.run(scenario())
