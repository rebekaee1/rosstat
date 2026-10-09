"""Круг 11, зона H: витрины регистраций, воронки, использования функций, поиска и надёжности."""
import uuid
from datetime import datetime, timedelta

from app.models import (
    BehaviorEvent, BehaviorSession, DailyGoalDim, FrontendEvent, IdentityLink, ServerSession, User, UserSignup,
)
from app.services import analytics_marts as m
from app.services.analytics_period import resolve_period

from tests.test_analytics2 import _run_with_db


def _now():
    return datetime.utcnow().replace(microsecond=0)


def test_mart_signups_splits_language_origin_and_keeps_unknown_separate():
    now = _now()
    ids = [uuid.uuid4() for _ in range(4)]

    async def scenario(maker):
        async with maker() as db:
            for i, uid in enumerate(ids):
                db.add(User(id=uid, created_at=now - timedelta(hours=i + 1)))
            db.add(UserSignup(user_id=ids[0], created_at=now, method="email", site_locale="ru", country="Россия",
                              channel="search", device_type="mobile", trigger="gate_download", days_to_signup=0,
                              landing_page="/russia/indicator/cpi", newsletter=True))
            db.add(UserSignup(user_id=ids[1], created_at=now, method="yandex", site_locale="en", country="Германия",
                              channel="direct", device_type="desktop", trigger="header", days_to_signup=4))
            # английская версия, но Россия: это не «иностранец»
            db.add(UserSignup(user_id=ids[2], created_at=now, method="google", site_locale="en", country="Russia"))
            # история до атрибуции: язык неизвестен
            db.add(UserSignup(user_id=ids[3], created_at=now, source="backfill"))
            await db.commit()
            data = await m.mart_signups(db, resolve_period("7d"))

        assert data["total"] == 4
        assert data["locale"] == {"en": 2, "ru": 1, "unknown": 1}
        assert data["origin"] == {"ru": 2, "foreign": 1, "unknown": 1}
        assert data["locale_by_origin"]["en|foreign"] == 1 and data["locale_by_origin"]["en|ru"] == 1
        assert data["foreign_countries"] == {"Германия": 1}
        assert data["channel"]["unknown"] == 2 and data["device"]["mobile"] == 1
        assert data["trigger"] == {"gate_download": 1, "header": 1, "unknown": 2}
        assert data["median_days_to_signup"] == 2.0
        assert data["newsletter"] == 1
        assert data["known_locale"] == 3 and data["unknown_locale"] == 1
        assert data["landing_top"] == {"/russia/indicator/cpi": 1}
        # никаких имён и почт
        assert "@" not in str(data)

    _run_with_db(scenario)


def test_mart_signups_return_rate_counts_only_old_enough_cohort():
    now = _now()
    old_back, old_gone, fresh = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    registered = now - timedelta(days=10)

    async def scenario(maker):
        async with maker() as db:
            db.add_all([
                User(id=old_back, created_at=registered), User(id=old_gone, created_at=registered),
                User(id=fresh, created_at=now - timedelta(days=1)),
                ServerSession(day=(registered + timedelta(days=3)).date(), visitor_id_hash="v1", user_id=str(old_back),
                              started_at=registered + timedelta(days=3), ended_at=registered + timedelta(days=3)),
                # сессия в тот же день регистрации и сессия робота не считаются возвратом
                ServerSession(day=registered.date(), visitor_id_hash="v2", user_id=str(old_gone),
                              started_at=registered, ended_at=registered),
                ServerSession(day=(registered + timedelta(days=2)).date(), visitor_id_hash="v3", user_id=str(old_gone),
                              started_at=registered + timedelta(days=2), ended_at=registered + timedelta(days=2), is_bot=True),
            ])
            await db.commit()
            data = await m.mart_signups(db, resolve_period("30d"))
        assert data["returned_7d"] == {"eligible": 2, "returned": 1, "pct": 50.0}
        assert data["returned_30d"]["eligible"] == 0 and data["returned_30d"]["pct"] is None

    _run_with_db(scenario)


