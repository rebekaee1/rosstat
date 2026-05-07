"""
Seed economic calendar events as a rolling 12-month window.

Sources synchronised with the official publication calendars:
  * CBR rate meetings — cbr.ru/dkp/cal_mp/ (8 regular meetings per year)
  * CBR Statistics Release Calendar — cbr.ru/eng/statistics/indcalendar
      - International Reserves: weekly (Thursdays 16:00) + monthly (~7-8th)
      - Monetary Base (narrow): weekly (Fridays 11:00) + monthly (~3rd)
      - Money Supply M2: monthly (~20th)
      - Balance of Payments / External Debt: quarterly + monthly estimates
  * Rosstat Plan of Statistical Works (rosstat.gov.ru/sdds, rosstat.gov.ru/folder/)
      - CPI: weekly (Wednesdays) + monthly (~6th)
      - Industrial production / unemployment / wages: monthly (~6th)
      - GDP: quarterly (~30-40 days after end of quarter)
      - Retail trade / housing commissioned: monthly (~15th)
  * Minfin federal budget: monthly (~25-30th)

The seeder always populates a rolling [today, today + 12 months] window.
On_conflict_do_nothing makes it idempotent: re-runs only fill gaps.

Run via:
  python -m app.services.calendar_seed
or call seed_calendar(months_ahead=12) from a scheduled job.
"""
from __future__ import annotations

import asyncio
import calendar as cal
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session as async_session_factory
from app.models import EconomicEvent, Indicator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CBR Board of Directors key rate meetings
# ---------------------------------------------------------------------------
# 2026 — published by CBR (cbr.ru/dkp/cal_mp/), 8 meetings: 4 "core" with
# medium-term forecast and 4 interim. Summary discussion is published ~2 weeks
# after each meeting.
CBR_MEETINGS_2026 = [
    {"date": date(2026, 2, 13), "has_forecast": True,  "summary_date": date(2026, 2, 26)},
    {"date": date(2026, 3, 20), "has_forecast": False, "summary_date": date(2026, 4, 1)},
    {"date": date(2026, 4, 24), "has_forecast": True,  "summary_date": date(2026, 5, 12)},
    {"date": date(2026, 6, 19), "has_forecast": False, "summary_date": date(2026, 7, 1)},
    {"date": date(2026, 7, 24), "has_forecast": True,  "summary_date": date(2026, 8, 5)},
    {"date": date(2026, 9, 11), "has_forecast": False, "summary_date": date(2026, 9, 23)},
    {"date": date(2026, 10, 23), "has_forecast": True, "summary_date": date(2026, 11, 4)},
    {"date": date(2026, 12, 18), "has_forecast": False, "summary_date": date(2026, 12, 29)},
]

# 2027 — official calendar publishes in early December 2026; until then use
# approximate Fridays (~6-week cadence with summer recess) and mark
# is_estimated=True in metadata so the UI/list can label them as preliminary.
CBR_MEETINGS_2027_TENTATIVE = [
    {"date": date(2027, 2, 12), "has_forecast": True,  "summary_date": date(2027, 2, 25)},
    {"date": date(2027, 3, 19), "has_forecast": False, "summary_date": date(2027, 4, 1)},
    {"date": date(2027, 4, 23), "has_forecast": True,  "summary_date": date(2027, 5, 13)},
]


# ---------------------------------------------------------------------------
# Rosstat monthly publications
# ---------------------------------------------------------------------------
ROSSTAT_MONTHLY_RELEASES: dict[str, dict] = {
    "cpi": {
        "name": "Индекс потребительских цен (ИПЦ)",
        "name_en": "Consumer Price Index (CPI)",
        "importance": 3,
        "typical_day": 6,
        "description": "Ежемесячная публикация ИПЦ за предыдущий месяц.",
    },
    "ipi": {
        "name": "Индекс промышленного производства (ИПП)",
        "name_en": "Industrial Production Index",
        "importance": 2,
        "typical_day": 6,
    },
    "unemployment": {
        "name": "Уровень безработицы",
        "name_en": "Unemployment Rate",
        "importance": 2,
        "typical_day": 6,
    },
    "wages-nominal": {
        "name": "Средняя номинальная заработная плата",
        "name_en": "Average Nominal Wages",
        "importance": 2,
        "typical_day": 6,
    },
    "retail-trade": {
        "name": "Оборот розничной торговли",
        "name_en": "Retail Trade Turnover",
        "importance": 2,
        "typical_day": 15,
    },
    "housing-commissioned": {
        "name": "Ввод в действие жилых домов",
        "name_en": "Housing Commissioned",
        "importance": 1,
        "typical_day": 15,
    },
    "ppi": {
        "name": "Индекс цен производителей промышленных товаров (ИЦП)",
        "name_en": "Producer Price Index (PPI)",
        "importance": 2,
        "typical_day": 25,
    },
    "construction-work": {
        "name": "Объём работ по виду деятельности «Строительство»",
        "name_en": "Construction Work Volume",
        "importance": 1,
        "typical_day": 18,
    },
}

