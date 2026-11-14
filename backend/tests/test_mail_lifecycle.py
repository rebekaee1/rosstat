"""Почта, вторая волна (14.11.2026): профиль рассылки, подсказка входа через провайдера,
«подтвердите почту» давним аккаунтам, разбор отказов и жалоб, сводка «колокольчика» со
своей отпиской, сводка для админ-BI."""
from datetime import date

import pytest
from sqlalchemy import select

from tests.conftest import csrf_headers
from tests.test_auth_oauth import fake_login
from tests.test_mail import SECRET, _link_token, mail_env  # noqa: F401 — фикстура

ADMIN = "admin_forecasteconomy@forecasteconomy.com"


def _db(tc, env, fn):
    async def run(maker):
        async with maker() as s:
            out = await fn(s)
            await s.commit()
            return out
    return tc.portal.call(run, env["session_maker"])


def _register(tc, email, newsletter=False):
    tc.cookies.clear()
    r = tc.post("/api/v1/auth/register", json={
        "email": email, "password": "supersecret1", "consent": True, "newsletter": newsletter})
    assert r.status_code == 201, r.text
    return r.json()["user"]["id"]


# --- профиль SMTP рассылки -----------------------------------------------------------

def test_bulk_profile_only_for_stream_mail(monkeypatch):
    from app.config import settings
    from app.services.mail import transport

    monkeypatch.setattr(settings, "mail_smtp_user", "info@forecasteconomy.com")
    monkeypatch.setattr(settings, "mail_bulk_smtp_host", "")
    assert transport.profile_for("newsletter").name == "main"
    monkeypatch.setattr(settings, "mail_bulk_smtp_host", "postbox.cloud.yandex.net")
    monkeypatch.setattr(settings, "mail_bulk_smtp_user", "key-id")
    monkeypatch.setattr(settings, "mail_bulk_from_address", "news@forecasteconomy.com")
    bulk = transport.profile_for("newsletter")
    assert (bulk.name, bulk.host, bulk.port, bulk.security, bulk.from_addr) == (
        "bulk", "postbox.cloud.yandex.net", 587, "starttls", "news@forecasteconomy.com")
    assert transport.profile_for("watch_digest").name == "bulk"
    # Служебные письма всегда через основной ящик.
    assert transport.profile_for("password_reset").name == "main"
    msg = transport.build_message(transport.OutgoingMail(
        to="x@example.com", subject="s", html="<p>x</p>", text="x", kind="newsletter", unsubscribe_url="https://x/u"))
    assert msg["From"] == "Forecast Economy <news@forecasteconomy.com>"


# --- «Забыли пароль?» для входа через провайдера -------------------------------------

def test_forgot_for_oauth_only_sends_sign_in_hint(mail_env, oauth_client):
    fake_login(oauth_client, sub="o1", email="allowed@example.com")
    oauth_client.cookies.clear()
    r = oauth_client.post("/api/v1/auth/password/forgot", json={"email": "allowed@example.com"})
    assert r.json() == {"ok": True}
    assert len(mail_env["sent"]) == 1
    msg = mail_env["sent"][0]
    body = msg.get_body(("plain",)).get_content()
    assert "/login" in body and "reset-password" not in body


# --- «подтвердите почту» давним аккаунтам --------------------------------------------

def test_reconfirm_dry_run_send_and_idempotency(mail_env, auth_client, monkeypatch):
    from app.config import settings
    from app.services.mail import campaign

    _register(auth_client, "allowed@example.com")
    _register(auth_client, "rebeka.ee@yandex.ru")
    mail_env["sent"].clear()

    dry = _db(auth_client, mail_env, lambda s: campaign.run_reconfirm(s, send=False))
    assert dry.audience == 2 and dry.dry_run and mail_env["sent"] == []
    with pytest.raises(campaign.CampaignError):
        _db(auth_client, mail_env, lambda s: campaign.run_reconfirm(s, send=True))
    monkeypatch.setattr(settings, "mail_allow_all_recipients", True)
    first = _db(auth_client, mail_env, lambda s: campaign.run_reconfirm(s, send=True, pause_seconds=0))
    assert first.statuses["sent"] == 2 and len(mail_env["sent"]) == 2
    again = _db(auth_client, mail_env, lambda s: campaign.run_reconfirm(s, send=True, pause_seconds=0))
    assert again.already_sent == 2 and len(mail_env["sent"]) == 2
    # Ссылка из письма подтверждает адрес тем же путём, что и обычное письмо подтверждения.
    tok = _link_token(mail_env["sent"][0], "/account/verify-email")
    assert auth_client.post("/api/v1/auth/email/verify", json={"token": tok}).status_code == 200


