"""Подписка на показатель по почте без пароля (совет 19.11.2026, ADR-0032 «подписка на тему»).

Человек под числом на странице показателя или после скачивания файла нажимает «Присылать на почту».

* **Вошедший** — слежение за рядом (`user_watches`) создаётся сразу. Письма уходят сводкой
  «колокольчика» (`watch_digest.py`) только на подтверждённый адрес; если адрес не подтверждён,
  уходит обычное письмо «подтвердите почту».
* **Гость** — вводит адрес и даёт согласие на обработку адреса. Заявка лежит в Redis 7 суток
  (адрес, ряд, язык, IP и браузер для журнала согласий), в письмо уходит подписанная ссылка
  с номером заявки — адреса в ссылке нет. Ответ на сайте всегда одинаковый: по нему нельзя узнать,
  есть ли адрес на сайте.
* **Подтверждение** — только нажатием кнопки на странице `/account/topic-confirm` (POST): почтовые
  сканеры открывают ссылки сами, GET ничего не меняет. Адрес уже есть на сайте — слежение
  добавляется этому аккаунту, адрес считается подтверждённым (человек открыл письмо). Адреса нет —
  создаётся аккаунт без пароля (вход — через «Забыли пароль?»), согласие `pd` пишется с IP и
  браузером из заявки, регистрация помечается поводом `topic_mail`.

Выбор человека («присылать этот ряд») хранится строкой `user_watches`, отдельно от вычисляемого
профиля личной рассылки (`newsletter_profiles`): профиль пересчитывается, выбор — нет.
"""
from __future__ import annotations

import json
import logging
import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Consent, EmailCredential, OAuthIdentity, User, UserSignup, UserWatch
from app.services.mail import service, tokens

logger = logging.getLogger(__name__)

PENDING_TTL_SECONDS = 7 * 24 * 3600
_KEY = "fe:topic_mail:{}"
SIGNUP_TRIGGER = "topic_mail"
SUBJECT_KIND = "indicator"  # федеральные показатели: темы строки «присылать» и бота


class TopicMailError(Exception):
    def __init__(self, code: str, status: int = 422):
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass
class Pending:
    id: str
    email: str
    code: str
    locale: str
    ip: str | None
    user_agent: str | None
    page: str | None


async def series_title(db: AsyncSession, code: str, locale: str) -> str:
    """Название ряда на языке письма; ряда нет или он не публичный — ``subject_not_found``."""
    from app.services.cabinet import CabinetError, clean_key, resolve_series
    from app.services.locale import reset_locale, set_locale

    try:
        key = clean_key(code)
    except CabinetError:
        raise TopicMailError("subject_not_found", 404)
    token = set_locale("en" if locale == "en" else "ru")
    try:
        info = (await resolve_series(db, [(SUBJECT_KIND, key)])).get((SUBJECT_KIND, key))
    finally:
        reset_locale(token)
    if info is None:
        raise TopicMailError("subject_not_found", 404)
    return info.title


async def _redis():
    from app.core.cache import get_state_redis

    return await get_state_redis()


async def save_pending(*, email: str, code: str, locale: str, ip: str | None, user_agent: str | None,
                       page: str | None) -> Pending:
    pid = secrets.token_urlsafe(18)
    item = Pending(id=pid, email=service.normalize(email), code=code, locale="en" if locale == "en" else "ru",
                   ip=(ip or "")[:64] or None, user_agent=(user_agent or "")[:500] or None,
                   page=(page or "")[:200] or None)
    r = await _redis()
    await r.set(_KEY.format(pid), json.dumps(item.__dict__, ensure_ascii=False), ex=PENDING_TTL_SECONDS)
    return item


async def load_pending(pid: str) -> Pending | None:
    r = await _redis()
    raw = await r.get(_KEY.format(pid))
    if not raw:
        return None
    try:
        return Pending(**json.loads(raw))
    except (TypeError, ValueError):
        return None


async def drop_pending(pid: str) -> None:
    r = await _redis()
    await r.delete(_KEY.format(pid))


