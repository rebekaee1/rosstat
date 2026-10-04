"""Opt-in F05b на реальном ClickHouse: слияние сессий в PG убирает ключ из CH.

Нужны оба изолированных контура: F01_TEST_DATABASE_URL (PG) и
F06_TEST_CLICKHOUSE_URL (CH, см. test_clickhouse_replication_ch.py). Состояние
Redis не требуется: журнал не использует курсор.
"""
import asyncio

from app.services import clickhouse_sync as sync
from test_clickhouse_replication_ch import actual_clickhouse
from test_session_change_log import VISITOR, _add, _event, _sessionize, log
from test_session_change_log_pg import journal_database


def test_native_clickhouse_drops_merged_session_and_keeps_survivor(monkeypatch):
    monkeypatch.setattr(log.settings, "clickhouse_enabled", True)

    async def scenario():
        async with journal_database() as maker:
            monkeypatch.setattr(sync, "analytics_session", maker)
            async with actual_clickhouse(monkeypatch) as ch:
                async def snapshot():
                    result = await asyncio.to_thread(
                        ch.query,
                        "SELECT toUnixTimestamp(started_at), pageviews FROM server_sessions FINAL "
                        "WHERE visitor_id_hash = {v:String} ORDER BY started_at",
                        parameters={"v": VISITOR},
                    )
                    return result.result_rows

                await _add(maker, _event(0), _event(40))
                await _sessionize(maker)
                await sync._sync_session_changes(ch)
                assert len(await snapshot()) == 2
                # Опоздавшая точка склеивает сессии: ключ T0+40 исчезает из PG.
                await _add(maker, _event(20))
                await _sessionize(maker)
                assert await sync._sync_session_changes(ch) == 2
                rows = await snapshot()
                assert len(rows) == 1 and rows[0][1] == 3
                assert await sync._sync_session_changes(ch) == 0  # идемпотентно
    asyncio.run(scenario())
