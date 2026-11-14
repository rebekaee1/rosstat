"""Разбор писем-отказов и жалоб из ящика отправителя по IMAP (ADR-0032).

Почтовый сервис возвращает недоставленное письмо отчётом (RFC 3464, ``multipart/report;
report-type=delivery-status``) в ящик отправителя — иногда через минуты, иногда через
сутки. Жалоба «это спам» от почтовых сервисов с обратной связью приходит отчётом ARF
(``report-type=feedback-report``). Задача:

* читает ящик только на чтение (``EXAMINE``, ``BODY.PEEK``): письма не помечаются
  прочитанными, не удаляются и не переносятся — ящик остаётся людям;
* смотрит только письма новее последнего разобранного UID (state-Redis) — первый раз
  за последние 7 суток;
* постоянный отказ (Action: failed, Status 5.x.x) или жалоба → адрес в
  ``mail_suppressions``, строка журнала с тем же Message-ID → статус ``bounced``;
  жалоба ещё и снимает подписку на рассылку (новая запись ``newsletter_revoked``);
* временный отказ (4.x.x) ничего не меняет: сервис сам повторит доставку.

Для Yandex Cloud Postbox отказы приходят не письмом, а событиями в Data Streams — этот
разбор их не видит (см. workflow, раздел «Почта сайта»).
"""
from __future__ import annotations

import asyncio
import email
import imaplib
import logging
import re
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import Message

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)

STATE_KEY = "fe:mail_bounce:state"
_ADDR_RE = re.compile(r"[^\s<>;\"']+@[^\s<>;\"']+")
_STATUS_RE = re.compile(r"^[245]\.\d{1,3}\.\d{1,3}$")


@dataclass(frozen=True)
class BounceEvent:
    email: str
    status: str  # «5.1.1» или «complaint»
    permanent: bool
    complaint: bool
    message_id: str | None


def _addr(value: str | None) -> str | None:
    if not value:
        return None
    # «rfc822; user@example.com» → user@example.com
    m = _ADDR_RE.search(value.split(";", 1)[-1])
    return m.group(0).strip().lower().rstrip(".") if m else None


def _original_message_id(msg: Message) -> str | None:
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype in ("text/rfc822-headers", "message/rfc822", "message/rfc822-headers"):
            payload = part.get_payload()
            if isinstance(payload, list) and payload:
                mid = payload[0].get("Message-ID")
                if mid:
                    return mid.strip()
            raw = part.get_payload(decode=True) or b""
            if isinstance(payload, str) and not raw:
                raw = payload.encode("utf-8", "replace")
            m = re.search(rb"(?im)^message-id:\s*(<[^>\r\n]+>)", raw)
            if m:
                return m.group(1).decode("ascii", "replace")
    return None


def _status_blocks(text: str) -> list[dict[str, str]]:
    """Поля delivery-status: блоки через пустую строку, ключи в нижнем регистре."""
    blocks, cur = [], {}
    for line in text.replace("\r\n", "\n").split("\n"):
        if not line.strip():
            if cur:
                blocks.append(cur)
                cur = {}
            continue
        if ":" in line and not line[0].isspace():
            key, val = line.split(":", 1)
            cur[key.strip().lower()] = val.strip()
    if cur:
        blocks.append(cur)
    return blocks


