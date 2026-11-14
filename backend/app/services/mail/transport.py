"""Сборка письма (MIME) и отправка по SMTP (ADR-0032).

Отправитель в конверте и в From — тот же ящик, под которым идёт вход на SMTP:
Яндекс 360 отклоняет письмо, если From не принадлежит вошедшему ящику. Подпись DKIM
ставит сам почтовый сервис домена (селектор ``mail`` в DNS), SPF разрешает его серверы.

Пароль SMTP никуда не пишется: в журнал попадает только код ответа сервера.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
import uuid
from dataclasses import dataclass
from email import policy as email_policy
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)


class MailConfigError(RuntimeError):
    """Почта включена, но не настроена (нет ящика или пароля)."""


class SendError(Exception):
    """Письмо не принято сервером. permanent=True — повтор не поможет (адрес, политика)."""

    def __init__(self, code: str, *, permanent: bool, limit: bool = False):
        super().__init__(code)
        self.code = code[:200]
        self.permanent = permanent
        # Сервер сообщил о суточном лимите или подозрении на спам: рассылку надо остановить.
        self.limit = limit


@dataclass
class OutgoingMail:
    to: str
    subject: str
    html: str
    text: str
    kind: str  # verify_email / password_reset / newsletter / test
    unsubscribe_url: str | None = None  # для рассылки: List-Unsubscribe + One-Click
    campaign: str | None = None


def from_address() -> str:
    return (settings.mail_from_address or settings.mail_smtp_user or "").strip()


def sender_domain() -> str:
    addr = from_address()
    return addr.rsplit("@", 1)[-1] if "@" in addr else "forecasteconomy.com"


# Строки заголовков до 998 знаков (RFC 5322): иначе длинный List-Unsubscribe складывается
# в закодированные слова (=?utf-8?q?…?=), и почтовые сервисы не видят в нём ссылку.
_POLICY = email_policy.default.clone(max_line_length=998)


def build_message(mail: OutgoingMail) -> EmailMessage:
    msg = EmailMessage(policy=_POLICY)
    msg["From"] = formataddr((settings.mail_from_name, from_address()))
    msg["To"] = mail.to
    msg["Subject"] = mail.subject
    msg["Date"] = format_datetime(datetime.now(timezone.utc))
    msg["Message-ID"] = make_msgid(idstring=uuid.uuid4().hex[:12], domain=sender_domain())
    if settings.mail_reply_to:
        msg["Reply-To"] = settings.mail_reply_to
    # Обратная связь почтовых сервисов (Яндекс, Gmail) группирует жалобы по этому ключу.
    msg["Feedback-ID"] = f"{(mail.campaign or mail.kind)[:40]}:{mail.kind}:fe"
    if mail.kind == "newsletter":
        domain = sender_domain()
        msg["List-Id"] = f"Forecast Economy <news.{domain}>"
        if mail.unsubscribe_url:
            # RFC 2369 + RFC 8058: кнопка «Отписаться» в интерфейсе почты, одно нажатие.
            msg["List-Unsubscribe"] = (
                f"<{mail.unsubscribe_url}>, <mailto:{settings.mail_reply_to or from_address()}?subject=unsubscribe>"
            )
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        msg["Precedence"] = "bulk"
    else:
        # Служебное письмо: автоответчики («я в отпуске») на него не отвечают.
        msg["Auto-Submitted"] = "auto-generated"
        msg["X-Auto-Response-Suppress"] = "OOF, AutoReply"
    msg.set_content(mail.text, subtype="plain", charset="utf-8", cte="quoted-printable")
    msg.add_alternative(mail.html, subtype="html", charset="utf-8", cte="quoted-printable")
    return msg


def _classify(exc: Exception) -> SendError:
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = [c for c, _m in exc.recipients.values()]
        code = codes[0] if codes else 550
        return SendError(f"recipient_refused:{code}", permanent=code >= 500)
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return SendError(f"auth_failed:{exc.smtp_code}", permanent=True, limit=True)
    if isinstance(exc, smtplib.SMTPResponseException):
        code = int(exc.smtp_code or 0)
        raw = exc.smtp_error.decode("utf-8", "replace") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
        low = raw.lower()
        limit = any(w in low for w in ("limit", "spam", "too many", "rate"))
        # В код ошибки — только номер и короткий признак, без адресов из ответа сервера.
        tag = "limit" if limit else "rejected"
        return SendError(f"smtp_{code}:{tag}", permanent=code >= 500, limit=limit)
    if isinstance(exc, (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, OSError, TimeoutError)):
        return SendError(f"network:{type(exc).__name__}", permanent=False)
    return SendError(f"error:{type(exc).__name__}", permanent=False)


def _send_sync(msg: EmailMessage) -> None:
    host, port = settings.mail_smtp_host, int(settings.mail_smtp_port)
    timeout = float(settings.mail_smtp_timeout_seconds)
    ctx = ssl.create_default_context()
    if (settings.mail_smtp_security or "ssl").lower() == "starttls":
        client: smtplib.SMTP = smtplib.SMTP(host, port, timeout=timeout)
        try:
            client.ehlo()
            client.starttls(context=ctx)
            client.ehlo()
            client.login(settings.mail_smtp_user, settings.mail_smtp_password)
            client.send_message(msg, from_addr=from_address(), to_addrs=[msg["To"]])
        finally:
            try:
                client.quit()
            except Exception:  # noqa: BLE001
                pass
        return
    with smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx) as client:
        client.login(settings.mail_smtp_user, settings.mail_smtp_password)
        client.send_message(msg, from_addr=from_address(), to_addrs=[msg["To"]])


def ensure_configured() -> None:
    if not settings.mail_smtp_user or not settings.mail_smtp_password or not from_address():
        raise MailConfigError("mail is enabled but SMTP user/password are not set")


async def send(mail: OutgoingMail) -> str:
    """Отправить одно письмо. Возвращает Message-ID; при отказе — SendError."""
    ensure_configured()
    msg = build_message(mail)
    try:
        await asyncio.to_thread(_send_sync, msg)
    except Exception as exc:  # noqa: BLE001 — классифицируем любой отказ
        err = _classify(exc)
        logger.warning("mail send failed kind=%s code=%s", mail.kind, err.code)
        raise err from None
    return str(msg["Message-ID"])
