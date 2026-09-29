"""ClickHouse-синк не блокирует event loop и не держит весь хвост в памяти.

Инцидент 2026-09-28/29: каждые 15 минут синк грузил ~130k ORM-объектов
(сессии + визиты Метрики за 2 суток, раздутые бот-фермой) и синхронно писал
их в ClickHouse прямо в event loop. Процесс scheduler упирался в cgroup 1 ГиБ,
уходил в своп и замирал на десятки секунд — соседние джобы получали
«Timeout reading from redis-state», Postgres-запросы — BrokenPipe.
"""

import asyncio
import threading
from datetime import datetime, timedelta, timezone

import pytest


class _FakeCH:
    def __init__(self):
        self.inserts: list[tuple[str, list, list[str], int]] = []

    def insert(self, table, data, column_names):
        self.inserts.append((table, [list(r) for r in data], list(column_names), threading.get_ident()))

    def rows(self, table):
        return [r for t, rows, _cols, _tid in self.inserts if t == table for r in rows]

    def cols(self, table):
        return next(cols for t, _rows, cols, _tid in self.inserts if t == table)


@pytest.fixture
def ch_env(auth_env, monkeypatch):
    import app.services.clickhouse_sync as chs

    monkeypatch.setattr(chs, "analytics_session", auth_env["session_maker"])
    monkeypatch.setattr(chs, "_BATCH", 2)
    monkeypatch.setattr(chs, "_REPLACING_BATCH", 2)
    return auth_env


def _seed(session_maker):
    from app.models import (
        BehaviorEvent,
        BehaviorSession,
        FrontendEvent,
        IdentityLink,
        RawMetrikaVisit,
        ServerSession,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async def _run():
        async with session_maker() as db:
            for i in range(5):
                db.add(BehaviorEvent(event_type="click", session_id_hash=f"s{i}",
                                     page="/russia/indicator/cpi", params_json={"i": i},
                                     occurred_at=now))
            for i in range(3):
                db.add(FrontendEvent(event_name="indicator_view", url="/x",
                                     params_json={"i": i}, occurred_at=now))
            for i in range(5):
                db.add(BehaviorSession(session_id_hash=f"bs{i}", visitor_id_hash=f"v{i}",
                                       started_at=now - timedelta(minutes=i), channel="direct"))
            # Вне окна 2 суток — не синкается.
            db.add(BehaviorSession(session_id_hash="old", started_at=now - timedelta(days=5)))
            for i in range(4):
                db.add(ServerSession(day=now.date(), visitor_id_hash=f"v{i}",
                                     started_at=now - timedelta(minutes=i), ended_at=now,
                                     pageviews=i + 1))
            for i in range(3):
                db.add(RawMetrikaVisit(
                    counter_id="1", visit_id=f"visit-{i}", client_id_hash=f"c{i}",
                    visit_date=now.date(), start_time=now, traffic_source="organic",
                    goals_json={"goals": "[]"},
                    raw_json={"ym:s:deviceCategory": "1", "ym:s:browser": "chrome",
                              "ym:s:operatingSystemRoot": "windows", "ym:s:isNewUser": "1",
                              "blob": "x" * 50_000},
                    row_hash=f"h{i}",
                ))
            db.add(IdentityLink(user_id="u1", visitor_id_hash="v1"))
            await db.commit()

    asyncio.run(_run())


def test_sync_streams_in_batches_off_event_loop(ch_env):
    import app.services.clickhouse_sync as chs

    _seed(ch_env["session_maker"])
    ch = _FakeCH()

    async def _run():
        loop_thread = threading.get_ident()
        n_events = await chs._sync_events(ch)
        n_repl = await chs._sync_replacing(ch)
        return loop_thread, n_events, n_repl

    loop_thread, n_events, n_repl = asyncio.run(_run())

    assert n_events == 5 + 3
    assert n_repl == 5 + 4 + 3 + 1
    assert ch.inserts, "ничего не вставлено"
    # Сетевой insert в CH — только в thread executor, не в event loop.
    assert all(tid != loop_thread for *_rest, tid in ch.inserts)
    # Потоковая выгрузка: ни одна вставка не больше пачки.
    assert max(len(rows) for _t, rows, _c, _tid in ch.inserts) <= 2

    assert len(ch.rows("behavior_events")) == 5
    assert len(ch.rows("frontend_events")) == 3
    sessions = ch.rows("behavior_sessions")
    assert sorted(r[0] for r in sessions) == [f"bs{i}" for i in range(5)]
    assert len(ch.rows("server_sessions")) == 4
    assert len(ch.rows("identity_links")) == 1

    visits = ch.rows("raw_metrika_visits")
    assert sorted(r[0] for r in visits) == ["visit-0", "visit-1", "visit-2"]
    cols = ch.cols("raw_metrika_visits")
    row = dict(zip(cols, visits[0]))
    # Маппинг Метрики сохранён (ключи raw_json доступны без ORM).
    assert row["device"] == "desktop"
    assert row["browser"] == "Chrome"
    assert row["os"] == "Windows"
    assert row["is_new"] == 1
    assert row["has_goal"] == 0


def test_event_cursor_advances(ch_env):
    import app.services.clickhouse_sync as chs

    _seed(ch_env["session_maker"])
    ch = _FakeCH()

    async def _run():
        await chs._sync_events(ch)
        first = len(ch.inserts)
        again = await chs._sync_events(ch)
        return first, again

    first, again = asyncio.run(_run())
    assert first > 0
    assert again == 0, "повторный синк не должен перезаливать события"
