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


def test_taxonomy_intent_tier_and_reclassification():
    """Ревизия 2026-07-06: intent — не конверсия; негативные сигналы —
    technical; login_success — micro (возвратный вход ≠ приобретение)."""
    from app.services.goal_taxonomy import (
        TIER_INTENT, TIER_MICRO, TIER_TECHNICAL, is_conversion, tier_for_event,
    )

    for ev in ("oauth_start", "header_register_click", "header_login_click",
               "register_nudge_cta", "feedback_nudge_cta"):
        assert tier_for_event(ev) == TIER_INTENT, ev
        assert not is_conversion(ev), f"{ev}: клик по кнопке — не достижение"

    assert tier_for_event("search_abandon") == TIER_TECHNICAL
    assert tier_for_event("outbound_link") == TIER_TECHNICAL
    assert tier_for_event("embed_runtime_view") == TIER_TECHNICAL
    assert tier_for_event("login_success") == TIER_MICRO
    assert tier_for_event("contact_email") == TIER_MICRO
    assert is_conversion("login_success") and is_conversion("contact_email")


def test_taxonomy_covers_frontend_registry():
    """Каждое событие реестра track.js классифицировано ЯВНО — фолбэк
    «engagement по умолчанию» не должен молча глотать новые события."""
    import re
    from pathlib import Path

    from app.services.goal_taxonomy import explicit_events

    track = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "track.js"
    if not track.exists():
        pytest.skip("frontend/src/lib/track.js недоступен в этом окружении")
    registry = set(re.findall(r"[A-Z_]+:\s*'([a-z0-9_]+)'", track.read_text()))
    assert len(registry) >= 90, "реестр track.js подозрительно мал — регекс разошёлся с форматом"
    missing = registry - explicit_events()
    assert not missing, f"события без явного tier в goal_taxonomy: {sorted(missing)}"


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


def test_sessionize_infers_channel_from_pageview_ref():
    """Волна 2, п. 1: сессия без портрета получает канал из referrer первого
    pageview (search / direct / ad по UTM в другой ветке), а не «не определён»."""
    from app.models import BehaviorEvent, ServerSession
    from app.tasks.analytics_rollups import sessionize
    from sqlalchemy import select

    base = datetime.utcnow().replace(microsecond=0) - timedelta(hours=2)

    async def scenario(maker):
        async with maker() as db:
            db.add_all([
                # Посетитель из поиска: ref = яндекс, touch-смартфон.
                BehaviorEvent(
                    session_id_hash="s-search", visitor_id_hash="v1",
                    event_type="pageview", occurred_at=base, page="/indicator/cpi",
                    params_json={"ref": "https://yandex.ru/search/?text=инфляция", "vw": 390, "touch": 1},
                ),
                # Прямой заход без единого признака: честный direct, десктоп.
                BehaviorEvent(
                    session_id_hash="s-direct", visitor_id_hash="v2",
                    event_type="pageview", occurred_at=base + timedelta(minutes=1), page="/",
                    params_json={"ref": None, "vw": 1920, "touch": 0},
                ),
            ])
            await db.commit()
            await sessionize(db, base - timedelta(minutes=5))
            rows = {
                s.visitor_id_hash: s for s in (await db.execute(select(ServerSession))).scalars()
            }
            assert rows["v1"].channel == "search" and rows["v1"].device == "mobile"
            assert rows["v2"].channel == "direct" and rows["v2"].device == "desktop"

    _run_with_db(scenario)


