"""Locale-aware auth / export detail strings (EN via X-FE-Locale)."""
from app.services.api_i18n import api_detail
from app.services.locale import reset_locale, set_locale


def test_api_detail_switches_on_locale():
    tok = set_locale("ru")
    try:
        assert api_detail("ru-msg", "en-msg") == "ru-msg"
    finally:
        reset_locale(tok)
    tok = set_locale("en")
    try:
        assert api_detail("ru-msg", "en-msg") == "en-msg"
    finally:
        reset_locale(tok)


def test_login_bad_password_detail_en(auth_client):
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "i18n-login@example.com", "password": "supersecret1", "consent": True},
    )
    r = auth_client.post(
        "/api/v1/auth/login",
        headers={"X-FE-Locale": "en"},
        json={"email": "i18n-login@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_bad_password_detail_ru(auth_client):
    auth_client.post(
        "/api/v1/auth/register",
        json={"email": "i18n-login-ru@example.com", "password": "supersecret1", "consent": True},
    )
    r = auth_client.post(
        "/api/v1/auth/login",
        headers={"X-FE-Locale": "ru"},
        json={"email": "i18n-login-ru@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Неверный email или пароль"


def test_register_duplicate_en(auth_client):
    payload = {
        "email": "i18n-dup@example.com",
        "password": "supersecret1",
        "consent": True,
    }
    assert auth_client.post("/api/v1/auth/register", json=payload).status_code == 201
    r = auth_client.post(
        "/api/v1/auth/register",
        headers={"X-FE-Locale": "en"},
        json=payload,
    )
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"].lower()


def test_export_limit_message_en(auth_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "download_anon_limit", 0)
    r = auth_client.post(
        "/api/v1/export/table",
        headers={"X-FE-Locale": "en"},
        json={
            "format": "csv",
            "filename": "row.csv",
            "value_label": "Value",
            "points": [{"date": "2020-01-01", "actual": 1.0}],
        },
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["code"] == "download_limit"
    assert "Sign in" in detail["message"]
