"""Круг 11, зона H: разрезы событий (daily_goal_dims), исключение роботов (E6), язык сайта сессий, миграция."""
import asyncio
import importlib.util
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, inspect, select

from app.models import (
    Base, BehaviorSession, DailyGoal, DailyGoalDim, FrontendEvent, ServerSession,
)
from app.services.analytics_dims import country_group, site_locale_from_url, surface_from_url

from tests.test_analytics2 import _run_with_db


def test_site_locale_from_url(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "apex_locale_en", True)
    assert site_locale_from_url("https://ru.forecasteconomy.com/indicator/cpi") == "ru"
    assert site_locale_from_url("https://forecasteconomy.com/indicator/cpi") == "en"
    assert site_locale_from_url("https://en.forecasteconomy.com/") == "en"
    assert site_locale_from_url("http://localhost:5173/") is None
    assert site_locale_from_url(None) is None
    monkeypatch.setattr(settings, "apex_locale_en", False)
    assert site_locale_from_url("https://forecasteconomy.com/") == "ru"


def test_surface_from_url():
    cases = {
        "https://ru.forecasteconomy.com/": "home",
        "https://ru.forecasteconomy.com/compare?a=b": "compare",
        "https://forecasteconomy.com/world/rating/gdp-usd/2025": "rating",
        "https://ru.forecasteconomy.com/russia/indicator/cpi": "indicator",
        "https://ru.forecasteconomy.com/russia/region/moskva/cpi": "region",
        "https://ru.forecasteconomy.com/russia/region-rating/x": "rating",
        "https://forecasteconomy.com/germany/indicator/gdp": "world_indicator",
        "https://forecasteconomy.com/germany/region/bavaria": "region",
        "https://forecasteconomy.com/germany": "country",
        "https://ru.forecasteconomy.com/calculator/mortgage": "calculator",
        "https://ru.forecasteconomy.com/currencies/indicator/usd-rub": "indicator",
        "https://ru.forecasteconomy.com/login": "other",
        None: None,
    }
    for url, expected in cases.items():
        assert surface_from_url(url) == expected, url


def test_country_group():
    assert country_group("Россия") == "ru"
    assert country_group("Germany") == "foreign"
    assert country_group(None) == "unknown"


def test_dims_rollup_splits_events_and_excludes_robots_and_own_activity():
    from app.tasks.analytics_rollups import rollup_daily_goal_dims, rollup_daily_goals

    now = datetime.utcnow().replace(microsecond=0)
    day = now.date() - timedelta(days=1)

    async def scenario(maker):
        async with maker() as db:
            db.add_all([
                BehaviorSession(session_id_hash="s-ru", visitor_id_hash="v-ru", started_at=now,
                                device_type="mobile", channel="search", country="Россия"),
                BehaviorSession(session_id_hash="s-de", visitor_id_hash="v-de", started_at=now,
                                device_type="desktop", channel="direct", country="Германия"),
                BehaviorSession(session_id_hash="s-bot", visitor_id_hash="v-bot", started_at=now,
                                device_type="desktop", channel="direct", country="Сингапур"),
                ServerSession(day=now.date(), visitor_id_hash="v-bot", started_at=now, ended_at=now, is_bot=True),
                ServerSession(day=now.date(), visitor_id_hash="v-own", started_at=now, ended_at=now, is_internal=True),
                FrontendEvent(event_name="download_csv", occurred_at=now, session_id_hash="s-ru", visitor_id_hash="v-ru",
                              url="https://ru.forecasteconomy.com/indicator/cpi", params_json={"surface": "indicator"}),
                FrontendEvent(event_name="download_csv", occurred_at=now, session_id_hash="s-ru", visitor_id_hash="v-ru",
                              url="https://ru.forecasteconomy.com/indicator/cpi", params_json={"surface": "indicator"}),
                FrontendEvent(event_name="download_excel", occurred_at=now, session_id_hash="s-de", visitor_id_hash="v-de",
                              url="https://en.forecasteconomy.com/world", params_json={"surface": "rating"}),
                FrontendEvent(event_name="download_limit", occurred_at=now, session_id_hash="s-de", visitor_id_hash="v-de",
                              url="https://en.forecasteconomy.com/world"),
                # роботы и своя активность не должны попасть ни в daily_goals, ни в разрезы
                FrontendEvent(event_name="download_csv", occurred_at=now, session_id_hash="s-bot", visitor_id_hash="v-bot",
                              url="https://ru.forecasteconomy.com/"),
                FrontendEvent(event_name="download_csv", occurred_at=now, session_id_hash="s-own", visitor_id_hash="v-own",
                              url="https://ru.forecasteconomy.com/"),
                # событие вне групп отчётов в разрезы не идёт
                FrontendEvent(event_name="scroll_depth", occurred_at=now, session_id_hash="s-ru", visitor_id_hash="v-ru",
                              url="https://ru.forecasteconomy.com/"),
            ])
            await db.commit()

            n_goals = await rollup_daily_goals(db, day)
            goals = {g.event_name: g.count for g in (await db.execute(select(DailyGoal))).scalars()}
            assert goals["download_csv"] == 2, "роботы и свои исключены из daily_goals (E6)"
            assert n_goals == 4

            assert await rollup_daily_goal_dims(db, day) > 0
            rows = (await db.execute(select(DailyGoalDim))).scalars().all()
            cells = {(r.event_name, r.dim, r.value): (r.count, r.sessions) for r in rows}
            today = {r.day for r in rows}
            assert len(today) == 1

            assert cells[("download_csv", "all", "all")] == (2, 1)
            assert cells[("download_csv", "site_locale", "ru")] == (2, 1)
            assert cells[("download_csv", "device", "mobile")] == (2, 1)
            assert cells[("download_csv", "channel", "search")] == (2, 1)
            assert cells[("download_csv", "country", "ru")] == (2, 1)
            assert cells[("download_csv", "surface", "indicator")] == (2, 1)
            assert cells[("download_excel", "country", "foreign")] == (1, 1)
            assert cells[("download_excel", "surface", "rating")] == (1, 1)
            # без параметра surface поверхность определяется по пути адреса
            assert cells[("download_limit", "surface", "world_home")] == (1, 1)
            assert cells[("download_limit", "site_locale", "en")] == (1, 1)
            assert not any(name == "scroll_depth" for name, _, _ in cells)
            assert not any(v == "Сингапур" for _, _, v in cells)

            # Идемпотентность: пересчёт окна не дублирует строки.
            before = len(rows)
            await rollup_daily_goal_dims(db, day)
            assert len((await db.execute(select(DailyGoalDim))).scalars().all()) == before

    _run_with_db(scenario)


