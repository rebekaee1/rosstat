"""Web-push: сервис отправки — ТОЛЬКО ЗАГОТОВКА (2026-10-05). Ничего не отправляется.

Жёсткие предохранители (все по умолчанию закрыты):
  1. `push_send_enabled=false` → любая отправка отказывает исключением PushSendDisabled,
     даже в режиме dry-run: функция «как будто отправить» тоже закрыта.
  2. `push_dry_run=true` (по умолчанию) → даже при включённой отправке в сеть ничего не
     уходит: считаем, кому бы ушло. Вызывающий код может ТОЛЬКО усилить сухой прогон
     (`dry_run=True`), но не может обойти настройку (`dry_run=False` при
     `push_dry_run=true` остаётся сухим прогоном).
  3. Реальная отправка требует ключей VAPID из окружения и `vapid_subject`; без них — отказ.
Ни одно задание планировщика этот модуль не вызывает (проверяет тест); единственный
вызов — вручную из будущего административного кода.

Приватность: адрес подписки и ключи — персональные данные. Здесь они не логируются
и не попадают в результат; в логах только счётчики.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PushSubscription

logger = logging.getLogger(__name__)

MAX_PAYLOAD_BYTES = 3000  # лимит шифрованного payload у push-сервисов ~4 КБ
DEFAULT_TTL_SECONDS = 24 * 3600
REVOKE_AFTER_FAILURES = 5


class PushSendDisabled(RuntimeError):
    """Отправка выключена настройками (или не хватает ключей). Это норма по умолчанию."""


@dataclass(frozen=True)
class SendResult:
    status: str          # dry_run | sent | gone | failed
    http_status: int | None = None


@dataclass(frozen=True)
class BatchResult:
    dry_run: bool
    total: int
    sent: int = 0
    gone: int = 0
    failed: int = 0


def sending_enabled() -> bool:
    return bool(settings.push_send_enabled)


def effective_dry_run(requested: bool | None = None) -> bool:
    """Сухой прогон, если он включён в настройках ИЛИ явно запрошен. Настройку не обойти."""
    return bool(settings.push_dry_run) or bool(requested)


def ensure_sendable(*, dry_run: bool) -> None:
    """Отказ, пока отправка выключена; для реальной отправки ещё и ключи VAPID."""
    if not settings.push_send_enabled:
        raise PushSendDisabled("web-push sending is disabled (RUSTATS_PUSH_SEND_ENABLED=false)")
    if dry_run:
        return
    if not settings.vapid_private_key or not settings.vapid_public_key or not settings.vapid_subject:
        raise PushSendDisabled("VAPID keys/subject are not configured")


def build_payload(title: str, body: str = "", url: str = "/", tag: str | None = None) -> str:
    """Безопасный JSON для service worker (sw.js читает title/body/url/tag). Без персональных данных."""
    payload = {
        "title": (title or "Forecast Economy")[:120],
        "body": (body or "")[:300],
        "url": url if (url or "").startswith("/") and not (url or "").startswith("//") else "/",
    }
    if tag:
        payload["tag"] = tag[:64]
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("push payload too large")
    return raw


def _subscription_info(sub: PushSubscription) -> dict:
    return {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}


def _webpush_blocking(sub: PushSubscription, data: str, ttl: int) -> SendResult:
    # Ленивый импорт: модуль и тесты работают без установленного pywebpush.
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=_subscription_info(sub),
            data=data,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            ttl=ttl,
            timeout=10,
        )
        return SendResult("sent", 201)
    except WebPushException as exc:
        code = getattr(getattr(exc, "response", None), "status_code", None)
        # 404/410 — подписка умерла (браузер отписался/очищен): её надо погасить.
        return SendResult("gone" if code in (404, 410) else "failed", code)


async def send_to_subscription(
    sub: PushSubscription, payload: str, *, dry_run: bool | None = None, ttl: int = DEFAULT_TTL_SECONDS,
) -> SendResult:
    """Одно сообщение одной подписке. При выключенной отправке — PushSendDisabled."""
    dry = effective_dry_run(dry_run)
    ensure_sendable(dry_run=dry)
    if dry:
        return SendResult("dry_run")
    return await asyncio.to_thread(_webpush_blocking, sub, payload, ttl)


async def send_to_all(
    db: AsyncSession, payload: str, *, dry_run: bool | None = None, limit: int = 1000,
) -> BatchResult:
    """Рассылка всем активным подписчикам (вызывать только вручную; в планировщике не используется)."""
    dry = effective_dry_run(dry_run)
    ensure_sendable(dry_run=dry)
    subs = (await db.scalars(
        select(PushSubscription).where(PushSubscription.revoked_at.is_(None)).limit(limit)
    )).all()
    if dry:
        logger.info("web-push dry-run: %d subscriptions would receive the message", len(subs))
        return BatchResult(dry_run=True, total=len(subs))
    sent = gone = failed = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for sub in subs:
        result = await send_to_subscription(sub, payload, dry_run=False)
        if result.status == "sent":
            sent += 1
            await db.execute(update(PushSubscription).where(PushSubscription.id == sub.id).values(
                last_success_at=now, failure_count=0))
        elif result.status == "gone":
            gone += 1
            await db.execute(update(PushSubscription).where(PushSubscription.id == sub.id).values(revoked_at=now))
        else:
            failed += 1
            failures = (sub.failure_count or 0) + 1
            values = {"failure_count": failures}
            if failures >= REVOKE_AFTER_FAILURES:
                values["revoked_at"] = now
            await db.execute(update(PushSubscription).where(PushSubscription.id == sub.id).values(**values))
    await db.commit()
    logger.info("web-push batch: sent=%d gone=%d failed=%d", sent, gone, failed)
    return BatchResult(dry_run=False, total=len(subs), sent=sent, gone=gone, failed=failed)