# --- разбор отказов ------------------------------------------------------------------

DSN = (b"From: mailer-daemon@yandex.ru\r\nTo: info@forecasteconomy.com\r\nSubject: Undelivered\r\n"
       b"MIME-Version: 1.0\r\nContent-Type: multipart/report; report-type=delivery-status; boundary=\"B\"\r\n\r\n"
       b"--B\r\nContent-Type: text/plain\r\n\r\nNot delivered\r\n"
       b"--B\r\nContent-Type: message/delivery-status\r\n\r\nReporting-MTA: dns; mx.yandex.ru\r\n\r\n"
       b"Final-Recipient: rfc822; Gone@Example.com\r\nAction: failed\r\nStatus: 5.1.1\r\n\r\n"
       b"--B\r\nContent-Type: text/rfc822-headers\r\n\r\nMessage-ID: <abc@forecasteconomy.com>\r\nSubject: x\r\n\r\n"
       b"--B--\r\n")
DELAYED = DSN.replace(b"Action: failed\r\nStatus: 5.1.1", b"Action: delayed\r\nStatus: 4.2.2")
ARF = (b"From: fbl@mail.ru\r\nMIME-Version: 1.0\r\n"
       b"Content-Type: multipart/report; report-type=feedback-report; boundary=\"C\"\r\n\r\n"
       b"--C\r\nContent-Type: text/plain\r\n\r\nabuse report\r\n"
       b"--C\r\nContent-Type: message/feedback-report\r\n\r\nFeedback-Type: abuse\r\n"
       b"Original-Rcpt-To: allowed@example.com\r\n\r\n--C--\r\n")


def test_parse_reports():
    from app.services.mail.bounces import parse_report

    [ev] = parse_report(DSN)
    assert (ev.email, ev.status, ev.permanent, ev.complaint, ev.message_id) == (
        "gone@example.com", "5.1.1", True, False, "<abc@forecasteconomy.com>")
    [tmp] = parse_report(DELAYED)
    assert tmp.permanent is False
    [c] = parse_report(ARF)
    assert c.complaint and c.email == "allowed@example.com"
    assert parse_report(b"From: a@b\r\nSubject: hi\r\n\r\nhello") == []


def test_bounce_suppresses_and_complaint_unsubscribes(mail_env, auth_client):
    from app.models import MailMessage, MailSuppression
    from app.services.mail import service
    from app.services.mail.bounces import apply_events, parse_report
    from app.services.mail.templates import render_action

    _register(auth_client, "allowed@example.com", newsletter=True)
    events = parse_report(DSN) + parse_report(DELAYED) + parse_report(ARF)
    counts = _db(auth_client, mail_env, lambda s: apply_events(s, events))
    assert counts == {"permanent": 1, "temporary": 1, "complaints": 1, "new_suppressions": 2}
    assert auth_client.get("/api/v1/auth/me").json()["user"]["newsletter"] is False
    rows = _db(auth_client, mail_env, lambda s: _all(s, MailSuppression))
    assert sorted((r.email, r.reason) for r in rows) == [
        ("allowed@example.com", "complaint"), ("gone@example.com", "bounce")]
    # Письмо на адрес из списка отказов не уходит.
    mail_env["sent"].clear()
    r = render_action("verify", "ru", action_url="https://x/", site_url="https://x/")
    status = auth_client.portal.call(lambda: service.send_now(kind="test", to="allowed@example.com",
                                                              locale="ru", rendered=r))
    assert status == "suppressed" and mail_env["sent"] == []
    assert _db(auth_client, mail_env, lambda s: _all(s, MailMessage))[-1].status == "suppressed"


