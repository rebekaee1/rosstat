"""Opt-in F05b на реальном PostgreSQL: журнал пишется в той же транзакции sessionize.

Только изолированный F01_TEST_DATABASE_URL (loopback, нестандартный порт);
схема — UUID-схема на тест. Проверяются настоящие временные таблицы,
`IS DISTINCT FROM`, UNION и INSERT … ON CONFLICT, которые SQLite не доказывает.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import ServerSession, ServerSessionChange
from test_session_change_log import T0, VISITOR, _add, _drain, _event, _journal, _sessionize, log
from test_sessionize_boundaries_pg import _analytics_database, _pg_url


@asynccontextmanager
async def journal_database():
    async with _analytics_database(_pg_url()) as maker:
        async with maker.kw["bind"].begin() as connection:
            await connection.execute(CreateTable(ServerSessionChange.__table__))
            for index in ServerSessionChange.__table__.indexes:
                await connection.execute(CreateIndex(index))
        yield maker


def test_real_pg_merge_journals_vanished_and_changed_keys_atomically(monkeypatch):
    monkeypatch.setattr(log.settings, "clickhouse_enabled", True)

    async def scenario():
        async with journal_database() as maker:
            await _add(maker, _event(0), _event(40))
            await _sessionize(maker)
            assert set(await _journal(maker)) == {(VISITOR, T0), (VISITOR, T0 + timedelta(minutes=40))}
            await _drain(maker)
            await _sessionize(maker)  # без изменений — журнал пуст
            assert await _journal(maker) == {}
            await _add(maker, _event(20))
            await _sessionize(maker)
            assert set(await _journal(maker)) == {(VISITOR, T0), (VISITOR, T0 + timedelta(minutes=40))}
            await _sessionize(maker)  # повтор: rev растёт только при изменении содержимого
            assert set((await _journal(maker)).values()) == {1}
            async with maker() as db:
                assert (await db.execute(select(ServerSession.started_at))).scalars().all() == [T0]
    asyncio.run(scenario())


def test_real_pg_flag_disabled_writes_no_journal(monkeypatch):
    monkeypatch.setattr(log.settings, "clickhouse_enabled", False)

    async def scenario():
        async with journal_database() as maker:
            await _add(maker, _event(0), _event(40))
            await _sessionize(maker)
            assert await _journal(maker) == {}
    asyncio.run(scenario())
