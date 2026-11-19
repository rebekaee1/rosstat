"""Подписка на показатель по почте без пароля (совет 19.11.2026): гость → письмо «подтвердите» →
слежение; вошедший — слежение сразу; письмо о новом значении уходит сводкой «колокольчика»."""
from datetime import date

import pytest
from sqlalchemy import select

from tests.conftest import csrf_headers
from tests.test_mail import _link_token, mail_env  # noqa: F401 — фикстура
from tests.test_mail_lifecycle import _db, _register

CODE = "fuel-diesel"
URL = "/api/v1/topic-mail"


@pytest.fixture
def topic_env(mail_env, auth_client, monkeypatch):  # noqa: F811
    from app.config import settings

    monkeypatch.setattr(settings, "topic_mail_enabled", True)

    async def seed(s):
        from app.models import Indicator, IndicatorData

        ind = Indicator(code=CODE, name="Цена дизельного топлива", name_en="Diesel price", unit="руб./л",
                        frequency="weekly", is_active=True, is_listed=True)
        s.add(ind)
        await s.flush()
        s.add_all([IndicatorData(indicator_id=ind.id, date=date(2026, 11, 2), value=86.4),
                   IndicatorData(indicator_id=ind.id, date=date(2026, 11, 9), value=86.63)])
    _db(auth_client, mail_env, seed)
    return mail_env


async def _all(s, model):
    return (await s.scalars(select(model))).all()


def _confirm_token(env):
    return _link_token(env["sent"][-1], "/account/topic-confirm")


def test_flag_off_hides_everything_but_config(mail_env, auth_client):  # noqa: F811
    assert auth_client.get(f"{URL}/config").json() == {"enabled": False}
    r = auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "allowed@example.com", "consent": True})
    assert r.status_code == 404
    assert auth_client.post(f"{URL}/confirm", json={"t": "x"}).status_code == 404


def test_guest_validation(topic_env, auth_client):
    auth_client.cookies.clear()
    r = auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "allowed@example.com", "consent": False})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "consent_required"
    r = auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "not-an-email", "consent": True})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_email"
    r = auth_client.post(f"{URL}/subscribe", json={"code": "no-such-series", "email": "allowed@example.com",
                                                   "consent": True})
    assert r.status_code == 404 and r.json()["detail"]["code"] == "subject_not_found"
    assert topic_env["sent"] == []


def test_guest_confirm_creates_account_watch_and_consents(topic_env, auth_client):
    from app.models import AuthAudit, Consent, EmailCredential, User, UserSignup, UserWatch

    auth_client.cookies.clear()
    r = auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "Allowed@Example.com", "consent": True,
                                                   "page": "/russia/indicator/fuel-diesel/2026"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "status": "confirm_sent", "title": "Цена дизельного топлива"}
    msg = topic_env["sent"][-1]
    assert msg["To"] == "allowed@example.com"
    assert msg["Subject"] == "Подтвердите подписку: Цена дизельного топлива"
    tok = _confirm_token(topic_env)
    # Адреса в ссылке нет.
    assert "allowed" not in tok.lower()

    # Открытие ссылки (GET) ничего не меняет: почтовые сканеры открывают ссылки сами.
    st = auth_client.get(f"{URL}/confirm", params={"t": tok}).json()
    assert st["title"] == "Цена дизельного топлива" and st["email"] == "a…d@example.com"
    assert _db(auth_client, topic_env, lambda s: _all(s, User)) == []

    ok = auth_client.post(f"{URL}/confirm", json={"t": tok}).json()
    assert ok["status"] == "subscribed" and ok["new_account"] is True

    users = _db(auth_client, topic_env, lambda s: _all(s, User))
    assert len(users) == 1
    [cred] = _db(auth_client, topic_env, lambda s: _all(s, EmailCredential))
    assert cred.email == "allowed@example.com" and cred.email_verified is True
    kinds = sorted(c.kind for c in _db(auth_client, topic_env, lambda s: _all(s, Consent)))
    assert kinds == ["pd", "watch_mail"]
    [watch] = _db(auth_client, topic_env, lambda s: _all(s, UserWatch))
    # «Новым» будет только значение, вышедшее после подписки.
    assert (watch.subject_kind, watch.subject_key, watch.last_seen_date) == ("indicator", CODE, date(2026, 11, 9))
    [signup] = _db(auth_client, topic_env, lambda s: _all(s, UserSignup))
    assert signup.trigger == "topic_mail" and signup.newsletter is False
    events = {a.event for a in _db(auth_client, topic_env, lambda s: _all(s, AuthAudit))}
    assert {"register", "topic_mail_on"} <= events

    # Ссылка одноразовая.
    again = auth_client.post(f"{URL}/confirm", json={"t": tok})
    assert again.status_code == 400 and again.json()["detail"]["code"] == "expired"


