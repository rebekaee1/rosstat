"""Резолв OAuth-профиля в User (ADR-0007, инвариант против pre-hijack).

Ключ — (provider, sub), НЕ email. Автосвязывание в существующего User только
по равному ВЕРИФИЦИРОВАННОМУ email (OAuth↔OAuth). Неверифицированный парольный
аккаунт никогда не мерджится автоматически. intent=link связывает под активной
сессией; конфликт (sub принадлежит другому User) → IdentityConflict.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, OAuthIdentity, EmailCredential
from app.services.identity.passwords import normalize_email


class IdentityConflict(Exception):
    """sub уже привязан к другому пользователю (при intent=link)."""


class LinkRequiresAuth(Exception):
    """intent=link без активной сессии."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _find_identity(db: AsyncSession, provider: str, sub: str) -> OAuthIdentity | None:
    return await db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == provider, OAuthIdentity.provider_user_id == sub
        )
    )


async def _auto_link_target(db: AsyncSession, email_norm: str) -> User | None:
    """Найти существующего User по равному верифицированному email."""
    sib = await db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.email == email_norm, OAuthIdentity.email_verified.is_(True)
        )
    )
    if sib is not None:
        return await db.get(User, sib.user_id)
    cred = await db.scalar(
        select(EmailCredential).where(
            EmailCredential.email == email_norm, EmailCredential.email_verified.is_(True)
        )
    )
    if cred is not None:
        return await db.get(User, cred.user_id)
    return None


def _new_identity(user: User, profile, email_norm: str | None) -> OAuthIdentity:
    return OAuthIdentity(
        user_id=user.id,
        provider=profile.provider,
        provider_user_id=profile.sub,
        email=email_norm,
        email_verified=profile.email_verified,
        phone=profile.phone,
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        last_login_at=_utcnow(),
    )


async def resolve_oauth(
    db: AsyncSession, profile, intent: str, current_user: User | None
) -> tuple[User, bool]:
    """Вернуть (user, created): created=True только если создан НОВЫЙ аккаунт."""
    email_norm = normalize_email(profile.email) if profile.email else None
    existing = await _find_identity(db, profile.provider, profile.sub)

    if intent == "link":
        if current_user is None:
            raise LinkRequiresAuth()
        if existing is not None:
            if existing.user_id != current_user.id:
                raise IdentityConflict()
            existing.last_login_at = _utcnow()
            return current_user, False
        db.add(_new_identity(current_user, profile, email_norm))
        await db.flush()
        return current_user, False

    # intent == "login"
    if existing is not None:
        existing.last_login_at = _utcnow()
        if email_norm and not existing.email:
            existing.email = email_norm
            existing.email_verified = profile.email_verified
        if profile.phone and not existing.phone:
            existing.phone = profile.phone
        return await db.get(User, existing.user_id), False

    user: User | None = None
    if email_norm and profile.email_verified:
        user = await _auto_link_target(db, email_norm)
    created = user is None
    if user is None:
        user = User(id=uuid.uuid4(), status="active", display_name=profile.display_name)
        db.add(user)
        await db.flush()
    db.add(_new_identity(user, profile, email_norm))
    await db.flush()
    return user, created
