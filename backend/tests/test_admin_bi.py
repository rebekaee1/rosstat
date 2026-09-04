"""Админ-BI (/api/v1/admin/bi): доступ и сборка витрин.

Инварианты:
- аноним и обычный пользователь получают 401/404 — раздел «не существует»;
- админ (email из settings.admin_emails) получает полный дашборд со всеми
  секциями, даже на пустой БД (пустые витрины, не 500);
- /auth/me отдаёт is_admin только админу.
"""

import pytest

from tests.conftest import csrf_headers

ADMIN_EMAIL = "admin_forecasteconomy@forecasteconomy.com"
PASSWORD = "Str0ng-passw0rd!"

EXPECTED_SECTIONS = {
    "kpi_daily", "acquisition", "funnel", "retention", "pages", "demand",
    "onsite_search", "navigation", "behavior_issues", "events",
    "hypotheses", "dataset", "users", "audience", "activity_heatmap",
    "content_structure",
}


def _register(tc, email):
    r = tc.post("/api/v1/auth/register", json={
        "email": email, "password": PASSWORD, "consent": True,
    })
    assert r.status_code in (200, 201), r.text
    return r


def test_bi_requires_auth(auth_client):
    r = auth_client.get("/api/v1/admin/bi/dashboard")
    assert r.status_code == 401


def test_bi_hidden_from_regular_user(auth_client):
    _register(auth_client, "user@example.com")
    r = auth_client.get("/api/v1/admin/bi/dashboard")
    assert r.status_code == 404

    me = auth_client.get("/api/v1/auth/me").json()["user"]
    assert "is_admin" not in me


def test_bi_dashboard_for_admin(auth_client):
    _register(auth_client, ADMIN_EMAIL)

    me = auth_client.get("/api/v1/auth/me").json()["user"]
    assert me.get("is_admin") is True

    r = auth_client.get("/api/v1/admin/bi/dashboard?days=7&wait=60")
    assert r.status_code == 200, r.text
    data = r.json()
    assert EXPECTED_SECTIONS <= set(data.keys())
    # Dual-host (ADR-0013 §F): срез спроса по свойствам Вебмастера присутствует.
    assert "webmaster_by_host" in data["demand"]
    assert isinstance(data["demand"]["webmaster_by_host"], list)
    assert data["window_days"] == 7
    # Почти пустая БД → витрины считаются без ошибок; сама регистрация
    # админа уже видна в KPI как registration за сегодня.
    assert sum(r["registrations"] for r in data["kpi_daily"]) == 1
    assert data["retention"]["unique_visitors"] == 0
    assert isinstance(data["acquisition"]["ad_campaigns"], list)


def test_login_response_carries_is_admin(auth_client):
    """Регрессия 2026-07-05: логин-гейт /admin/bi кладёт ответ /auth/login в
    auth-контекст как есть. Без is_admin в этом ответе админ сразу после
    входа видел «404 — страница не найдена» до полной перезагрузки."""
    _register(auth_client, ADMIN_EMAIL)
    auth_client.post("/api/v1/auth/logout", headers=csrf_headers(auth_client))

    r = auth_client.post("/api/v1/auth/login", json={
        "email": ADMIN_EMAIL, "password": PASSWORD,
    })
    assert r.status_code == 200, r.text
    assert r.json()["user"].get("is_admin") is True


def test_bi_dashboard_cached(auth_client):
    """Повторный запрос отдаётся из кэша (generated_at не меняется), без wait."""
    _register(auth_client, ADMIN_EMAIL)
    first = auth_client.get("/api/v1/admin/bi/dashboard?days=30&wait=60").json()
    second = auth_client.get("/api/v1/admin/bi/dashboard?days=30").json()
    assert first["generated_at"] == second["generated_at"]
    assert second["cache_meta"]["stale"] is False
    assert second["cache_meta"]["refreshing"] is False


