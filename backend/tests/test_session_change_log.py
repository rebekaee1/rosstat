"""F05b: удаления и поздние обновления server_sessions доезжают до ClickHouse.

Логика журнала `server_session_changes` проверяется на изолированном SQLite с
настоящим sessionize; CH подменён записывающим клиентом (команды/вставки).
Реальные PG/CH — в test_session_change_log_pg.py (по образцу F06, в песочнице
пропускается).
"""

import asyncio
import threading
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import BehaviorEvent, ServerSession, ServerSessionChange
from app.services import clickhouse_sync as chs
from app.services import session_change_log as log
from app.tasks import analytics_rollups as rollups
from test_analytics2 import _run_with_db

T0 = datetime(2026, 9, 30, 12, 0, 0)
WINDOW = (T0 - timedelta(hours=1), T0 + timedelta(hours=3))
VISITOR = "visitor-f05b"


class _FakeCH:
    def __init__(self):
        self.inserts: list[tuple[str, list, list[str]]] = []
        self.commands: list[tuple[str, dict | None]] = []
        self.threads: set[int] = set()

    def insert(self, table, data, column_names):
        self.threads.add(threading.get_ident())
        self.inserts.append((table, [list(r) for r in data], list(column_names)))

    def command(self, sql, settings=None):
        self.threads.add(threading.get_ident())
        self.commands.append((sql, settings))

    def rows(self):
        return [dict(zip(cols, row)) for t, rows, cols in self.inserts if t == "server_sessions" for row in rows]


@pytest.fixture
def cl_on(monkeypatch):
    monkeypatch.setattr(log.settings, "clickhouse_enabled", True)
    return monkeypatch


def _event(minute, page="/p", visitor=VISITOR):
    return BehaviorEvent(visitor_id_hash=visitor, session_id_hash="client-" + visitor,
                         occurred_at=T0 + timedelta(minutes=minute),
                         event_type="pageview", page=page, params_json={})


async def _add(maker, *events):
    async with maker() as db:
        db.add_all(events)
        await db.commit()


async def _sessionize(maker, since=WINDOW[0], until=WINDOW[1]):
    async with maker() as db:
        return await rollups.sessionize(db, since, until)


async def _journal(maker):
    async with maker() as db:
        rows = (await db.execute(select(ServerSessionChange).order_by(ServerSessionChange.started_at))).scalars().all()
        return {(r.visitor_id_hash, r.started_at): r.rev for r in rows}


async def _drain(maker):
    async with maker() as db:
        entries = await log.claim(db, 10_000)
        await log.ack(db, entries)


def _epoch(dt):
    return int(dt.timestamp())


def test_mirrored_columns_match_clickhouse_server_sessions_columns():
    assert set(log.MIRRORED_COLUMNS) == set(chs._SERVER_SESSION_COLUMNS) - {"id"}
    assert set(log.MIRRORED_COLUMNS) <= set(ServerSession.__table__.c.keys())


def test_merge_records_vanished_and_changed_keys_and_new_ones(cl_on):
    async def scenario(maker):
        await _add(maker, _event(0), _event(40))  # разрыв 40 мин → две сессии
        await _sessionize(maker)
        first = await _journal(maker)
        assert set(first) == {(VISITOR, T0), (VISITOR, T0 + timedelta(minutes=40))}
        assert set(first.values()) == {1}
        await _drain(maker)

        # Повторный пересчёт без изменений: журнал не пополняется.
        await _sessionize(maker)
        assert await _journal(maker) == {}

        # Опоздавшая точка в середине склеивает сессии: ключ T0+40 исчезает, T0 меняется.
        await _add(maker, _event(20))
        await _sessionize(maker)
        assert set(await _journal(maker)) == {(VISITOR, T0), (VISITOR, T0 + timedelta(minutes=40))}
        async with maker() as db:
            keys = (await db.execute(select(ServerSession.started_at))).scalars().all()
        assert keys == [T0]
    _run_with_db(scenario)


def test_repeated_change_of_same_key_bumps_rev_not_rows(cl_on):
    async def scenario(maker):
        await _add(maker, _event(0))
        await _sessionize(maker)
        await _add(maker, _event(5))
        await _sessionize(maker)
        assert await _journal(maker) == {(VISITOR, T0): 2}
    _run_with_db(scenario)


