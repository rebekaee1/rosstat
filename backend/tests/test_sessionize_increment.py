"""Инкрементная сессионизация (14.11.2026): тот же результат, что полный прогон.

Сценарий: первая порция событий → полный прогон; затем поступают продолжение сессии, пакет со старыми
occurred_at (пакетная доставка, поздние часы устройства — 16 ч назад), поздний портрет устройства
(behavior_sessions после событий), поздняя цель; один посетитель ничего нового не получает.
Инкремент по отметкам id (запас 0 — чтобы проверить точность отбора) должен дать ту же таблицу
server_sessions, что полный прогон по всем данным в чистой базе.
"""
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import BehaviorEvent, BehaviorSession, FrontendEvent, ServerSession
from app.tasks import analytics_rollups as rollups

from tests.test_analytics2 import _run_with_db

NOW = datetime.utcnow().replace(microsecond=0)
SINCE = NOW - timedelta(days=2)
FIELDS = tuple(c for c in ServerSession.__table__.columns if c.name not in {"id", "computed_at"})


def _ev(visitor, sid, minutes_ago, kind="pageview", page="/russia/indicator/cpi"):
    return BehaviorEvent(visitor_id_hash=visitor, session_id_hash=sid, event_type=kind, page=page,
                         occurred_at=NOW - timedelta(minutes=minutes_ago),
                         params_json={"ref": "https://ya.ru/"} if kind == "pageview" else None)


def _portrait(visitor, sid, minutes_ago, device="desktop"):
    return BehaviorSession(session_id_hash=sid, visitor_id_hash=visitor, device_type=device, channel="search",
                           started_at=NOW - timedelta(minutes=minutes_ago), screen_w=1920, screen_h=1080,
                           cpu_cores=8, is_synthetic=False)


def first_batch():
    return [
        _ev("a", "a1", 200), _ev("a", "a1", 190, "dwell"),
        _ev("b", "b1", 1500), _ev("b", "b1", 1490, "click"),
        _ev("d", "d1", 120), _portrait("a", "a1", 200), _portrait("b", "b1", 1500),
        _ev("e", "e1", 100), _ev("e", "e1", 95, "dwell"), _portrait("e", "e1", 100),
        _ev("f", "f1", 300), _ev("f", "f1", 280, "click"), _portrait("f", "f1", 300),  # ничего нового не получит
    ]


def second_batch():
    return [
        _ev("a", "a1", 180, "click"),                                  # продолжение сессии
        _ev("b", "b0", 1000), _ev("b", "b0", 985, "dwell"),            # пакет: 16 ч назад, другая сессия
        _ev("c", "c1", 900), _ev("c", "c1", 899, "click"), _ev("c", "c1", 850, "dwell"),  # пакетная доставка
        _portrait("d", "d1", 119.99),                                   # поздние данные устройства
        _portrait("c", "c1", 900, device="mobile"),
        FrontendEvent(event_name="download_excel", session_id_hash="e1", visitor_id_hash="e",
                      occurred_at=NOW - timedelta(minutes=96)),       # поздняя цель
    ]


async def _sessions(maker):
    async with maker() as db:
        return [tuple(r) for r in (await db.execute(
            select(*FIELDS).order_by(ServerSession.visitor_id_hash, ServerSession.started_at))).all()]