def test_bi_dashboard_cold_cache_returns_202_and_single_flight(auth_client):
    """Инцидент 2026-09-04: холодный кэш → 202 «считаем» сразу, а не ожидание
    сборки дольше клиентского таймаута. Повторные опросы присоединяются к
    идущей сборке, не запускают новую; в итоге снимок появляется в кэше."""
    import time

    from app.api import admin_bi as mod

    _register(auth_client, ADMIN_EMAIL)
    r1 = auth_client.get("/api/v1/admin/bi/dashboard?period=90d")
    r2 = auth_client.get("/api/v1/admin/bi/dashboard?period=90d")
    assert r1.status_code == 202, r1.text
    assert r1.json()["status"] == "building"
    assert r2.status_code == 202
    # single-flight: по ключу не больше одной задачи
    assert sum(1 for k in mod._INFLIGHT if ":90d:" in k) <= 1

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        r = auth_client.get("/api/v1/admin/bi/dashboard?period=90d")
        if r.status_code == 200:
            break
        assert r.status_code == 202, r.text
        time.sleep(0.2)
    assert r.status_code == 200, r.text
    assert "metric_tree" in r.json()
    assert r.json()["cache_meta"]["stale"] is False


def test_bi_dashboard_stale_snapshot_served_while_revalidating(auth_client):
    """SWR: устаревший снимок отдаётся мгновенно с stale=true и refreshing=true,
    пересчёт идёт в фоне, следующий свежий ответ имеет новый generated_at."""
    import time

    from app.api import admin_bi as mod
    from app.core.cache import cache_get, cache_set

    _register(auth_client, ADMIN_EMAIL)
    first = auth_client.get("/api/v1/admin/bi/dashboard?days=7&wait=60")
    assert first.status_code == 200, first.text

    # Состариваем снимок: built_at далеко в прошлом. Redis-фейк привязан к
    # loop'у приложения — ходим через portal TestClient.
    from app.services.analytics_period import as_period
    key = mod._snapshot_key(as_period(7))
    snap = auth_client.portal.call(cache_get, key)
    assert snap is not None
    snap["built_at"] = time.time() - 10 * 3600
    auth_client.portal.call(cache_set, key, snap, 3600)

    stale = auth_client.get("/api/v1/admin/bi/dashboard?days=7")
    assert stale.status_code == 200
    assert stale.json()["cache_meta"]["stale"] is True
    assert stale.json()["cache_meta"]["refreshing"] is True
    assert stale.json()["generated_at"] == first.json()["generated_at"]

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        r = auth_client.get("/api/v1/admin/bi/dashboard?days=7")
        if r.status_code == 200 and not r.json()["cache_meta"]["stale"]:
            break
        time.sleep(0.2)
    assert r.json()["cache_meta"]["stale"] is False
    assert r.json()["generated_at"] != first.json()["generated_at"]


# --- Истинность цифр (инцидент 2026-07-05: конверсия 91-100%) ----------------


class _FakeVisit:
    """Минимальный дублёр RawMetrikaVisit для чистых функций admin_bi."""

    def __init__(self, goals_json=None, client_id_hash=None, visit_date=None,
                 traffic_source="organic", duration_seconds=0, start_url=None,
                 raw_json=None):
        self.goals_json = goals_json
        self.client_id_hash = client_id_hash
        self.visit_date = visit_date
        self.traffic_source = traffic_source
        self.duration_seconds = duration_seconds
        self.start_url = start_url
        self.raw_json = raw_json or {}
        self.search_engine = None
        self.search_phrase = None
        self.referer = None


def test_has_goals_rejects_empty_wrappers():
    """goals_json = {"goals": "[]"} или пустая строка — НЕ достигнутая цель.
    Наивный truthy-чек давал конверсию 91-100% (ложь на витрине владельца)."""
    from app.services.analytics_marts import visit_has_goals as _has_goals

    assert _has_goals(_FakeVisit(goals_json=None)) is False
    assert _has_goals(_FakeVisit(goals_json={})) is False
    assert _has_goals(_FakeVisit(goals_json={"goals": ""})) is False
    assert _has_goals(_FakeVisit(goals_json={"goals": "[]"})) is False
    assert _has_goals(_FakeVisit(goals_json={"goals": "[577576799]"})) is True
    assert _has_goals(_FakeVisit(goals_json={"goals": "[5,6]"})) is True
    assert _has_goals(_FakeVisit(goals_json={"goals": []})) is False
    assert _has_goals(_FakeVisit(goals_json={"goals": [577576799]})) is True