def test_late_update_of_session_older_than_incremental_window_is_journaled(cl_on):
    since = T0
    before = T0 - timedelta(minutes=10)

    async def scenario(maker):
        await _add(maker, BehaviorEvent(visitor_id_hash=VISITOR, session_id_hash="c", occurred_at=before,
                                        event_type="pageview", page="/a", params_json={}))
        await _sessionize(maker, since - timedelta(hours=1), since + timedelta(hours=2))
        await _drain(maker)
        # Сессия началась ДО since; новая точка в окне присоединяется к ней (carry).
        await _add(maker, _event(10, "/b"))
        await _sessionize(maker, since, since + timedelta(hours=2))
        assert set(await _journal(maker)) == {(VISITOR, before)}
        async with maker() as db:
            row = (await db.execute(select(ServerSession))).scalar_one()
        assert row.started_at == before and row.pageviews == 2
    _run_with_db(scenario)


def test_flag_disabled_writes_nothing(monkeypatch):
    monkeypatch.setattr(log.settings, "clickhouse_enabled", False)

    async def scenario(maker):
        await _add(maker, _event(0), _event(40))
        await _sessionize(maker)
        assert await _journal(maker) == {}
        async with maker() as db:
            assert len((await db.execute(select(ServerSession))).scalars().all()) == 2
            await log.mark_session_ids_changed(db, [1, 2])
            await db.commit()
        assert await _journal(maker) == {}
    _run_with_db(scenario)


def test_repair_style_update_marks_key(cl_on):
    async def scenario(maker):
        await _add(maker, _event(0))
        await _sessionize(maker)
        await _drain(maker)
        async with maker() as db:
            sid = (await db.execute(select(ServerSession.id))).scalar_one()
            await log.mark_session_ids_changed(db, [sid])
            await db.commit()
        assert set(await _journal(maker)) == {(VISITOR, T0)}
    _run_with_db(scenario)


def test_ack_keeps_entries_changed_after_claim(cl_on):
    async def scenario(maker):
        await _add(maker, _event(0))
        await _sessionize(maker)
        async with maker() as db:
            claimed = await log.claim(db, 10)
        await _add(maker, _event(5))
        await _sessionize(maker)  # rev 2 уже после claim
        async with maker() as db:
            await log.ack(db, claimed)
        assert await _journal(maker) == {(VISITOR, T0): 2}
    _run_with_db(scenario)


def test_sync_deletes_vanished_key_replaces_changed_and_is_idempotent(cl_on, auth_env):
    cl_on.setattr(chs, "analytics_session", auth_env["session_maker"])
    maker = auth_env["session_maker"]
    gone_start = T0 + timedelta(minutes=40)

    async def scenario():
        await _add(maker, _event(0), _event(40))
        await _sessionize(maker)
        await _drain(maker)
        await _add(maker, _event(20))
        await _sessionize(maker)
        ch = _FakeCH()
        loop_thread = threading.get_ident()

        assert await chs._sync_session_changes(ch) == 2
        assert len(ch.commands) == 1
        sql, settings = ch.commands[0]
        assert settings == {"mutations_sync": 1}
        assert sql.startswith("ALTER TABLE server_sessions DELETE WHERE (visitor_id_hash, toUnixTimestamp(started_at)) IN (")
        assert f"('{VISITOR}', {_epoch(gone_start)})" in sql
        assert str(_epoch(T0)) not in sql  # живая сессия не удаляется, а заменяется
        rows = ch.rows()
        assert len(rows) == 1 and rows[0]["started_at"] == T0 and rows[0]["pageviews"] == 3
        assert loop_thread not in ch.threads  # сеть CH — только в executor
        assert await _journal(maker) == {}

        again = _FakeCH()
        assert await chs._sync_session_changes(again) == 0
        assert not again.commands and not again.inserts
    asyncio.run(scenario())


def test_sync_reships_session_older_than_two_day_window(cl_on, auth_env):
    cl_on.setattr(chs, "analytics_session", auth_env["session_maker"])
    maker = auth_env["session_maker"]
    before = T0 - timedelta(minutes=10)

    async def scenario():
        await _add(maker, BehaviorEvent(visitor_id_hash=VISITOR, session_id_hash="c", occurred_at=before,
                                        event_type="pageview", page="/a", params_json={}))
        await _sessionize(maker, T0 - timedelta(hours=1), T0 + timedelta(hours=2))
        await _drain(maker)
        await _add(maker, _event(10, "/b"))
        await _sessionize(maker, T0, T0 + timedelta(hours=2))
        ch = _FakeCH()
        assert await chs._sync_session_changes(ch) == 1
        assert not ch.commands
        # Давняя по start сессия переотправлена независимо от окна `since` синка.
        assert [(r["started_at"], r["pageviews"]) for r in ch.rows()] == [(before, 2)]
    asyncio.run(scenario())


