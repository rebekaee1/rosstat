"""Почта (ADR-0032): ссылки, письма, список допуска, подтверждение, сброс, отписка, выпуск."""
import asyncio
import email
import time

import pytest

from tests.conftest import csrf_headers

SECRET = "test-mail-secret-0123456789abcdef"


@pytest.fixture
def mail_env(auth_env, monkeypatch):
    from app.config import settings
    from app.services.mail import service, transport

    monkeypatch.setattr(settings, "mail_token_secret", SECRET)
    monkeypatch.setattr(settings, "mail_enabled", True)
    monkeypatch.setattr(settings, "mail_smtp_user", "noreply@forecasteconomy.com")
    monkeypatch.setattr(settings, "mail_smtp_password", "x")
    monkeypatch.setattr(settings, "mail_allowlist", "allowed@example.com,rebeka.ee@yandex.ru")
    monkeypatch.setattr(settings, "mail_allow_all_recipients", False)
    monkeypatch.setattr(settings, "mail_campaign_pause_seconds", 0)
    monkeypatch.setattr(service, "session_factory", auth_env["session_maker"])
    sent: list = []

    def _fake_send(msg, profile=None):
        sent.append(msg)

    monkeypatch.setattr(transport, "_send_sync", _fake_send)
    return {"sent": sent, **auth_env}


def _rows(env):
    from sqlalchemy import select
    from app.models import MailMessage

    async def _q():
        async with env["session_maker"]() as db:
            return (await db.scalars(select(MailMessage).order_by(MailMessage.id))).all()
    return asyncio.run(_q())


def _link_token(msg, marker):
    body = msg.get_body(("plain",)).get_content()
    for line in body.splitlines():
        if marker in line and "t=" in line:
            return line.split("t=", 1)[1].strip()
    raise AssertionError("no link")


# --- ссылки --------------------------------------------------------------------------

def test_tokens_roundtrip_purpose_and_expiry(monkeypatch):
    from app.config import settings
    from app.services.mail import tokens

    monkeypatch.setattr(settings, "mail_token_secret", SECRET)
    tok = tokens.issue("verify", "u1", "fp")
    assert tokens.verify("verify", tok).user_id == "u1"
    with pytest.raises(tokens.TokenError):
        tokens.verify("reset", tok)  # чужое назначение
    with pytest.raises(tokens.TokenError):
        tokens.verify("verify", tok[:-2] + "aa")
    with pytest.raises(tokens.TokenError, match="expired"):
        tokens.verify("verify", tok, now=time.time() + 8 * 24 * 3600)
    unsub = tokens.issue("unsub", "u1")
    assert tokens.verify("unsub", unsub, now=time.time() + 10 * 365 * 24 * 3600).expires_at is None


def test_tokens_require_secret(monkeypatch):
    from app.config import settings
    from app.services.mail import tokens

    monkeypatch.setattr(settings, "mail_token_secret", "")
    with pytest.raises(tokens.TokenSecretMissing):
        tokens.issue("unsub", "u1")


# --- письмо: заголовки и вид ---------------------------------------------------------

def test_newsletter_message_headers(monkeypatch):
    from app.config import settings
    from app.services.mail import transport

    monkeypatch.setattr(settings, "mail_smtp_user", "noreply@forecasteconomy.com")
    long_url = "https://ru.forecasteconomy.com/api/v1/mail/unsubscribe?t=" + "a" * 160
    msg = transport.build_message(transport.OutgoingMail(
        to="x@example.com", subject="Тема", html="<p>x</p>", text="x", kind="newsletter",
        unsubscribe_url=long_url, campaign="2026-11-digest"))
    raw = bytes(msg).decode("ascii")
    # Заголовок не закодирован в =?utf-8?…?= — почтовые сервисы видят ссылку.
    assert f"List-Unsubscribe: <{long_url}>" in raw
    assert "List-Unsubscribe-Post: List-Unsubscribe=One-Click" in raw
    assert msg["From"] == "Forecast Economy <noreply@forecasteconomy.com>"
    assert msg["Message-ID"].endswith("@forecasteconomy.com>")
    parsed = email.message_from_bytes(bytes(msg))
    assert parsed.get_content_type() == "multipart/alternative"


def test_service_message_is_auto_submitted():
    from app.services.mail import transport

    msg = transport.build_message(transport.OutgoingMail(
        to="x@example.com", subject="s", html="<p>x</p>", text="x", kind="verify_email"))
    assert msg["Auto-Submitted"] == "auto-generated"
    assert msg["List-Unsubscribe"] is None


def test_templates_follow_design_rules():
    from app.services.mail.templates import render_action, render_digest, sample_digest

    for loc in ("ru", "en"):
        for r in (render_action("verify", loc, action_url="https://x/a?t=1", site_url="https://x/"),
                  render_digest(sample_digest(loc, "https://x/"), loc, site_url="https://x/",
                                unsubscribe_url="https://x/u")):
            low = r.html.lower()
            assert "border:" not in low.replace("border-radius", "")  # без рамок
            assert "<img" not in low  # без картинок: не блокируются и не размываются
            assert "#b08a3e" in low  # золото — одна тонкая линия
            assert r.text and r.subject
    news = render_digest(sample_digest("ru", "https://x/"), "ru", site_url="https://x/", unsubscribe_url="https://x/u")
    assert "Отписаться" in news.html and "https://x/u" in news.text
    assert "ИИМПАКТ ПЛЮС" in news.html


