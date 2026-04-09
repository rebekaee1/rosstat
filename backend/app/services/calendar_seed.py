"""
Seed economic calendar events for 2026.

Sources:
  - CBR key rate meetings: cbr.ru/dkp/cal_mp/ (8 regular meetings)
  - CBR key rate summaries: published ~2 weeks after each meeting
  - Minfin ARC / SDDS: approximate release dates for Rosstat indicators

Run via: python -m app.services.calendar_seed
"""
import asyncio
import logging
from datetime import date, datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session as async_session_factory
from app.models import EconomicEvent, Indicator

logger = logging.getLogger(__name__)

CBR_MEETINGS_2026 = [
    {
        "date": date(2026, 2, 13),
        "has_forecast": True,
        "summary_date": date(2026, 2, 26),
    },
    {
        "date": date(2026, 3, 20),
        "has_forecast": False,
        "summary_date": date(2026, 4, 1),
    },
    {
        "date": date(2026, 4, 24),
        "has_forecast": True,
        "summary_date": date(2026, 5, 12),
    },
    {
        "date": date(2026, 6, 19),
        "has_forecast": False,
        "summary_date": date(2026, 7, 1),
    },
    {
        "date": date(2026, 7, 24),
        "has_forecast": True,
        "summary_date": date(2026, 8, 5),
    },
    {
        "date": date(2026, 9, 11),
        "has_forecast": False,
        "summary_date": date(2026, 9, 23),
    },
    {
        "date": date(2026, 10, 23),
        "has_forecast": True,
        "summary_date": date(2026, 11, 4),
    },
    {
        "date": date(2026, 12, 18),
        "has_forecast": False,
        "summary_date": date(2026, 12, 29),
    },
]

ROSSTAT_MONTHLY_RELEASES = {
    "cpi": {
        "name": "Индекс потребительских цен (ИПЦ)",
        "name_en": "Consumer Price Index (CPI)",
        "importance": 3,
        "typical_day": 6,
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
}

ROSSTAT_QUARTERLY_RELEASES = {
    "gdp-nominal": {
        "name": "ВВП (оценка Росстата)",
        "name_en": "GDP Estimate",
        "importance": 3,
        "release_months": {4: "Q4 2025", 7: "Q1 2026", 10: "Q2 2026"},
        "typical_day": 10,
    },
}

CBR_STAT_MONTHLY = {
    "money-m2": {
        "name": "Денежная масса М2",
        "name_en": "Money Supply M2",
        "importance": 2,
        "typical_day": 20,
    },
    "reserves-gold-fx": {
        "name": "Международные резервы РФ",
        "name_en": "International Reserves",
        "importance": 2,
        "typical_day": 7,
    },
}

MINFIN_MONTHLY = {
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


async def _resolve_indicator_ids(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(select(Indicator.code, Indicator.id))
    return {code: id_ for code, id_ in result.all()}


def _build_cbr_meeting_events() -> list[dict]:
    events = []
    for m in CBR_MEETINGS_2026:
        label = "опорное" if m["has_forecast"] else "промежуточное"
        events.append({
            "title": f"Заседание ЦБ по ключевой ставке ({label})",
            "title_en": f"CBR Key Rate Decision ({'core' if m['has_forecast'] else 'interim'})",
            "event_type": "rate_decision",
            "source": "cbr",
            "indicator_code": "key-rate",
            "scheduled_date": m["date"],
            "scheduled_time": "13:30",
            "importance": 3,
            "status": "released" if m["date"] < date.today() else "scheduled",
            "description": (
                f"Пресс-релиз в 13:30 МСК, пресс-конференция в 15:00 МСК."
                + (f" С публикацией среднесрочного прогноза." if m["has_forecast"] else "")
            ),
            "source_url": "https://cbr.ru/dkp/cal_mp/",
            "metadata_json": {"type": label, "has_forecast": m["has_forecast"]},
        })
        events.append({
            "title": "Резюме обсуждения ключевой ставки",
            "title_en": "Key Rate Discussion Summary",
            "event_type": "report",
            "source": "cbr",
            "indicator_code": "key-rate",
            "scheduled_date": m["summary_date"],
            "importance": 2,
            "status": "released" if m["summary_date"] < date.today() else "scheduled",
            "source_url": "https://cbr.ru/dkp/cal_mp/",
        })
    return events


def _build_monthly_release_events(
    releases: dict, source: str, year: int = 2026
) -> list[dict]:
    events = []
    for code, cfg in releases.items():
        for release_month in range(4, 13):
            ref_month = release_month - 1
            ref_year = year if ref_month >= 1 else year - 1
            if ref_month < 1:
                ref_month = 12
            try:
                sched = date(year, release_month, cfg["typical_day"])
            except ValueError:
                sched = date(year, release_month, 28)
            events.append({
                "title": cfg["name"],
                "title_en": cfg.get("name_en"),
                "event_type": "data_release",
                "source": source,
                "indicator_code": code,
                "scheduled_date": sched,
                "is_estimated": True,
                "reference_period": _month_ref(ref_month, ref_year),
                "importance": cfg["importance"],
                "status": "released" if sched < date.today() else "scheduled",
            })
    return events


def _build_quarterly_release_events(
    releases: dict, source: str, year: int = 2026
) -> list[dict]:
    events = []
    for code, cfg in releases.items():
        for release_month, ref_period in cfg["release_months"].items():
            try:
                sched = date(year, release_month, cfg["typical_day"])
            except ValueError:
                sched = date(year, release_month, 28)
            events.append({
                "title": cfg["name"],
                "title_en": cfg.get("name_en"),
                "event_type": "data_release",
                "source": source,
                "indicator_code": code,
                "scheduled_date": sched,
                "is_estimated": True,
                "reference_period": ref_period,
                "importance": cfg["importance"],
                "status": "released" if sched < date.today() else "scheduled",
            })
    return events


async def seed_calendar():
    all_events = []
    all_events.extend(_build_cbr_meeting_events())
    all_events.extend(_build_monthly_release_events(ROSSTAT_MONTHLY_RELEASES, "rosstat"))
    all_events.extend(_build_monthly_release_events(CBR_STAT_MONTHLY, "cbr"))
    all_events.extend(_build_monthly_release_events(MINFIN_MONTHLY, "minfin"))
    all_events.extend(_build_quarterly_release_events(ROSSTAT_QUARTERLY_RELEASES, "rosstat"))

    async with async_session_factory() as db:
        code_to_id = await _resolve_indicator_ids(db)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        inserted = 0
        for ev_data in all_events:
            code = ev_data.pop("indicator_code", None)
            ind_id = code_to_id.get(code) if code else None
            ev_data["indicator_id"] = ind_id
            ev_data["created_at"] = now
            ev_data["updated_at"] = now

            stmt = pg_insert(EconomicEvent).values(**ev_data)
            stmt = stmt.on_conflict_do_nothing(
                constraint="uq_event_natural_key"
            )
            result = await db.execute(stmt)
            if result.rowcount:
                inserted += 1

        await db.commit()
        logger.info("Calendar seed: %d events inserted (total candidates: %d)", inserted, len(all_events))
        return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_calendar())