def test_signup_funnel_counts_people_excludes_robots_and_finds_last_step():
    now = _now()
    registered = uuid.uuid4()

    async def scenario(maker):
        async with maker() as db:
            def fe(name, visitor, url="https://ru.forecasteconomy.com/russia/indicator/cpi"):
                return FrontendEvent(event_name=name, visitor_id_hash=visitor, session_id_hash=f"s-{visitor}",
                                     occurred_at=now, url=url)

            db.add_all([
                # шесть человек смотрели показатель; v-bot — робот
                *[fe("indicator_view", f"v{i}") for i in range(1, 7)], fe("indicator_view", "v-bot"),
                # трое упёрлись в стену (один дважды), двое нажали «Регистрация»
                fe("download_limit", "v1"), fe("download_limit", "v1"), fe("chart_image_blocked", "v2"),
                fe("compare_limit_hit", "v3", url="https://forecasteconomy.com/compare"),
                fe("register_nudge_cta", "v1"), fe("header_register_click", "v2"),
                fe("download_limit", "v-bot"),
                # v1 открыл форму и отправил; v2 открыл окно соцсети и вышел
                fe("oauth_consent_open", "v2"), fe("oauth_start", "v1"),
                BehaviorEvent(event_type="pageview", visitor_id_hash="v1", page="/register", occurred_at=now),
                BehaviorEvent(event_type="form", visitor_id_hash="v1", page="/register", occurred_at=now,
                              params_json={"f": "register-email", "step": "submit"}),
                BehaviorEvent(event_type="form", visitor_id_hash="v5", page="/register", occurred_at=now,
                              params_json={"f": "register-email", "step": "focus"}),
                # посетители
                *[ServerSession(day=now.date(), visitor_id_hash=f"v{i}", started_at=now, ended_at=now,
                                site_locale="ru" if i % 2 else "en") for i in range(1, 7)],
                ServerSession(day=now.date(), visitor_id_hash="v-bot", started_at=now, ended_at=now, is_bot=True),
                # v1 зарегистрировался
                User(id=registered, created_at=now),
                IdentityLink(user_id=str(registered), visitor_id_hash="v1"),
                UserSignup(user_id=registered, created_at=now, site_locale="ru", method="email"),
            ])
            await db.commit()
            data = await m.mart_signup_funnel(db, resolve_period("7d"))

        steps = {s["key"]: s["count"] for s in data["steps"]}
        assert steps == {"visitors": 6, "viewed": 6, "wall": 3, "register_click": 2, "form_open": 2,
                         "submit": 1, "signed_up": 1}
        # v1 зарегистрировался и в «ушли» не входит; v2 ушёл на шаге «форма или соцсеть»; v3 — на лимите
        assert data["dropped_at"] == {"wall": 1, "form_open": 1}
        assert data["engaged_not_registered"] == 2
        # слабое звено ищется только там, где база не меньше 10: здесь её нет
        assert data["weakest"] is None
        assert data["by_locale"]["ru"]["signed_up"] == 1 and data["by_locale"]["ru"]["visitors"] == 3
        assert data["by_locale"]["en"]["wall"] == 1 and data["by_locale"]["ru"]["wall"] == 2  # v3 — на apex

    _run_with_db(scenario)


def test_signup_funnel_weakest_step_needs_a_sample():
    now = _now()

    async def scenario(maker):
        async with maker() as db:
            for i in range(12):
                db.add(FrontendEvent(event_name="download_limit", visitor_id_hash=f"w{i}", session_id_hash=f"sw{i}",
                                     occurred_at=now, url="https://ru.forecasteconomy.com/"))
            for i in range(3):
                db.add(FrontendEvent(event_name="register_nudge_cta", visitor_id_hash=f"w{i}", session_id_hash=f"sw{i}",
                                     occurred_at=now, url="https://ru.forecasteconomy.com/"))
            await db.commit()
            data = await m.mart_signup_funnel(db, resolve_period("7d"))
        assert data["weakest"] == {"from": "wall", "to": "register_click", "base": 12, "next": 3, "rate_pct": 25.0}

    _run_with_db(scenario)


def test_goal_usage_sums_dims_and_reports_missing_data():
    day = _now().date()

    async def scenario(maker):
        async with maker() as db:
            empty = await m.mart_goal_usage(db, resolve_period("7d"))
            assert empty["has_data"] is False and empty["days_covered"] == 0

            def cell(name, dim, value, count, sessions):
                return DailyGoalDim(day=day, event_name=name, dim=dim, value=value, count=count, sessions=sessions)

            db.add_all([
                cell("download_csv", "all", "all", 3, 2), cell("download_csv", "site_locale", "ru", 3, 2),
                cell("download_csv", "surface", "indicator", 3, 2),
                cell("download_excel", "all", "all", 2, 2), cell("download_excel", "site_locale", "en", 2, 2),
                cell("download_limit", "all", "all", 4, 3), cell("download_limit", "device", "mobile", 4, 3),
                cell("scroll_depth", "all", "all", 99, 9),  # вне групп
            ])
            await db.commit()
            data = await m.mart_goal_usage(db, resolve_period("7d"))

        assert data["has_data"] is True
        download = data["groups"]["download"]
        assert (download["actions"], download["sessions"]) == (5, 4)
        assert download["events"] == {"download_csv": 3, "download_excel": 2}
        assert download["locale"] == {"ru": 3, "en": 2} and download["surface"] == {"indicator": 3}
        assert data["groups"]["wall"]["actions"] == 4 and data["groups"]["wall"]["device"] == {"mobile": 4}
        assert data["groups"]["compare"]["actions"] == 0

    _run_with_db(scenario)


