"""Письма о новых значениях по «колокольчику» (ADR-0032, утверждено 14.11.2026).

Раз в день (``mail_watch_digest_hour_msk``, по умолчанию 10:00 МСК) каждому, у кого есть
слежения с новой точкой ряда, уходит одна сводка. Правила:

* выключено флагом ``RUSTATS_MAIL_WATCH_DIGEST_ENABLED`` (и общим ``RUSTATS_MAIL_ENABLED``);
* не больше одного письма в день: ключ выпуска ``watch-ГГГГ-ММ-ДД`` + уникальность
  (выпуск, человек) в журнале;
* «новое» — последняя дата ряда позже и даты, когда человек видел ряд в кабинете
  (``last_seen_date``), и даты прошлого письма (``last_notified_date``): одно значение
  не приходит дважды; после отправки ``last_notified_date`` = дата ряда;
* только подтверждённые адреса; своя отписка (журнал согласий ``watch_mail_revoked``),
  независимая от рассылки; без записи — письма включены (человек сам нажал «Следить»);
* ответ сервера о лимите останавливает задачу до следующего дня.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Consent, MailMessage, User, UserWatch
from app.services.mail import audience, service, tokens, transport
from app.services.mail.templates import DigestItem, render_watch

logger = logging.getLogger(__name__)

WATCH_KINDS = ("watch_mail", "watch_mail_revoked")
MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


async def watch_mail_on(db: AsyncSession, user_id: uuid.UUID) -> bool:
    last = await db.scalar(
        select(Consent.kind).where(Consent.user_id == user_id, Consent.kind.in_(WATCH_KINDS))
        .order_by(Consent.granted_at.desc(), Consent.id.desc()).limit(1))
    return last != "watch_mail_revoked"


def _date_label(d: date, locale: str) -> str:
    return f"{d.day} {MONTHS_EN[d.month - 1]} {d.year}" if locale == "en" else d.strftime("%d.%m.%Y")


def _url(info, locale: str) -> str:
    from app.services import site_paths as paths

    if info.kind == "indicator":
        path = paths.russia_indicator(info.key)
    elif info.kind == "world" and info.country_slug:
        path = paths.indicator(info.country_slug, info.key)
    elif info.kind == "region":
        path = paths.region_rating(info.key)
    else:
        path = "/account"
    from app.services.mail.campaign import with_utm

    url = service.site_link(locale, path)
    return with_utm(url, "watch").replace("utm_medium=newsletter", "utm_medium=watch")


def _item(info, locale: str) -> DigestItem:
    from app.services.display import format_number_ru

    title = f"{info.country_name}: {info.title}" if info.country_name and info.kind == "world" else info.title
    value = ""
    if info.latest_value is not None:
        value = format_number_ru(info.latest_value, locale=locale)
        if info.unit and len(info.unit) <= 12:
            value = f"{value} {info.unit}"
    from app.services.mail.templates import t

    text = t(locale, "watch.as_of").format(date=_date_label(info.latest_date, locale)) if info.latest_date else ""
    return DigestItem(title=title[:200], text=text, url=_url(info, locale), value=value)


async def new_items(db: AsyncSession, user_id: uuid.UUID, locale: str) -> list[tuple[UserWatch, object]]:
    """Слежения человека с новой точкой ряда (с учётом увиденного и уже отправленного)."""
    from app.services.cabinet import watches_with_info
    from app.services.locale import reset_locale, set_locale

    token = set_locale("en" if locale == "en" else "ru")  # названия рядов на языке письма
    try:
        pairs = await watches_with_info(db, user_id)
    finally:
        reset_locale(token)
    out = []
    for watch, info in pairs:
        if info is None or info.latest_date is None:
            continue
        marks = [d for d in (watch.last_seen_date, watch.last_notified_date) if d is not None]
        if marks and info.latest_date <= max(marks):
            continue
        out.append((watch, info))
    return out


async def run(db: AsyncSession, *, today: date, send: bool = True, only_user: uuid.UUID | None = None) -> dict:
    """Один проход: сводка каждому, у кого есть новое. ``send=False`` — только счёт."""
    key = f"watch-{today.isoformat()}"
    report = {"key": key, "users": 0, "with_new": 0, "skipped_unverified": 0, "skipped_off": 0,
              "already_sent": 0, "statuses": {}, "stopped": None}
    q = select(UserWatch.user_id).distinct()
    if only_user is not None:
        q = q.where(UserWatch.user_id == only_user)
    user_ids = [r[0] for r in (await db.execute(q)).all()]
    for uid in user_ids:
        user = await db.get(User, uid)
        if user is None or user.status != "active":
            continue
        report["users"] += 1
        if not await watch_mail_on(db, uid):
            report["skipped_off"] += 1
            continue
        rec = await audience.resolve(db, uid)
        if rec is None or not rec.verified:
            report["skipped_unverified"] += 1
            continue
        if await db.scalar(select(MailMessage.id).where(
                MailMessage.campaign == key, MailMessage.user_id == uid, MailMessage.status == "sent")):
            report["already_sent"] += 1
            continue
        pairs = await new_items(db, uid, rec.locale)
        if not pairs:
            continue
        report["with_new"] += 1
        if not send:
            continue
        unsub = tokens.issue("unsub_watch", str(uid))
        rendered = render_watch(
            [_item(info, rec.locale) for _w, info in pairs[:20]], rec.locale,
            site_url=service.site_origin(rec.locale) + "/",
            cabinet_url=service.site_link(rec.locale, "/account"),
            unsubscribe_url=service.site_link(rec.locale, "/account/unsubscribe", t=unsub),
        )
        row = await db.scalar(select(MailMessage).where(MailMessage.campaign == key, MailMessage.user_id == uid))
        if row is None:
            row = await service.record(db, kind="watch_digest", to=rec.email, locale=rec.locale,
                                       subject=rendered.subject, user_id=uid, campaign=key)
        try:
            await service.attempt(db, row, rendered,
                                  unsubscribe_url=service.api_link(rec.locale, "/mail/unsubscribe", t=unsub))
        except transport.SendError as err:
            report["statuses"][row.status] = report["statuses"].get(row.status, 0) + 1
            report["stopped"] = f"server_limit:{err.code}"
            await db.commit()
            break
        report["statuses"][row.status] = report["statuses"].get(row.status, 0) + 1
        if row.status == "sent":
            for watch, info in pairs:
                watch.last_notified_date = info.latest_date
        await db.commit()
    return report


async def watch_digest_job() -> dict | None:
    if not (settings.mail_enabled and settings.mail_watch_digest_enabled):
        return None
    from app.services.display import today_msk

    try:
        tokens._secret()
    except tokens.TokenSecretMissing:
        logger.warning("watch digest skipped: RUSTATS_MAIL_TOKEN_SECRET is not set")
        return None
    async with service._factory()() as db:
        report = await run(db, today=today_msk())
    logger.info("watch digest: %s", {k: v for k, v in report.items() if k != "key"})
    return report