async def _all(s, model):
    return (await s.scalars(select(model))).all()


# --- сводка «колокольчика» -----------------------------------------------------------

async def _seed_watch(s, user_id, seen=date(2026, 7, 1)):
    import uuid
    from app.models import EmailCredential, Indicator, IndicatorData, UserWatch

    ind = Indicator(code="cpi_yoy", name="Инфляция", name_en="Inflation", unit="%", frequency="monthly",
                    is_active=True, is_listed=True)
    s.add(ind)
    await s.flush()
    s.add_all([IndicatorData(indicator_id=ind.id, date=date(2026, 7, 1), value=8.1),
               IndicatorData(indicator_id=ind.id, date=date(2026, 8, 1), value=8.4)])
    uid = uuid.UUID(user_id)
    s.add(UserWatch(user_id=uid, subject_kind="indicator", subject_key="cpi_yoy", last_seen_date=seen))
    cred = await s.scalar(select(EmailCredential).where(EmailCredential.user_id == uid))
    cred.email_verified = True


def test_watch_digest_once_per_day_and_own_unsubscribe(mail_env, auth_client, monkeypatch):
    from app.config import settings
    from app.services.mail import watch_digest

    uid = _register(auth_client, "allowed@example.com", newsletter=True)
    _db(auth_client, mail_env, lambda s: _seed_watch(s, uid))
    mail_env["sent"].clear()
    monkeypatch.setattr(settings, "mail_allow_all_recipients", False)

    dry = _db(auth_client, mail_env, lambda s: watch_digest.run(s, today=date(2026, 11, 14), send=False))
    assert dry["with_new"] == 1 and mail_env["sent"] == []
    rep = _db(auth_client, mail_env, lambda s: watch_digest.run(s, today=date(2026, 11, 14)))
    assert rep["statuses"] == {"sent": 1}
    msg = mail_env["sent"][0]
    assert msg["Subject"].startswith("Новые данные: Инфляция")
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    html = msg.get_body(("html",)).get_content()
    assert "8,4 %" in html and "utm_medium=watch" in html
    # Тот же день — второго письма нет; на следующий день — тоже нет: значение уже отправлено.
    _db(auth_client, mail_env, lambda s: watch_digest.run(s, today=date(2026, 11, 14)))
    _db(auth_client, mail_env, lambda s: watch_digest.run(s, today=date(2026, 11, 15)))
    assert len(mail_env["sent"]) == 1
    # Отписка от писем «колокольчика» не трогает рассылку.
    tok = _link_token(msg, "/account/unsubscribe")
    r = auth_client.post("/api/v1/mail/unsubscribe", json={"t": tok}).json()
    assert r["list"] == "watch" and r["subscribed"] is False
    assert auth_client.get("/api/v1/auth/me").json()["user"]["newsletter"] is True
    off = _db(auth_client, mail_env, lambda s: watch_digest.run(s, today=date(2026, 11, 16), send=False))
    assert off["skipped_off"] == 1


def test_watch_digest_skips_unverified(mail_env, auth_client):
    from app.models import EmailCredential
    from app.services.mail import watch_digest

    uid = _register(auth_client, "allowed@example.com")

    async def seed(s):
        await _seed_watch(s, uid)
        cred = await s.scalar(select(EmailCredential))
        cred.email_verified = False
    _db(auth_client, mail_env, seed)
    rep = _db(auth_client, mail_env, lambda s: watch_digest.run(s, today=date(2026, 11, 14), send=False))
    assert rep["skipped_unverified"] == 1


# --- админ-BI ------------------------------------------------------------------------

def test_bi_mail_summary_admin_only(mail_env, auth_client):
    _register(auth_client, "user@example.com")
    assert auth_client.get("/api/v1/admin/bi/mail").status_code == 404
    _register(auth_client, ADMIN, newsletter=True)
    data = auth_client.get("/api/v1/admin/bi/mail").json()
    assert data["config"]["allowlist_only"] is True
    assert data["by_kind"]["verify_email"]["blocked"] == 2
    assert data["audience"]["newsletter_subscribers"] == 1
    assert data["audience"]["password_unverified"] == 2
    assert "@" not in str(data)  # ни одного адреса