ROSSTAT_QUARTERLY_RELEASES: dict[str, dict] = {
    "gdp-nominal": {
        "name": "ВВП (предварительная оценка)",
        "name_en": "GDP First Estimate",
        "importance": 3,
        "lag_days": 60,  # ≈Q+60 days for first estimate
    },
    "gdp-real": {
        "name": "ВВП (вторая оценка)",
        "name_en": "GDP Second Estimate",
        "importance": 2,
        "lag_days": 90,
    },
}


# ---------------------------------------------------------------------------
# CBR monthly statistics
# ---------------------------------------------------------------------------
CBR_STAT_MONTHLY: dict[str, dict] = {
    "m2": {
        "name": "Денежная масса М2",
        "name_en": "Money Supply M2",
        "importance": 2,
        "typical_day": 20,
    },
    "international-reserves": {
        "name": "Международные резервы РФ (ежемесячные)",
        "name_en": "International Reserves (monthly)",
        "importance": 2,
        "typical_day": 8,
    },
    "external-debt": {
        "name": "Внешний долг РФ",
        "name_en": "External Debt of the Russian Federation",
        "importance": 1,
        "typical_day": 18,
    },
    "current-account": {
        "name": "Текущий счёт платёжного баланса (оценка)",
        "name_en": "Balance of Payments — current account estimate",
        "importance": 2,
        "typical_day": 17,
    },
}


# ---------------------------------------------------------------------------
# Minfin monthly publications
# ---------------------------------------------------------------------------
MINFIN_MONTHLY: dict[str, dict] = {
    "budget-revenue": {
        "name": "Доходы федерального бюджета",
        "name_en": "Federal Budget Revenue",
        "importance": 2,
        "typical_day": 30,
    },
    "budget-expenditure": {
        "name": "Расходы федерального бюджета",
        "name_en": "Federal Budget Expenditure",
        "importance": 2,
        "typical_day": 30,
    },
}


# ---------------------------------------------------------------------------
# Weekly / recurring events
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WeeklySpec:
    """Recurring event published every week on a fixed weekday."""
    weekday: int                 # 0 = Monday … 6 = Sunday
    indicator_code: str | None   # link to indicator if available, else None
    title: str
    title_en: str
    source: str                  # "cbr" | "rosstat"
    importance: int              # 1, 2, 3
    scheduled_time: str | None   # "HH:MM" MSK or None
    description: str
    source_url: str | None = None


