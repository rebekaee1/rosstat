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
    "hypotheses", "dataset", "users",
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


def test_bi_dashboard_cached(auth_client):
    """Повторный запрос отдаётся из кэша (generated_at не меняется)."""
    _register(auth_client, ADMIN_EMAIL)
    first = auth_client.get("/api/v1/admin/bi/dashboard?days=30").json()
    second = auth_client.get("/api/v1/admin/bi/dashboard?days=30").json()
    assert first["generated_at"] == second["generated_at"]
