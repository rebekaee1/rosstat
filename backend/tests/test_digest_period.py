"""E1 (круг 11): блок «Пользователи» и поиск в дайджесте считают МСК-сутки."""
import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime

import app.tasks.analytics_scheduler as sched
from app.models import EmailCredential, FrontendEvent, User


def _patch_session(monkeypatch, auth_env):
    @asynccontextmanager
    async def session():
        async with auth_env["session_maker"]() as db:
            yield db

    monkeypatch.setattr(sched, "analytics_session", session)


def test_user_stats_use_moscow_day(monkeypatch, auth_env):
    """Регистрация в 01:00 МСК 08.10 (22:00 UTC 07.10) относится к 08.10, а в 23:00 МСК 07.10
    (20:00 UTC) — к 07.10; скользящих 24 часов больше нет."""
    _patch_session(monkeypatch, auth_env)

    async def seed():
        async with auth_env["session_maker"]() as db:
            db.add_all([
                User(id=uuid.uuid4(), display_name="Ночная", created_at=datetime(2026, 10, 7, 22, 0)),
                User(id=uuid.uuid4(), display_name="Вечерняя", created_at=datetime(2026, 10, 7, 20, 0)),
                User(id=uuid.uuid4(), display_name="Следующая", created_at=datetime(2026, 10, 8, 21, 30)),
            ])
            await db.commit()

    asyncio.run(seed())
    lines8 = asyncio.run(sched._user_stats_lines(date(2026, 10, 8)))
    assert "всего 3" in lines8[0] and "+1 за сутки" in lines8[0]
    assert any("Ночная" in line for line in lines8)
    assert not any("Вечерняя" in line or "Следующая" in line for line in lines8)

    lines7 = asyncio.run(sched._user_stats_lines(date(2026, 10, 7)))
    assert "+1 за сутки" in lines7[0] and any("Вечерняя" in line for line in lines7)


def test_search_lines_use_moscow_day(monkeypatch, auth_env):
    _patch_session(monkeypatch, auth_env)

    async def seed():
        async with auth_env["session_maker"]() as db:
            db.add_all([
                FrontendEvent(event_name="search_query", occurred_at=datetime(2026, 10, 7, 22, 30),
                              params_json={"q": "ввп", "results": 3}),
                FrontendEvent(event_name="search_query", occurred_at=datetime(2026, 10, 7, 20, 30),
                              params_json={"q": "вчера", "results": 3}),
            ])
            await db.commit()

    asyncio.run(seed())
    lines = asyncio.run(sched._search_demand_lines(date(2026, 10, 8)))
    text = "\n".join(lines)
    assert "ввп" in text and "вчера" not in text