def test_guest_confirm_attaches_to_existing_account(topic_env, auth_client):
    from app.models import EmailCredential, User, UserWatch

    uid = _register(auth_client, "allowed@example.com")
    auth_client.cookies.clear()
    topic_env["sent"].clear()
    r = auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "allowed@example.com", "consent": True})
    # Тот же ответ, что и для нового адреса: по нему нельзя узнать, что адрес есть на сайте.
    assert r.json()["status"] == "confirm_sent"
    ok = auth_client.post(f"{URL}/confirm", json={"t": _confirm_token(topic_env)}).json()
    assert ok["new_account"] is False
    assert [str(u.id) for u in _db(auth_client, topic_env, lambda s: _all(s, User))] == [uid]
    [cred] = _db(auth_client, topic_env, lambda s: _all(s, EmailCredential))
    assert cred.email_verified is True
    [watch] = _db(auth_client, topic_env, lambda s: _all(s, UserWatch))
    assert str(watch.user_id) == uid


def test_tampered_or_foreign_token_rejected(topic_env, auth_client):
    from app.services.mail import tokens

    auth_client.cookies.clear()
    auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "allowed@example.com", "consent": True})
    tok = _confirm_token(topic_env)
    assert auth_client.post(f"{URL}/confirm", json={"t": tok[:-2] + "aa"}).json()["detail"]["code"] == "invalid_link"
    # Токен подтверждения адреса не подходит как токен подписки.
    verify = tokens.issue("verify", tokens.verify("topic", tok).user_id, tokens.verify("topic", tok).fingerprint)
    assert auth_client.post(f"{URL}/confirm", json={"t": verify}).status_code == 400


def test_email_rate_limit_answers_the_same(topic_env, auth_client):
    auth_client.cookies.clear()
    for _ in range(5):
        r = auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "allowed@example.com", "consent": True})
        assert r.json()["status"] == "confirm_sent"
    assert len(topic_env["sent"]) == 3


def test_signed_in_subscribes_at_once_and_needs_csrf(topic_env, auth_client):
    from app.models import UserWatch

    _register(auth_client, "allowed@example.com")
    topic_env["sent"].clear()
    assert auth_client.post(f"{URL}/subscribe", json={"code": CODE}).status_code == 403
    r = auth_client.post(f"{URL}/subscribe", json={"code": CODE}, headers=csrf_headers(auth_client))
    assert r.status_code == 200
    body = r.json()
    # Адрес не подтверждён — ушло письмо «подтвердите почту», слежение уже есть.
    assert body["status"] == "confirm_email" and body["created"] is True
    assert any("/account/verify-email" in m.get_body(("plain",)).get_content() for m in topic_env["sent"])
    assert len(_db(auth_client, topic_env, lambda s: _all(s, UserWatch))) == 1
    # Повтор не плодит строк.
    again = auth_client.post(f"{URL}/subscribe", json={"code": CODE}, headers=csrf_headers(auth_client)).json()
    assert again["created"] is False
    assert len(_db(auth_client, topic_env, lambda s: _all(s, UserWatch))) == 1


def test_signed_in_resubscribe_turns_watch_mail_back_on(topic_env, auth_client):
    from app.api.auth import AUTH_CONSENT_VERSION
    from app.models import Consent, EmailCredential
    from app.services.mail.watch_digest import watch_mail_on
    import uuid

    uid = uuid.UUID(_register(auth_client, "allowed@example.com"))

    async def revoke(s):
        s.add(Consent(user_id=uid, kind="watch_mail_revoked", version=AUTH_CONSENT_VERSION))
        cred = await s.scalar(select(EmailCredential))
        cred.email_verified = True
    _db(auth_client, topic_env, revoke)
    assert _db(auth_client, topic_env, lambda s: watch_mail_on(s, uid)) is False
    r = auth_client.post(f"{URL}/subscribe", json={"code": CODE}, headers=csrf_headers(auth_client)).json()
    assert r["status"] == "subscribed" and r["email"] == "a…d@example.com"
    assert _db(auth_client, topic_env, lambda s: watch_mail_on(s, uid)) is True