def test_increment_equals_full_with_late_device_data_and_batches(monkeypatch):
    monkeypatch.setattr(rollups, "INCREMENT_SLACK_ROWS", {k: 0 for k in rollups.INCREMENT_SLACK_ROWS})
    # Портреты отбираются по started_at ≥ отметка − запас; запас 0 + отметка на 2 часа раньше «сейчас» —
    # поздний портрет «d» (started_at 2 ч назад) попадает, старые портреты первой порции — нет.
    monkeypatch.setattr(rollups, "PORTRAIT_INCREMENT_MARGIN", timedelta(0))
    touched = []
    real_stage = rollups._stage

    async def spy_stage(db, table, source, temporary, **kw):
        out = await real_stage(db, table, source, temporary, **kw)
        if table.name.startswith("sessionize_visitors_"):
            touched.append(sorted(r[0] for r in (await db.execute(select(out.c.visitor))).all()))
        return out

    async def incremental(maker):
        async with maker() as db:
            db.add_all(first_batch())
            await db.commit()
        async with maker() as db:
            marks = await rollups.current_marks(db)
            marks["at"] = (NOW - timedelta(minutes=125)).isoformat()
            await rollups.sessionize(db, SINCE)
        before_f = [r for r in await _sessions(maker) if r[1] == "f"]
        async with maker() as db:
            db.add_all(second_batch())
            await db.commit()
        monkeypatch.setattr(rollups, "_stage", spy_stage)
        async with maker() as db:
            await rollups.sessionize(db, SINCE, changed=marks)
        monkeypatch.setattr(rollups, "_stage", real_stage)
        return await _sessions(maker), before_f

    async def full(maker):
        async with maker() as db:
            db.add_all(first_batch())
            await db.commit()
        async with maker() as db:
            db.add_all(second_batch())
            await db.commit()
        async with maker() as db:
            await rollups.sessionize(db, SINCE)
        return await _sessions(maker)

    inc, before_f = _run_with_db(incremental)
    ref = _run_with_db(full)
    assert inc == ref
    # Пересчитаны только посетители с новыми поступлениями; «f» не трогался и остался прежним.
    assert touched == [["a", "b", "c", "d", "e"]]
    assert [r for r in inc if r[1] == "f"] == before_f
    # Поздний портрет дошёл до сессии «d», поздняя цель — до «e», пакет «b» дал отдельную сессию.
    by = {}
    for r in inc:
        by.setdefault(r[1], []).append(dict(zip([c.name for c in FIELDS], r)))
    assert by["d"][0]["device"] == "desktop"
    assert by["e"][0]["micro_goals"] == 1
    assert len(by["b"]) == 2 and by["c"][0]["device"] == "mobile"


def test_15min_runner_switches_between_full_and_increment(monkeypatch):
    import fakeredis.aioredis

    from app.config import settings
    import app.core.cache as cache_mod

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def state():
        return fake

    monkeypatch.setattr(cache_mod, "get_state_redis", state)
    calls = []

    async def fake_run(days=2, changed=None):
        calls.append(changed)
        return {"sessions": 1}

    marks = iter([{"behavior_events": 10, "frontend_events": 1},
                  {"behavior_events": 20, "frontend_events": 2},
                  {"behavior_events": 30, "frontend_events": 3},
                  {"behavior_events": 40, "frontend_events": 4}])

    async def fake_marks(_db):
        return next(marks)

    class Session:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    clock = [NOW]
    monkeypatch.setattr(rollups, "run_rollups", fake_run)
    monkeypatch.setattr(rollups, "current_marks", fake_marks)
    monkeypatch.setattr(rollups, "analytics_session", lambda: Session())
    monkeypatch.setattr(rollups, "_utcnow", lambda: clock[0])

    async def scenario():
        monkeypatch.setattr(settings, "analytics_sessionize_incremental_enabled", False)
        assert (await rollups.run_rollups_15min())["mode"] == "full"
        assert await fake.get(rollups._MARKS_KEY) is None  # выключено — всё как раньше, отметок нет

        monkeypatch.setattr(settings, "analytics_sessionize_incremental_enabled", True)
        assert (await rollups.run_rollups_15min())["mode"] == "full"     # нет отметок → полный
        clock[0] = NOW + timedelta(minutes=15)
        assert (await rollups.run_rollups_15min())["mode"] == "increment"
        assert calls[-1] == {"behavior_events": 20, "frontend_events": 2}  # отметки прошлого прогона
        clock[0] = NOW + timedelta(minutes=56)
        assert (await rollups.run_rollups_15min())["mode"] == "full"     # раз в час — полный
        assert calls[0] is None and calls[1] is None and calls[3] is None

    asyncio.run(scenario())
