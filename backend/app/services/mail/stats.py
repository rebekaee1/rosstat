"""Сводка почты для админ-BI (ADR-0032): только числа, без адресов и тем писем людям."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Consent, EmailCredential, MailMessage, MailSuppression, User


async def mail_summary(db: AsyncSession, *, days: int = 30) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = now - timedelta(days=days)
    by_kind: dict[str, dict[str, int]] = {}
    for kind, status, n in (await db.execute(
        select(MailMessage.kind, MailMessage.status, func.count())
        .where(MailMessage.created_at >= since).group_by(MailMessage.kind, MailMessage.status)
    )).all():
        by_kind.setdefault(kind, {})[status] = int(n)

    day_col = func.date(MailMessage.created_at)
    daily: dict[str, dict[str, int]] = {}
    for d, status, n in (await db.execute(
        select(day_col, MailMessage.status, func.count())
        .where(MailMessage.created_at >= now - timedelta(days=14)).group_by(day_col, MailMessage.status)
    )).all():
        daily.setdefault(str(d), {})[status] = int(n)

    campaigns = []
    for key, status, n, last in (await db.execute(
        select(MailMessage.campaign, MailMessage.status, func.count(), func.max(MailMessage.created_at))
        .where(MailMessage.campaign.isnot(None), ~MailMessage.campaign.like("watch-%"))
        .group_by(MailMessage.campaign, MailMessage.status)
    )).all():
        row = next((c for c in campaigns if c["key"] == key), None)
        if row is None:
            row = {"key": key, "statuses": {}, "last": None}
            campaigns.append(row)
        row["statuses"][status] = int(n)
        stamp = last.isoformat() if last else None
        if stamp and (row["last"] is None or stamp > row["last"]):
            row["last"] = stamp
    campaigns.sort(key=lambda c: c["last"] or "", reverse=True)

    from app.services.identity.consents import newsletter_subscriber_count_query

    subscribers = int(await db.scalar(newsletter_subscriber_count_query()) or 0)
    creds_unverified = int(await db.scalar(
        select(func.count()).select_from(EmailCredential).join(User, User.id == EmailCredential.user_id)
        .where(EmailCredential.email_verified.is_(False), User.status == "active")) or 0)
    creds_verified = int(await db.scalar(
        select(func.count()).select_from(EmailCredential).where(EmailCredential.email_verified.is_(True))) or 0)
    consent_events = {k: int(n) for k, n in (await db.execute(
        select(Consent.kind, func.count()).where(
            Consent.granted_at >= since,
            Consent.kind.in_(("newsletter", "newsletter_revoked", "watch_mail", "watch_mail_revoked")))
        .group_by(Consent.kind))).all()}
    suppressions = {k: int(n) for k, n in (await db.execute(
        select(MailSuppression.reason, func.count()).group_by(MailSuppression.reason))).all()}
    return {
        "days": days,
        "config": {
            "enabled": bool(settings.mail_enabled),
            "allowlist_only": not settings.mail_allow_all_recipients,
            "bulk_profile": bool((settings.mail_bulk_smtp_host or "").strip()),
            "bounce_poll": bool(settings.mail_bounce_poll_enabled),
            "watch_digest": bool(settings.mail_watch_digest_enabled),
        },
        "by_kind": by_kind,
        "daily": dict(sorted(daily.items())),
        "campaigns": campaigns[:20],
        "audience": {
            "newsletter_subscribers": subscribers,
            "password_verified": creds_verified,
            "password_unverified": creds_unverified,
        },
        "consent_events": consent_events,
        "suppressions": suppressions,
    }