def test_synthetic_portrait_upserted_and_upgraded():
    """Батч без session_start рождает синтетический портрет; настоящий
    session_start, дошедший позже, апгрейдит строку полными данными."""
    from app.api.analytics import _insert_portrait
    from app.models import BehaviorSession
    from sqlalchemy import select

    now = datetime.utcnow().replace(microsecond=0)

    async def scenario(maker):
        async with maker() as db:
            synthetic = {
                "session_id_hash": "sess-x", "visitor_id_hash": "v1",
                "started_at": now, "channel": "search", "browser": "Chrome",
                "is_synthetic": True,
            }
            await _insert_portrait(db, dict(synthetic), upgrade_synthetic=False)
            await db.commit()
            # Повторный синтетический — no-op (DO NOTHING).
            await _insert_portrait(db, dict(synthetic, browser="Edge"), upgrade_synthetic=False)
            await db.commit()
            row = (await db.execute(select(BehaviorSession))).scalar_one()
            assert row.is_synthetic is True and row.browser == "Chrome"

            # Настоящий session_start апгрейдит синтетическую строку.
            real = dict(synthetic, browser="Firefox", channel="ad", is_synthetic=False)
            await _insert_portrait(db, real, upgrade_synthetic=True)
            await db.commit()
            db.expire_all()
            row = (await db.execute(select(BehaviorSession))).scalar_one()
            assert row.is_synthetic is False and row.browser == "Firefox" and row.channel == "ad"

            # Но настоящий портрет повторный session_start НЕ перетирает.
            await _insert_portrait(db, dict(real, browser="Opera"), upgrade_synthetic=True)
            await db.commit()
            db.expire_all()
            row = (await db.execute(select(BehaviorSession))).scalar_one()
            assert row.browser == "Firefox"

    _run_with_db(scenario)


def test_mart_goal_reconciliation():
    """Волна 2, п. 6: сверка наших business-событий с целями Метрики.
    Событие без цели → metrika_visits is None; цель без события → metrika_only."""
    from app.models import FrontendEvent, MetrikaGoal, RawMetrikaVisit
    from app.services.analytics_marts import mart_goal_reconciliation

    now = datetime.utcnow().replace(microsecond=0)

    async def scenario(maker):
        async with maker() as db:
            db.add_all([
                FrontendEvent(event_name="signup", occurred_at=now, session_id_hash="s1", authed=True),
                FrontendEvent(event_name="download_csv", occurred_at=now, session_id_hash="s1", authed=False),
                FrontendEvent(event_name="download_csv", occurred_at=now, session_id_hash="s2", authed=False),
                MetrikaGoal(goal_id=101, name="Регистрация", event_name="signup", tier="macro"),
                MetrikaGoal(goal_id=102, name="Скролл 90%", event_name=None, tier="technical"),
                RawMetrikaVisit(counter_id="c1", visit_id="v1", row_hash="h1", visit_date=now.date(), goals_json={"goals": "[101, 102]"}),
                RawMetrikaVisit(counter_id="c1", visit_id="v2", row_hash="h2", visit_date=now.date(), goals_json={"goals": "[102]"}),
            ])
            await db.commit()
            rec = await mart_goal_reconciliation(db, 7)
            rows = {r["event"]: r for r in rec["rows"]}
            assert rows["signup"]["our_events"] == 1
            assert rows["signup"]["metrika_visits"] == 1
            # download_csv не замаплен на цель Метрики → прочерк, не ноль.
            assert rows["download_csv"]["our_events"] == 2
            assert rows["download_csv"]["metrika_visits"] is None
            # Цель без нашего события — в metrika_only.
            only = {g["goal"]: g["visits"] for g in rec["metrika_only"]}
            assert only.get("Скролл 90%") == 2

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
        mart_collection_quality, mart_experiments, mart_metric_tree,
        mart_own_funnel, mart_segments,
    )

    async def scenario(maker):
        async with maker() as db:
            tree = await mart_metric_tree(db, period=7)
            assert {"north_star", "drivers"} <= set(tree)
            assert len(tree["drivers"]) == 4
            assert {d["key"] for d in tree["drivers"]} == {"acquisition", "engagement", "conversion", "retention"}
            for drv in tree["drivers"]:
                assert drv["status"] in ("green", "yellow", "red")
            # Раскрытие узла «Удержание»: окна 1/7/30 присутствуют всегда.
            ret = next(d for d in tree["drivers"] if d["key"] == "retention")
            assert {"d1", "d7", "d30"} <= set(ret["detail"]["windows"])

            funnel = await mart_own_funnel(db, period=7)
            assert [s["step"] for s in funnel["steps"]] == ["Сессии", "Вовлечённые", "Микро-цель", "Макро-цель"]

            cq = await mart_collection_quality(db, period=7)
            assert cq["own_sessions"] == 0

            segs = await mart_segments(db, period=7)
            assert segs["segments"] == []

            exps = await mart_experiments(db, period=30)
            assert exps["experiments"] == [] and exps["note"]

    _run_with_db(scenario)


