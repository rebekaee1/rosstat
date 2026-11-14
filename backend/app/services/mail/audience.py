"""Кому уходит рассылка (ADR-0032).

Подписчик — активный аккаунт, у которого последняя запись журнала согласий среди
``newsletter`` / ``newsletter_revoked`` — ``newsletter`` (тот же отбор, что в счётчике
подписчиков, `identity/consents.py`). Адрес выбирается так:
  1. адрес входа по паролю, если он подтверждён;
  2. иначе адрес, подтверждённый провайдером входа (Яндекс, Google; у VK адреса обычно нет);
  3. иначе неподтверждённый адрес входа по паролю (``verified=False``).
Язык письма: язык сайта при регистрации → страна регистрации → язык профиля
провайдера → домен почты → русский.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Consent, EmailCredential, OAuthIdentity, User, UserSignup
from app.services.identity.consents import NEWSLETTER_KINDS

RU_COUNTRIES = frozenset({"RU", "BY", "KZ", "KG", "AM", "UZ", "TJ", "AZ", "MD", "UA", "GE", "TM"})
RU_MAIL_DOMAINS = ("yandex.", "ya.ru", "mail.ru", "list.ru", "bk.ru", "inbox.ru", "rambler.ru", "internet.ru")


@dataclass
class Recipient:
    user_id: uuid.UUID
    email: str
    verified: bool
    locale: str


def _locale(site_locale: str | None, country_code: str | None, oauth_locales: list[str], email: str) -> str:
    if site_locale in ("ru", "en"):
        return site_locale
    if country_code:
        return "ru" if country_code.upper() in RU_COUNTRIES else "en"
    for loc in oauth_locales:
        if loc:
            return "ru" if loc.lower().startswith("ru") else "en"
    domain = email.rsplit("@", 1)[-1].lower()
    if domain.endswith(".ru") or any(domain.startswith(d) for d in RU_MAIL_DOMAINS):
        return "ru"
    return "ru"


async def subscriber_ids(db: AsyncSession) -> list[uuid.UUID]:
    latest = select(
        Consent.user_id, Consent.kind,
        func.row_number().over(
            partition_by=Consent.user_id, order_by=(Consent.granted_at.desc(), Consent.id.desc()),
        ).label("position"),
    ).where(Consent.kind.in_(NEWSLETTER_KINDS)).subquery()
    rows = await db.execute(
        select(latest.c.user_id).join(User, User.id == latest.c.user_id)
        .where(latest.c.position == 1, latest.c.kind == "newsletter", User.status == "active")
    )
    return [r[0] for r in rows.all()]


async def resolve(db: AsyncSession, user_id: uuid.UUID) -> Recipient | None:
    cred = await db.scalar(select(EmailCredential).where(EmailCredential.user_id == user_id))
    idents = (await db.scalars(select(OAuthIdentity).where(OAuthIdentity.user_id == user_id))).all()
    signup = await db.get(UserSignup, user_id)
    email, verified = None, False
    if cred is not None and cred.email_verified:
        email, verified = cred.email, True
    if email is None:
        ident = next((i for i in idents if i.email and i.email_verified), None)
        if ident is not None:
            email, verified = ident.email.strip().lower(), True
    if email is None and cred is not None:
        email, verified = cred.email, False
    if not email:
        return None
    locale = _locale(
        signup.site_locale if signup else None,
        signup.country_code if signup else None,
        [i.locale or "" for i in idents],
        email,
    )
    return Recipient(user_id=user_id, email=email, verified=verified, locale=locale)


async def subscribers(db: AsyncSession) -> tuple[list[Recipient], int]:
    """Подписчики с адресом и число подписчиков без адреса (вход через VK без почты)."""
    out: list[Recipient] = []
    missing = 0
    for uid in await subscriber_ids(db):
        rec = await resolve(db, uid)
        if rec is None:
            missing += 1
        else:
            out.append(rec)
    return out, missing


async def is_subscribed(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Последняя запись журнала согласий человека — подписка (а не отзыв)."""
    last = await db.scalar(
        select(Consent.kind)
        .where(Consent.user_id == user_id, Consent.kind.in_(NEWSLETTER_KINDS))
        .order_by(Consent.granted_at.desc(), Consent.id.desc())
        .limit(1)
    )
    return last == "newsletter"


async def unverified_password_accounts(db: AsyncSession) -> list[Recipient]:
    """Активные аккаунты со входом по паролю и неподтверждённым адресом (письмо «подтвердите почту»).

    Подписка на рассылку не важна: это служебное письмо по аккаунту. Язык — как у рассылки.
    """
    rows = (await db.execute(
        select(EmailCredential.user_id, EmailCredential.email)
        .join(User, User.id == EmailCredential.user_id)
        .where(EmailCredential.email_verified.is_(False), User.status == "active")
        .order_by(EmailCredential.id)
    )).all()
    out: list[Recipient] = []
    for uid, email in rows:
        idents = (await db.scalars(select(OAuthIdentity).where(OAuthIdentity.user_id == uid))).all()
        signup = await db.get(UserSignup, uid)
        locale = _locale(signup.site_locale if signup else None, signup.country_code if signup else None,
                         [i.locale or "" for i in idents], email)
        out.append(Recipient(user_id=uid, email=email, verified=False, locale=locale))
    return out
