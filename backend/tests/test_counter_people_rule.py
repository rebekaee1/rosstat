"""Сверка с Метрикой по людям, а не по «не подтверждено» (пункт 8 разбора Пульса 20.11.2026).

19.11: «Google: у нас 87, в Метрике 15» — 75 из 87 были ферма «не подтверждено»; алерт «Скрейп из Сингапура
1288 сессий» — 1275 из них уже роботы; в сырых визитах Метрики 1 817 «прямых» из Сингапура с длительностью 0 с.
"""
from datetime import date, datetime, timedelta

import fakeredis.aioredis

from app.models import BehaviorSession, RawMetrikaVisit, ServerSession
from app.services import analytics_alerts as alerts
from test_analytics2 import _run_with_db

DAY = date(2026, 11, 19)
START = datetime(2026, 11, 18, 21)


def _quiet_alerts(monkeypatch) -> list[tuple[str, str]]:
    from app.core import cache as cache_mod

    sent: list[tuple[str, str]] = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        sent.append((kind, message))
        return True

    monkeypatch.setattr(cache_mod, "_state_redis", fakeredis.aioredis.FakeRedis(decode_responses=True))
    monkeypatch.setattr("app.services.alerting.send_telegram", fake_send)
    return sent


def _portrait(db, sid, visitor, at, *, human, bot=False, country=None, channel="search", host="google.com"):
    db.add(BehaviorSession(session_id_hash=sid, visitor_id_hash=visitor, started_at=at, channel=channel,
                           referrer_host=host, country=country))
    db.add(ServerSession(day=DAY, visitor_id_hash=visitor, started_at=at, ended_at=at, is_bot=bot,
                         is_human=human, bot_score=80 if bot else 10))


def test_counter_mismatch_counts_confirmed_people_not_unconfirmed_farm(monkeypatch):
    sent = _quiet_alerts(monkeypatch)

    async def scenario(maker):
        monkeypatch.setattr(alerts, "analytics_session", maker)
        async with maker() as db:
            for n in range(12):  # люди из Google
                _portrait(db, f"h{n}", f"hv{n}", START + timedelta(hours=8, minutes=n), human=True)
            for n in range(75):  # ферма Chrome 158 Linux: не робот по счёту, но и не человек
                _portrait(db, f"u{n}", f"uv{n}", START + timedelta(hours=9, minutes=n), human=False)
            # Посетитель с одной неподтверждённой и одной подтверждённой сессией — человек.
            at = START + timedelta(hours=11)
            db.add(BehaviorSession(session_id_hash="mix", visitor_id_hash="hv0", started_at=at,
                                   channel="search", referrer_host="google.com"))
            db.add(ServerSession(day=DAY, visitor_id_hash="hv0", started_at=at, ended_at=at, is_bot=False,
                                 is_human=False))
            for n in range(15):
                db.add(RawMetrikaVisit(counter_id=1, visit_id=n + 1, client_id_hash=f"m{n}", visit_date=DAY,
                                       traffic_source="organic", search_engine="google", raw_json={},
                                       row_hash=f"h{n}"))
            await db.commit()
        return await alerts.check_engine_counter_mismatch(DAY)

    assert _run_with_db(scenario) == []  # 13 людей против 15 визитов Метрики — расхождения нет
    assert sent == []


def test_portrait_conditions_keep_unrated_sessions():
    """Сессии до правила (is_human NULL) и портреты без server_sessions остаются в портретах."""
    from sqlalchemy import func, select

    from app.services.analytics_marts import human_portrait_conditions

    async def scenario(maker):
        async with maker() as db:
            at = START + timedelta(hours=8)
            _portrait(db, "unrated", "v-null", at, human=None)
            _portrait(db, "unconfirmed", "v-false", at, human=False)
            _portrait(db, "robot", "v-bot", at, human=False, bot=True)
            db.add(BehaviorSession(session_id_hash="no-server", visitor_id_hash="v-none", started_at=at))
            db.add(BehaviorSession(session_id_hash="no-visitor", visitor_id_hash=None, started_at=at))
            await db.commit()
            conds = await human_portrait_conditions(db, DAY, DAY)
            rows = (await db.execute(select(BehaviorSession.session_id_hash).where(*conds))).scalars().all()
            assert sorted(rows) == ["no-server", "no-visitor", "unrated"]
            assert await db.scalar(select(func.count()).select_from(BehaviorSession)) == 5

    _run_with_db(scenario)


def test_singapore_alert_only_for_sessions_past_the_bot_filter(monkeypatch):
    from app.services import pulse

    sent = _quiet_alerts(monkeypatch)

    async def scenario(maker):
        monkeypatch.setattr(pulse, "analytics_session", maker)
        async with maker() as db:
            for n in range(120):  # ферма из Сингапура, уже роботы
                _portrait(db, f"sg{n}", f"sgv{n}", START + timedelta(hours=2, seconds=n), human=False, bot=True,
                          country="Сингапур", channel="direct", host=None)
            for n in range(5):
                _portrait(db, f"sgh{n}", f"sghv{n}", START + timedelta(hours=3, seconds=n), human=False,
                          country="Сингапур", channel="direct", host=None)
            for n in range(30):
                _portrait(db, f"ru{n}", f"ruv{n}", START + timedelta(hours=4, seconds=n), human=True,
                          country="Россия", channel="direct", host=None)
            await db.commit()
        first = await pulse._bot_signals(DAY)
        async with maker() as db:
            for n in range(120):  # та же ферма прошла мимо фильтра
                _portrait(db, f"sgl{n}", f"sglv{n}", START + timedelta(hours=5, seconds=n), human=False,
                          country="Сингапур", channel="direct", host=None)
            await db.commit()
        second = await pulse._bot_signals(DAY)
        return first, second

    first, second = _run_with_db(scenario)
    assert first["singapore"] == 125 and first["singapore_not_bot"] == 5
    assert second["singapore_not_bot"] == 125
    kinds = [k for k, _ in sent]
    assert kinds.count("sg_scrape") <= 1
    assert any("прошёл мимо фильтра роботов: 125" in m for _, m in sent)


def test_pulse_metrika_visits_leave_zero_second_direct_aside(tmp_path, monkeypatch):
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.models import AnalyticsSyncRun, MetrikaReportSnapshot, MetrikaSearchPhrase
    from app.services.pulse import _acquisition_from_warehouse

    monkeypatch.setattr(settings, "analytics_allowed_counter_ids", "test")

    async def run():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'acq.db'}")
        async with engine.begin() as conn:
            for model in (AnalyticsSyncRun, MetrikaReportSnapshot, MetrikaSearchPhrase, RawMetrikaVisit):
                await conn.run_sync(model.__table__.create)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            rows = [("direct", 0)] * 6 + [("direct", 40)] * 2 + [("organic", 0)] * 3 + [("organic", 90)] * 4
            for i, (source, sec) in enumerate(rows):
                db.add(RawMetrikaVisit(counter_id="test", visit_id=f"v{i}", row_hash=f"r{i}", visit_date=DAY,
                                       client_id_hash=f"c{i}", traffic_source=source, duration_seconds=sec,
                                       raw_json={"ym:s:browser": "chrome"}))
            await db.commit()
            acq = await _acquisition_from_warehouse(db, DAY)
        await engine.dispose()
        return acq["raw_visits"]

    raw = asyncio.run(run())
    assert raw == {"total": 9, "by_source": {"direct": 2, "organic": 7}, "direct_zero_seconds_excluded": 6}