def test_mart_experiments_conversion_by_variant():
    """A/B-автоанализ: экспозиция по вариантам + конверсия visitor'а в цель."""
    from datetime import datetime, timedelta

    from app.models import FrontendEvent
    from app.services.analytics_marts import mart_experiments

    now = datetime.utcnow().replace(microsecond=0) - timedelta(hours=1)

    async def scenario(maker):
        async with maker() as db:
            def exp(vid, variant):
                return FrontendEvent(
                    event_name="experiment_exposure", occurred_at=now,
                    visitor_id_hash=vid, authed=False,
                    params_json={"experiment": "cta-color", "variant": variant},
                )
            db.add_all([
                exp("v1", "A"), exp("v2", "A"), exp("v3", "B"),
                # v1 конвертируется (микро-цель), v2/v3 — нет.
                FrontendEvent(event_name="download_csv", occurred_at=now,
                              visitor_id_hash="v1", authed=False),
                # scroll_depth — вовлечение, конверсией не считается.
                FrontendEvent(event_name="scroll_depth", occurred_at=now,
                              visitor_id_hash="v3", authed=False),
            ])
            await db.commit()

            res = await mart_experiments(db, period=7)
            assert len(res["experiments"]) == 1
            variants = {v["variant"]: v for v in res["experiments"][0]["variants"]}
            assert variants["A"]["visitors"] == 2 and variants["A"]["converted"] == 1
            assert variants["A"]["conversion_pct"] == 50.0
            assert variants["B"]["visitors"] == 1 and variants["B"]["converted"] == 0

    _run_with_db(scenario)


def test_bi_targets_status():
    from app.data.bi_targets import next_milestone, status_for

    assert status_for(100, 100) == "green"
    assert status_for(96, 100) == "green"
    assert status_for(80, 100) == "yellow"
    assert status_for(30, 100) == "red"
    assert next_milestone(150) > 150
    assert next_milestone(10_500) >= 10_000


def test_period_resolver_msk():
    """BI 2.1: «день» — 00:00 МСК → сейчас; custom-даты МСК; tail-подокно."""
    from datetime import datetime, timedelta, timezone

    from app.services.analytics_period import MSK_OFFSET, as_period, msk_day, resolve_period

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    today_msk = (now_utc + MSK_OFFSET).date()

    p = resolve_period("today")
    assert p.start_date == p.end_date == today_msk
    # Начало окна = 00:00 МСК в UTC (МСК-полночь минус 3 часа).
    assert p.start + MSK_OFFSET == datetime.combine(today_msk, datetime.min.time())
    assert p.start <= now_utc <= p.end + timedelta(seconds=5)

    y = resolve_period("yesterday")
    assert y.end_date == today_msk - timedelta(days=1)
    assert y.end == p.start  # стык суток без дыр и перекрытий

    # custom: перепутанные даты меняются местами, будущее обрезается по сегодня.
    c = resolve_period("custom", "2026-07-04", "2026-07-01")
    assert (c.start_date.isoformat(), c.end_date.isoformat()) == ("2026-07-01", "2026-07-04")
    assert resolve_period("custom", None, None).preset == "30d"  # мягкий фолбэк

    # int-легаси: N последних МСК-дней включая сегодня.
    p14 = as_period(14)
    assert p14.days == 14 and p14.end_date == today_msk

    # tail: хвостовое подокно не длиннее исходного и заканчивается тем же днём.
    t = resolve_period("90d").tail(7)
    assert t.days == 7 and t.end_date == today_msk
    assert resolve_period("today").tail(7).days == 1

    assert msk_day(datetime(2026, 7, 5, 21, 30)) == (datetime(2026, 7, 5, 21, 30) + MSK_OFFSET).date()


