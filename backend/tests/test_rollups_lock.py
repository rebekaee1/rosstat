"""Один пересчёт аналитики за раз (19.11.2026).

19.11.2026 04:59:54 ночной пересчёт (60 дней, окна по 3 дня) упал с UniqueViolationError
uq_server_session_visitor_start: 15-минутный прогон в ту же минуту переносил ту же left_owner-сессию
(02.11 13:17 → 18.11 20:41), обе транзакции удалили и вставили одну строку server_sessions. Теперь каждая
транзакция прогона начинается с pg_advisory_xact_lock (ночной ждёт) или pg_try_advisory_xact_lock
(15-минутный уступает и не сохраняет отметки).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from tests.test_analytics2 import _run_with_db


class _FakePgDb:
    """Сессия с диалектом postgresql: записывает SQL, try-lock отвечает `free`."""

    def __init__(self, free: bool = True):
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        self.sql: list[tuple[str, dict]] = []
        self.free = free

    async def execute(self, stmt, params=None):
        self.sql.append((str(stmt), params or {}))
        return SimpleNamespace(scalar=lambda: self.free)


def test_lock_sql_on_postgres():
    import app.tasks.analytics_rollups as ar

    db = _FakePgDb()
    asyncio.run(ar._lock_rollups(db, wait=True))
    assert db.sql == [("SELECT pg_advisory_xact_lock(:k)", {"k": ar._ROLLUPS_LOCK_KEY})]

    db = _FakePgDb(free=True)
    asyncio.run(ar._lock_rollups(db, wait=False))
    assert db.sql == [("SELECT pg_try_advisory_xact_lock(:k)", {"k": ar._ROLLUPS_LOCK_KEY})]

    with pytest.raises(ar.RollupsBusy):
        asyncio.run(ar._lock_rollups(_FakePgDb(free=False), wait=False))


def test_lock_is_noop_on_sqlite():
    import app.tasks.analytics_rollups as ar

    db = _FakePgDb()
    db.bind.dialect.name = "sqlite"
    asyncio.run(ar._lock_rollups(db, wait=False))
    assert db.sql == []


def test_every_transaction_of_the_run_takes_the_lock(monkeypatch):
    """Каждое окно сессионизации и каждая сводка берут блокировку первой командой своей транзакции."""
    import app.tasks.analytics_rollups as ar
    from app.models import BehaviorEvent

    now = datetime.utcnow().replace(microsecond=0)

    async def scenario(maker):
        async with maker() as db:
            for d in range(1, 7):
                db.add(BehaviorEvent(session_id_hash=f"s{d}", visitor_id_hash="v", event_type="pageview",
                                     page="/", params_json={}, occurred_at=now - timedelta(days=d, hours=1)))
            await db.commit()
        monkeypatch.setattr(ar, "analytics_session", maker)
        monkeypatch.setattr(ar, "SESSIONIZE_WINDOW_DAYS", 3)
        locks: list[bool] = []
        real_lock = ar._lock_rollups

        async def spy_lock(db, wait):
            locks.append(wait)
            return await real_lock(db, wait)

        monkeypatch.setattr(ar, "_lock_rollups", spy_lock)
        windows: list[tuple] = []
        real = ar.sessionize

        async def spy(db, since, until=None, **kw):
            windows.append((since, until))
            return await real(db, since, until=until, **kw)

        monkeypatch.setattr(ar, "sessionize", spy)
        stats = await ar.run_rollups(days=8, statement_timeout_ms=600_000)
        assert stats["sessions"] == 6
        assert len(windows) >= 3
        # окна сессионизации + трафик, цели, разрезы, страницы, регистрации
        assert locks == [True] * (len(windows) + 5)

        locks.clear()
        await ar.run_rollups(days=2, wait_for_lock=False)
        assert locks and set(locks) == {False}

    _run_with_db(scenario)


def test_busy_lock_is_not_swallowed_by_optional_steps(monkeypatch):
    """Разрезы целей и регистрации глушат свои ошибки; занятая блокировка должна пройти наверх."""
    import app.tasks.analytics_rollups as ar

    calls: list[str] = []

    @asynccontextmanager
    async def session(statement_timeout_ms, wait_for_lock=True):
        yield object()

    async def ok(name):
        calls.append(name)
        return 0

    monkeypatch.setattr(ar, "_rollup_session", session)
    monkeypatch.setattr(ar, "sessionize", lambda db, since, until=None, **kw: ok("sessionize"))
    monkeypatch.setattr(ar, "rollup_daily_traffic", lambda db, d: ok("traffic"))
    monkeypatch.setattr(ar, "rollup_daily_goals", lambda db, d: ok("goals"))

    async def busy(db, d):
        raise ar.RollupsBusy("held")

    monkeypatch.setattr(ar, "rollup_daily_goal_dims", busy)
    monkeypatch.setattr(ar, "rollup_daily_pages", lambda db, d: ok("pages"))
    with pytest.raises(ar.RollupsBusy):
        asyncio.run(ar.run_rollups(days=2, wait_for_lock=False))
    assert "pages" not in calls


def test_short_run_yields_to_nightly_and_keeps_marks(monkeypatch):
    """15-минутный при занятой блокировке не падает и не сохраняет отметки: следующий возьмёт всё с прежних."""
    import app.tasks.analytics_rollups as ar
    from app.config import settings

    seen: list[dict] = []
    saved: list[dict] = []

    async def busy_run(**kw):
        seen.append(kw)
        raise ar.RollupsBusy("held")

    async def no_marks(db):
        return {"behavior_events": 10}

    class _Db:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    async def load():
        return None

    async def save(marks):
        saved.append(marks)

    monkeypatch.setattr(ar, "run_rollups", busy_run)
    monkeypatch.setattr(ar, "analytics_session", lambda: _Db())
    monkeypatch.setattr(ar, "current_marks", no_marks)
    monkeypatch.setattr(ar, "_load_marks", load)
    monkeypatch.setattr(ar, "_save_marks", save)
    monkeypatch.setattr(settings, "analytics_sessionize_incremental_enabled", True)
    assert asyncio.run(ar.run_rollups_15min()) == {"mode": "skipped"}
    assert seen and seen[0]["wait_for_lock"] is False
    assert saved == []


def test_nightly_waits_for_the_lock(monkeypatch):
    import app.tasks.analytics_rollups as ar

    seen: list[dict] = []

    async def fake_run(**kw):
        seen.append(kw)
        return {}

    async def fail(*a, **kw):
        raise RuntimeError("not under test")

    monkeypatch.setattr(ar, "run_rollups", fake_run)
    monkeypatch.setattr(ar, "analytics_session", fail)
    asyncio.run(ar.rollups_daily_job())
    assert seen and seen[0].get("wait_for_lock", True) is True