# --- список допуска и выключатель ----------------------------------------------------

def test_allowlist_blocks_other_recipients(mail_env):
    from app.services.mail import service
    from app.services.mail.templates import render_action

    r = render_action("verify", "ru", action_url="https://x/", site_url="https://x/")
    assert asyncio.run(service.send_now(kind="test", to="stranger@example.com", locale="ru", rendered=r)) == "blocked"
    assert asyncio.run(service.send_now(kind="test", to="Allowed@Example.com", locale="ru", rendered=r)) == "sent"
    assert len(mail_env["sent"]) == 1
    assert [x.status for x in _rows(mail_env)] == ["blocked", "sent"]


def test_disabled_mail_sends_nothing(mail_env, monkeypatch):
    from app.config import settings
    from app.services.mail import service
    from app.services.mail.templates import render_action

    monkeypatch.setattr(settings, "mail_enabled", False)
    r = render_action("verify", "ru", action_url="https://x/", site_url="https://x/")
    assert asyncio.run(service.send_now(kind="test", to="allowed@example.com", locale="ru", rendered=r)) == "disabled"
    assert mail_env["sent"] == []


# --- подтверждение адреса ------------------------------------------------------------

def test_register_sends_verify_and_link_confirms(mail_env, auth_client):
    r = auth_client.post("/api/v1/auth/register", json={
        "email": "allowed@example.com", "password": "supersecret1", "consent": True})
    assert r.status_code == 201
    assert r.json()["user"]["email_verified"] is False
    assert len(mail_env["sent"]) == 1
    msg = mail_env["sent"][0]
    assert msg["To"] == "allowed@example.com"
    tok = _link_token(msg, "/account/verify-email")
    assert auth_client.post("/api/v1/auth/email/verify", json={"token": "bad.token"}).status_code == 400
    ok = auth_client.post("/api/v1/auth/email/verify", json={"token": tok})
    assert ok.status_code == 200
    assert auth_client.get("/api/v1/auth/me").json()["user"]["email_verified"] is True
    # Повторное открытие ссылки — не ошибка.
    assert auth_client.post("/api/v1/auth/email/verify", json={"token": tok}).status_code == 200


def test_register_outside_allowlist_is_logged_not_sent(mail_env, auth_client):
    r = auth_client.post("/api/v1/auth/register", json={
        "email": "someone@example.com", "password": "supersecret1", "consent": True})
    assert r.status_code == 201
    assert mail_env["sent"] == []
    assert [(x.kind, x.status) for x in _rows(mail_env)] == [("verify_email", "blocked")]


def test_resend_is_rate_limited(mail_env, auth_client):
    auth_client.post("/api/v1/auth/register", json={
        "email": "allowed@example.com", "password": "supersecret1", "consent": True})
    codes = [auth_client.post("/api/v1/auth/email/verify/resend", headers=csrf_headers(auth_client)).status_code
             for _ in range(4)]
    assert codes == [200, 200, 200, 423]


# --- сброс пароля --------------------------------------------------------------------

def test_password_reset_flow_single_use(mail_env, auth_client):
    auth_client.post("/api/v1/auth/register", json={
        "email": "allowed@example.com", "password": "supersecret1", "consent": True})
    mail_env["sent"].clear()
    # Неизвестный адрес — тот же ответ, письма нет.
    assert auth_client.post("/api/v1/auth/password/forgot", json={"email": "nobody@example.com"}).json() == {"ok": True}
    assert mail_env["sent"] == []
    assert auth_client.post("/api/v1/auth/password/forgot", json={"email": "Allowed@example.com"}).status_code == 200
    assert len(mail_env["sent"]) == 1
    tok = _link_token(mail_env["sent"][0], "/account/reset-password")
    r = auth_client.post("/api/v1/auth/password/reset", json={"token": tok, "password": "brandnew123"})
    assert r.status_code == 200, r.text
    # Старая сессия закрыта, второй раз ссылка не работает, вход — новым паролем.
    assert auth_client.get("/api/v1/auth/me").status_code == 401
    again = auth_client.post("/api/v1/auth/password/reset", json={"token": tok, "password": "another123"})
    assert again.status_code == 400
    assert auth_client.post("/api/v1/auth/login", json={"email": "allowed@example.com", "password": "brandnew123"}).status_code == 200
    assert auth_client.get("/api/v1/auth/me").json()["user"]["email_verified"] is True


def test_forgot_rate_limit_per_email(mail_env, auth_client):
    auth_client.post("/api/v1/auth/register", json={
        "email": "allowed@example.com", "password": "supersecret1", "consent": True})
    mail_env["sent"].clear()
    for _ in range(5):
        assert auth_client.post("/api/v1/auth/password/forgot", json={"email": "allowed@example.com"}).status_code == 200
    assert len(mail_env["sent"]) == 3