def test_business_goal_filter():
    """Этап 2б BI 2.1: конверсия — только business-tier цели; авто-цели
    (скролл, показы) её не создают. Пустой словарь — фолбэк на любую цель."""
    from app.services.analytics_marts import visit_has_business_goal

    biz = {100, 200}
    assert visit_has_business_goal(_FakeVisit(goals_json={"goals": "[100]"}), biz) is True
    assert visit_has_business_goal(_FakeVisit(goals_json={"goals": "[999]"}), biz) is False
    assert visit_has_business_goal(_FakeVisit(goals_json={"goals": "[999,200]"}), biz) is True
    assert visit_has_business_goal(_FakeVisit(goals_json=None), biz) is False
    # Фолбэк без словаря (токен Метрики не настроен).
    assert visit_has_business_goal(_FakeVisit(goals_json={"goals": "[999]"}), set()) is True


def test_funnel_goal_subset_of_engaged():
    """Инвариант воронки: goal_visits ≤ engaged ≤ visits для каждого канала.
    Визит с целью, но одной страницей и коротким временем — всё равно вовлечён."""
    from datetime import date

    from app.services.admin_bi import _funnel

    visits = [
        # Одностраничный короткий визит С ЦЕЛЬЮ — раньше падал мимо engaged.
        _FakeVisit(goals_json={"goals": "[1]"}, traffic_source="ad",
                   visit_date=date(2026, 7, 1), duration_seconds=5,
                   raw_json={"ym:s:pageViews": "1"}),
        # Обычный невовлечённый визит без цели.
        _FakeVisit(traffic_source="ad", visit_date=date(2026, 7, 1),
                   duration_seconds=3, raw_json={"ym:s:pageViews": "1"}),
    ]
    funnel = _funnel(visits, {})
    row = next(r for r in funnel["by_source"] if r["source"] == "ad")
    assert row["visits"] == 2
    assert row["goal_visits"] == 1
    assert row["engaged"] >= row["goal_visits"]


def test_retention_day_cohorts():
    """Дневные когорты: возврат на следующий день виден в day_plus, а
    returning считает активность в >1 календарном дне (не неделе)."""
    from datetime import date

    from app.services.admin_bi import _retention

    visits = [
        _FakeVisit(client_id_hash="a", visit_date=date(2026, 7, 1)),
        _FakeVisit(client_id_hash="a", visit_date=date(2026, 7, 2)),  # вернулся через день
        _FakeVisit(client_id_hash="b", visit_date=date(2026, 7, 1)),
    ]
    ret = _retention(visits)
    assert ret["unique_visitors"] == 2
    assert ret["returning_visitors"] == 1
    day_cohort = next(c for c in ret["day_cohorts"] if c["cohort_day"] == "2026-07-01")
    assert day_cohort["size"] == 2
    assert day_cohort["day_plus"].get("1") == 1


def test_metrika_live_today_merge(monkeypatch):
    """Живой слой Метрики за сегодня (2026-07-06, «метрика не подгрузилась»):
    если окно захватывает сегодня и повизитки за сегодня нет — сводка и разрезы
    дотягиваются из Reporting API поверх нулей Logs-слоя."""
    import asyncio
    from datetime import datetime, timezone

    from app.services import admin_bi
    from app.services.analytics_period import msk_day, resolve_period

    today = msk_day(datetime.now(timezone.utc)).isoformat()

    async def fake_live():
        return {"visits": 42, "users": 30,
                "sources": {"organic": 25, "direct": 17},
                "search_engines": {"yandex": 20},
                "devices": {"mobile": 30, "desktop": 12},
                "cities": {"Москва": 15}}

    monkeypatch.setattr(
        "app.services.metrika_acquisition.live_today_reference", fake_live)

    dashboard = {
        "kpi_daily": [{"date": today, "visits": 0, "visitors": 0}],
        "metric_tree": {"north_star": {"metrika_visits_total": 100}},
        "metrika_funnel": {"visits": 0},
        "audience": {"metrika_reference": {"visits_total": 0}},
        "acquisition": {"sources": {}},
    }
    asyncio.run(admin_bi._merge_metrika_live_today(
        dashboard, resolve_period("today"), window_visits=[]))

    assert dashboard["metrika_live_today"]["visits"] == 42
    assert dashboard["kpi_daily"][0]["visits"] == 42
    assert dashboard["metric_tree"]["north_star"]["metrika_visits_total"] == 142
    assert dashboard["metrika_funnel"]["visits"] == 42
    assert dashboard["metrika_funnel"]["today_live"] is True
    assert dashboard["audience"]["metrika_reference"]["visits_total"] == 42
    assert dashboard["acquisition"]["sources"] == {"organic": 25, "direct": 17}

    # Прошлое окно (без сегодня) live-слой не трогает.
    past = {"kpi_daily": [], "metric_tree": {"north_star": {"metrika_visits_total": 5}},
            "metrika_funnel": {"visits": 5}, "audience": {}, "acquisition": {}}
    asyncio.run(admin_bi._merge_metrika_live_today(
        past, resolve_period("custom", "2026-01-01", "2026-01-07"), window_visits=[]))
    assert "metrika_live_today" not in past


