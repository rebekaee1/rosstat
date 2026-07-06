"""Аналитика 2.0 (ADR-0010): таксономия целей, каналы, сессионизация, rollup'ы, marts.

Инварианты:
- каждое из 90+ бизнес-событий имеет tier; ошибки/показы — technical (не цели);
- классификация каналов повторяет модель Метрики (ad > campaign > search > ...);
- серверная сессионизация режет поток по правилу 30 минут и считает
  вовлечённость/цели так, как их потом читает воронка;
- rollup'ы дают строки на день × измерение; marts работают на пустой БД без 500.

Всё герметично: SQLite + asyncio.run, без внешних сервисов.
"""
import asyncio
import os
import tempfile
from datetime import datetime, timedelta

import pytest


# ---------------------------------------------------------------------------
# Таксономия целей
# ---------------------------------------------------------------------------

def test_taxonomy_tiers():
    from app.services.goal_taxonomy import (
        TIER_ENGAGEMENT, TIER_MACRO, TIER_MICRO, TIER_TECHNICAL,
        is_conversion, tier_for_event, weight_for_event,
    )

    assert tier_for_event("signup") == TIER_MACRO
    assert tier_for_event("newsletter_opt_in") == TIER_MACRO
    assert tier_for_event("download_csv") == TIER_MICRO
    assert tier_for_event("compare_add") == TIER_MICRO
    assert tier_for_event("scroll_depth") == TIER_ENGAGEMENT
    assert tier_for_event("api_load_error") == TIER_TECHNICAL
    assert tier_for_event("register_nudge_view") == TIER_TECHNICAL

    # Неизвестное событие — вовлечение по умолчанию, не конверсия.
    assert tier_for_event("some_future_event") == TIER_ENGAGEMENT

    assert is_conversion("signup") and is_conversion("download_csv")
    assert not is_conversion("scroll_depth") and not is_conversion("api_load_error")

    # Веса: макро дороже микро, микро дороже вовлечения, technical = 0.
    assert weight_for_event("signup") > weight_for_event("download_csv") > weight_for_event("scroll_depth")
    assert weight_for_event("api_load_error") == 0


# ---------------------------------------------------------------------------
# Классификация каналов
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs,expected", [
    ({"yclid": "123"}, "ad"),
    ({"utm_medium": "cpc", "utm_source": "yandex"}, "ad"),
    ({"utm_source": "newsletter"}, "campaign"),
    ({"referrer": "https://yandex.ru/search/?text=инфляция"}, "search"),
    ({"referrer": "https://www.google.com/"}, "search"),
    ({"referrer": "https://vk.com/feed"}, "social"),
    ({"referrer": "https://t.me/somechannel"}, "social"),
    ({"referrer": "https://forecasteconomy.com/indicator/cpi"}, "internal"),
    ({"referrer": "https://www.rbc.ru/economics/"}, "referral"),
    ({}, "direct"),
    ({"referrer": ""}, "direct"),
])
def test_classify_channel(kwargs, expected):
    from app.services.traffic_channel import classify_channel

    assert classify_channel(**kwargs) == expected


# ---------------------------------------------------------------------------
# Герметичная async-среда (SQLite)
# ---------------------------------------------------------------------------

def _run_with_db(coro_factory):
    """Создать схему во временном SQLite и выполнить coro(db_session_maker)."""
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        sync_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(sync_engine)
        sync_engine.dispose()

        async def _main():
            engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
            maker = async_sessionmaker(engine, expire_on_commit=False)
            try:
                return await coro_factory(maker)
            finally:
                await engine.dispose()

        return asyncio.run(_main())
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Серверная сессионизация
# ---------------------------------------------------------------------------

def test_sessionize_30min_rule_and_goals():
    from app.models import BehaviorEvent, FrontendEvent, ServerSession
    from app.tasks.analytics_rollups import sessionize
    from sqlalchemy import select

    base = datetime.utcnow().replace(microsecond=0) - timedelta(hours=3)

    async def scenario(maker):
        async with maker() as db:
            def ev(minute, etype, page="/indicator/cpi", params=None):
                return BehaviorEvent(
                    session_id_hash="sess1", visitor_id_hash="visitorA",
                    event_type=etype, occurred_at=base + timedelta(minutes=minute),
                    page=page, params_json=params or {},
                )
            # Чанк 1: два pageview + dwell (вовлечён по 2+ страницам).
            db.add_all([
                ev(0, "pageview", "/"),
                ev(1, "pageview", "/indicator/cpi"),
                ev(2, "dwell", "/indicator/cpi", {"ms": 30000, "active_ms": 20000, "scroll_pct": 70}),
            ])
            # Разрыв 40 минут → новая сессия: один pageview, не вовлечён.
            db.add(ev(45, "pageview", "/calendar"))
            # Бизнес-цель внутри первой сессии: скачивание CSV (микро).
            db.add(FrontendEvent(
                event_name="download_csv", occurred_at=base + timedelta(minutes=2),
                session_id_hash="sess1", authed=False,
            ))
            await db.commit()

            n = await sessionize(db, base - timedelta(minutes=5))
            assert n == 2

            sessions = (await db.execute(
                select(ServerSession).order_by(ServerSession.started_at)
            )).scalars().all()
            first, second = sessions
            assert first.pageviews == 2 and first.is_engaged is True
            assert first.max_scroll_pct == 70 and first.active_ms == 20000
            assert first.entry_page == "/" and first.exit_page == "/indicator/cpi"
            assert first.is_new_visitor is True
            # download_csv попал в ОБЕ сессии одного session_id? Нет: цель
            # привязывается по времени — только первая сессия её содержит.
            assert first.micro_goals == 1 and first.macro_goals == 0
            assert second.pageviews == 1 and second.is_engaged is False
            assert second.micro_goals == 0
            assert second.is_new_visitor is False  # визитор уже известен

            # Идемпотентность: повторный прогон не дублирует сессии.
            n2 = await sessionize(db, base - timedelta(minutes=5))
            assert n2 == 2

    _run_with_db(scenario)


