"""Подписка/отписка на web-push — ПОДГОТОВКА (2026-10-05): ничего не отправляется.

Оба эндпоинта отвечают 404, пока `push_subscribe_enabled=false` (по умолчанию).
Подписку присылает клиент (lib/pushSubscription.js) ТОЛЬКО после явного действия
пользователя и системного запроса разрешения в браузере. Адрес подписки и ключи —
персональные данные: не логируются, не возвращаются в ответах, не попадают в
аналитику; отписка удаляет строку целиком, удаление аккаунта — каскадом.
Открыто и гостям (как /api-interest): защита — лимит на IP в state-Redis, строгая
валидация формы адреса и ключей, общий RateLimitMiddleware.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import get_state_redis
from app.database import get_db
from app.models import PushSubscription
from app.security.auth import current_session
from app.services.api_i18n import api_detail
from app.services.locale import get_locale

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/push", tags=["push"])

_B64URL = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")
_IP_LIMIT = 10
_IP_WINDOW_SECONDS = 3600
_PREFIX = "fe:push:ip:"


def _valid_endpoint(value: str) -> str:
    value = (value or "").strip()
    if len(value) > 2048:
        raise ValueError("endpoint too long")
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    # Адреса push-сервисов — только https с доменным именем (не IP, не localhost, не userinfo).
    if parts.scheme != "https" or "." not in host or parts.username or parts.password:
        raise ValueError("invalid endpoint")
    if re.fullmatch(r"[\d.]+", host) or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("invalid endpoint")
    return value


class PushKeys(BaseModel):
    p256dh: str
    auth: str

    @field_validator("p256dh")
    @classmethod
    def _p256dh(cls, v: str) -> str:
        v = (v or "").strip()
        if not _B64URL.match(v) or not 80 <= len(v) <= 100:
            raise ValueError("invalid p256dh")
        return v

    @field_validator("auth")
    @classmethod
    def _auth(cls, v: str) -> str:
        v = (v or "").strip()
        if not _B64URL.match(v) or not 16 <= len(v) <= 32:
            raise ValueError("invalid auth")
        return v


class SubscribeIn(BaseModel):
    endpoint: str
    keys: PushKeys
    expirationTime: float | None = Field(default=None)  # поле PushSubscription.toJSON(); не используем

    @field_validator("endpoint")
    @classmethod
    def _endpoint(cls, v: str) -> str:
        return _valid_endpoint(v)


class UnsubscribeIn(BaseModel):
    endpoint: str

    @field_validator("endpoint")
    @classmethod
    def _endpoint(cls, v: str) -> str:
        return _valid_endpoint(v)


def _hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def _require_enabled() -> None:
    if not settings.push_subscribe_enabled:
        raise HTTPException(status_code=404, detail="Not found")


async def _rate_limit(request: Request) -> None:
    from app.main import pick_client_ip  # лениво: app.main импортирует роутеры

    ip = pick_client_ip(
        request.headers.get("x-forwarded-for", ""),
        request.client.host if request.client else "unknown",
    )
    try:
        redis = await get_state_redis()
        key = f"{_PREFIX}{ip}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, _IP_WINDOW_SECONDS)
        if count > _IP_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=api_detail("Слишком много запросов. Попробуйте позже", "Too many requests. Try again later"),
                headers={"Retry-After": str(_IP_WINDOW_SECONDS)},
            )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 — fail-open как у lockout; содержимое запроса не логируем
        logger.warning("push: state-Redis unavailable, rate limit skipped")


@router.post("/subscribe")
async def subscribe(body: SubscribeIn, request: Request, db: AsyncSession = Depends(get_db)):
    _require_enabled()
    await _rate_limit(request)
    sess = await current_session(request)
    user_id = None
    if sess and sess.get("user_id"):
        try:
            user_id = uuid.UUID(str(sess["user_id"]))
        except ValueError:
            user_id = None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    digest = _hash(body.endpoint)
    existing = await db.scalar(select(PushSubscription).where(PushSubscription.endpoint_hash == digest))
    user_agent = (request.headers.get("user-agent") or "")[:300] or None
    if existing is None:
        db.add(PushSubscription(
            endpoint_hash=digest, endpoint=body.endpoint, p256dh=body.keys.p256dh, auth=body.keys.auth,
            user_id=user_id, locale=get_locale(), user_agent=user_agent, created_at=now, updated_at=now,
        ))
    else:
        existing.p256dh = body.keys.p256dh
        existing.auth = body.keys.auth
        existing.locale = get_locale()
        existing.user_agent = user_agent
        existing.updated_at = now
        existing.revoked_at = None
        existing.failure_count = 0
        if user_id:
            existing.user_id = user_id
    await db.commit()
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(body: UnsubscribeIn, request: Request, db: AsyncSession = Depends(get_db)):
    _require_enabled()
    await _rate_limit(request)
    # Идемпотентно: удаляем строку целиком (персональные данные), нашлась ли она — не раскрываем.
    await db.execute(delete(PushSubscription).where(PushSubscription.endpoint_hash == _hash(body.endpoint)))
    await db.commit()
    return {"ok": True}