WEEKLY_SPECS: list[WeeklySpec] = [
    WeeklySpec(
        weekday=3,  # Thursday
        indicator_code="international-reserves",
        title="Международные резервы РФ",
        title_en="International Reserves of the Russian Federation (weekly)",
        source="cbr",
        importance=2,
        scheduled_time="16:00",
        description=(
            "Еженедельная публикация международных резервов на конец предыдущей "
            "пятницы. Стандарт МВФ ССРД."
        ),
        source_url="https://www.cbr.ru/hd_base/mrrf/mrrf_7d/",
    ),
    WeeklySpec(
        weekday=4,  # Friday
        indicator_code=None,
        title="Денежная база (узкая)",
        title_en="Monetary Base (Narrow Definition, weekly)",
        source="cbr",
        importance=1,
        scheduled_time="11:00",
        description="Еженедельная публикация узкой денежной базы.",
        source_url="https://cbr.ru/hd_base/mb_nd/mb_nd_weekly/",
    ),
    WeeklySpec(
        weekday=2,  # Wednesday
        indicator_code="cpi",
        title="Недельная инфляция (ИПЦ)",
        title_en="Weekly Consumer Price Index",
        source="rosstat",
        importance=2,
        scheduled_time=None,
        description=(
            "Еженедельный бюллетень об индексе потребительских цен на товары "
            "и услуги (Росстат)."
        ),
        source_url="https://rosstat.gov.ru/price",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
MONTH_NAMES_RU = [
    "", "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]

MONTH_NAMES_EN = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _month_ref(month: int, year: int) -> str:
    return f"{MONTH_NAMES_RU[month]} {year}"


def _month_ref_en(month: int, year: int) -> str:
    return f"{MONTH_NAMES_EN[month]} {year}"


def _safe_date(year: int, month: int, day: int) -> date:
    """Clamp day to last day of month (e.g. Feb 30 → Feb 28)."""
    last_day = cal.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _iter_months(start: date, months_ahead: int) -> Iterable[tuple[int, int]]:
    """Yield (year, month) tuples covering [start, start + months_ahead)."""
    y, m = start.year, start.month
    for _ in range(months_ahead + 1):
        yield (y, m)
        m += 1
        if m > 12:
            m = 1
            y += 1


def _previous_month(y: int, m: int) -> tuple[int, int]:
    if m == 1:
        return (y - 1, 12)
    return (y, m - 1)


def _previous_quarter(y: int, m: int) -> tuple[int, int]:
    """Return (year, quarter_number 1..4) of the quarter that ends before
    month m of year y."""
    quarter_of_release_month = (m - 1) // 3 + 1
    prev_q = quarter_of_release_month - 1
    if prev_q == 0:
        return (y - 1, 4)
    return (y, prev_q)


def _quarter_label(q: int, year: int) -> str:
    return f"Q{q} {year}"


async def _resolve_indicator_ids(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(select(Indicator.code, Indicator.id))
    return {code: id_ for code, id_ in result.all()}


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def _build_cbr_meeting_events(
    meetings: list[dict],
    *,
    is_estimated: bool,
    today: date,
) -> list[dict]:
    events = []
    for m in meetings:
        label = "опорное" if m["has_forecast"] else "промежуточное"
        events.append({
            "title": f"Заседание ЦБ по ключевой ставке ({label})",
            "title_en": f"CBR Key Rate Decision ({'core' if m['has_forecast'] else 'interim'})",
            "event_type": "rate_decision",
            "source": "cbr",
            "indicator_code": "key-rate",
            "scheduled_date": m["date"],
            "scheduled_time": "13:30",
            "is_estimated": is_estimated,
            "importance": 3,
            "status": "released" if m["date"] < today else "scheduled",
            "description": (
                "Пресс-релиз в 13:30 МСК, пресс-конференция в 15:00 МСК."
                + (" С публикацией среднесрочного прогноза." if m["has_forecast"] else "")
            ),
            "source_url": "https://cbr.ru/dkp/cal_mp/",
            "metadata_json": {
                "type": label,
                "has_forecast": m["has_forecast"],
                "tentative": is_estimated,
            },
        })
        events.append({
            "title": "Резюме обсуждения ключевой ставки",
            "title_en": "Key Rate Discussion Summary",
            "event_type": "report",
            "source": "cbr",
            "indicator_code": "key-rate",
            "scheduled_date": m["summary_date"],
            "is_estimated": is_estimated,
            "importance": 2,
            "status": "released" if m["summary_date"] < today else "scheduled",
            "source_url": "https://cbr.ru/dkp/cal_mp/",
        })
    return events


def _build_monthly_release_events(
    releases: dict,
    source: str,
    *,
    today: date,
    months_ahead: int,
) -> list[dict]:
    events: list[dict] = []
    horizon = today + timedelta(days=months_ahead * 31)

    # Iterate over a window that covers today's month plus months_ahead;
    # for each (release_year, release_month) we generate ONE event per indicator
    # whose reference period is the previous calendar month.
    cursor = today.replace(day=1) - timedelta(days=1)  # last day of previous month
    cursor = cursor.replace(day=1)
    end = (today + timedelta(days=(months_ahead + 1) * 31)).replace(day=1)

    while cursor <= end:
        ry, rm = cursor.year, cursor.month
        ref_y, ref_m = _previous_month(ry, rm)
        for code, cfg in releases.items():
            sched = _safe_date(ry, rm, cfg["typical_day"])
            if sched < today - timedelta(days=14):
                # Skip events deep in the past — keep only ~2 weeks of history.
                continue
            if sched > horizon:
                continue
            events.append({
                "title": cfg["name"],
                "title_en": cfg.get("name_en"),
                "event_type": "data_release",
                "source": source,
                "indicator_code": code,
                "scheduled_date": sched,
                "is_estimated": True,
                "reference_period": _month_ref(ref_m, ref_y),
                "importance": cfg["importance"],
                "status": "released" if sched < today else "scheduled",
                "description": cfg.get("description"),
            })
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return events


def _build_quarterly_release_events(
    releases: dict,
    source: str,
    *,
    today: date,
    months_ahead: int,
) -> list[dict]:
    """Quarterly releases — one event per quarter end, lagged by `lag_days`."""
    events: list[dict] = []
    horizon = today + timedelta(days=months_ahead * 31)

    quarter_ends: list[date] = []
    base_year = today.year - 1
    for y in range(base_year, today.year + 3):
        quarter_ends.extend([
            date(y, 3, 31),
            date(y, 6, 30),
            date(y, 9, 30),
            date(y, 12, 31),
        ])

    for code, cfg in releases.items():
        for q_end in quarter_ends:
            sched = q_end + timedelta(days=cfg["lag_days"])
            if sched < today - timedelta(days=14) or sched > horizon:
                continue
            q = (q_end.month - 1) // 3 + 1
            events.append({
                "title": cfg["name"],
                "title_en": cfg.get("name_en"),
                "event_type": "data_release",
                "source": source,
                "indicator_code": code,
                "scheduled_date": sched,
                "is_estimated": True,
                "reference_period": _quarter_label(q, q_end.year),
                "importance": cfg["importance"],
                "status": "released" if sched < today else "scheduled",
            })
    return events


def _build_weekly_events(
    *,
    today: date,
    months_ahead: int,
) -> list[dict]:
    """Generate one event per week per WeeklySpec across the rolling window."""
    events: list[dict] = []
    horizon = today + timedelta(days=months_ahead * 31)

    # Start from the Monday of the week that contains (today - 14d), so a small
    # backlog of the most recent past events is preserved for context.
    start = today - timedelta(days=today.weekday() + 14)
    end = horizon

    for spec in WEEKLY_SPECS:
        # Find the first occurrence of spec.weekday on/after start.
        days_to_target = (spec.weekday - start.weekday()) % 7
        cur = start + timedelta(days=days_to_target)
        while cur <= end:
            events.append({
                "title": spec.title,
                "title_en": spec.title_en,
                "event_type": "data_release",
                "source": spec.source,
                "indicator_code": spec.indicator_code,
                "scheduled_date": cur,
                "scheduled_time": spec.scheduled_time,
                "is_estimated": True,
                "reference_period": None,
                "importance": spec.importance,
                "status": "released" if cur < today else "scheduled",
                "description": spec.description,
                "source_url": spec.source_url,
            })
            cur += timedelta(days=7)
    return events


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def seed_calendar(
    *,
    months_ahead: int = 12,
    today: date | None = None,
    db: AsyncSession | None = None,
) -> int:
    """Idempotently fill the calendar with a rolling [today, +months_ahead] window.

    Returns the number of newly inserted rows. Existing rows are left untouched
    via on_conflict_do_nothing on (source, event_type, scheduled_date, indicator_id).
    """
    today = today or date.today()

    all_events: list[dict] = []
    all_events.extend(_build_cbr_meeting_events(
        CBR_MEETINGS_2026, is_estimated=False, today=today,
    ))
    all_events.extend(_build_cbr_meeting_events(
        CBR_MEETINGS_2027_TENTATIVE, is_estimated=True, today=today,
    ))
    all_events.extend(_build_monthly_release_events(
        ROSSTAT_MONTHLY_RELEASES, "rosstat",
        today=today, months_ahead=months_ahead,
    ))
    all_events.extend(_build_monthly_release_events(
        CBR_STAT_MONTHLY, "cbr",
        today=today, months_ahead=months_ahead,
    ))
    all_events.extend(_build_monthly_release_events(
        MINFIN_MONTHLY, "minfin",
        today=today, months_ahead=months_ahead,
    ))
    all_events.extend(_build_quarterly_release_events(
        ROSSTAT_QUARTERLY_RELEASES, "rosstat",
        today=today, months_ahead=months_ahead,
    ))
    all_events.extend(_build_weekly_events(
        today=today, months_ahead=months_ahead,
    ))

    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)
    all_events = [
        e for e in all_events
        if cutoff <= e["scheduled_date"] <= horizon
    ]

    if db is not None:
        return await _persist_events(db, all_events)

    async with async_session_factory() as session:
        return await _persist_events(session, all_events)


async def _cleanup_legacy_orphans(db: AsyncSession) -> int:
    """Remove events from earlier seed iterations whose `indicator_code` did
    not exist in the catalogue (indicator_id IS NULL) but for which the new
    seeder produces a properly-linked event on the same date/title.

    The unique constraint treats two NULL indicator_ids as distinct rows
    (PostgreSQL standard SQL behaviour), so without this cleanup the same
    Thursday "Международные резервы РФ" can appear twice.
    """
    from sqlalchemy import text as _text

    stmt = _text(
        """
        DELETE FROM economic_events e1
        WHERE e1.indicator_id IS NULL
          AND EXISTS (
              SELECT 1 FROM economic_events e2
              WHERE e2.id <> e1.id
                AND e2.scheduled_date = e1.scheduled_date
                AND e2.source = e1.source
                AND e2.event_type = e1.event_type
                AND e2.title = e1.title
                AND e2.indicator_id IS NOT NULL
          )
        """
    )
    result = await db.execute(stmt)
    return result.rowcount or 0


async def _cleanup_orphan_duplicates(db: AsyncSession) -> int:
    """Drop duplicates among events with NULL indicator_id, keeping the lowest id."""
    from sqlalchemy import text as _text

    stmt = _text(
        """
        DELETE FROM economic_events e
        WHERE e.indicator_id IS NULL
          AND e.id > (
              SELECT MIN(e2.id) FROM economic_events e2
              WHERE e2.indicator_id IS NULL
                AND e2.scheduled_date = e.scheduled_date
                AND e2.source = e.source
                AND e2.event_type = e.event_type
                AND e2.title = e.title
          )
        """
    )
    result = await db.execute(stmt)
    return result.rowcount or 0


async def _persist_events(db: AsyncSession, events: list[dict]) -> int:
    code_to_id = await _resolve_indicator_ids(db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    inserted = 0
    for ev_data in events:
        ev_data = dict(ev_data)  # don't mutate caller's data
        code = ev_data.pop("indicator_code", None)
        ind_id = code_to_id.get(code) if code else None
        ev_data["indicator_id"] = ind_id
        ev_data["created_at"] = now
        ev_data["updated_at"] = now

        if ind_id is None:
            # PostgreSQL treats NULLs as distinct in unique constraints, so we
            # cannot rely on uq_event_natural_key for orphan rows. Manually
            # check (source, event_type, scheduled_date, title) before insert.
            existing = await db.execute(
                select(EconomicEvent.id).where(
                    EconomicEvent.source == ev_data["source"],
                    EconomicEvent.event_type == ev_data["event_type"],
                    EconomicEvent.scheduled_date == ev_data["scheduled_date"],
                    EconomicEvent.indicator_id.is_(None),
                    EconomicEvent.title == ev_data["title"],
                )
            )
            if existing.first():
                continue

        stmt = pg_insert(EconomicEvent).values(**ev_data)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_event_natural_key")
        result = await db.execute(stmt)
        if result.rowcount:
            inserted += 1

    cleaned = await _cleanup_legacy_orphans(db)
    if cleaned:
        logger.info("Calendar seed: removed %d legacy orphan duplicates", cleaned)

    cleaned_unlinked = await _cleanup_orphan_duplicates(db)
    if cleaned_unlinked:
        logger.info("Calendar seed: dedup'd %d unlinked event duplicates", cleaned_unlinked)

    await db.commit()
    logger.info(
        "Calendar seed: %d events inserted (total candidates: %d)",
        inserted, len(events),
    )
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_calendar())
