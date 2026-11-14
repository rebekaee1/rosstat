"""Отправка писем с журналом и защитами (ADR-0032).

Порядок для каждого письма:
  1. строка в ``mail_outbox`` (кому, что, тема) — до сети, чтобы попытка не потерялась;
  2. почта выключена → статус ``disabled``; адрес не из списка допуска → ``blocked``;
  3. иначе SMTP; итог ``sent`` с Message-ID или ``failed`` с кодом ошибки.

Служебные письма из запросов (регистрация, сброс пароля) уходят фоновой задачей
после ответа, чтобы медленный почтовый сервер не задерживал страницу. Фоновая
задача открывает свою сессию базы (``session_factory``; тесты подменяют её).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MailMessage
from app.services.mail import transport
from app.services.mail.templates import RenderedMail

logger = logging.getLogger(__name__)

# Тесты подменяют фабрику сессий (герметичный SQLite); на сервере — основная база.
session_factory = None


def _factory():
    if session_factory is not None:
        return session_factory
    from app.database import async_session
    return async_session


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize(addr: str | None) -> str:
    return (addr or "").strip().lower()


def allowlist() -> set[str]:
    return {normalize(a) for a in (settings.mail_allowlist or "").split(",") if a.strip()}


def recipient_allowed(addr: str) -> bool:
    """Пока владелец не снял ограничение, письма уходят только на адреса из списка."""
    if settings.mail_allow_all_recipients:
        return True
    return normalize(addr) in allowlist()


def site_origin(locale: str) -> str:
    """Адрес сайта на языке письма: русский хост для ru, основной для en."""
    if locale == "en":
        return (settings.mail_link_origin_en or settings.public_origin).rstrip("/")
    if settings.mail_link_origin_ru:
        return settings.mail_link_origin_ru.rstrip("/")
    from app.services.locale import ru_public_origin
    return ru_public_origin().rstrip("/")


def site_link(locale: str, path: str, **query: str) -> str:
    url = f"{site_origin(locale)}{path}"
    if query:
        url += "?" + urlencode(query)
    return url


def api_link(locale: str, path: str, **query: str) -> str:
    """Ссылка на API того же хоста (для заголовка List-Unsubscribe: POST без браузера)."""
    return site_link(locale, f"/api/v1{path}", **query)


async def record(db: AsyncSession, *, kind: str, to: str, locale: str, subject: str,
                 user_id: uuid.UUID | None = None, campaign: str | None = None) -> MailMessage:
    row = MailMessage(kind=kind, campaign=campaign, user_id=user_id, to_email=normalize(to),
                      locale=locale, subject=subject[:300], status="queued", attempts=0)
    db.add(row)
    await db.flush()
    return row


async def attempt(db: AsyncSession, row: MailMessage, rendered: RenderedMail, *,
                  unsubscribe_url: str | None = None) -> MailMessage:
    """Одна попытка доставки строки журнала; статус пишется в ту же строку (без commit)."""
    if not settings.mail_enabled:
        row.status, row.error = "disabled", None
        return row
    if not recipient_allowed(row.to_email):
        row.status, row.error = "blocked", "not_in_allowlist"
        return row
    if await is_suppressed(db, row.to_email):
        # Адрес уже возвращал постоянный отказ или жалобу: новые письма вредят репутации домена.
        row.status, row.error = "suppressed", "suppressed"
        return row
    row.attempts = (row.attempts or 0) + 1
    try:
        row.message_id = await transport.send(transport.OutgoingMail(
            to=row.to_email, subject=rendered.subject, html=rendered.html, text=rendered.text,
            kind=row.kind, unsubscribe_url=unsubscribe_url, campaign=row.campaign,
        ))
        row.status, row.error, row.sent_at = "sent", None, _now()
    except transport.MailConfigError:
        row.status, row.error = "failed", "not_configured"
    except transport.SendError as err:
        row.status, row.error = "failed", err.code
        if err.limit:
            raise
    return row


async def send_now(*, kind: str, to: str, locale: str, rendered: RenderedMail,
                   user_id: uuid.UUID | None = None, unsubscribe_url: str | None = None) -> str:
    """Записать и отправить одно письмо в собственной сессии. Возвращает итоговый статус.

    Используется фоновыми задачами запросов и скриптом проверки. Ошибки не бросает:
    служебное письмо не должно ронять регистрацию или сброс пароля.
    """
    try:
        async with _factory()() as db:
            row = await record(db, kind=kind, to=to, locale=locale, subject=rendered.subject, user_id=user_id)
            try:
                await attempt(db, row, rendered, unsubscribe_url=unsubscribe_url)
            except transport.SendError:
                pass  # статус и код уже в строке
            await db.commit()
            return row.status
    except Exception:  # noqa: BLE001
        logger.warning("mail send_now failed kind=%s", kind, exc_info=True)
        return "error"


async def recent_count(db: AsyncSession, *, user_id: uuid.UUID, kind: str, since: datetime) -> int:
    rows = await db.scalars(select(MailMessage.id).where(
        MailMessage.user_id == user_id, MailMessage.kind == kind, MailMessage.created_at >= since,
    ))
    return len(rows.all())


async def rate_ok(scope: str, key: str, *, limit: int, window_seconds: int) -> bool:
    """Счётчик в Redis: не больше ``limit`` запросов за окно. При сбое Redis — пропускаем
    (как lockout входа): лучше лишнее письмо, чем запертый сброс пароля."""
    from app.core.cache import get_state_redis
    import hashlib

    k = f"fe:mail_rate:{scope}:{hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]}"
    try:
        r = await get_state_redis()
        n = await r.incr(k)
        if n == 1:
            await r.expire(k, window_seconds)
        return int(n) <= limit
    except Exception:  # noqa: BLE001
        logger.error("mail rate limiter unavailable (%s)", scope, exc_info=True)
        return True


async def is_suppressed(db: AsyncSession, addr: str) -> bool:
    """Адрес в mail_suppressions (постоянный отказ, жалоба, ручная пометка)."""
    from app.models import MailSuppression

    found = await db.scalar(select(MailSuppression.id).where(MailSuppression.email == normalize(addr)))
    return found is not None
