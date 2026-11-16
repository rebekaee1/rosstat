"""Разделы Пульса, которых не было в дневном снимке (ревизия 16.11.2026, ADR-0034).

До этой ревизии снимок дня не видел: почту и рассылку, движение согласий, личный кабинет,
публичный бот, скачивания исследований, загрузку мировых данных, устаревшие ряды, доставку
самого Telegram и ближайшие публикации календаря. Каждый раздел — только суммы, без имён,
адресов и текстов сообщений; сбой раздела не роняет снимок (`{"error": …}`).
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

logger = logging.getLogger(__name__)


async def _mail(db, start: datetime, end: datetime) -> dict[str, Any]:
    from app.config import settings
    from app.models import MailEvent, MailMessage, MailSuppression
    from app.services.mail import funnel

    by_kind: dict[str, dict[str, int]] = {}
    for kind, status, n in (await db.execute(
            select(MailMessage.kind, MailMessage.status, func.count())
            .where(MailMessage.created_at >= start, MailMessage.created_at < end)
            .group_by(MailMessage.kind, MailMessage.status))).all():
        by_kind.setdefault(kind, {})[status] = int(n)
    events = {f"{kind}{'_machine' if machine else ''}": int(n) for kind, machine, n in (await db.execute(
        select(MailEvent.kind, MailEvent.machine, func.count())
        .where(MailEvent.occurred_at >= start, MailEvent.occurred_at < end)
        .group_by(MailEvent.kind, MailEvent.machine))).all()}
    suppressed_new = int(await db.scalar(select(func.count()).select_from(MailSuppression).where(
        MailSuppression.created_at >= start, MailSuppression.created_at < end)) or 0)
    out: dict[str, Any] = {
        "enabled": bool(settings.mail_enabled), "people_allowed": bool(settings.mail_allow_all_recipients),
        "tracking": bool(settings.mail_tracking_enabled),
        "letters_by_kind": by_kind, "events": events, "new_suppressions": suppressed_new,
    }
    recent = await funnel.campaigns(db, limit=2)
    if recent:
        f = await funnel.campaign_funnel(db, recent[0]["key"], now=end)
        out["last_campaign"] = {k: f.get(k) for k in (
            "campaign", "first_sent", "age_days", "accepted", "delivered", "bounced", "tracked", "opened_people",
            "open_rate_pct", "opened_machine_only", "clicked_people", "click_rate_pct", "click_sessions",
            "unsubscribed", "personal_off", "complaints", "returned", "blocks", "visit")}
    else:
        out["last_campaign"] = None   # выпуски людям ещё не отправлялись
    return out


async def _consents(db, start: datetime, end: datetime) -> dict[str, Any]:
    from app.models import Consent, EmailCredential, User

    day = {k: int(n) for k, n in (await db.execute(
        select(Consent.kind, func.count()).where(Consent.granted_at >= start, Consent.granted_at < end)
        .group_by(Consent.kind))).all()}
    new_users = int(await db.scalar(select(func.count()).select_from(User).where(
        User.created_at >= start, User.created_at < end)) or 0)
    unverified = int(await db.scalar(select(func.count()).select_from(EmailCredential).where(
        EmailCredential.email_verified.is_(False))) or 0)
    verified_day = None
    if hasattr(EmailCredential, "email_verified_at"):
        verified_day = int(await db.scalar(select(func.count()).select_from(EmailCredential).where(
            EmailCredential.email_verified_at >= start, EmailCredential.email_verified_at < end)) or 0)
    return {
        "new_users": new_users, "newsletter_opt_in": day.get("newsletter", 0),
        "newsletter_revoked": day.get("newsletter_revoked", 0),
        "personal_revoked": day.get("mail_personal_revoked", 0),
        "watch_mail_revoked": day.get("watch_mail_revoked", 0),
        "password_addresses_unverified_total": unverified, "addresses_verified_today": verified_day,
    }


async def _cabinet(db, start: datetime, end: datetime) -> dict[str, Any]:
    from app.config import settings
    from app.models import UserExport, UserPreference, UserSavedItem, UserWatch

    async def pair(model, col) -> dict[str, int]:
        total = int(await db.scalar(select(func.count()).select_from(model)) or 0)
        new = int(await db.scalar(select(func.count()).select_from(model).where(col >= start, col < end)) or 0)
        return {"new": new, "total": total}

    saved_kinds = {k: int(n) for k, n in (await db.execute(
        select(UserSavedItem.kind, func.count()).where(UserSavedItem.created_at >= start, UserSavedItem.created_at < end)
        .group_by(UserSavedItem.kind))).all()}
    export_formats = {f"{s}:{f}": int(n) for s, f, n in (await db.execute(
        select(UserExport.source, UserExport.format, func.count())
        .where(UserExport.created_at >= start, UserExport.created_at < end)
        .group_by(UserExport.source, UserExport.format))).all()}
    return {
        "enabled": bool(getattr(settings, "cabinet_enabled", False)),
        "saved": await pair(UserSavedItem, UserSavedItem.created_at), "saved_by_kind": saved_kinds,
        "watches": await pair(UserWatch, UserWatch.created_at),
        "exports": await pair(UserExport, UserExport.created_at), "exports_by_format": export_formats,
        "preferences": await pair(UserPreference, UserPreference.updated_at),
    }


async def _public_bot(db, start: datetime, end: datetime) -> dict[str, Any]:
    from app.models import PublicBotChat, PublicBotDialog, PublicBotEvent, PublicBotSubscription

    chats_total = int(await db.scalar(select(func.count()).select_from(PublicBotChat)) or 0)
    chats_new = int(await db.scalar(select(func.count()).select_from(PublicBotChat).where(
        PublicBotChat.first_seen_at >= start, PublicBotChat.first_seen_at < end)) or 0)
    chats_active = int(await db.scalar(select(func.count(func.distinct(PublicBotEvent.chat_hash))).where(
        PublicBotEvent.occurred_at >= start, PublicBotEvent.occurred_at < end)) or 0)
    blocked = int(await db.scalar(select(func.count()).select_from(PublicBotChat).where(
        PublicBotChat.blocked_at.is_not(None))) or 0)
    events = {k: int(n) for k, n in (await db.execute(
        select(PublicBotEvent.kind, func.count()).where(PublicBotEvent.occurred_at >= start, PublicBotEvent.occurred_at < end)
        .group_by(PublicBotEvent.kind))).all()}
    topics = {str(k): int(n) for k, n in (await db.execute(
        select(PublicBotEvent.topic, func.count())
        .where(PublicBotEvent.occurred_at >= start, PublicBotEvent.occurred_at < end, PublicBotEvent.topic.is_not(None))
        .group_by(PublicBotEvent.topic).order_by(func.count().desc()).limit(8))).all()}
    messages = {str(k): int(n) for k, n in (await db.execute(
        select(PublicBotDialog.direction, func.count())
        .where(PublicBotDialog.occurred_at >= start, PublicBotDialog.occurred_at < end)
        .group_by(PublicBotDialog.direction))).all()}
    heard = {str(k or "не сказал"): int(n) for k, n in (await db.execute(
        select(PublicBotChat.heard_from, func.count()).group_by(PublicBotChat.heard_from))).all()}
    subs = int(await db.scalar(select(func.count()).select_from(PublicBotSubscription)) or 0)
    return {"chats_total": chats_total, "chats_new": chats_new, "chats_active": chats_active, "blocked_total": blocked,
            "events": events, "topics": topics, "messages": messages, "heard_from_total": heard,
            "subscriptions_total": subs}


async def _research(db, d: date) -> dict[str, Any]:
    from app.models import ResearchDownload

    rows = (await db.execute(
        select(ResearchDownload.slug, ResearchDownload.source, func.sum(ResearchDownload.count))
        .where(ResearchDownload.date == d).group_by(ResearchDownload.slug, ResearchDownload.source))).all()
    total = int(await db.scalar(select(func.sum(ResearchDownload.count))) or 0)
    return {"downloads_day": sum(int(n or 0) for _s, _src, n in rows),
            "by_material": {f"{s} ({src})": int(n or 0) for s, src, n in rows}, "downloads_total": total}


async def _world_ingest(db, start: datetime, end: datetime) -> dict[str, Any]:
    from app.models import WorldIngestRun

    rows = (await db.execute(
        select(WorldIngestRun.source, WorldIngestRun.status, func.count(), func.sum(WorldIngestRun.datasets_succeeded),
               func.sum(WorldIngestRun.datasets_failed))
        .where(WorldIngestRun.started_at >= start, WorldIngestRun.started_at < end, WorldIngestRun.is_shadow.is_(False))
        .group_by(WorldIngestRun.source, WorldIngestRun.status))).all()
    by_source: dict[str, dict[str, Any]] = {}
    for source, status, runs, ok, failed in rows:
        s = by_source.setdefault(source, {"runs": {}, "datasets_ok": 0, "datasets_failed": 0})
        s["runs"][status] = int(runs)
        s["datasets_ok"] += int(ok or 0)
        s["datasets_failed"] += int(failed or 0)
    last = await db.scalar(select(func.max(WorldIngestRun.completed_at)).where(WorldIngestRun.status == "success"))
    return {"by_source": by_source, "runs": sum(sum(s["runs"].values()) for s in by_source.values()),
            "datasets_failed": sum(s["datasets_failed"] for s in by_source.values()),
            "last_success_utc": last.isoformat() if last else None}


async def _freshness(db, d: date) -> dict[str, Any]:
    """Сколько российских рядов каталога устарели по правилу сайта (то, что видит посетитель)."""
    from app.models import Indicator, IndicatorData
    from app.services import freshness

    rows = (await db.execute(
        select(Indicator.code, Indicator.frequency, Indicator.category, func.max(IndicatorData.date))
        .join(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(Indicator.is_active.is_(True), Indicator.is_listed.is_(True))
        .group_by(Indicator.code, Indicator.frequency, Indicator.category))).all()
    levels: Counter[str] = Counter()
    stale: list[tuple[int, str]] = []
    by_cat: Counter[str] = Counter()
    for code, freq, cat, last in rows:
        level = freshness.freshness_level(last, freq, d) or "no_data"
        levels[level] += 1
        if level == "stale":
            stale.append((freshness.age_days(last, freq, d), code))
            by_cat[str(cat or "—")] += 1
    stale.sort(reverse=True)
    return {"listed_series": len(rows), "levels": dict(levels), "stale_by_category": dict(by_cat.most_common(8)),
            "stale_oldest": [code for _age, code in stale[:10]]}


async def _telegram(db, start: datetime, end: datetime) -> dict[str, Any]:
    from app.models import TelegramOutbox

    rows = (await db.execute(
        select(TelegramOutbox.method, TelegramOutbox.kind, TelegramOutbox.ok, func.count())
        .where(TelegramOutbox.sent_at >= start, TelegramOutbox.sent_at < end)
        .group_by(TelegramOutbox.method, TelegramOutbox.kind, TelegramOutbox.ok))).all()
    sent = failed = held = 0
    failed_kinds: Counter[str] = Counter()
    held_kinds: Counter[str] = Counter()
    for method, kind, ok, n in rows:
        n = int(n)
        if method == "held":
            held += n
            held_kinds[kind] += n
        elif ok:
            sent += n
        else:
            failed += n
            failed_kinds[kind] += n
    return {"sent": sent, "failed": failed, "failed_by_kind": dict(failed_kinds), "held_for_summary": held,
            "held_by_kind": dict(held_kinds.most_common(8))}


async def _calendar(db, d: date) -> dict[str, Any]:
    """Публикации официальных данных: что вышло в отчётный день и что ждём в ближайшие три дня."""
    from app.models import EconomicEvent

    def row(e) -> dict[str, Any]:
        return {"date": e.scheduled_date.isoformat(), "title": (e.title or "")[:90], "status": e.status,
                "importance": e.importance}

    day = (await db.scalars(select(EconomicEvent).where(EconomicEvent.scheduled_date == d)
                            .order_by(EconomicEvent.importance.desc()).limit(8))).all()
    nxt = (await db.scalars(select(EconomicEvent).where(
        EconomicEvent.scheduled_date > d, EconomicEvent.scheduled_date <= d + timedelta(days=3),
        EconomicEvent.importance >= 2).order_by(EconomicEvent.scheduled_date, EconomicEvent.importance.desc()).limit(10))).all()
    overdue = int(await db.scalar(select(func.count()).select_from(EconomicEvent).where(
        EconomicEvent.scheduled_date < d, EconomicEvent.scheduled_date >= d - timedelta(days=14),
        EconomicEvent.status == "scheduled", EconomicEvent.actual_date.is_(None))) or 0)
    return {"day": [row(e) for e in day], "next_3_days": [row(e) for e in nxt],
            "scheduled_but_not_released_14d": overdue}


async def build_extra(db, d: date, start: datetime, end: datetime) -> dict[str, Any]:
    """Все новые разделы; раздел со сбоем отдаёт `{"error": …}` и не мешает остальным."""
    sections = {
        "mail": lambda: _mail(db, start, end),
        "consents": lambda: _consents(db, start, end),
        "cabinet": lambda: _cabinet(db, start, end),
        "public_bot": lambda: _public_bot(db, start, end),
        "research": lambda: _research(db, d),
        "world_ingest": lambda: _world_ingest(db, start, end),
        "freshness": lambda: _freshness(db, d),
        "telegram": lambda: _telegram(db, start, end),
        "calendar": lambda: _calendar(db, d),
    }
    out: dict[str, Any] = {}
    for name, fn in sections.items():
        try:
            out[name] = await fn()
        except Exception as exc:  # noqa: BLE001 — Пульс не падает из-за одного раздела
            logger.warning("Pulse extra section %s failed: %s", name, type(exc).__name__, exc_info=True)
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass
            out[name] = {"error": type(exc).__name__}
    return out


def digits_lines(snapshot: dict) -> list[str]:
    """Строки для блока «сырые цифры» отчёта Пульса: только то, где есть что сказать."""
    lines: list[str] = []
    m = snapshot.get("mail") or {}
    if m and not m.get("error"):
        letters = m.get("letters_by_kind") or {}
        if letters:
            lines.append("Почта за день: " + "; ".join(
                f"{k}: " + ", ".join(f"{s} {n}" for s, n in sorted(v.items())) for k, v in sorted(letters.items())))
        ev = m.get("events") or {}
        if ev:
            lines.append(f"Письма: открытий людьми {ev.get('open', 0)}, программами {ev.get('open_machine', 0)}, "
                         f"переходов на сайт {ev.get('click', 0)}")
        lc = m.get("last_campaign")
        if lc:
            lines.append(f"Последний выпуск {lc.get('campaign')}: дошло {lc.get('delivered')}, открыли {lc.get('opened_people')}, "
                         f"перешли {lc.get('clicked_people')}, отписались {lc.get('unsubscribed')}")
        elif not letters:
            lines.append("Рассылка: выпуски людям ещё не отправлялись")
    c = snapshot.get("consents") or {}
    if c and not c.get("error"):
        lines.append(f"Согласия: на рассылку подписались {c.get('newsletter_opt_in', 0)} из {c.get('new_users', 0)} новых, "
                     f"отписались {c.get('newsletter_revoked', 0)}, отказались от подборки {c.get('personal_revoked', 0)}; "
                     f"адресов без подтверждения {c.get('password_addresses_unverified_total', 0)}")
    cab = snapshot.get("cabinet") or {}
    if cab and not cab.get("error"):
        lines.append(f"Кабинет: избранное +{cab['saved']['new']} (всего {cab['saved']['total']}), слежения "
                     f"+{cab['watches']['new']} (всего {cab['watches']['total']}), выгрузки +{cab['exports']['new']} "
                     f"(всего {cab['exports']['total']})")
    pb = snapshot.get("public_bot") or {}
    if pb and not pb.get("error"):
        lines.append(f"Публичный бот: чатов {pb.get('chats_total', 0)} (новых {pb.get('chats_new', 0)}, активных за день "
                     f"{pb.get('chats_active', 0)}), подписок {pb.get('subscriptions_total', 0)}")
    rs = snapshot.get("research") or {}
    if rs and not rs.get("error") and rs.get("downloads_day"):
        lines.append(f"Исследования: скачиваний {rs['downloads_day']} (всего {rs.get('downloads_total', 0)})")
    wi = snapshot.get("world_ingest") or {}
    if wi and not wi.get("error"):
        lines.append(f"Мировые данные: запусков загрузки {wi.get('runs', 0)}, наборов с ошибкой {wi.get('datasets_failed', 0)}")
    fr = snapshot.get("freshness") or {}
    if fr and not fr.get("error"):
        lv = fr.get("levels") or {}
        lines.append(f"Свежесть рядов России: свежих {lv.get('fresh', 0)}, стареют {lv.get('aging', 0)}, "
                     f"устарели {lv.get('stale', 0)} из {fr.get('listed_series', 0)}")
    tg = snapshot.get("telegram") or {}
    if tg and not tg.get("error") and (tg.get("failed") or tg.get("held_for_summary")):
        lines.append(f"Telegram: отправлено {tg.get('sent', 0)}, не доставлено {tg.get('failed', 0)}, "
                     f"отложено в утреннюю сводку {tg.get('held_for_summary', 0)}")
    cal = snapshot.get("calendar") or {}
    if cal and not cal.get("error") and cal.get("next_3_days"):
        lines.append("Ближайшие публикации: " + "; ".join(
            f"{e['date'][8:]}.{e['date'][5:7]} {e['title']}" for e in cal["next_3_days"][:4]))
    return lines
