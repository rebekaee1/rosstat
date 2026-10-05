"""«Фальшивая дверь» платного API: флаг, валидация, антиспам, формат заявки.

Заявка идёт в Telegram-outbox владельца без новой схемы БД; почта не должна
попадать ни в логи, ни в frontend_events (последнее проверяет фронт-тест:
событие несёт только use_case/source).
"""
import asyncio
import logging

import pytest

import app.api.api_interest as api_interest
import app.services.alerting as alerting
from app.config import settings

URL = "/api/v1/api-interest"
GOOD = {
    "email": "analyst@example.com",
    "use_case": "analytics_treasury",
    "comment": "нужен прогноз ключевой ставки в CSV",
    "source": "indicator",
    "indicator_code": "key-rate",
}


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "api_interest_enabled", True)


@pytest.fixture
def sent(monkeypatch):
    """Подменяет доставку: собирает заявки, возвращает True (доставлено)."""
    calls: list[dict] = []

    async def fake_notify(info):
        calls.append(info)
        return True

    monkeypatch.setattr(api_interest, "notify_api_interest", fake_notify)
    return calls


# --- флаг ---

def test_config_reports_flag_default_off(auth_client):
    r = auth_client.get(f"{URL}/config")
    assert r.status_code == 200
    assert r.json() == {"enabled": False}
    assert r.headers["cache-control"] == "no-store"


def test_config_reports_flag_on(auth_client, enabled):
    assert auth_client.get(f"{URL}/config").json() == {"enabled": True}


def test_post_is_404_while_disabled(auth_client, sent):
    r = auth_client.post(URL, json=GOOD)
    assert r.status_code == 404
    assert sent == []


# --- приём заявки гостем ---

def test_guest_can_submit_and_owner_gets_payload(auth_client, enabled, sent):
    r = auth_client.post(URL, json=GOOD)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert len(sent) == 1
    assert sent[0]["email"] == "analyst@example.com"
    assert sent[0]["use_case"] == "analytics_treasury"
    assert sent[0]["source"] == "indicator"
    assert sent[0]["indicator_code"] == "key-rate"
    assert sent[0]["comment"].startswith("нужен прогноз")
    assert sent[0]["locale"] in ("ru", "en")


def test_comment_and_code_are_optional_and_sanitised(auth_client, enabled, sent):
    r = auth_client.post(URL, json={
        "email": "a@b.co", "use_case": "study", "source": "weird", "indicator_code": "<script>",
    })
    assert r.status_code == 200
    assert sent[0]["comment"] is None
    assert sent[0]["source"] == "indicator"      # неизвестный источник → дефолт
    assert sent[0]["indicator_code"] is None     # мусор в коде отбрасывается


@pytest.mark.parametrize("patch", [
    {"email": "not-an-email"},
    {"email": ""},
    {"use_case": "pirate"},
    {"use_case": ""},
    {"comment": "x" * 1001},
])
def test_validation_rejects_bad_input(auth_client, enabled, sent, patch):
    r = auth_client.post(URL, json={**GOOD, **patch})
    assert r.status_code == 422
    assert sent == []


def test_validation_message_follows_locale(auth_client, enabled, sent):
    r = auth_client.post(URL, json={**GOOD, "email": "nope"}, headers={"X-FE-Locale": "en"})
    assert r.status_code == 422
    assert "Invalid email" in r.text


# --- антиспам ---