def test_sessionize_copies_site_locale_from_portrait():
    from app.models import BehaviorEvent
    from app.tasks.analytics_rollups import sessionize

    base = datetime.utcnow().replace(microsecond=0) - timedelta(hours=3)

    async def scenario(maker):
        async with maker() as db:
            db.add(BehaviorSession(session_id_hash="sess-en", visitor_id_hash="vis", started_at=base,
                                   site_locale="en", device_type="desktop", channel="direct"))
            db.add(BehaviorEvent(event_type="pageview", visitor_id_hash="vis", session_id_hash="sess-en",
                                 occurred_at=base + timedelta(seconds=5), page="/"))
            await db.commit()
            await sessionize(db, base - timedelta(minutes=5))
            row = (await db.execute(select(ServerSession))).scalars().one()
            assert row.site_locale == "en"

    _run_with_db(scenario)


# --- миграция --------------------------------------------------------------------

def _load_migration():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261009b_analytics_signups.py"
    spec = importlib.util.spec_from_file_location("signups_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_identifiers_and_length():
    m = _load_migration()
    assert m.revision == "20261009b_analytics_signups"
    assert m.down_revision == "20261009_user_cabinet"
    assert len(m.revision) <= 32  # alembic_version.version_num = VARCHAR(32)


def test_migration_upgrade_and_downgrade_match_models():
    """Одна миграция (без цепочки): на схеме «до» добавляет ровно то, что описывают модели.

    Цепочка целиком не запускается: предыдущая ревизия `20261009_user_cabinet` пишется
    другой зоной и в этой ветке файла нет, при слиянии цепочка сойдётся.
    """
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    m = _load_migration()
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            # Состояние «до миграции»: убираем новые таблицы и колонки.
            conn.exec_driver_sql("DROP TABLE user_signups")
            conn.exec_driver_sql("DROP TABLE daily_goal_dims")
            conn.exec_driver_sql("ALTER TABLE behavior_sessions DROP COLUMN site_locale")
            conn.exec_driver_sql("ALTER TABLE server_sessions DROP COLUMN site_locale")
        with engine.begin() as conn:
            before = inspect(conn)
            assert "user_signups" not in before.get_table_names()
            with Operations.context(MigrationContext.configure(conn)):
                m.upgrade()
        insp = inspect(engine)
        for table in ("user_signups", "daily_goal_dims"):
            model_cols = {c.name for c in Base.metadata.tables[table].columns}
            db_cols = {c["name"] for c in insp.get_columns(table)}
            assert db_cols == model_cols, table
        for table in ("behavior_sessions", "server_sessions"):
            assert "site_locale" in {c["name"] for c in insp.get_columns(table)}
        assert {i["name"] for i in insp.get_indexes("user_signups")} == {"ix_user_signups_created"}
        assert {i["name"] for i in insp.get_indexes("daily_goal_dims")} == {"ix_daily_goal_dims_day"}
        # Ни одного нового индекса на больших таблицах событий.
        for table in ("frontend_events", "behavior_events"):
            assert not any("signup" in (i["name"] or "") or "site_locale" in (i["name"] or "")
                           for i in insp.get_indexes(table))
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                m.downgrade()
        insp = inspect(engine)
        assert "user_signups" not in insp.get_table_names()
        assert "daily_goal_dims" not in insp.get_table_names()
        assert "site_locale" not in {c["name"] for c in insp.get_columns("behavior_sessions")}
        engine.dispose()
    finally:
        os.unlink(db_path)