def test_bot_score_heuristics():
    """BI 2.1 этап 3: антибот-скоринг — неопровержимые сигналы >= порога,
    поведенческие складываются, живой человек не штрафуется."""
    from app.services.bot_score import BOT_THRESHOLD, SessionSignals, score_session, signal_breakdown

    def sig(**kw):
        base = dict(pageviews=1, clicks=0, moves=0, active_ms=0, max_scroll_pct=0,
                    synthetic_clicks=0, visitor_sessions=1)
        base.update(kw)
        return SessionSignals(**base)

    # Headless/webdriver — бот безусловно.
    assert score_session(sig(is_webdriver=True, has_portrait=True)) >= BOT_THRESHOLD
    # Явный бот-UA.
    assert score_session(sig(has_portrait=True, ua_raw="Mozilla/5.0 (compatible; YandexBot/3.0)")) >= BOT_THRESHOLD
    # Паттерн 41% прода: 1 pageview, ноль следов человека.
    s = sig()
    assert score_session(s) >= BOT_THRESHOLD
    assert "no_human_traces" in signal_breakdown(s)
    # Живой человек: движение мыши + активное время → не бот.
    human = sig(moves=3, active_ms=8000)
    assert score_session(human) < BOT_THRESHOLD
    # Мобильный человек: без мыши и кликов, но тач-скролл оставил след.
    assert score_session(sig(max_scroll_pct=45)) < BOT_THRESHOLD
    # Headless с доставленным dwell, но без единого следа ввода — бот
    # (dwell сам по себе следом не считается).
    assert score_session(sig()) >= BOT_THRESHOLD
    # Только синтетические клики (isTrusted=false) — бот.
    assert score_session(sig(clicks=2, synthetic_clicks=2)) >= BOT_THRESHOLD
    # Настоящие клики среди синтетических — сигнал не срабатывает.
    assert "synthetic_clicks" not in signal_breakdown(sig(clicks=5, synthetic_clicks=1, moves=2, active_ms=3000))
    # Флуд сессий с одного visitor — добавка, но не приговор сам по себе.
    flood = sig(moves=2, active_ms=3000, visitor_sessions=50)
    assert 0 < score_session(flood) < BOT_THRESHOLD


def test_sessionize_sets_bot_score():
    """Сессионизация проставляет bot_score/is_bot: бот-паттерн ловится,
    человек с движениями мыши и dwell — чистый."""
    from sqlalchemy import select

    from app.models import BehaviorEvent, ServerSession
    from app.tasks import analytics_rollups as ar

    base = datetime.utcnow().replace(microsecond=0) - timedelta(hours=2)

    async def scenario(maker):
        async with maker() as db:
            def ev(vis, etype, minutes, **kw):
                return BehaviorEvent(
                    event_type=etype, visitor_id_hash=vis, session_id_hash=f"s-{vis}",
                    occurred_at=base + timedelta(minutes=minutes), page="/", **kw,
                )

            db.add_all([
                # Бот: одиночный pageview без следов.
                ev("bot1", "pageview", 0),
                # Человек: pageview + мышь + dwell с active_ms.
                ev("hum1", "pageview", 0),
                ev("hum1", "move", 1),
                ev("hum1", "dwell", 2, params_json={"ms": 60000, "active_ms": 20000, "scroll_pct": 60}),
            ])
            await db.commit()

            n = await ar.sessionize(db, base - timedelta(minutes=5))
            assert n == 2
            rows = {s.visitor_id_hash: s for s in (await db.execute(select(ServerSession))).scalars()}
            assert rows["bot1"].is_bot and rows["bot1"].bot_score >= 60
            assert not rows["hum1"].is_bot and rows["hum1"].bot_score < 60

    _run_with_db(scenario)