# --- отписка по ссылке ---------------------------------------------------------------

def _subscribe(auth_client, email_addr="allowed@example.com"):
    r = auth_client.post("/api/v1/auth/register", json={
        "email": email_addr, "password": "supersecret1", "consent": True, "newsletter": True})
    return r.json()["user"]["id"]


def test_one_click_unsubscribe_and_resubscribe(mail_env, auth_client):
    from app.services.mail import tokens

    uid = _subscribe(auth_client)
    tok = tokens.issue("unsub", uid)
    state = auth_client.get(f"/api/v1/mail/unsubscribe?t={tok}").json()
    assert state == {"subscribed": True, "email": "a…d@example.com", "list": "newsletter"}
    # GET ничего не меняет (сканеры ссылок), POST формы RFC 8058 — отписывает.
    r = auth_client.post(f"/api/v1/mail/unsubscribe?t={tok}", content="List-Unsubscribe=One-Click",
                         headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 200 and r.json()["subscribed"] is False
    assert auth_client.get("/api/v1/auth/me").json()["user"]["newsletter"] is False
    # Повтор — без новой записи и без ошибки.
    assert auth_client.post("/api/v1/mail/unsubscribe", json={"t": tok}).json()["subscribed"] is False
    back = auth_client.post("/api/v1/mail/resubscribe", json={"t": tok})
    assert back.json()["subscribed"] is True
    assert auth_client.post("/api/v1/mail/unsubscribe", json={"t": "x.y"}).status_code == 400


# --- выпуск рассылки -----------------------------------------------------------------

ISSUE = {
    "key": "2026-11-test",
    "ru": {"subject": "Новости", "title": "Главное за месяц",
           "items": [{"title": "Инфляция", "value": "7,7 %", "url": "https://ru.forecasteconomy.com/russia"}]},
}


def _verify_all(env):
    from sqlalchemy import update
    from app.models import EmailCredential

    async def _q():
        async with env["session_maker"]() as db:
            await db.execute(update(EmailCredential).values(email_verified=True))
            await db.commit()
    asyncio.run(_q())


def _run(env, **kw):
    from app.services.mail import campaign

    async def _q():
        async with env["session_maker"]() as db:
            return await campaign.run(db, campaign.parse_issue(ISSUE), **kw)
    return asyncio.run(_q())


def test_campaign_guards_and_idempotency(mail_env, auth_client, monkeypatch):
    from app.config import settings
    from app.services.mail import campaign

    _subscribe(auth_client, "allowed@example.com")
    auth_client.cookies.clear()
    _subscribe(auth_client, "rebeka.ee@yandex.ru")
    mail_env["sent"].clear()

    dry = _run(mail_env, send=False)
    assert dry.audience == 2 and dry.unverified_skipped == 2 and mail_env["sent"] == []
    with pytest.raises(campaign.CampaignError):
        _run(mail_env, send=True)  # люди закрыты списком допуска
    _verify_all(mail_env)
    monkeypatch.setattr(settings, "mail_allow_all_recipients", True)
    first = _run(mail_env, send=True, max_per_run=1)
    assert first.stopped == "max_per_run" and len(mail_env["sent"]) == 1
    second = _run(mail_env, send=True)
    assert second.already_sent == 1 and len(mail_env["sent"]) == 2
    third = _run(mail_env, send=True)
    assert third.already_sent == 2 and len(mail_env["sent"]) == 2
    msg = mail_env["sent"][0]
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    html = msg.get_body(("html",)).get_content()
    assert "utm_source=email" in html and "utm_campaign=2026-11-test" in html


def test_campaign_stops_on_server_limit(mail_env, auth_client, monkeypatch):
    import smtplib
    from app.config import settings
    from app.services.mail import transport

    _subscribe(auth_client, "allowed@example.com")
    auth_client.cookies.clear()
    _subscribe(auth_client, "rebeka.ee@yandex.ru")
    _verify_all(mail_env)
    monkeypatch.setattr(settings, "mail_allow_all_recipients", True)

    def _limit(_msg, profile=None):
        raise smtplib.SMTPDataError(554, b"5.7.1 Message rejected: daily limit exceeded")

    monkeypatch.setattr(transport, "_send_sync", _limit)
    rep = _run(mail_env, send=True)
    assert rep.stopped and rep.stopped.startswith("server_limit") and rep.statuses["failed"] == 1


def test_delete_account_removes_mail_log(mail_env, auth_client):
    auth_client.post("/api/v1/auth/register", json={
        "email": "allowed@example.com", "password": "supersecret1", "consent": True})
    assert len(_rows(mail_env)) == 1
    export = auth_client.get("/api/v1/auth/account/export").json()
    assert export["emails"][0]["kind"] == "verify_email"
    assert auth_client.delete("/api/v1/auth/account", headers=csrf_headers(auth_client)).status_code == 200
    assert _rows(mail_env) == []
