"""Enrich official calendar events from IndicatorData already in the DB.

ADR-0005: we do not invent estimated dates. Matching a published data point
to an existing official_rule/explicit event and marking it released is OK —
the release already happened; the calendar just lagged the scheduled_date.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EconomicEvent, Indicator, IndicatorData
from app.services.display import format_number_ru

logger = logging.getLogger(__name__)

MONTH_NAMES_RU = [
    "", "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]

_MONTH_REF_RE = re.compile(
    r"(январ\w*|феврал\w*|март\w*|апрел\w*|ма[йя]|июн\w*|июл\w*|"
    r"август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)\s+(20\d{2})",
    re.IGNORECASE,
)
_QUARTER_REF_RE = re.compile(r"Q([1-4])\s+(20\d{2})", re.IGNORECASE)

# First month of each quarter → stored GDP-style date (month = quarter end month).
_QUARTER_STORE_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}


def parse_reference_period_date(reference_period: str | None) -> date | None:
    """Map calendar reference_period to IndicatorData.date (1st of period month)."""
    if not reference_period:
        return None
    text = reference_period.strip()
    qm = _QUARTER_REF_RE.search(text)
    if qm:
        q, year = int(qm.group(1)), int(qm.group(2))
        return date(year, _QUARTER_STORE_MONTH[q], 1)
    mm = _MONTH_REF_RE.search(text)
    if not mm:
        return None
    stem = mm.group(1).lower()
    year = int(mm.group(2))
    for idx, name in enumerate(MONTH_NAMES_RU):
        if idx == 0:
            continue
        if stem.startswith(name[:4]) or name.startswith(stem[:4]):
            return date(year, idx, 1)
    # «май» is short — stem may be «май»/«мая»
    if stem.startswith("ма"):
        return date(year, 5, 1)
    return None


def months_ahead_of_latest(ref: date, latest: date) -> int:
    """How many calendar months `ref` is ahead of `latest` (0 = same month)."""
    return (ref.year - latest.year) * 12 + (ref.month - latest.month)


def should_advertise_rosstat_monthly_ref(
    reference_period: str | None,
    latest_data: date | None,
    *,
    max_months_ahead: int = 1,
) -> bool:
    """Suppress speculative far-future Rosstat monthly refs beyond latest+N."""
    if latest_data is None:
        return True  # no data yet — keep official rule window as-is
    ref = parse_reference_period_date(reference_period)
    if ref is None:
        return True
    return months_ahead_of_latest(ref, latest_data) <= max_months_ahead


def _format_actual(value: float) -> str:
    text = format_number_ru(value)
    return text[:50] if text else str(value)[:50]


async def load_latest_data_dates(
    db: AsyncSession,
    codes: set[str],
) -> dict[str, date]:
    """Latest IndicatorData.date per indicator code."""
    if not codes:
        return {}
    from sqlalchemy import func

    result = await db.execute(
        select(Indicator.code, func.max(IndicatorData.date))
        .join(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(Indicator.code.in_(codes))
        .group_by(Indicator.code)
    )
    return {code: dt for code, dt in result.all() if dt is not None}


async def filter_speculative_rosstat_monthly(
    db: AsyncSession,
    candidates: list,
) -> list:
    """Drop rosstat monthly rule candidates >1 month ahead of latest data."""
    from app.services.calendar_sources.common import CalendarCandidate

    rosstat_codes = {
        c.indicator_code
        for c in candidates
        if isinstance(c, CalendarCandidate)
        and c.source == "rosstat"
        and c.date_confidence == "official_rule"
        and c.indicator_code
        and c.reference_period
        and not (c.reference_period or "").upper().startswith("Q")
    }
    latest = await load_latest_data_dates(db, rosstat_codes)
    kept = []
    suppressed = 0
    for c in candidates:
        if (
            isinstance(c, CalendarCandidate)
            and c.source == "rosstat"
            and c.date_confidence == "official_rule"
            and c.indicator_code in latest
            and c.reference_period
            and not (c.reference_period or "").upper().startswith("Q")
            and not should_advertise_rosstat_monthly_ref(
                c.reference_period, latest.get(c.indicator_code),
            )
        ):
            suppressed += 1
            continue
        kept.append(c)
    if suppressed:
        logger.info(
            "Calendar: suppressed %d speculative rosstat monthly refs "
            "(>1 month ahead of latest data)",
            suppressed,
        )
    return kept


async def prune_persisted_speculative_rosstat_monthly(db: AsyncSession) -> int:
    """Delete already-stored rosstat monthly events that are too far ahead of data.

    Candidate filter alone leaves stale rows from earlier syncs (A1: wages «июнь»
    while series ends in April). ADR-0005: we do not invent dates — removing a
    speculative advertisement is not inventing one.
    """
    result = await db.execute(
        select(EconomicEvent, Indicator)
        .join(Indicator, EconomicEvent.indicator_id == Indicator.id)
        .where(
            EconomicEvent.source == "rosstat",
            EconomicEvent.date_confidence == "official_rule",
            EconomicEvent.is_estimated.is_(False),
            EconomicEvent.reference_period.is_not(None),
            EconomicEvent.status == "scheduled",
        )
    )
    rows = result.all()
    if not rows:
        return 0

    codes = {ind.code for _, ind in rows if ind is not None}
    latest = await load_latest_data_dates(db, codes)
    removed = 0
    for ev, ind in rows:
        if ind is None or ind.code not in latest:
            continue
        ref = ev.reference_period or ""
        if ref.upper().startswith("Q"):
            continue
        if should_advertise_rosstat_monthly_ref(ref, latest.get(ind.code)):
            continue
        await db.delete(ev)
        removed += 1
    if removed:
        await db.commit()
        logger.info(
            "Calendar: pruned %d persisted speculative rosstat monthly events",
            removed,
        )
    return removed


# Выпуск, который не даёт новой точки в ряду показателя (предварительная оценка ВВП — только
# темп, ряд пополнится на первой оценке), не подтверждается из ряда: иначе ему достался бы
# чужой факт.
def _confirmable(ev: EconomicEvent) -> bool:
    details = ((ev.metadata_json or {}).get("provenance") or {}).get("details") or {}
    return not (details.get("no_data_confirmation") or str(ev.event_key or "").endswith(":flash"))


def _msk_date(moment: datetime | None) -> date | None:
    if moment is None:
        return None
    return (moment + timedelta(hours=3)).date()


def _stamp_release(ev: EconomicEvent, *, value: float, point_date: date, created_at: datetime | None,
                   previous: float | None, via: str, now: datetime) -> bool:
    """Записать факт выхода; True — что-то поменялось."""
    actual_str = _format_actual(value)
    prev_str = _format_actual(previous) if previous is not None else None
    changed = False
    if ev.actual_value != actual_str:
        ev.actual_value = actual_str
        changed = True
    if ev.status != "released":
        ev.status = "released"
        changed = True
    if ev.actual_date is None:
        ev.actual_date = point_date
        changed = True
    if prev_str and not ev.previous_value:
        ev.previous_value = prev_str
        changed = True
    metadata = dict(ev.metadata_json or {})
    fact = dict(metadata.get("release_fact") or {})
    seen_on = _msk_date(created_at)
    wanted = {
        "via": via,
        "point_date": point_date.isoformat(),
        "seen_on": seen_on.isoformat() if seen_on else fact.get("seen_on"),
    }
    if any(fact.get(k) != v for k, v in wanted.items()):
        fact.update(wanted)
        metadata["release_fact"] = fact
        ev.metadata_json = metadata
        changed = True
    if changed:
        ev.updated_at = now
    return changed


async def _previous_point(db: AsyncSession, indicator_id: int, before: date) -> float | None:
    row = (await db.execute(
        select(IndicatorData.value)
        .where(IndicatorData.indicator_id == indicator_id, IndicatorData.date < before)
        .order_by(IndicatorData.date.desc())
        .limit(1)
    )).first()
    return float(row[0]) if row else None


async def enrich_events_from_indicator_data(db: AsyncSession, *, today: date | None = None) -> int:
    """Отметить выход события с отчётным периодом, когда точка этого периода есть в ряду.

    Точка периода подтверждает выпуск, если дата выпуска уже наступила или точка пришла не
    раньше чем за 7 дней до неё (источник опубликовал раньше графика). 14.11.2026: второй выпуск
    ВВП за квартал (уточнение) получал «вышло» ещё за три недели до своей даты — по точке
    первого выпуска. Кроме значения пишется предыдущее значение ряда и день, когда факт
    появился в нашей загрузке.
    """
    from app.services.display import today_msk

    today = today or today_msk()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(
        select(EconomicEvent, Indicator)
        .outerjoin(Indicator, EconomicEvent.indicator_id == Indicator.id)
        .where(
            EconomicEvent.indicator_id.is_not(None),
            EconomicEvent.reference_period.is_not(None),
            EconomicEvent.is_estimated.is_(False),
        )
    )
    rows = result.all()
    if not rows:
        return 0

    needed: dict[int, set[date]] = {}
    parsed_by_event: dict[int, date] = {}
    for ev, ind in rows:
        if ind is None or not _confirmable(ev):
            continue
        ref_date = parse_reference_period_date(ev.reference_period)
        if ref_date is None:
            continue
        parsed_by_event[ev.id] = ref_date
        needed.setdefault(ind.id, set()).add(ref_date)

    if not needed:
        return 0

    points: dict[tuple[int, date], tuple[float, datetime | None]] = {}
    for ind_id, dates in needed.items():
        pts = await db.execute(
            select(IndicatorData.date, IndicatorData.value, IndicatorData.created_at).where(
                IndicatorData.indicator_id == ind_id,
                IndicatorData.date.in_(dates),
            )
        )
        for d, v, created in pts.all():
            points[(ind_id, d)] = (float(v), created)

    updated = 0
    for ev, ind in rows:
        if ind is None or ev.id not in parsed_by_event:
            continue
        ref_date = parsed_by_event[ev.id]
        hit = points.get((ind.id, ref_date))
        if hit is None:
            continue
        value, created = hit
        seen_on = _msk_date(created)
        due = ev.scheduled_date <= today or (
            seen_on is not None and seen_on >= ev.scheduled_date - timedelta(days=7)
        )
        if not due:
            continue
        previous = await _previous_point(db, ind.id, ref_date) if not ev.previous_value else None
        if _stamp_release(ev, value=value, point_date=ref_date, created_at=created,
                          previous=previous, via="reference_period", now=now):
            updated += 1

    if updated:
        await db.commit()
        logger.info("Calendar enrichment: marked %d events released from IndicatorData", updated)
    return updated


# Сколько дней после даты выпуска ждём новую точку в загрузке, и как далеко назад смотрим.
LOAD_CONFIRM_WINDOW_DAYS = 4
LOAD_CONFIRM_LOOKBACK_DAYS = 75
# Дневные публикации ЦБ: курс, установленный в день D, ряд хранит датой следующего дня
# (после пятницы — субботой или понедельником); RUONIA за день D выходит на следующий рабочий день.
_DAILY_POINT_OFFSET = {
    "usd-rub": (0, 4), "eur-rub": (0, 4), "cny-rub": (0, 4), "gold-price": (0, 4),
    "ruonia": (-4, 0),
}


async def confirm_releases_from_loads(db: AsyncSession, *, today: date | None = None) -> int:
    """Отметить выход событий без отчётного периода по факту нашей загрузки.

    До 14.11.2026 у событий ЦБ (заседания по ставке, резервы, денежная масса, ставки, курсы)
    не было отчётного периода, и они навсегда оставались «ожидает подтверждения»: заседание
    23 октября через три недели было «ориентировочно». Теперь выход подтверждает загрузка:
    - дневные ряды ЦБ — точка с датой рядом с днём выпуска (``_DAILY_POINT_OFFSET``);
    - решение по ключевой ставке — значение ставки, действующее после заседания;
    - остальные — самая поздняя по дате точка из первой загрузки в день выпуска или в
      следующие 4 дня (ЦБ грузится тем же вечером; дольше — уже следующая публикация ряда).
    """
    from app.services.display import today_msk

    today = today or today_msk()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = (await db.execute(
        select(EconomicEvent, Indicator)
        .join(Indicator, EconomicEvent.indicator_id == Indicator.id)
        .where(
            EconomicEvent.reference_period.is_(None),
            EconomicEvent.is_estimated.is_(False),
            EconomicEvent.scheduled_date <= today,
            EconomicEvent.scheduled_date >= today - timedelta(days=LOAD_CONFIRM_LOOKBACK_DAYS),
            EconomicEvent.event_type.in_(("data_release", "rate_decision")),
            or_(EconomicEvent.actual_value.is_(None), EconomicEvent.actual_value == ""),
        )
    )).all()
    updated = 0
    for ev, ind in rows:
        if not _confirmable(ev):
            continue
        hit = await _load_fact_for(db, ev, ind)
        if hit is None:
            continue
        point_date, value, created = hit
        previous = await _previous_point(db, ind.id, point_date)
        if _stamp_release(ev, value=value, point_date=point_date, created_at=created,
                          previous=previous, via="load", now=now):
            updated += 1
    if updated:
        await db.commit()
        logger.info("Calendar: %d events confirmed from our data loads", updated)
    return updated


async def _load_fact_for(db: AsyncSession, ev: EconomicEvent, ind: Indicator):
    day = ev.scheduled_date
    # Начало дня выпуска по Москве в UTC (created_at хранится в UTC без зоны).
    day_start_utc = datetime(day.year, day.month, day.day) - timedelta(hours=3)
    window_end_utc = day_start_utc + timedelta(days=LOAD_CONFIRM_WINDOW_DAYS + 1)

    if ind.code in _DAILY_POINT_OFFSET:
        lo, hi = _DAILY_POINT_OFFSET[ind.code]
        if hi > 0:
            # Курс на следующий день — ближайшая точка после дня выпуска.
            stmt = (
                select(IndicatorData.date, IndicatorData.value, IndicatorData.created_at)
                .where(IndicatorData.indicator_id == ind.id,
                       IndicatorData.date > day,
                       IndicatorData.date <= day + timedelta(days=hi))
                .order_by(IndicatorData.date.asc())
            )
        else:
            # RUONIA — последняя точка не позже дня выпуска, загруженная в этот день или позже.
            stmt = (
                select(IndicatorData.date, IndicatorData.value, IndicatorData.created_at)
                .where(IndicatorData.indicator_id == ind.id,
                       IndicatorData.date >= day + timedelta(days=lo),
                       IndicatorData.date <= day,
                       IndicatorData.created_at >= day_start_utc)
                .order_by(IndicatorData.date.desc())
            )
        row = (await db.execute(stmt.limit(1))).first()
        return (row[0], float(row[1]), row[2]) if row else None

    if ev.event_type == "rate_decision":
        # Ставка, действующая после заседания: первая точка с датой позже заседания
        # (новая ставка вступает в силу со следующего рабочего дня).
        row = (await db.execute(
            select(IndicatorData.date, IndicatorData.value, IndicatorData.created_at)
            .where(IndicatorData.indicator_id == ind.id, IndicatorData.date > day,
                   IndicatorData.date <= day + timedelta(days=LOAD_CONFIRM_WINDOW_DAYS))
            .order_by(IndicatorData.date.asc())
            .limit(1)
        )).first()
        return (row[0], float(row[1]), row[2]) if row else None

    first = (await db.execute(
        select(func.min(IndicatorData.created_at)).where(
            IndicatorData.indicator_id == ind.id,
            IndicatorData.created_at >= day_start_utc,
            IndicatorData.created_at < window_end_utc,
        )
    )).scalar()
    if first is None:
        return None
    # Точки одной загрузки пишутся в пределах минут; берём самую позднюю по дате.
    row = (await db.execute(
        select(IndicatorData.date, IndicatorData.value, IndicatorData.created_at)
        .where(
            IndicatorData.indicator_id == ind.id,
            IndicatorData.created_at >= first,
            IndicatorData.created_at < first + timedelta(hours=1),
            IndicatorData.date <= day,
        )
        .order_by(IndicatorData.date.desc())
        .limit(1)
    )).first()
    return (row[0], float(row[1]), row[2]) if row else None