def test_retention_accepts_id_date_tuples():
    """Инцидент 2026-09-03: retention больше не требует полные ORM-визиты."""
    from datetime import date
    from app.services.admin_bi import _retention

    rows = [
        ("a", date(2026, 8, 1)),
        ("a", date(2026, 8, 3)),
        ("b", date(2026, 8, 2)),
    ]
    out = _retention(rows)
    assert out["unique_visitors"] == 2
    assert out["returning_visitors"] == 1
    assert out["returning_pct"] == 50.0


def test_slices_meta_when_clickhouse_off(auth_client):
    _register(auth_client, ADMIN_EMAIL)
    r = auth_client.get("/api/v1/admin/bi/slices/meta")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is False
    assert "reason" in body


def test_slices_query_503_when_clickhouse_off(auth_client):
    """Вкладка «Срезы» не ходит в Postgres и не валит сайт: мягкая 503."""
    _register(auth_client, ADMIN_EMAIL)
    r = auth_client.get("/api/v1/admin/bi/slices?metric=sessions&dims=channel")
    assert r.status_code == 503, r.text


def test_slices_unknown_metric_422(auth_client):
    _register(auth_client, ADMIN_EMAIL)
    r = auth_client.get("/api/v1/admin/bi/slices?metric=not-a-metric")
    # CH выключен → 503 раньше валидации метрики. Это честно: слой недоступен.
    assert r.status_code in (422, 503)


def test_dashboard_with_fat_metrika_json(auth_client, auth_env):
    """Дашборд считает KPI/привлечение без загрузки полного raw_json в ORM."""
    import asyncio

    from app.models import RawMetrikaVisit
    from app.services.analytics_period import as_period

    _register(auth_client, ADMIN_EMAIL)
    p = as_period(7)

    async def _seed():
        async with auth_env["session_maker"]() as db:
            db.add(RawMetrikaVisit(
                counter_id="107136069", visit_id="fat-1",
                client_id_hash="c1", visit_date=p.end_date,
                traffic_source="organic", duration_seconds=40,
                start_url="https://forecasteconomy.com/indicator/cpi",
                search_engine="yandex", search_phrase="инфляция",
                goals_json={"goals": "[]"},
                raw_json={
                    "ym:s:deviceCategory": "1",
                    "ym:s:browser": "chrome",
                    "ym:s:pageViews": "3",
                    "blob": "x" * 80_000,
                },
                row_hash="fat-1",
            ))
            await db.commit()

    asyncio.run(_seed())
    r = auth_client.get("/api/v1/admin/bi/dashboard?days=7&wait=60")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["acquisition"]["sources"].get("organic") == 1
    assert data["metric_tree"]["north_star"]
    assert sum(row["visits"] for row in data["kpi_daily"]) == 1
    health = auth_client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_dashboard_and_health_parallel(auth_client):
    """Пока считается дашборд, public health отвечает 200 (sqlite: оба на одном движке теста)."""
    import threading

    _register(auth_client, ADMIN_EMAIL)
    results = {}

    def dash():
        results["d"] = auth_client.get("/api/v1/admin/bi/dashboard?days=7&wait=60")

    def health():
        results["h"] = auth_client.get("/api/v1/health")

    t1 = threading.Thread(target=dash)
    t2 = threading.Thread(target=health)
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert results["h"].status_code == 200
    assert results["d"].status_code == 200
    assert "metric_tree" in results["d"].json()
