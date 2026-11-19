"""Флаги строки «присылать» и первого экрана (совет 19.11.2026)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import site_acq
from app.config import settings


def _get():
    app = FastAPI()
    app.include_router(site_acq.router, prefix="/api/v1")
    return TestClient(app).get("/api/v1/site-acq/config")


def test_config_off_by_default(monkeypatch):
    monkeypatch.setattr(settings, "acq_site_line_enabled", False)
    monkeypatch.setattr(settings, "acq_site_first_screen_enabled", False)
    r = _get()
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert {k: body[k] for k in ("line", "topics", "bot", "first_screen")} == {
        "line": False, "topics": [], "bot": "", "first_screen": False}
    # Почта не зависит от Telegram-части: темы для неё есть и при выключенной строке.
    assert body["mail_topics"] == ["inflation", "gold", "keyrate", "deposit", "mortgage", "usd", "eur"]


def test_line_needs_public_bot(monkeypatch):
    monkeypatch.setattr(settings, "acq_site_line_enabled", True)
    monkeypatch.setattr(settings, "public_bot_enabled", False)
    body = _get().json()
    assert body["line"] is False and body["topics"] == [] and body["bot"] == ""
    assert "inflation" in body["mail_topics"]


def test_line_on_gives_topics_and_bot(monkeypatch):
    monkeypatch.setattr(settings, "acq_site_line_enabled", True)
    monkeypatch.setattr(settings, "public_bot_enabled", True)
    monkeypatch.setattr(settings, "public_bot_username", "ForecastEconomyBot")
    monkeypatch.setattr(settings, "acq_site_line_topics", "inflation, gold,unknown,gold,DIESEL")
    monkeypatch.setattr(settings, "acq_site_first_screen_enabled", True)
    assert _get().json() == {
        "line": True, "topics": ["inflation", "gold", "diesel"], "bot": "ForecastEconomyBot", "first_screen": True,
        "mail_topics": ["inflation", "gold", "diesel"],
    }


def test_default_topics_exclude_fuel():
    keys = site_acq.line_topics(settings.model_fields["acq_site_line_topics"].default)
    assert keys == ["inflation", "gold", "keyrate", "deposit", "mortgage", "usd", "eur"]
    assert not {"diesel", "ai92", "ai95"} & set(keys)


def test_router_registered():
    from app.api.router import api_router

    assert any(getattr(r, "path", "") == "/api/v1/site-acq/config" for r in api_router.routes)