def confirm_link(item: Pending) -> str:
    tok = tokens.issue("topic", item.id, tokens.fingerprint(item.email))
    return service.site_link(item.locale, "/account/topic-confirm", t=tok)


def confirm_mail(item: Pending, title: str):
    from app.services.mail.templates import render_action

    return render_action(
        "topic", item.locale, action_url=confirm_link(item), site_url=service.site_origin(item.locale) + "/",
        topic=title,
    )


async def pending_from_token(token: str) -> Pending:
    """Заявка по ссылке из письма: подпись, срок, заявка ещё в Redis, адрес совпадает с отпечатком."""
    try:
        tok = tokens.verify("topic", token or "")
    except tokens.TokenError as exc:
        raise TopicMailError("expired" if str(exc) == "expired" else "invalid_link", 400)
    except tokens.TokenSecretMissing:
        raise TopicMailError("invalid_link", 400)
    item = await load_pending(tok.user_id)
    if item is None:
        # Срок заявки истёк или ссылка уже сработала.
        raise TopicMailError("expired", 400)
    if tokens.fingerprint(item.email) != tok.fingerprint:
        raise TopicMailError("invalid_link", 400)
    return item


async def user_by_email(db: AsyncSession, email: str) -> tuple[User | None, EmailCredential | None]:
    email = service.normalize(email)
    cred = await db.scalar(select(EmailCredential).where(EmailCredential.email == email))
    if cred is not None:
        return await db.get(User, cred.user_id), cred
    ident = await db.scalar(select(OAuthIdentity).where(
        func.lower(OAuthIdentity.email) == email, OAuthIdentity.email_verified.is_(True)))
    if ident is not None:
        return await db.get(User, ident.user_id), None
    return None, None


async def ensure_watch_mail_on(db: AsyncSession, user_id: uuid.UUID, *, ip: str | None, user_agent: str | None) -> bool:
    """Письма «колокольчика» включены; если человек раньше от них отписался — новая запись
    журнала согласий (он снова сам попросил присылать). Возвращает True, если запись добавлена."""
    from app.api.auth import AUTH_CONSENT_VERSION
    from app.services.mail.watch_digest import WATCH_KINDS

    last = await db.scalar(
        select(Consent.kind).where(Consent.user_id == user_id, Consent.kind.in_(WATCH_KINDS))
        .order_by(Consent.granted_at.desc(), Consent.id.desc()).limit(1))
    if last == "watch_mail":
        return False
    db.add(Consent(user_id=user_id, kind="watch_mail", version=AUTH_CONSENT_VERSION, ip=ip,
                   user_agent=(user_agent or "")[:500] or None))
    return True


async def add_subject(db: AsyncSession, user_id: uuid.UUID, code: str) -> tuple[UserWatch, bool]:
    from app.services.cabinet import CabinetError, add_watch

    try:
        row, _info, created = await add_watch(db, user_id, SUBJECT_KIND, code)
    except CabinetError as err:
        raise TopicMailError(err.code, err.status)
    return row, created


async def create_account(db: AsyncSession, item: Pending) -> User:
    """Аккаунт без пароля: случайный пароль никому не известен, вход — через «Забыли пароль?»."""
    from app.api.auth import AUTH_CONSENT_VERSION
    from app.services.identity.passwords import hash_password

    user = User(id=uuid.uuid4(), status="active")
    db.add(user)
    await db.flush()
    db.add(EmailCredential(user_id=user.id, email=item.email, password_hash=hash_password(secrets.token_urlsafe(32)),
                           email_verified=True))
    db.add(Consent(user_id=user.id, kind="pd", version=AUTH_CONSENT_VERSION, ip=item.ip, user_agent=item.user_agent))
    await db.flush()
    return user


async def mark_signup(db: AsyncSession, item: Pending, user: User) -> None:
    from app.services.signup_attribution import record_signup

    await record_signup(db, user_id=user.id, method="email", site_locale=item.locale, newsletter=False, ip=item.ip)
    row = await db.get(UserSignup, user.id)
    if row is not None and not row.trigger:
        row.trigger = SIGNUP_TRIGGER
        if item.page and not row.landing_page:
            row.landing_page = item.page