def parse_report(raw: bytes) -> list[BounceEvent]:
    """События из одного письма: отказы по получателям или жалоба. Иначе пусто."""
    msg = email.message_from_bytes(raw)
    report_type = (msg.get_param("report-type") or "").lower() if msg.get_content_type() == "multipart/report" else ""
    mid = _original_message_id(msg)
    events: list[BounceEvent] = []
    if report_type == "feedback-report":
        for part in msg.walk():
            if part.get_content_type() == "message/feedback-report":
                payload = part.get_payload()
                text = payload[0].as_string() if isinstance(payload, list) and payload else str(payload)
                fields = {k: v for b in _status_blocks(text) for k, v in b.items()}
                addr = _addr(fields.get("original-rcpt-to")) or _addr(fields.get("removal-recipient"))
                if addr:
                    events.append(BounceEvent(addr, "complaint", True, True, mid))
        return events
    if report_type != "delivery-status":
        return events
    for part in msg.walk():
        if part.get_content_type() != "message/delivery-status":
            continue
        payload = part.get_payload()
        if isinstance(payload, list):
            text = "\n\n".join(p.as_string() for p in payload)
        else:
            text = payload if isinstance(payload, str) else (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        for block in _status_blocks(text):
            addr = _addr(block.get("final-recipient") or block.get("original-recipient"))
            status = (block.get("status") or "").split()[0] if block.get("status") else ""
            action = (block.get("action") or "").lower()
            if not addr or not _STATUS_RE.match(status):
                continue
            if action and action not in ("failed", "delayed"):
                continue  # delivered / relayed / expanded — не отказ
            events.append(BounceEvent(addr, status, status.startswith("5") and action != "delayed", False, mid))
    return events


def _fetch_sync(last_uid: int, uidvalidity: str | None) -> tuple[list[tuple[int, bytes]], str]:
    ctx = ssl.create_default_context()
    with imaplib.IMAP4_SSL(settings.mail_imap_host, int(settings.mail_imap_port), ssl_context=ctx) as imap:
        imap.login(settings.mail_smtp_user, settings.mail_smtp_password)
        typ, _ = imap.select("INBOX", readonly=True)
        if typ != "OK":
            raise RuntimeError("imap select failed")
        _typ, vdata = imap.response("UIDVALIDITY")
        validity = (vdata or [b""])[0] or b""
        validity = validity.decode() if isinstance(validity, bytes) else str(validity)
        if uidvalidity and uidvalidity != validity:
            last_uid = 0  # ящик пересоздан: начинаем заново по дате
        if last_uid:
            typ, data = imap.uid("SEARCH", None, f"UID {last_uid + 1}:*")
        else:
            since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%d-%b-%Y")
            typ, data = imap.uid("SEARCH", None, f"SINCE {since}")
        uids = [int(u) for u in (data[0] or b"").split() if int(u) > last_uid] if typ == "OK" else []
        out = []
        for uid in uids[-200:]:  # за раз не больше 200 писем
            typ, parts = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
            if typ == "OK" and parts and isinstance(parts[0], tuple):
                out.append((uid, parts[0][1]))
        return out, validity


async def apply_events(db: AsyncSession, events: list[BounceEvent]) -> dict[str, int]:
    """Записать постоянные отказы и жалобы; вернуть счётчики (без адресов)."""
    from app.api.auth import AUTH_CONSENT_VERSION
    from app.models import Consent, EmailCredential, MailMessage, MailSuppression, OAuthIdentity
    from sqlalchemy import func
    from app.services.mail import audience

    counts = {"permanent": 0, "temporary": 0, "complaints": 0, "new_suppressions": 0}
    for ev in events:
        if ev.complaint:
            counts["complaints"] += 1
        elif ev.permanent:
            counts["permanent"] += 1
        else:
            counts["temporary"] += 1
            continue
        if ev.message_id:
            for row in (await db.scalars(select(MailMessage).where(MailMessage.message_id == ev.message_id))).all():
                row.status, row.error = "bounced", f"bounce:{ev.status}"[:200]
        uid = await db.scalar(select(EmailCredential.user_id).where(EmailCredential.email == ev.email))
        if uid is None:
            uid = await db.scalar(select(OAuthIdentity.user_id).where(func.lower(OAuthIdentity.email) == ev.email))
        exists = await db.scalar(select(MailSuppression.id).where(MailSuppression.email == ev.email))
        if exists is None:
            db.add(MailSuppression(email=ev.email, user_id=uid,
                                   reason="complaint" if ev.complaint else "bounce", status_code=ev.status[:20]))
            counts["new_suppressions"] += 1
        if ev.complaint and uid is not None and await audience.is_subscribed(db, uid):
            db.add(Consent(user_id=uid, kind="newsletter_revoked", version=AUTH_CONSENT_VERSION,
                           ip=None, user_agent="mail-complaint"))
        await db.flush()
    await db.commit()
    return counts


async def bounce_poll_job() -> dict[str, int] | None:
    """Задача планировщика: новые письма ящика → отказы и жалобы."""
    if not (settings.mail_enabled and settings.mail_bounce_poll_enabled):
        return None
    if not (settings.mail_smtp_user and settings.mail_smtp_password):
        logger.warning("mail bounce poll skipped: no mailbox credentials")
        return None
    import json
    from app.core.cache import get_state_redis
    from app.services.mail import service

    redis = await get_state_redis()
    state = json.loads(await redis.get(STATE_KEY) or "{}")
    try:
        messages, validity = await asyncio.to_thread(_fetch_sync, int(state.get("uid") or 0), state.get("validity"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("mail bounce poll failed: %s", type(exc).__name__)
        return None
    events: list[BounceEvent] = []
    for _uid, raw in messages:
        try:
            events.extend(parse_report(raw))
        except Exception:  # noqa: BLE001 — одно кривое письмо не ломает разбор
            logger.warning("mail bounce parse failed", exc_info=True)
    async with service._factory()() as db:
        counts = await apply_events(db, events)
    if messages:
        state = {"uid": max(u for u, _ in messages), "validity": validity}
        await redis.set(STATE_KEY, json.dumps(state))
    logger.info("mail bounce poll: messages=%s %s", len(messages), counts)
    return counts
