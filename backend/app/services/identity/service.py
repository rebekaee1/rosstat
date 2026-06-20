"""Identity-сервис: регистрация/вход по email, выборка пользователя.

OAuth-резолв — в oauth/resolve.py (Срез B+). Здесь — email+пароль и сериализация.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, EmailCredential, OAuthIdentity, Consent
from app.services.identity.passwords import (
    hash_password, verify_password, needs_rehash, normalize_email,
)


class EmailAlreadyExists(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def register_email(db: AsyncSession, email: str, password: str) -> User:
    norm = normalize_email(email)
    existing = await db.scalar(
        select(EmailCredential).where(EmailCredential.email == norm)
    )
    if existing is not None:
        raise EmailAlreadyExists()
    user = User(id=uuid.uuid4(), status="active")
    db.add(user)
    await db.flush()
    cred = EmailCredential(
        user_id=user.id,
        email=norm,
        password_hash=hash_password(password),
        email_verified=False,
    )
    db.add(cred)
    await db.flush()
    return user


async def authenticate_email(db: AsyncSession, email: str, password: str) -> User | None:
    norm = normalize_email(email)
    cred = await db.scalar(
        select(EmailCredential).where(EmailCredential.email == norm)
    )
    if cred is None:
        return None
    if not verify_password(cred.password_hash, password):
        return None
    if needs_rehash(cred.password_hash):
        cred.password_hash = hash_password(password)
        await db.flush()
    return await db.get(User, cred.user_id)


async def get_user(db: AsyncSession, user_id) -> User | None:
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            return None
    return await db.get(User, user_id)


async def serialize_user(db: AsyncSession, user: User) -> dict:
    """Публичное представление пользователя для /me и /account/export."""
    identities = (
        await db.scalars(
            select(OAuthIdentity).where(OAuthIdentity.user_id == user.id)
        )
    ).all()
    cred = await db.scalar(
        select(EmailCredential).where(EmailCredential.user_id == user.id)
    )
    methods = [
        {"id": i.id, "provider": i.provider, "email": i.email, "display_name": i.display_name}
        for i in identities
    ]
    # Primary email для UI: пароль-email, иначе первый email из OAuth-привязок.
    primary_email = cred.email if cred else next((i.email for i in identities if i.email), None)
    # Телефон берём из OAuth-привязок (пароль-вход телефон не собирает).
    primary_phone = next((i.phone for i in identities if i.phone), None)
    # Подписка на рассылку — append-only журнал согласий: побеждает последняя
    # запись среди newsletter / newsletter_revoked (пользователь может отписаться
    # и снова подписаться в кабинете, история сохраняется для 152-ФЗ).
    nl = (
        await db.scalars(
            select(Consent)
            .where(Consent.user_id == user.id, Consent.kind.in_(("newsletter", "newsletter_revoked")))
            .order_by(Consent.granted_at.desc(), Consent.id.desc())
        )
    ).first()
    return {
        "id": str(user.id),
        "status": user.status,
        "display_name": user.display_name,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "email": primary_email,
        "phone": primary_phone,
        "has_password": cred is not None,
        "newsletter": nl is not None and nl.kind == "newsletter",
        "identities": methods,
    }