def test_same_second_survivor_prevents_delete(cl_on, auth_env):
    """CH хранит секунды: исчезнувший ключ не должен удалить соседа той же секунды."""
    cl_on.setattr(chs, "analytics_session", auth_env["session_maker"])
    maker = auth_env["session_maker"]

    async def scenario():
        async with maker() as db:
            db.add(ServerSession(day=T0.date(), visitor_id_hash=VISITOR, started_at=T0 + timedelta(microseconds=700000),
                                 ended_at=T0 + timedelta(minutes=1), pageviews=4))
            db.add(ServerSessionChange(visitor_id_hash=VISITOR, started_at=T0 + timedelta(microseconds=200000),
                                       rev=1, changed_at=T0))
            await db.commit()
        ch = _FakeCH()
        assert await chs._sync_session_changes(ch) == 1
        assert not ch.commands
        assert [r["pageviews"] for r in ch.rows()] == [4]
    asyncio.run(scenario())


def test_sync_is_bounded_per_run_and_resumes(cl_on, auth_env):
    cl_on.setattr(chs, "analytics_session", auth_env["session_maker"])
    cl_on.setattr(chs, "_CHANGE_BATCH", 2)
    cl_on.setattr(chs, "_CHANGE_BATCHES_PER_RUN", 2)
    cl_on.setattr(chs, "_CHANGE_CHUNK", 2)
    maker = auth_env["session_maker"]

    async def scenario():
        async with maker() as db:
            for i in range(5):
                db.add(ServerSessionChange(visitor_id_hash=f"gone-{i}", started_at=T0 + timedelta(minutes=i),
                                           rev=1, changed_at=T0 + timedelta(seconds=i)))
            await db.commit()
        ch = _FakeCH()
        assert await chs._sync_session_changes(ch) == 4
        assert len(ch.commands) == 2 and all("DELETE" in sql for sql, _ in ch.commands)
        assert len(await _journal(maker)) == 1
        assert await chs._sync_session_changes(ch) == 1
        assert await _journal(maker) == {}
    asyncio.run(scenario())


def test_ch_failure_keeps_journal_for_retry(cl_on, auth_env):
    cl_on.setattr(chs, "analytics_session", auth_env["session_maker"])
    maker = auth_env["session_maker"]

    class _Down(_FakeCH):
        def command(self, sql, settings=None):
            raise RuntimeError("clickhouse down")

    async def scenario():
        async with maker() as db:
            db.add(ServerSessionChange(visitor_id_hash="gone", started_at=T0, rev=1, changed_at=T0))
            await db.commit()
        with pytest.raises(RuntimeError):
            await chs._sync_session_changes(_Down())
        assert len(await _journal(maker)) == 1
        ok = _FakeCH()
        assert await chs._sync_session_changes(ok) == 1
        assert await _journal(maker) == {}
    asyncio.run(scenario())


def test_delete_sql_escapes_visitor_hash():
    sql = chs._delete_sessions_sql([("a'b\\c", 1759233600), ("z", 5)])
    assert "('a\\'b\\\\c', 1759233600), ('z', 5)" in sql


def test_job_order_and_disabled_flag(auth_env, monkeypatch):
    calls = []

    async def events(ch):
        calls.append("events")
        return 0

    async def changes(ch):
        calls.append("changes")
        return 0

    async def replacing(ch, days=2):
        calls.append("replacing")
        return 0

    async def pending():
        return False

    ch = _FakeCH()
    ch.close = lambda: None
    monkeypatch.setattr(chs, "_client", lambda **kw: ch)
    monkeypatch.setattr(chs, "_ensure_schema", lambda c: None)
    monkeypatch.setattr(chs, "resync_pending", pending)
    monkeypatch.setattr(chs, "_sync_events", events)
    monkeypatch.setattr(chs, "_sync_session_changes", changes)
    monkeypatch.setattr(chs, "_sync_replacing", replacing)

    monkeypatch.setattr(chs.settings, "clickhouse_enabled", False)
    asyncio.run(chs.clickhouse_sync_job())
    assert calls == []

    monkeypatch.setattr(chs.settings, "clickhouse_enabled", True)
    asyncio.run(chs.clickhouse_sync_job())
    assert calls == ["events", "changes", "replacing"]
