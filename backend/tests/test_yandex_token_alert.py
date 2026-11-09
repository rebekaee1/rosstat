"""Истёкший токен Яндекса: одно понятное сообщение в сутки вместо «сбоя задачи», двух «recrawl» и «fetch failed»."""

import asyncio

import app.services.alerting as alerting
from app.services import yandex_token_alert as tok
from app.services.yandex_client import YandexApiError

EXPIRED = YandexApiError(
    "Yandex API returned HTTP 403 for GET /v4/user/", status_code=403,
    payload={"error_message": "Used OAuth token is invalid or expired", "error_code": "INVALID_OAUTH_TOKEN"},
)
NO_SCOPE = YandexApiError(
    "Yandex API returned HTTP 403 for GET /v4/user/", status_code=403,
    payload={"error_code": "ACCESS_FORBIDDEN", "error_message": "Required scope: ALL_SCOPES"},
)


def test_expired_token_is_recognised_and_other_403_is_not():
    assert tok.is_token_expired(EXPIRED)
    assert not tok.is_token_expired(NO_SCOPE)
    assert not tok.is_token_expired(RuntimeError("expired"))
    assert not tok.is_token_expired(None)


def test_service_is_taken_from_api_path():
    assert tok.service_for(EXPIRED) == "webmaster"
    assert tok.service_for(YandexApiError("Yandex API returned HTTP 403 for GET /management/v1/counters")) == "metrika"


def test_text_says_what_to_do_without_jargon():
    text = tok.expired_text("webmaster")
    assert "Вебмастер" in text and "не повторится" in text
    for jargon in ("403", "OAuth", "API", "INVALID"):
        assert jargon not in text


def test_report_once_per_token(monkeypatch):
    sent, muted = [], set()

    async def fake_muted(key, ttl):
        if key in muted:
            return True
        muted.add(key)
        return False

    async def fake_send(text, *a, kind=None, **k):
        sent.append(kind)
        return True

    monkeypatch.setattr(alerting, "alert_muted", fake_muted)
    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    assert asyncio.run(tok.report_token_expired("webmaster")) is True
    assert asyncio.run(tok.report_token_expired("webmaster")) is False
    assert sent == ["token_expired"]


def test_recrawl_job_reports_token_instead_of_recrawl_alert(monkeypatch):
    from app.services import webmaster_recrawl

    reported, alerts = [], []

    class _Client:
        async def user(self):
            raise EXPIRED

    async def fake_report(service="webmaster"):
        reported.append(service)
        return True

    async def fake_alert(text):
        alerts.append(text)

    monkeypatch.setattr(webmaster_recrawl, "YandexWebmasterClient", _Client)
    monkeypatch.setattr(tok, "report_token_expired", fake_report)
    monkeypatch.setattr(webmaster_recrawl, "_alert_recrawl", fake_alert)
    monkeypatch.setattr(webmaster_recrawl.settings, "yandex_webmaster_token", "x", raising=False)
    monkeypatch.setattr(webmaster_recrawl.settings, "analytics_live_writes_enabled", True, raising=False)
    result = asyncio.run(webmaster_recrawl.recrawl_daily_job())
    assert result.get("blocked") == "token_expired"
    assert reported == ["webmaster"] and alerts == []


def test_new_token_gets_its_own_message(monkeypatch):
    from app.config import settings

    keys = []

    async def fake_muted(key, ttl):
        keys.append(key)
        return False

    async def fake_send(*a, **k):
        return True

    monkeypatch.setattr(alerting, "alert_muted", fake_muted)
    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    monkeypatch.setattr(settings, "yandex_webmaster_token", "old", raising=False)
    asyncio.run(tok.report_token_expired("webmaster"))
    monkeypatch.setattr(settings, "yandex_webmaster_token", "new", raising=False)
    asyncio.run(tok.report_token_expired("webmaster"))
    assert keys[0] != keys[1] and all("old" not in k and "new" not in k for k in keys)
