"""Эффект персонального выпуска по блокам (ADR-0033). Только числа, без адресов.

Показ — блок в снимке выпуска человека (`newsletter_personal_issues.blocks_meta`). Переход —
сессия сайта с `utm_medium=newsletter`, `utm_campaign=<выпуск>` и `utm_content=<метка блока>`
(`behavior_sessions`); человек находится по аккаунту сессии, а без входа — по псевдонимной метке
`utm_term` (если она включена). Переходы без человека считаются только суммой по метке.

Разрезы: группа (личный выпуск / контроль), группа темы, генератор блока, позиция, уровень данных.
Плюс отписки (журнал согласий, 7 суток после сборки) и возвраты на сайт (сессии, 7 суток).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BehaviorSession, Consent, IdentityLink, MailMessage, NewsletterPersonalIssue
from app.services.newsletter_personal import ab

WINDOW_DAYS = 7


async def campaign_metrics(db: AsyncSession, campaign: str) -> dict:
    snaps = (await db.scalars(select(NewsletterPersonalIssue).where(
        NewsletterPersonalIssue.campaign == campaign))).all()
    sent = {str(uid) for uid, in (await db.execute(select(MailMessage.user_id).where(
        MailMessage.campaign == campaign, MailMessage.status == "sent"))).all() if uid}
    if not snaps:
        return {"campaign": campaign, "snapshots": 0}
    by_user = {str(s.user_id): s for s in snaps}
    tokens = {ab.click_token(uid, campaign): uid for uid in by_user}
    tokens.pop(None, None)
    visitors = {vid: uid for uid, vid in (await db.execute(
        select(IdentityLink.user_id, IdentityLink.visitor_id_hash)
        .where(IdentityLink.user_id.in_(list(by_user))))).all()}
    first_built = min(s.built_at for s in snaps)

    clicks_user: dict[str, set[str]] = defaultdict(set)   # человек → метки блоков
    anon_clicks: dict[str, int] = defaultdict(int)
    for uid, vid, content, term in (await db.execute(
            select(BehaviorSession.user_id, BehaviorSession.visitor_id_hash, BehaviorSession.utm_content,
                   BehaviorSession.utm_term)
            .where(BehaviorSession.utm_medium == "newsletter", BehaviorSession.utm_campaign == campaign,
                   BehaviorSession.started_at >= first_built))).all():
        who = uid if uid in by_user else visitors.get(vid) or tokens.get(term)
        if who in by_user and content:
            clicks_user[who].add(content)
        elif content:
            anon_clicks[content] += 1

    rows: dict[tuple, dict] = {}
    arms: dict[str, dict] = defaultdict(lambda: {"users": 0, "sent": 0, "clicked": 0, "unsubscribed": 0, "returned": 0})
    for uid, snap in by_user.items():
        a = arms[snap.arm]
        a["users"] += 1
        if uid in sent:
            a["sent"] += 1
        if clicks_user.get(uid):
            a["clicked"] += 1
        for m in snap.blocks_meta or []:
            if not m.get("pos") or m.get("origin") not in ("personal", "editorial"):
                continue
            k = (snap.arm, snap.subject_arm or "-", m.get("origin"), m.get("gen") or m.get("type"), m["pos"], snap.tier)
            r = rows.setdefault(k, {"shown": 0, "sent": 0, "clicked": 0})
            r["shown"] += 1
            if uid in sent:
                r["sent"] += 1
                if m.get("utm_content") and m["utm_content"] in clicks_user.get(uid, set()):
                    r["clicked"] += 1
    unsub = {str(u) for u, in (await db.execute(select(Consent.user_id).where(
        Consent.user_id.in_([s.user_id for s in snaps]), Consent.kind == "newsletter_revoked",
        Consent.granted_at >= first_built, Consent.granted_at < first_built + timedelta(days=WINDOW_DAYS)))).all()}
    returned = {str(u) for u, in (await db.execute(select(BehaviorSession.user_id).where(
        BehaviorSession.user_id.in_(list(by_user)), BehaviorSession.started_at >= first_built,
        BehaviorSession.started_at < first_built + timedelta(days=WINDOW_DAYS)))).all()}
    for uid, snap in by_user.items():
        if uid in unsub:
            arms[snap.arm]["unsubscribed"] += 1
        if uid in returned:
            arms[snap.arm]["returned"] += 1
    blocks = []
    for (arm, s_arm, origin, gen, pos, tier), r in sorted(rows.items(), key=lambda kv: (kv[0][0], kv[0][4])):
        ctr = round(r["clicked"] / r["sent"], 4) if r["sent"] else None
        blocks.append({"arm": arm, "subject_arm": s_arm, "origin": origin, "gen": gen, "pos": pos, "tier": tier,
                       **r, "ctr": ctr})
    return {"campaign": campaign, "snapshots": len(snaps), "arms": dict(arms), "blocks": blocks,
            "clicks_without_person": dict(anon_clicks)}


def summary_by_generator(metrics: dict) -> list[dict]:
    """Свод для вкладки «Почта» в админ-BI: генератор → показано, отправлено, кликнули, доля."""
    agg: dict[str, dict] = defaultdict(lambda: {"shown": 0, "sent": 0, "clicked": 0})
    for b in metrics.get("blocks") or []:
        a = agg[f"{b['origin']}:{b['gen']}"]
        for k in ("shown", "sent", "clicked"):
            a[k] += b[k]
    return [{"block": k, **v, "ctr": round(v["clicked"] / v["sent"], 4) if v["sent"] else None}
            for k, v in sorted(agg.items())]


GEN_LABELS = {
    "series": "Ваши показатели", "download": "Вы скачивали", "search": "Вы искали", "region": "Регион",
    "related": "Связанное", "now": "Теперь есть", "forecast": "Прогноз", "check": "Сверка",
    "since": "Пока вас не было", "table": "Таблица «Ваши показатели»", "calendar": "Календарь (личные даты)",
    "section": "Заголовок «Для вас»", "editorial": "Блоки редакции",
}


async def block_effect_summary(db: AsyncSession, days: int = 30) -> list[dict]:
    """Для вкладки «Почта» админ-BI: генератор блока → показано в отправленных письмах и переходы.

    Берутся выпуски со снимками, собранными за последние `days` суток; только числа.
    """
    from datetime import datetime, timezone

    from app.services.newsletter_personal import store

    if not await store.tables_ready(db):
        return []
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    campaigns = [c for c, in (await db.execute(
        select(NewsletterPersonalIssue.campaign).where(NewsletterPersonalIssue.built_at >= since).distinct())).all()]
    agg: dict[str, dict] = defaultdict(lambda: {"shown": 0, "clicks": 0})
    for key in campaigns:
        m = await campaign_metrics(db, key)
        for b in m.get("blocks") or []:
            gen = b["gen"] if b["origin"] == "personal" else "editorial"
            agg[gen]["shown"] += b["sent"]
            agg[gen]["clicks"] += b["clicked"]
    return [{"generator": gen, "label": GEN_LABELS.get(gen, gen), "shown": v["shown"], "clicks": v["clicks"]}
            for gen, v in sorted(agg.items(), key=lambda kv: -kv[1]["shown"])]