# ---------------------------------------------------------------------------
# Rollup'ы
# ---------------------------------------------------------------------------

def test_rollup_daily_goals_and_pages():
    from app.models import BehaviorEvent, DailyGoal, DailyPage, FrontendEvent
    from app.tasks.analytics_rollups import rollup_daily_goals, rollup_daily_pages
    from sqlalchemy import select

    now = datetime.utcnow().replace(microsecond=0)

    async def scenario(maker):
        async with maker() as db:
            db.add_all([
                FrontendEvent(event_name="signup", occurred_at=now, session_id_hash="s1", authed=True),
                FrontendEvent(event_name="download_csv", occurred_at=now, session_id_hash="s1", authed=False),
                FrontendEvent(event_name="download_csv", occurred_at=now, session_id_hash="s2", authed=False),
                BehaviorEvent(session_id_hash="s1", event_type="pageview", occurred_at=now, page="/indicator/cpi"),
                BehaviorEvent(session_id_hash="s2", event_type="pageview", occurred_at=now, page="/indicator/cpi"),
                BehaviorEvent(session_id_hash="s1", event_type="dwell", occurred_at=now, page="/indicator/cpi",
                              params_json={"ms": 10000, "active_ms": 6000, "scroll_pct": 40}),
                BehaviorEvent(session_id_hash="s1", event_type="click", occurred_at=now, page="/indicator/cpi", is_dead=True),
            ])
            await db.commit()

            day = now.date() - timedelta(days=1)
            assert await rollup_daily_goals(db, day) == 2
            assert await rollup_daily_pages(db, day) == 1

            goals = {g.event_name: g for g in (await db.execute(select(DailyGoal))).scalars()}
            assert goals["signup"].tier == "macro" and goals["signup"].authed_count == 1
            assert goals["download_csv"].count == 2 and goals["download_csv"].sessions == 2

            page = (await db.execute(select(DailyPage))).scalars().one()
            assert page.views == 2 and page.dead_clicks == 1
            assert page.total_active_ms == 6000 and page.avg_scroll_pct == 40.0

            # Идемпотентность: пересчёт окна не дублирует строки.
            assert await rollup_daily_goals(db, day) == 2
            assert len((await db.execute(select(DailyGoal))).scalars().all()) == 2

    _run_with_db(scenario)


# ---------------------------------------------------------------------------
# Marts: считаются на пустой БД (без 500) и дают ожидаемые ключи
# ---------------------------------------------------------------------------

def test_marts_on_empty_db():
    from app.services.analytics_marts import (
        mart_collection_quality, mart_metric_tree, mart_own_funnel, mart_segments,
    )

    async def scenario(maker):
        async with maker() as db:
            tree = await mart_metric_tree(db, days=7)
            assert {"north_star", "drivers"} <= set(tree)
            assert len(tree["drivers"]) == 4
            assert {d["key"] for d in tree["drivers"]} == {"acquisition", "engagement", "conversion", "retention"}
            for drv in tree["drivers"]:
                assert drv["status"] in ("green", "yellow", "red")

            funnel = await mart_own_funnel(db, days=7)
            assert [s["step"] for s in funnel["steps"]] == ["Сессии", "Вовлечённые", "Микро-цель", "Макро-цель"]

            cq = await mart_collection_quality(db, days=7)
            assert cq["own_sessions"] == 0

            segs = await mart_segments(db, days=7)
            assert segs["segments"] == []

    _run_with_db(scenario)


def test_bi_targets_status():
    from app.data.bi_targets import next_milestone, status_for

    assert status_for(100, 100) == "green"
    assert status_for(96, 100) == "green"
    assert status_for(80, 100) == "yellow"
    assert status_for(30, 100) == "red"
    assert next_milestone(150) > 150
    assert next_milestone(10_500) >= 10_000
