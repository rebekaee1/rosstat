"""Выпуск рассылки (ADR-0032): файл выпуска → письма подписчикам.

Файл выпуска — JSON::

    {"key": "2026-11-digest",
     "ru": {"subject": "...", "title": "...", "intro": "...", "preheader": "...",
            "items": [{"title": "...", "text": "...", "url": "https://...", "value": "7,7 %"}],
            "cta_label": "...", "cta_url": "https://...", "outro": "..."},
     "en": {...}}

Защиты:
  * отправка людям запускается только при ``mail_allow_all_recipients=true`` и явном
    ``send=True`` (скрипт: ``--send``); без этого — сухой прогон со счётом получателей;
  * один выпуск одному человеку уходит один раз (уникальность campaign+user в журнале),
    повторный запуск продолжает с места остановки;
  * не больше ``mail_campaign_max_per_run`` писем за запуск, пауза между письмами;
  * ответ сервера о лимите или спаме останавливает выпуск сразу;
  * перед каждым письмом заново проверяется подписка (человек мог отписаться во время выпуска);
  * по умолчанию только подтверждённые адреса.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MailMessage
from app.services.mail import audience, service, tokens, transport
from app.services.mail.templates import Digest, DigestItem, render_digest

logger = logging.getLogger(__name__)

KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
OWN_HOSTS = ("forecasteconomy.com",)


class CampaignError(ValueError):
    pass


@dataclass
class Issue:
    key: str
    by_locale: dict[str, Digest]


@dataclass
class RunReport:
    key: str
    dry_run: bool
    audience: int = 0
    no_address: int = 0
    unverified_skipped: int = 0
    no_locale_skipped: int = 0
    already_sent: int = 0
    by_locale: Counter = field(default_factory=Counter)
    statuses: Counter = field(default_factory=Counter)
    stopped: str | None = None

    def as_dict(self) -> dict:
        return {
            "key": self.key, "dry_run": self.dry_run, "audience": self.audience,
            "no_address": self.no_address, "unverified_skipped": self.unverified_skipped,
            "no_locale_skipped": self.no_locale_skipped, "already_sent": self.already_sent,
            "by_locale": dict(self.by_locale), "statuses": dict(self.statuses), "stopped": self.stopped,
        }


def with_utm(url: str, key: str) -> str:
    """Метки перехода на ссылки своего сайта: в аналитике видно, что человек пришёл из письма."""
    if not url:
        return url
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in OWN_HOSTS):
        return url
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q.setdefault("utm_source", "email")
    q.setdefault("utm_medium", "newsletter")
    q.setdefault("utm_campaign", key)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def parse_issue(data: dict) -> Issue:
    key = str(data.get("key") or "").strip()
    if not KEY_RE.match(key):
        raise CampaignError("key: латиница, цифры, точка, дефис; 3–80 знаков")
    by_locale: dict[str, Digest] = {}
    for loc in ("ru", "en"):
        raw = data.get(loc)
        if not raw:
            continue
        if not raw.get("subject") or not raw.get("title"):
            raise CampaignError(f"{loc}: нужны subject и title")
        items = [
            DigestItem(title=str(i["title"]), text=str(i.get("text") or ""),
                       url=with_utm(str(i.get("url") or ""), key), value=str(i.get("value") or ""))
            for i in (raw.get("items") or [])
        ]
        by_locale[loc] = Digest(
            subject=str(raw["subject"]), title=str(raw["title"]), intro=str(raw.get("intro") or ""),
            preheader=str(raw.get("preheader") or ""), items=items,
            cta_label=str(raw.get("cta_label") or ""), cta_url=with_utm(str(raw.get("cta_url") or ""), key),
            outro=str(raw.get("outro") or ""),
        )
    if not by_locale:
        raise CampaignError("нет ни ru, ни en")
    return Issue(key=key, by_locale=by_locale)


def load_issue(path: str | Path) -> Issue:
    return parse_issue(json.loads(Path(path).read_text(encoding="utf-8")))


def unsubscribe_links(user_id, locale: str) -> tuple[str, str]:
    """(страница отписки для человека, адрес для одного нажатия в почтовой программе)."""
    tok = tokens.issue("unsub", str(user_id))
    return (service.site_link(locale, "/account/unsubscribe", t=tok),
            service.api_link(locale, "/mail/unsubscribe", t=tok))


def render_for(issue: Issue, locale: str, user_id) -> tuple:
    page_url, one_click = unsubscribe_links(user_id, locale)
    rendered = render_digest(
        issue.by_locale[locale], locale, site_url=service.site_origin(locale) + "/",
        unsubscribe_url=page_url, manage_url=service.site_link(locale, "/account"),
    )
    return rendered, one_click


async def send_test(issue: Issue, to: str) -> dict[str, str]:
    """Каждый язык выпуска — одним письмом на проверочный адрес (только список допуска)."""
    if not service.recipient_allowed(to):
        raise CampaignError("проверочный адрес не в списке допуска (RUSTATS_MAIL_ALLOWLIST)")
    out = {}
    for loc in issue.by_locale:
        rendered, one_click = render_for(issue, loc, "00000000-0000-0000-0000-000000000000")
        rendered.subject = f"[test] {rendered.subject}"
        out[loc] = await service.send_now(kind="newsletter", to=to, locale=loc, rendered=rendered,
                                          unsubscribe_url=one_click)
    return out


async def run(db: AsyncSession, issue: Issue, *, send: bool, include_unverified: bool = False,
              max_per_run: int | None = None, pause_seconds: float | None = None) -> RunReport:
    report = RunReport(key=issue.key, dry_run=not send)
    if send and not settings.mail_allow_all_recipients:
        raise CampaignError("отправка людям выключена (RUSTATS_MAIL_ALLOW_ALL_RECIPIENTS=false)")
    if send and not settings.mail_enabled:
        raise CampaignError("почта выключена (RUSTATS_MAIL_ENABLED=false)")
    if send:
        tokens._secret()  # без секрета ссылок отписки рассылка не уходит
        transport.ensure_configured("newsletter")
    limit = settings.mail_campaign_max_per_run if max_per_run is None else max_per_run
    pause = settings.mail_campaign_pause_seconds if pause_seconds is None else pause_seconds

    recipients, report.no_address = await audience.subscribers(db)
    report.audience = len(recipients)
    sent_now = 0
    for rec in recipients:
        if not rec.verified and not include_unverified:
            report.unverified_skipped += 1
            continue
        if rec.locale not in issue.by_locale:
            report.no_locale_skipped += 1
            continue
        existing = await db.scalar(select(MailMessage).where(
            MailMessage.campaign == issue.key, MailMessage.user_id == rec.user_id))
        if existing is not None and existing.status == "sent":
            report.already_sent += 1
            continue
        report.by_locale[rec.locale] += 1
        if not send:
            continue
        if sent_now >= limit:
            report.stopped = "max_per_run"
            break
        # Человек мог отписаться, пока шёл выпуск.
        if not await audience.is_subscribed(db, rec.user_id):
            report.statuses["unsubscribed_meanwhile"] += 1
            continue
        rendered, one_click = render_for(issue, rec.locale, rec.user_id)
        row = existing or await service.record(
            db, kind="newsletter", to=rec.email, locale=rec.locale, subject=rendered.subject,
            user_id=rec.user_id, campaign=issue.key)
        row.to_email, row.subject = service.normalize(rec.email), rendered.subject[:300]
        try:
            await service.attempt(db, row, rendered, unsubscribe_url=one_click)
        except transport.SendError as err:
            report.statuses[row.status] += 1
            report.stopped = f"server_limit:{err.code}"
            await db.commit()
            break
        report.statuses[row.status] += 1
        await db.commit()
        sent_now += 1
        if pause > 0:
            await asyncio.sleep(pause)
    return report


RECONFIRM_KEY = "2026-11-reconfirm"


async def run_reconfirm(db: AsyncSession, *, send: bool, key: str = RECONFIRM_KEY,
                        max_per_run: int | None = None, pause_seconds: float | None = None) -> RunReport:
    """Письмо «подтвердите почту» всем со входом по паролю и неподтверждённым адресом.

    Те же защиты, что у выпуска: без ``send`` — сухой прогон; людям — только при снятом
    списке допуска; один раз на человека (уникальность выпуска); лимит за запуск; остановка
    по лимиту сервера; адрес, подтверждённый во время выпуска, пропускается.
    """
    from app.models import EmailCredential
    from app.services.mail.account import reconfirm_mail

    report = RunReport(key=key, dry_run=not send)
    if send and not settings.mail_allow_all_recipients:
        raise CampaignError("отправка людям выключена (RUSTATS_MAIL_ALLOW_ALL_RECIPIENTS=false)")
    if send and not settings.mail_enabled:
        raise CampaignError("почта выключена (RUSTATS_MAIL_ENABLED=false)")
    if send:
        tokens._secret()
        transport.ensure_configured("reconfirm")
    limit = settings.mail_campaign_max_per_run if max_per_run is None else max_per_run
    pause = settings.mail_campaign_pause_seconds if pause_seconds is None else pause_seconds
    recipients = await audience.unverified_password_accounts(db)
    report.audience = len(recipients)
    sent_now = 0
    for rec in recipients:
        existing = await db.scalar(select(MailMessage).where(
            MailMessage.campaign == key, MailMessage.user_id == rec.user_id))
        if existing is not None and existing.status == "sent":
            report.already_sent += 1
            continue
        report.by_locale[rec.locale] += 1
        if not send:
            continue
        if sent_now >= limit:
            report.stopped = "max_per_run"
            break
        verified = await db.scalar(select(EmailCredential.email_verified).where(
            EmailCredential.user_id == rec.user_id))
        if verified:
            report.statuses["verified_meanwhile"] += 1
            continue
        rendered = reconfirm_mail(rec.user_id, rec.email, rec.locale)
        row = existing or await service.record(
            db, kind="reconfirm", to=rec.email, locale=rec.locale, subject=rendered.subject,
            user_id=rec.user_id, campaign=key)
        try:
            await service.attempt(db, row, rendered)
        except transport.SendError as err:
            report.statuses[row.status] += 1
            report.stopped = f"server_limit:{err.code}"
            await db.commit()
            break
        report.statuses[row.status] += 1
        await db.commit()
        sent_now += 1
        if pause > 0:
            await asyncio.sleep(pause)
    return report


async def send_reconfirm_test(to: str) -> dict[str, str]:
    """Письмо «подтвердите почту» на проверочный адрес, по одному на язык."""
    from app.services.mail.account import reconfirm_mail

    if not service.recipient_allowed(to):
        raise CampaignError("проверочный адрес не в списке допуска (RUSTATS_MAIL_ALLOWLIST)")
    out = {}
    for loc in ("ru", "en"):
        rendered = reconfirm_mail("00000000-0000-0000-0000-000000000000", to, loc)
        rendered.subject = f"[test] {rendered.subject}"
        out[loc] = await service.send_now(kind="reconfirm", to=to, locale=loc, rendered=rendered)
    return out
