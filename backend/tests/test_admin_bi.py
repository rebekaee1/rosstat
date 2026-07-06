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

    r = auth_client.get("/api/v1/admin/bi/dashboard?days=7")
    assert r.status_code == 200, r.text
    data = r.json()
    assert EXPECTED_SECTIONS <= set(data.keys())
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
    """Повторный запрос отдаётся из кэша (generated_at не меняется)."""
    _register(auth_client, ADMIN_EMAIL)
    first = auth_client.get("/api/v1/admin/bi/dashboard?days=30").json()
    second = auth_client.get("/api/v1/admin/bi/dashboard?days=30").json()
    assert first["generated_at"] == second["generated_at"]


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
