"""Ночной пересчёт истории аналитики: свой предел запроса (18.11.2026).

На боевом окно дней бот-фермы 27–30.09.2026 (≈ 60 тыс. сессий в неделю) не укладывалось в общий предел пула
аналитики 60 с: исключение обрывало сессионизацию следующих окон и все сводки ночного прогона. Ночной пересчёт
передаёт `analytics_history_statement_timeout_ms`, короткий 15-минутный прогон остаётся на общем пределе.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from tests.test_analytics2 import _run_with_db


def test_history_timeout_reaches_every_transaction_of_the_run(monkeypatch):
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
        limits: list[int] = []

        async def record(db, ms):
            limits.append(ms)

        monkeypatch.setattr(ar, "set_local_statement_timeout", record)
        windows: list[tuple] = []
        real = ar.sessionize

        async def spy(db, since, until=None, **kw):
            windows.append((since, until))
            return await real(db, since, until=until, **kw)

        monkeypatch.setattr(ar, "sessionize", spy)
        stats = await ar.run_rollups(days=8, statement_timeout_ms=600_000)
        assert stats["sessions"] == 6
        # Каждое окно сессионизации и каждая сводка (трафик, цели, разрезы, страницы, регистрации) — своя транзакция.
        assert len(windows) >= 3
        assert len(limits) == len(windows) + 5
        assert set(limits) == {600_000}

        limits.clear()
        await ar.run_rollups(days=2)
        assert limits == [], "короткий прогон остаётся на общем пределе пула"

    _run_with_db(scenario)


def test_nightly_job_passes_history_timeout(monkeypatch):
    import app.tasks.analytics_rollups as ar
    from app.config import settings

    seen: list[dict] = []

    async def fake_run(**kw):
        seen.append(kw)
        return {}

    async def fail(*a, **kw):
        raise RuntimeError("not under test")

    monkeypatch.setattr(ar, "run_rollups", fake_run)
    monkeypatch.setattr(ar, "analytics_session", fail)
    asyncio.run(ar.rollups_daily_job())
    assert seen == [{"days": 60, "statement_timeout_ms": settings.analytics_history_statement_timeout_ms}]
    assert settings.analytics_history_statement_timeout_ms > settings.analytics_db_statement_timeout_ms


def test_short_run_keeps_pool_timeout(monkeypatch):
    import app.tasks.analytics_rollups as ar

    seen: list[dict] = []

    async def fake_run(**kw):
        seen.append(kw)
        return {}

    async def no_marks(db):
        return {}

    class _Db:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(ar, "run_rollups", fake_run)
    monkeypatch.setattr(ar, "analytics_session", lambda: _Db())
    monkeypatch.setattr(ar, "current_marks", no_marks)

    async def no_load():
        return None

    async def no_save(marks):
        return None

    monkeypatch.setattr(ar, "_load_marks", no_load)
    monkeypatch.setattr(ar, "_save_marks", no_save)
    asyncio.run(ar.run_rollups_15min())
    assert seen and "statement_timeout_ms" not in seen[0]
