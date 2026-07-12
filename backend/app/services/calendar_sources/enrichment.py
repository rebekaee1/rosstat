"""Enrich official calendar events from IndicatorData already in the DB.

ADR-0005: we do not invent estimated dates. Matching a published data point
to an existing official_rule/explicit event and marking it released is OK —
the release already happened; the calendar just lagged the scheduled_date.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

from sqlalchemy import select
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


async def enrich_events_from_indicator_data(db: AsyncSession) -> int:
    """Set actual_value + status=released when reference_period has a data point.

    Returns number of events updated.
    """
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

    # Collect (indicator_id, date) lookups we need
    needed: dict[int, set[date]] = {}
    parsed_by_event: dict[int, date] = {}
    for ev, ind in rows:
        if ind is None:
            continue
        ref_date = parse_reference_period_date(ev.reference_period)
        if ref_date is None:
            continue
        parsed_by_event[ev.id] = ref_date
        needed.setdefault(ind.id, set()).add(ref_date)

    if not needed:
        return 0

    # Batch-load matching points
    values: dict[tuple[int, date], float] = {}
    for ind_id, dates in needed.items():
        pts = await db.execute(
            select(IndicatorData.date, IndicatorData.value).where(
                IndicatorData.indicator_id == ind_id,
                IndicatorData.date.in_(dates),
            )
        )
        for d, v in pts.all():
            values[(ind_id, d)] = float(v)

    updated = 0
    for ev, ind in rows:
        if ind is None or ev.id not in parsed_by_event:
            continue
        ref_date = parsed_by_event[ev.id]
        val = values.get((ind.id, ref_date))
        if val is None:
            continue
        actual_str = _format_actual(val)
        changed = False
        if ev.actual_value != actual_str:
            ev.actual_value = actual_str
            changed = True
        if ev.status != "released":
            ev.status = "released"
            changed = True
        if ev.actual_date is None:
            ev.actual_date = ref_date
            changed = True
        if changed:
            ev.updated_at = now
            updated += 1

    if updated:
        await db.commit()
        logger.info("Calendar enrichment: marked %d events released from IndicatorData", updated)
    return updated