def test_honeypot_looks_like_success_but_sends_nothing(auth_client, enabled, sent):
    r = auth_client.post(URL, json={**GOOD, "website": "http://spam.example"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert sent == []


def test_noise_user_agent_is_silently_dropped(auth_client, enabled, sent):
    r = auth_client.post(URL, json=GOOD, headers={"User-Agent": "HeadlessChrome/145.0 Safari"})
    assert r.status_code == 200
    assert sent == []


def test_same_email_twice_is_sent_once(auth_client, enabled, sent):
    assert auth_client.post(URL, json=GOOD).status_code == 200
    assert auth_client.post(URL, json={**GOOD, "use_case": "study"}).status_code == 200
    assert len(sent) == 1


def test_email_dedupe_is_case_insensitive_and_stores_only_a_hash(auth_client, auth_env, enabled, sent):
    auth_client.post(URL, json={**GOOD, "email": "Analyst@Example.com"})
    auth_client.post(URL, json={**GOOD, "email": "analyst@example.com"})
    assert len(sent) == 1

    async def keys():
        return await auth_env["state_redis"].keys("fe:api_interest:*")

    stored = auth_client.portal.call(keys)
    assert stored and not any("analyst" in k.lower() for k in stored)


def test_ip_rate_limit_after_five_submissions(auth_client, enabled, sent):
    for i in range(5):
        r = auth_client.post(URL, json={**GOOD, "email": f"user{i}@example.com"})
        assert r.status_code == 200
    r = auth_client.post(URL, json={**GOOD, "email": "user99@example.com"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert len(sent) == 5


# --- доставка ---

def test_503_when_telegram_not_configured_and_retry_not_swallowed(auth_client, enabled, monkeypatch):
    async def undelivered(info):
        return False

    monkeypatch.setattr(api_interest, "notify_api_interest", undelivered)
    monkeypatch.setattr(settings, "telegram_bot_token", "", raising=False)
    monkeypatch.setattr(settings, "telegram_chat_id", "", raising=False)
    assert auth_client.post(URL, json=GOOD).status_code == 503
    # Повтор не считается дублем «уже приняли» (метка снята) — снова честная 503.
    assert auth_client.post(URL, json=GOOD).status_code == 503


def test_ok_when_telegram_configured_but_delivery_failed(auth_client, enabled, monkeypatch):
    """Недоставленное лежит в telegram_outbox и досылается job'ом."""
    async def undelivered(info):
        return False

    monkeypatch.setattr(api_interest, "notify_api_interest", undelivered)
    monkeypatch.setattr(settings, "telegram_bot_token", "x", raising=False)
    monkeypatch.setattr(settings, "telegram_chat_id", "111", raising=False)
    assert auth_client.post(URL, json=GOOD).status_code == 200


def test_email_never_reaches_logs(auth_client, enabled, sent, caplog):
    with caplog.at_level(logging.DEBUG):
        auth_client.post(URL, json=GOOD)
        auth_client.post(URL, json={**GOOD, "website": "x", "email": "bot@example.com"})
    assert "analyst@example.com" not in caplog.text
    assert "bot@example.com" not in caplog.text


# --- форматирование заявки ---

def test_format_message_has_marker_and_all_fields():
    text = alerting.format_api_interest_message({
        "email": "analyst@example.com", "use_case": "analytics_treasury",
        "comment": "нужен CSV", "source": "limit_modal",
        "indicator_code": "key-rate", "locale": "en",
    })
    assert "Заявка на API" in text
    assert "analyst@example.com" in text
    assert "аналитика / казначейство" in text
    assert "окно лимита скачиваний" in text
    assert "key-rate" in text
    assert "английская" in text
    assert "нужен CSV" in text


def test_format_message_escapes_html_and_handles_missing_fields():
    text = alerting.format_api_interest_message({
        "email": "a<b>@x.io", "use_case": "other", "comment": "<script>alert(1)</script>",
    })
    assert "<script>" not in text and "&lt;script&gt;" in text
    assert "a&lt;b&gt;@x.io" in text
    assert "Показатель: —" in text


def test_notify_goes_to_all_digest_recipients_with_resendable_kind(monkeypatch):
    seen: list[tuple] = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        seen.append((chat_id, kind))
        return chat_id == "222"   # хотя бы один доставлен → True

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    monkeypatch.setattr(alerting.settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_digest_chat_ids", "222", raising=False)
    # Заявка — данные замера, а не алерт: realtime-флаг её не глушит.
    monkeypatch.setattr(alerting.settings, "telegram_realtime_alerts_enabled", False)
    ok = asyncio.run(alerting.notify_api_interest({"email": "a@b.co", "use_case": "study"}))
    assert ok is True
    assert seen == [("111", "api_interest"), ("222", "api_interest")]

    from app.services.telegram_resend import RESEND_KINDS
    assert "api_interest" in RESEND_KINDS
