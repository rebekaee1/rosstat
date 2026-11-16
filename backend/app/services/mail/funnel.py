"""Воронка выпуска рассылки и её отчёт (ADR-0034, 16.11.2026). Только суммы, без адресов.

Шаги: отправлено → принято сервером → отказ → открыто человеком / программой → переход на сайт →
что смотрели в визите → вернулись на сайт за 1 / 7 / 30 суток → скачали → отписались или отказались
от подборки. Разрезы: личное или общее письмо, язык, почтовый сервис, подтверждён ли адрес, блок.

Источники: `mail_outbox` (итоги по письму), `mail_events` (открытия, переходы), `behavior_sessions`
и `frontend_events` (визиты и действия), `consents` (отписки), `mail_suppressions` (жалобы).
Если учёт открытий выключен или письма ещё не уходили — в отчёте честно стоит «нет данных».
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BehaviorSession, Consent, FrontendEvent, IdentityLink, MailEvent, MailMessage, MailSuppression,
)

ACCEPTED = ("sent", "bounced")
RETURN_WINDOWS = (1, 7, 30)
BLOCK_LABELS = {
    "series": "ваши показатели", "download": "вы скачивали", "search": "вы искали", "region": "регион",
    "related": "рядом с вашими темами", "now": "теперь есть на сайте", "forecast": "прогноз", "check": "сверка",
    "since": "пока вас не было", "table": "таблица «Ваши показатели»", "calendar": "календарь",
    "lead": "число недели", "story": "блок редакции", "cta": "кнопка в конце",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _pct(part: int, whole: int) -> float | None:
    return round(100.0 * part / whole, 1) if whole else None


def _median_minutes(values: list[float]) -> float | None:
    return round(statistics.median(values) / 60.0, 1) if values else None


def block_label(content: str | None) -> tuple[str, str]:
    """Метка блока письма (`p3-series`, `b2-story`) → (личный/редакция/без метки, вид блока)."""
    c = (content or "").strip()
    if not c:
        return "—", "cta"
    origin = "personal" if c.startswith("p") else "editorial" if c.startswith("b") else "—"
    return origin, (c.split("-", 1)[1] if "-" in c else c)


async def campaigns(db: AsyncSession, *, limit: int = 12) -> list[dict]:
    """Выпуски рассылки (без писем «колокольчика»), новые первыми: ключ и время первой отправки."""
    rows = (await db.execute(
        select(MailMessage.campaign, func.min(MailMessage.sent_at), func.count())
        .where(MailMessage.kind == "newsletter", MailMessage.campaign.is_not(None),
               MailMessage.status.in_(ACCEPTED))
        .group_by(MailMessage.campaign))).all()
    out = [{"key": k, "first_sent": first, "accepted": int(n)} for k, first, n in rows if first]
    out.sort(key=lambda c: c["first_sent"], reverse=True)
    return out[:limit]


async def campaign_funnel(db: AsyncSession, campaign: str, *, now: datetime | None = None) -> dict:
    at = now or _now()
    mails = (await db.scalars(select(MailMessage).where(
        MailMessage.campaign == campaign, MailMessage.kind == "newsletter"))).all()
    statuses = Counter(m.status for m in mails)
    accepted = [m for m in mails if m.status in ACCEPTED]
    out: dict = {"campaign": campaign, "letters": len(mails), "statuses": dict(statuses),
                 "accepted": len(accepted), "has_data": bool(accepted)}
    if not accepted:
        return out
    first_sent = min(m.sent_at for m in accepted if m.sent_at)
    age_days = (at - first_sent).total_seconds() / 86400.0
    delivered = [m for m in accepted if m.status == "sent"]
    tracked = [m for m in delivered if m.tracked]
    opened = [m for m in tracked if m.opened_at]
    machine_only = [m for m in tracked if m.machine_opened_at and not m.opened_at]
    clicked = [m for m in delivered if m.clicked_at]
    out.update({
        "first_sent": first_sent.isoformat(), "age_days": round(age_days, 1),
        "bounced": statuses.get("bounced", 0), "failed": statuses.get("failed", 0),
        "not_sent": {k: v for k, v in statuses.items() if k not in ACCEPTED and k != "failed"},
        "delivered": len(delivered), "tracked": len(tracked),
        "opened_people": len(opened), "opened_machine_only": len(machine_only),
        "open_rate_pct": _pct(len(opened), len(tracked)),
        "clicked_people": len(clicked), "click_rate_pct": _pct(len(clicked), len(delivered)),
        "click_to_open_pct": _pct(len([m for m in opened if m.clicked_at]), len(opened)),
        "minutes_to_open_median": _median_minutes(
            [(m.opened_at - m.sent_at).total_seconds() for m in opened if m.sent_at]),
        "minutes_to_click_median": _median_minutes(
            [(m.clicked_at - m.sent_at).total_seconds() for m in clicked if m.sent_at]),
        "open_clients": dict(Counter(m.open_client or "—" for m in opened)),
    })

    # --- разрезы ---------------------------------------------------------------
    def cut(key) -> dict:
        agg: dict[str, dict[str, int]] = defaultdict(lambda: {"delivered": 0, "tracked": 0, "opened": 0, "clicked": 0})
        for m in delivered:
            a = agg[str(key(m))]
            a["delivered"] += 1
            a["tracked"] += 1 if m.tracked else 0
            a["opened"] += 1 if (m.tracked and m.opened_at) else 0
            a["clicked"] += 1 if m.clicked_at else 0
        return dict(agg)

    out["cuts"] = {
        "variant": cut(lambda m: m.variant or "—"),
        "locale": cut(lambda m: m.locale or "—"),
        "provider": cut(lambda m: m.provider or "—"),
        "addr_verified": cut(lambda m: "verified" if m.addr_verified else "unverified" if m.addr_verified is False else "—"),
    }

    # --- переходы и визиты -----------------------------------------------------
    by_id = {m.id: m for m in mails}
    events = (await db.execute(
        select(MailEvent.mail_id, MailEvent.block, MailEvent.session_id_hash, MailEvent.machine)
        .where(MailEvent.campaign == campaign, MailEvent.kind == "click"))).all()
    human_clicks = [(mid, block, sid) for mid, block, sid, machine in events if not machine and mid in by_id]
    out["click_sessions"] = len(human_clicks)
    out["click_sessions_machine"] = sum(1 for e in events if e[3])
    blocks: dict[tuple[str, str], dict] = defaultdict(lambda: {"clicks": 0, "people": set()})
    for mid, block, _sid in human_clicks:
        b = blocks[block_label(block)]
        b["clicks"] += 1
        b["people"].add(mid)
    out["blocks"] = sorted(
        ({"origin": o, "block": g, "label": BLOCK_LABELS.get(g, g), "clicks": v["clicks"], "people": len(v["people"])}
         for (o, g), v in blocks.items()), key=lambda r: -r["clicks"])
    matched = {sid for _m, _b, sid in human_clicks} | {e[2] for e in events}
    total_sessions = int(await db.scalar(select(func.count()).select_from(BehaviorSession).where(
        BehaviorSession.utm_medium == "newsletter", BehaviorSession.utm_campaign == campaign,
        BehaviorSession.started_at >= first_sent)) or 0)
    out["sessions_from_mail"] = total_sessions
    out["sessions_without_person"] = max(0, total_sessions - len(matched))

    sids = [sid for _m, _b, sid in human_clicks if sid]
    viewed: Counter[str] = Counter()
    by_event: Counter[str] = Counter()
    if sids:
        ind = FrontendEvent.params_json["indicator"].as_string()
        for name, indicator, n in (await db.execute(
                select(FrontendEvent.event_name, ind, func.count())
                .where(FrontendEvent.session_id_hash.in_(sids)).group_by(FrontendEvent.event_name, ind))).all():
            by_event[name] += int(n)
            if name in ("indicator_view", "region_indicator_view") and indicator:
                viewed[str(indicator)] += int(n)
    from app.services.goal_taxonomy import GROUP_DOWNLOAD, events_in_group

    downloads = sum(n for name, n in by_event.items() if name in events_in_group(GROUP_DOWNLOAD))
    out["visit"] = {
        "events": sum(by_event.values()), "indicator_views": sum(viewed.values()),
        "top_viewed": dict(viewed.most_common(7)), "downloads": downloads,
        "forecast_views": by_event.get("forecast_view", 0), "searches": by_event.get("search_query", 0),
        "events_per_session": round(sum(by_event.values()) / len(sids), 1) if sids else None,
    }

    # --- вернулись ли ------------------------------------------------------------
    users = {str(m.user_id): m for m in delivered if m.user_id}
    visitor_owner: dict[str, str | None] = {}
    if users:
        for uid, vid in (await db.execute(select(IdentityLink.user_id, IdentityLink.visitor_id_hash)
                                          .where(IdentityLink.user_id.in_(list(users))))).all():
            visitor_owner[vid] = None if vid in visitor_owner and visitor_owner[vid] != uid else uid
    visits: dict[str, list[tuple[datetime, bool]]] = defaultdict(list)   # человек → (время, из письма)
    if users:
        from sqlalchemy import or_

        cond = [BehaviorSession.user_id.in_(list(users))]
        vids = [v for v, u in visitor_owner.items() if u]
        if vids:
            cond.append(BehaviorSession.visitor_id_hash.in_(vids))
        for uid, vid, started, medium, camp, webdriver in (await db.execute(
                select(BehaviorSession.user_id, BehaviorSession.visitor_id_hash, BehaviorSession.started_at,
                       BehaviorSession.utm_medium, BehaviorSession.utm_campaign, BehaviorSession.is_webdriver)
                .where(or_(*cond), BehaviorSession.started_at >= first_sent - timedelta(days=30),
                       BehaviorSession.started_at < first_sent + timedelta(days=31)))).all():
            who = uid if uid in users else visitor_owner.get(vid)
            if who in users and not webdriver:
                visits[who].append((started, medium == "newsletter" and camp == campaign))
    returned: dict[str, dict] = {}
    for days in RETURN_WINDOWS:
        complete = age_days >= days
        came = came_before = 0
        for uid, m in users.items():
            sent = m.sent_at or first_sent
            if any(sent <= t < sent + timedelta(days=days) for t, _ in visits.get(uid, ())):
                came += 1
            if any(sent - timedelta(days=days) <= t < sent for t, _ in visits.get(uid, ())):
                came_before += 1
        returned[f"d{days}"] = {"people": came, "pct": _pct(came, len(users)), "window_complete": complete,
                                "same_window_before_send": came_before}
    out["returned"] = returned
    again = 0
    for uid, m in users.items():
        if not m.clicked_at:
            continue
        day = m.clicked_at.date()
        if any(t.date() > day and t < m.clicked_at + timedelta(days=7) for t, _ in visits.get(uid, ())):
            again += 1
    out["clickers_back_another_day_d7"] = again
    out["recipients_with_account"] = len(users)

    # --- отписки, отказ от подборки, жалобы ---------------------------------------
    uids = [m.user_id for m in delivered if m.user_id]
    kinds = Counter()
    if uids:
        for kind, n in (await db.execute(
                select(Consent.kind, func.count(func.distinct(Consent.user_id)))
                .where(Consent.user_id.in_(uids), Consent.granted_at >= first_sent,
                       Consent.granted_at < first_sent + timedelta(days=30),
                       Consent.kind.in_(("newsletter_revoked", "mail_personal_revoked")))
                .group_by(Consent.kind))).all():
            kinds[kind] = int(n)
        complaints = int(await db.scalar(select(func.count()).select_from(MailSuppression).where(
            MailSuppression.user_id.in_(uids), MailSuppression.reason == "complaint",
            MailSuppression.created_at >= first_sent)) or 0)
    else:
        complaints = 0
    out["unsubscribed"] = kinds.get("newsletter_revoked", 0)
    out["unsubscribe_pct"] = _pct(out["unsubscribed"], len(delivered))
    out["personal_off"] = kinds.get("mail_personal_revoked", 0)
    out["complaints"] = complaints
    return out


async def previous_campaign(db: AsyncSession, campaign: str) -> str | None:
    lst = await campaigns(db, limit=50)
    keys = [c["key"] for c in lst]
    if campaign not in keys:
        return None
    i = keys.index(campaign)
    return keys[i + 1] if i + 1 < len(keys) else None


# --- текст для Telegram --------------------------------------------------------------

def _n(value) -> str:
    return "нет данных" if value is None else str(value).replace(".", ",")


def _delta(cur, prev, unit: str = " п. п.") -> str:
    if cur is None or prev is None:
        return ""
    d = round(cur - prev, 1)
    if d == 0:
        return " (как в прошлом выпуске)"
    return f" ({'+' if d > 0 else '−'}{str(abs(d)).replace('.', ',')}{unit} к прошлому выпуску)"


def format_report(f: dict, prev: dict | None = None, *, stage: str = "") -> str:
    """Отчёт по выпуску для служебного Telegram: простыми словами, только суммы."""
    key = escape(f.get("campaign") or "")
    head = f"✉️ <b>Рассылка {key}</b>" + (f" — {escape(stage)}" if stage else "")
    if not f.get("has_data"):
        st = f.get("statuses") or {}
        why = ", ".join(f"{escape(k)}: {v}" for k, v in sorted(st.items())) or "писем этого выпуска в журнале нет"
        return f"{head}\nНет данных: ни одно письмо не принято почтовым сервером ({why})."
    p = prev if (prev and prev.get("has_data")) else None
    lines = [head]
    lines.append(f"Принято почтой: <b>{f['accepted']}</b> из {f['letters']}; дошло {f['delivered']}, "
                 f"вернулось с отказом {f['bounced']}, не ушло из-за ошибки {f['failed']}.")
    if f.get("not_sent"):
        lines.append("Не отправлялось: " + ", ".join(f"{escape(k)} {v}" for k, v in sorted(f["not_sent"].items())) + ".")
    if f["tracked"]:
        lines.append(f"Открыли: <b>{f['opened_people']}</b> из {f['tracked']} ({_n(f['open_rate_pct'])} %)"
                     f"{_delta(f['open_rate_pct'], p and p.get('open_rate_pct'))}. "
                     f"Ещё {f['opened_machine_only']} открыла почтовая программа без человека — они не в счёте. "
                     f"Доля занижена: почта без картинок открытие не показывает.")
        if f.get("minutes_to_open_median") is not None:
            lines.append(f"Половина открыла за {_n(f['minutes_to_open_median'])} мин после отправки.")
    else:
        lines.append("Открытия: нет данных — учёт открытий был выключен.")
    lines.append(f"Перешли на сайт: <b>{f['clicked_people']}</b> человек ({_n(f['click_rate_pct'])} % от дошедших)"
                 f"{_delta(f['click_rate_pct'], p and p.get('click_rate_pct'))}; визитов из письма {f['click_sessions']}"
                 + (f", ещё {f['sessions_without_person']} визитов без известного человека" if f.get("sessions_without_person") else "")
                 + ".")
    v = f.get("visit") or {}
    if f["click_sessions"]:
        top = ", ".join(f"{escape(k)} ×{n}" for k, n in (v.get("top_viewed") or {}).items()) or "нет данных"
        lines.append(f"В этих визитах: действий {v.get('events', 0)} (в среднем {_n(v.get('events_per_session'))} на визит), "
                     f"открыто показателей {v.get('indicator_views', 0)}, прогнозов {v.get('forecast_views', 0)}, "
                     f"скачиваний {v.get('downloads', 0)}. Смотрели: {top}.")
    if f.get("blocks"):
        parts = [f"{escape(b['label'])} — {b['clicks']}" for b in f["blocks"][:6]]
        lines.append("Какие блоки сработали (переходы): " + "; ".join(parts) + ".")
    r = f.get("returned") or {}
    ret = []
    for days in RETURN_WINDOWS:
        w = r.get(f"d{days}") or {}
        if not w:
            continue
        label = {1: "за сутки", 7: "за 7 суток", 30: "за 30 суток"}[days]
        if w.get("window_complete"):
            ret.append(f"{label} — {w['people']} ({_n(w['pct'])} %; за такой же срок до письма было {w['same_window_before_send']})")
        else:
            ret.append(f"{label} — пока {w['people']}, срок не истёк")
    if ret:
        lines.append(f"Были на сайте после письма (из {f['recipients_with_account']} получателей): " + "; ".join(ret) + ".")
    if f.get("clickers_back_another_day_d7") is not None and f["clicked_people"]:
        lines.append(f"Из перешедших вернулись в другой день в течение недели: {f['clickers_back_another_day_d7']}.")
    lines.append(f"Отписались: {f['unsubscribed']} ({_n(f['unsubscribe_pct'])} %)"
                 f"{_delta(f['unsubscribe_pct'], p and p.get('unsubscribe_pct'))}; отказались от личной подборки: "
                 f"{f['personal_off']}; жалоб на спам: {f['complaints']}.")
    cuts = f.get("cuts") or {}
    var = cuts.get("variant") or {}
    if len([k for k in var if k != "—"]) > 1:
        parts = []
        for name, label in (("personal", "личные"), ("general", "общие")):
            a = var.get(name)
            if a:
                parts.append(f"{label}: дошло {a['delivered']}, открыли {a['opened']}, перешли {a['clicked']}")
        lines.append("Личные и общие письма — " + "; ".join(parts) + ".")
    prov = cuts.get("provider") or {}
    if prov:
        parts = [f"{escape(k)} {a['delivered']}/{a['opened']}/{a['clicked']}"
                 for k, a in sorted(prov.items(), key=lambda kv: -kv[1]["delivered"])[:6]]
        lines.append("По почтовым сервисам (дошло/открыли/перешли): " + ", ".join(parts) + ".")
    need = []
    if f["complaints"]:
        need.append("есть жалобы на спам — следующий выпуск не отправлять, пока не разберём")
    if f["delivered"] and f["bounced"] / max(1, f["accepted"]) > 0.05:
        need.append("отказов больше 5 % — проверить адреса перед следующим выпуском")
    if (f.get("unsubscribe_pct") or 0) > 2:
        need.append("отписок больше 2 % — посмотреть, что в письме оттолкнуло")
    lines.append("Что сделать: " + ("; ".join(need) + "." if need else "ничего, всё в норме."))
    return "\n".join(lines)


async def report_text(db: AsyncSession, campaign: str | None = None, *, stage: str = "",
                      now: datetime | None = None) -> str:
    """Отчёт по выпуску (последнему, если ключ не назван) с сравнением с предыдущим."""
    if campaign is None:
        lst = await campaigns(db, limit=1)
        if not lst:
            return ("✉️ <b>Рассылка</b>\nНет данных: ни один выпуск ещё не отправлялся людям "
                    "(в журнале писем нет принятых писем рассылки).")
        campaign = lst[0]["key"]
    cur = await campaign_funnel(db, campaign, now=now)
    prev_key = await previous_campaign(db, campaign)
    prev = await campaign_funnel(db, prev_key, now=now) if prev_key else None
    return format_report(cur, prev, stage=stage)


# --- задача: итог через сутки и через 7 суток -------------------------------------------

REPORT_STAGES = ((1, "итог за первые сутки"), (7, "итог за 7 суток"))
_STATE_KEY = "fe:mail_report:{campaign}:d{days}"


async def newsletter_report_job() -> int:
    """Утром: по каждому выпуску — итог через сутки и через 7 суток, по одному разу. Сколько отправлено."""
    from app.config import settings
    from app.core.cache import get_state_redis
    from app.database import async_session
    from app.services.mail import tracking
    from app.services.alerting import digest_recipients
    from app.services.telegram_bot import send_message

    if not (settings.mail_report_enabled and settings.telegram_bot_token):
        return 0
    recipients = set(digest_recipients())
    if settings.pulse_chat_id:
        recipients.add(str(settings.pulse_chat_id))
    if not recipients:
        return 0
    r = await get_state_redis()
    now = _now()
    sent = 0
    async with async_session() as db:
        await tracking.sync_clicks(db, now=now)
        await db.commit()
        for c in await campaigns(db, limit=20):
            age = (now - c["first_sent"]).total_seconds() / 86400.0
            for days, stage in REPORT_STAGES:
                if age < days or age > days + 3:
                    continue
                key = _STATE_KEY.format(campaign=c["key"], days=days)
                if await r.get(key):
                    continue
                text = await report_text(db, c["key"], stage=stage, now=now)
                ok = False
                for cid in sorted(recipients):
                    ok = await send_message(cid, text, kind="newsletter_report", link_preview=False) or ok
                if ok:
                    await r.set(key, "1", ex=40 * 86400)
                    sent += 1
    return sent