def test_search_gaps_scrubs_pii_and_ranks_by_people():
    now = _now()

    async def scenario(maker):
        async with maker() as db:
            for visitor, q, results in [
                ("a", "биткоин к рублю", 0), ("b", "биткоин к рублю", 0), ("a", "ввп", 5),
                ("c", "пишите bob@example.com", 0), ("d", "золото 585", 0),
            ]:
                db.add(FrontendEvent(event_name="search_query", visitor_id_hash=visitor, session_id_hash=f"s{visitor}",
                                     occurred_at=now, params_json={"q": q, "results": results}))
            await db.commit()
            data = await m.mart_search_gaps(db, resolve_period("7d"))
        assert data["top"][0] == {"q": "биткоин к рублю", "searches": 2, "people": 2}
        assert data["queries"] == 5 and data["empty_queries"] == 4
        assert "@" not in str(data)
        assert any(item["q"] == "пишите [скрыто]" for item in data["top"])

    _run_with_db(scenario)


def test_audience_geo_separates_russia_foreign_and_unknown_and_excludes_robots():
    now = _now()

    async def scenario(maker):
        async with maker() as db:
            for sid, visitor, country, wd in [
                ("1", "ru1", "Россия", False), ("2", "ru2", "Россия", False), ("3", "de1", "Германия", False),
                ("4", "xx1", None, False), ("5", "bot1", "Сингапур", True), ("6", "bot2", "Сингапур", False),
            ]:
                db.add(BehaviorSession(session_id_hash=sid, visitor_id_hash=visitor, started_at=now, country=country,
                                       is_webdriver=wd))
            db.add(ServerSession(day=now.date(), visitor_id_hash="bot2", started_at=now, ended_at=now, is_bot=True))
            await db.commit()
            data = await m.mart_audience_geo(db, resolve_period("7d"))
        assert (data["visitors"], data["ru"], data["foreign"], data["unknown"]) == (4, 2, 1, 1)
        assert data["foreign_share_pct"] == 33.3

    _run_with_db(scenario)


def test_reliability_has_page_group_by_device_cells():
    now = _now()

    async def scenario(maker):
        async with maker() as db:
            db.add(BehaviorSession(session_id_hash="s-m", visitor_id_hash="v", started_at=now, device_type="mobile"))
            for ms in (3000, 3200, 3400):
                db.add(BehaviorEvent(event_type="vital", session_id_hash="s-m", page="/russia/indicator/cpi",
                                     occurred_at=now, params_json={"m": "LCP", "v": ms}))
            db.add(BehaviorEvent(event_type="js_error", session_id_hash="s-m", page="/russia/indicator/cpi",
                                 occurred_at=now, params_json={"msg": "boom", "src": "https://forecasteconomy.com/a.js"}))
            db.add(BehaviorEvent(event_type="js_error", session_id_hash="s-m", page="/russia/indicator/cpi",
                                 occurred_at=now, params_json={"msg": "ads", "src": "https://yastatic.net/x.js"}))
            await db.commit()
            data = await m.mart_reliability(db, resolve_period("7d"))
        cell = next(c for c in data["page_device"] if c["page_group"] == "indicator" and c["device"] == "mobile")
        assert cell["lcp_samples"] == 3 and cell["lcp_p75_ms"] == 3400.0
        assert cell["js_errors_own"] == 1  # чужие скрипты в «свои ошибки» не входят
        assert data["js_errors_total"] == 2  # прежний показатель не изменился

    _run_with_db(scenario)


def test_daily_context_includes_new_marts_and_survives_a_failing_one(monkeypatch):
    async def boom(db, period):
        raise RuntimeError("slow query")

    async def scenario(maker):
        async with maker() as db:
            ok = await m.build_marts_daily_context(db)
            monkeypatch.setattr(m, "mart_signup_funnel", boom)
            partial = await m.build_marts_daily_context(db)
        for ctx in (ok, partial):
            assert {"signups_7d", "signup_funnel_7d", "goal_usage_7d"} <= set(ctx)
        assert ok["signups_7d"]["total"] == 0
        assert partial["signup_funnel_7d"] == {"error": "mart unavailable"}
        assert partial["signups_7d"]["total"] == 0  # остальное цело

    _run_with_db(scenario)
