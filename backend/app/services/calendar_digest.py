"""Календарь в утренней сводке (спокойный режим, 14.11.2026, утверждено владельцем).

1. Сторож календаря (``calendar_watchdog_enabled``, по умолчанию включён): пишет строку, только
   если что-то не так — источник дат не отвечал больше 36 часов (по ``last_seen_at`` его событий)
   или у главного показателя нет ни одной будущей даты на 45 дней вперёд. Тогда «календарь устарел»
   видно в сводке раньше, чем это заметит посетитель.
2. Строка «сегодня в календаре» (``telegram_calendar_today_enabled``, по умолчанию выключена):
   важные выпуски дня и переносы дат, которые источники сделали за сутки.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EconomicEvent, Indicator

logger = logging.getLogger(__name__)

# Источник дат → условие на ключ его событий и понятное имя.
FEEDS = (
    ("cbr:key-rate-", "Банк России, решения по ставке"),
    ("cbr:ics:", "Банк России, календарь статистики"),
    ("rosstat:plan:", "Росстат, график срочных публикаций"),
    ("rosstat:sep:", "Росстат, график докладов"),
    ("world:fed:", "ФРС США"),
    ("world:bea:", "BEA (США)"),
    ("world:eurostat:", "Eurostat"),
)
FEED_STALE_HOURS = 36
# Главные показатели, у которых в календаре всегда должна быть следующая дата.
KEY_CODES = {
    "cpi": "инфляция (ИПЦ)", "key-rate": "ключевая ставка", "ipi": "промышленное производство",
    "ppi": "цены производителей", "unemployment": "безработица", "wages-nominal": "зарплата",
    "retail-trade": "розничная торговля", "gdp-real": "ВВП", "budget-revenue": "бюджет",
}
GAP_DAYS = 45
_MONTHS_GEN = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
               "сентября", "октября", "ноября", "декабря")


def _day(d: date) -> str:
    return f"{d.day} {_MONTHS_GEN[d.month - 1]}"


async def watchdog_lines(db: AsyncSession, *, now: datetime | None = None, today: date | None = None) -> list[str]:
    from app.api.calendar import _public_calendar_conditions

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    today = today or (now + timedelta(hours=3)).date()
    problems: list[str] = []
    for prefix, name in FEEDS:
        last = (await db.execute(
            select(func.max(EconomicEvent.last_seen_at)).where(EconomicEvent.event_key.like(f"{prefix}%"))
        )).scalar()
        if last is None:
            continue  # источник ещё ни разу не отвечал — это не поломка, а «не подключён»
        hours = (now - last).total_seconds() / 3600
        if hours > FEED_STALE_HOURS:
            problems.append(f"{name} — не отвечает {int(hours // 24)} сут.")
    rows = (await db.execute(
        select(Indicator.code, func.min(EconomicEvent.scheduled_date))
        .join(EconomicEvent, EconomicEvent.indicator_id == Indicator.id)
        .where(Indicator.code.in_(tuple(KEY_CODES)),
               EconomicEvent.scheduled_date >= today,
               *_public_calendar_conditions())
        .group_by(Indicator.code)
    )).all()
    nearest = {code: d for code, d in rows}
    gaps = [label for code, label in KEY_CODES.items()
            if code not in nearest or nearest[code] > today + timedelta(days=GAP_DAYS)]
    if gaps:
        problems.append(f"нет даты на {GAP_DAYS} дней: " + ", ".join(gaps))
    if not problems:
        return []
    return ["<b>Календарь:</b> " + escape("; ".join(problems)) + "."]


async def today_lines(db: AsyncSession, *, now: datetime | None = None, today: date | None = None) -> list[str]:
    from app.api.calendar import RUSSIAN_SOURCES, WORLD_SOURCES, _public_calendar_conditions

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    today = today or (now + timedelta(hours=3)).date()
    events = (await db.execute(
        select(EconomicEvent)
        .where(EconomicEvent.scheduled_date == today, EconomicEvent.importance >= 2,
               EconomicEvent.source.in_(RUSSIAN_SOURCES + WORLD_SOURCES),
               EconomicEvent.date_confidence != "official_rule",  # ежедневные курсы не перечисляем
               *_public_calendar_conditions())
        .order_by(EconomicEvent.scheduled_time, EconomicEvent.importance.desc())
    )).scalars().all()
    seen: list[str] = []
    for ev in events:
        label = ev.title + (f" {ev.scheduled_time}" if ev.scheduled_time else "")
        if label not in seen:
            seen.append(label)
    moved: list[str] = []
    recent = (await db.execute(
        select(EconomicEvent).where(EconomicEvent.updated_at >= now - timedelta(hours=26),
                                    EconomicEvent.scheduled_date >= today,
                                    *_public_calendar_conditions())
    )).scalars().all()
    for ev in recent:
        audit = (ev.metadata_json or {}).get("reschedule_audit") or []
        if not audit:
            continue
        last = audit[-1]
        try:
            fetched = datetime.fromisoformat(str(last.get("fetched_at")))
            old = date.fromisoformat(str(last.get("previous_date")))
        except ValueError:
            continue
        if fetched < now - timedelta(hours=26) or old == ev.scheduled_date:
            continue
        ref = f" за {ev.reference_period}" if ev.reference_period else ""
        item = f"{ev.title}{ref}: {_day(old)} → {_day(ev.scheduled_date)}"
        if item not in moved:
            moved.append(item)
    lines = []
    if seen:
        lines.append("<b>Сегодня в календаре:</b> " + escape("; ".join(seen[:8])) + ".")
    if moved:
        lines.append("<b>Источники перенесли:</b> " + escape("; ".join(moved[:5])) + ".")
    return lines


async def morning_calendar_lines() -> list[str]:
    """Строки для утренней сводки; сбой базы не ломает сводку."""
    from app.config import settings
    from app.database import async_session

    out: list[str] = []
    try:
        async with async_session() as db:
            if getattr(settings, "telegram_calendar_today_enabled", False):
                out += await today_lines(db)
            if getattr(settings, "calendar_watchdog_enabled", True):
                out += await watchdog_lines(db)
    except Exception:  # noqa: BLE001
        logger.warning("calendar digest lines failed", exc_info=True)
    return out