def test_new_value_arrives_by_watch_digest(topic_env, auth_client, monkeypatch):
    from app.models import Indicator, IndicatorData
    from app.services.mail import watch_digest

    auth_client.cookies.clear()
    auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "allowed@example.com", "consent": True})
    auth_client.post(f"{URL}/confirm", json={"t": _confirm_token(topic_env)})
    topic_env["sent"].clear()
    # Старое значение не приходит: человек его уже видел на странице.
    rep = _db(auth_client, topic_env, lambda s: watch_digest.run(s, today=date(2026, 11, 20), send=False))
    assert rep["with_new"] == 0

    async def new_point(s):
        ind = await s.scalar(select(Indicator).where(Indicator.code == CODE))
        s.add(IndicatorData(indicator_id=ind.id, date=date(2026, 11, 16), value=86.9))
    _db(auth_client, topic_env, new_point)
    rep = _db(auth_client, topic_env, lambda s: watch_digest.run(s, today=date(2026, 11, 20)))
    assert rep["statuses"] == {"sent": 1}
    msg = topic_env["sent"][-1]
    assert msg["Subject"] == "Новое значение: Цена дизельного топлива"
    assert "86,9" in msg.get_body(("html",)).get_content()


def test_confirm_mail_follows_design_rules(monkeypatch):
    from app.config import settings
    from app.services.mail.templates import render_action
    from tests.test_mail import SECRET

    monkeypatch.setattr(settings, "mail_token_secret", SECRET)
    for locale in ("ru", "en"):
        mail = render_action("topic", locale, action_url="https://ru.forecasteconomy.com/account/topic-confirm?t=x",
                             site_url="https://ru.forecasteconomy.com/", topic="Diesel")
        assert "Diesel" in mail.subject and len(mail.subject) <= 50
        assert "topic-confirm" in mail.text


def test_double_confirm_gets_clear_answer_not_500(topic_env, auth_client):
    """Второе одновременное нажатие (замок занят) — 409 «уже подтверждается»; после первого — «уже сработала»."""
    from app.models import User
    from app.services.mail import tokens

    auth_client.cookies.clear()
    auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "allowed@example.com", "consent": True})
    tok = _confirm_token(topic_env)
    pid = tokens.verify("topic", tok).user_id
    redis = topic_env["state_redis"]
    auth_client.portal.call(redis.set, f"fe:topic_mail_lock:{pid}", "1")
    busy = auth_client.post(f"{URL}/confirm", json={"t": tok})
    assert busy.status_code == 409 and busy.json()["detail"]["code"] == "in_progress"
    assert _db(auth_client, topic_env, lambda s: _all(s, User)) == []
    # Замок снят (первое нажатие закончилось неудачей) — ссылка снова работает.
    auth_client.portal.call(redis.delete, f"fe:topic_mail_lock:{pid}")
    assert auth_client.post(f"{URL}/confirm", json={"t": tok}).json()["new_account"] is True
    again = auth_client.post(f"{URL}/confirm", json={"t": tok})
    assert again.status_code == 400 and again.json()["detail"]["code"] == "expired"
    assert len(_db(auth_client, topic_env, lambda s: _all(s, User))) == 1


def test_failed_confirm_releases_lock(topic_env, auth_client, monkeypatch):
    from app.services.mail import topic_subscribe as svc

    auth_client.cookies.clear()
    auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "allowed@example.com", "consent": True})
    tok = _confirm_token(topic_env)

    real = svc.add_subject

    async def boom(*a, **k):
        raise svc.TopicMailError("limit_reached", 409)
    monkeypatch.setattr(svc, "add_subject", boom)
    assert auth_client.post(f"{URL}/confirm", json={"t": tok}).json()["detail"]["code"] == "limit_reached"
    monkeypatch.setattr(svc, "add_subject", real)
    assert auth_client.post(f"{URL}/confirm", json={"t": tok}).json()["status"] == "subscribed"


def test_account_created_meanwhile_is_reused(topic_env, auth_client):
    from app.models import User
    from app.services.mail import topic_subscribe as svc

    uid = _register(auth_client, "allowed@example.com")
    item = svc.Pending(id="p1", email="allowed@example.com", code=CODE, locale="ru", ip=None, user_agent=None, page=None)

    async def run(s):
        user, created = await svc.create_account(s, item)
        return str(user.id), created
    assert _db(auth_client, topic_env, run) == (uid, False)
    assert len(_db(auth_client, topic_env, lambda s: _all(s, User))) == 1


def test_redis_down_answers_try_later(topic_env, auth_client, monkeypatch):
    from app.services.mail import topic_subscribe as svc

    auth_client.cookies.clear()
    auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "allowed@example.com", "consent": True})
    tok = _confirm_token(topic_env)

    async def down():
        raise ConnectionError("redis down")
    monkeypatch.setattr(svc, "_redis", down)
    r = auth_client.post(f"{URL}/subscribe", json={"code": CODE, "email": "rebeka.ee@yandex.ru", "consent": True})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "unavailable"
    assert "Попробуйте позже" in r.json()["detail"]["message"] or "try again later" in r.json()["detail"]["message"]
    assert auth_client.get(f"{URL}/confirm", params={"t": tok}).status_code == 503
    assert auth_client.post(f"{URL}/confirm", json={"t": tok}).status_code == 503
