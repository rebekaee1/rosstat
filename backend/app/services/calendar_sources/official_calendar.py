from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session as async_session_factory
from app.services.calendar_sources.common import CalendarCandidate, stable_key, upsert_calendar_candidates
from app.services.calendar_sources.working_calendar import (
    calendar_source_url,
    next_month,
    nth_working_day,
)

logger = logging.getLogger(__name__)

CBR_CALENDAR_PAGE = "https://www.cbr.ru/statistics/indcalendar/"
CBR_ICS_URL = "https://www.cbr.ru/Queries/FileSource/105732/vCalendar.ics?inline=True"
MINFIN_SCHEDULE_URL = "https://minfin.gov.ru/ru/statistics/schedule"
ROSSTAT_CPI_RULE_URL = "https://rosstat.gov.ru/free_doc/new_site/prices/ipc.htm"
ROSSTAT_PRICE_URL = "https://rosstat.gov.ru/statistics/price"
ROSSTAT_GDP_URL = "https://rosstat.gov.ru/statistics/accounts"
ROSSTAT_LABOR_URL = "https://rosstat.gov.ru/labor_market_employment_salaries"
ROSSTAT_BUSINESS_URL = "https://rosstat.gov.ru/enterprise_industrial"


MONTH_NAMES_RU = [
    "", "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]


ROSSTAT_MONTHLY_RULES = [
    {
        "code": "cpi",
        "title": "Индекс потребительских цен (ИПЦ)",
        "title_en": "Consumer Price Index (CPI)",
        "importance": 3,
        "nth_workday": 9,
        "source_url": ROSSTAT_CPI_RULE_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "ipi",
        "title": "Индекс промышленного производства (ИПП)",
        "title_en": "Industrial Production Index",
        "importance": 2,
        "nth_workday": 9,
        "source_url": ROSSTAT_BUSINESS_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "unemployment",
        "title": "Уровень безработицы",
        "title_en": "Unemployment Rate",
        "importance": 2,
        "nth_workday": 9,
        "source_url": ROSSTAT_LABOR_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "wages-nominal",
        "title": "Средняя номинальная заработная плата",
        "title_en": "Average Nominal Wages",
        "importance": 2,
        "nth_workday": 9,
        "source_url": ROSSTAT_LABOR_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "retail-trade",
        "title": "Оборот розничной торговли",
        "title_en": "Retail Trade Turnover",
        "importance": 2,
        "nth_workday": 15,
        "source_url": ROSSTAT_BUSINESS_URL,
        "rule": "15-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "housing-commissioned",
        "title": "Ввод в действие жилых домов",
        "title_en": "Housing Commissioned",
        "importance": 1,
        "nth_workday": 15,
        "source_url": ROSSTAT_BUSINESS_URL,
        "rule": "15-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "ppi",
        "title": "Индекс цен производителей промышленных товаров (ИЦП)",
        "title_en": "Producer Price Index (PPI)",
        "importance": 2,
        "nth_workday": 18,
        "source_url": ROSSTAT_PRICE_URL,
        "rule": "18-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "construction-work",
        "title": "Объём работ по виду деятельности «Строительство»",
        "title_en": "Construction Work Volume",
        "importance": 1,
        "nth_workday": 15,
        "source_url": ROSSTAT_BUSINESS_URL,
        "rule": "15-й рабочий день месяца, следующего за отчетным периодом",
    },
]

ROSSTAT_GDP_RULES = [
    {
        "code": "gdp-nominal",
        "title": "ВВП (предварительная оценка)",
        "title_en": "GDP First Estimate",
        "importance": 3,
        "lag_days": 60,
    },
    {
        "code": "gdp-real",
        "title": "ВВП (вторая оценка)",
        "title_en": "GDP Second Estimate",
        "importance": 2,
        "lag_days": 90,
    },
]

MINFIN_RULES = [
    {
        "code": "budget-revenue",
        "title": "Доходы федерального бюджета",
        "title_en": "Federal Budget Revenue",
        "importance": 2,
    },
    {
        "code": "budget-expenditure",
        "title": "Расходы федерального бюджета",
        "title_en": "Federal Budget Expenditure",
        "importance": 2,
    },
]

CBR_KEYWORDS = [
    ("international-reserves", "Международные резервы РФ", "International Reserves", 2,
     ("международн", "international reserves")),
    ("m2", "Денежная масса М2", "Money Supply M2", 2,
     ("денежная масса", "money supply")),
    ("external-debt", "Внешний долг РФ", "External Debt of the Russian Federation", 1,
     ("внешний долг", "external debt")),
    ("current-account", "Текущий счёт платёжного баланса", "Current Account", 2,
     ("текущ", "current account")),
    ("key-rate", "Ключевая ставка Банка России", "Bank of Russia Key Rate", 3,
     ("ключевая ставка", "key rate")),
]


async def refresh_official_calendar(
    *,
    months_ahead: int = 12,
    today: date | None = None,
    db: AsyncSession | None = None,
) -> int:
    today = today or date.today()
    candidates = build_rule_candidates(today=today, months_ahead=months_ahead)
    candidates.extend(fetch_cbr_calendar_candidates(today=today, months_ahead=months_ahead))

    if db is not None:
        return await upsert_calendar_candidates(db, candidates)
    async with async_session_factory() as session:
        return await upsert_calendar_candidates(session, candidates)


def build_rule_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    candidates: list[CalendarCandidate] = []
    candidates.extend(build_rosstat_rule_candidates(today=today, months_ahead=months_ahead))
    candidates.extend(build_minfin_rule_candidates(today=today, months_ahead=months_ahead))
    return candidates


def build_rosstat_rule_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    candidates: list[CalendarCandidate] = []
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)

    for ref_year, ref_month in _iter_reference_months(today, months_ahead):
        release_year, release_month = next_month(ref_year, ref_month)
        if not calendar_source_url(release_year):
            continue
        for rule in ROSSTAT_MONTHLY_RULES:
            scheduled = nth_working_day(release_year, release_month, rule["nth_workday"])
            if not (cutoff <= scheduled <= horizon):
                continue
            candidates.append(CalendarCandidate(
                event_key=stable_key("rosstat", rule["code"], f"{ref_year}-{ref_month:02d}"),
                title=rule["title"],
                title_en=rule["title_en"],
                event_type="data_release",
                source="rosstat",
                indicator_code=rule["code"],
                scheduled_date=scheduled,
                date_confidence="official_rule",
                reference_period=_month_ref(ref_month, ref_year),
                importance=rule["importance"],
                source_url=rule["source_url"],
                description=f"Дата рассчитана по официальному правилу: {rule['rule']}.",
                metadata={
                    "rule": rule["rule"],
                    "working_calendar_source": calendar_source_url(release_year),
                },
            ))

    for rule in ROSSTAT_GDP_RULES:
        for q_end in _quarter_ends(today.year - 1, today.year + 2):
            scheduled = q_end + timedelta(days=rule["lag_days"])
            if not (cutoff <= scheduled <= horizon):
                continue
            q = (q_end.month - 1) // 3 + 1
            candidates.append(CalendarCandidate(
                event_key=stable_key("rosstat", rule["code"], f"{q_end.year}-q{q}"),
                title=rule["title"],
                title_en=rule["title_en"],
                event_type="data_release",
                source="rosstat",
                indicator_code=rule["code"],
                scheduled_date=scheduled,
                date_confidence="official_rule",
                reference_period=f"Q{q} {q_end.year}",
                importance=rule["importance"],
                source_url=ROSSTAT_GDP_URL,
                description=f"Дата рассчитана по официальному лагу: Q+{rule['lag_days']} дней.",
                metadata={"rule": f"quarter_end + {rule['lag_days']} days"},
            ))

    return candidates


def build_minfin_rule_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    candidates: list[CalendarCandidate] = []
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)
    for ref_year, ref_month in _iter_reference_months(today, months_ahead):
        release_year, release_month = next_month(ref_year, ref_month)
        if not calendar_source_url(release_year):
            continue
        scheduled = nth_working_day(release_year, release_month, 14)
        if not (cutoff <= scheduled <= horizon):
            continue
        for rule in MINFIN_RULES:
            candidates.append(CalendarCandidate(
                event_key=stable_key("minfin", rule["code"], f"{ref_year}-{ref_month:02d}"),
                title=rule["title"],
                title_en=rule["title_en"],
                event_type="data_release",
                source="minfin",
                indicator_code=rule["code"],
                scheduled_date=scheduled,
                date_confidence="official_rule",
                reference_period=_month_ref(ref_month, ref_year),
                importance=rule["importance"],
                source_url=MINFIN_SCHEDULE_URL,
                description="Дата рассчитана по графику Минфина: 14-й рабочий день месяца.",
                metadata={
                    "rule": "14-й рабочий день месяца, следующего за отчетным",
                    "working_calendar_source": calendar_source_url(release_year),
                },
            ))
    return candidates


def fetch_cbr_calendar_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    try:
        page = requests.get(CBR_CALENDAR_PAGE, timeout=20)
        page.raise_for_status()
        ics_url = _extract_cbr_ics_url(page.text) or CBR_ICS_URL
        response = requests.get(ics_url, timeout=20)
        response.raise_for_status()
        return parse_cbr_ics(response.text, source_url=ics_url, today=today, months_ahead=months_ahead)
    except Exception:
        logger.exception("Failed to fetch CBR official calendar")
        return []


def parse_cbr_ics(
    text: str,
    *,
    source_url: str,
    today: date,
    months_ahead: int,
) -> list[CalendarCandidate]:
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)
    candidates: list[CalendarCandidate] = []
    for event in _parse_ics_events(text):
        scheduled = _parse_ics_date(event.get("DTSTART"))
        if not scheduled or not (cutoff <= scheduled <= horizon):
            continue
        blob = " ".join([
            event.get("SUMMARY", ""),
            event.get("DESCRIPTION", ""),
            event.get("URL", ""),
        ]).lower()
        matched = _match_cbr_indicator(blob)
        if not matched:
            continue
        code, title, title_en, importance = matched
        uid = event.get("UID") or stable_key(code, event.get("SUMMARY", ""), scheduled.isoformat())
        scheduled_time = _parse_ics_time(event.get("DTSTART"))
        candidates.append(CalendarCandidate(
            event_key=stable_key("cbr", code, uid),
            title=title,
            title_en=title_en,
            event_type="data_release",
            source="cbr",
            indicator_code=code,
            scheduled_date=scheduled,
            scheduled_time=scheduled_time,
            date_confidence="official_explicit",
            reference_period=_reference_from_text(event.get("SUMMARY", "") + " " + event.get("DESCRIPTION", "")),
            importance=importance,
            source_url=event.get("URL") or source_url,
            source_event_uid=uid,
            description=event.get("SUMMARY"),
            metadata={"calendar_url": source_url, "raw_summary": event.get("SUMMARY")},
        ))
    return candidates


def _extract_cbr_ics_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "vCalendar.ics" in href:
            if href.startswith("http"):
                return href
            return "https://www.cbr.ru" + href
    return None


def _parse_ics_events(text: str) -> list[dict[str, str]]:
    unfolded: list[str] = []
    for raw in text.splitlines():
        if raw.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += raw[1:]
        else:
            unfolded.append(raw.rstrip("\r"))

    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in unfolded:
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        name = key.split(";", 1)[0].upper()
        current[name] = _clean_ics_text(value)
    return events


def _clean_ics_text(value: str) -> str:
    return (
        value
        .replace("\\n", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .strip()
    )


def _parse_ics_date(value: str | None) -> date | None:
    if not value:
        return None
    compact = value.split("T", 1)[0]
    try:
        return datetime.strptime(compact[:8], "%Y%m%d").date()
    except ValueError:
        return None


def _parse_ics_time(value: str | None) -> str | None:
    if not value or "T" not in value:
        return None
    part = value.split("T", 1)[1]
    if len(part) < 4:
        return None
    return f"{part[:2]}:{part[2:4]}"


def _match_cbr_indicator(blob: str) -> tuple[str, str, str, int] | None:
    for code, title, title_en, importance, keywords in CBR_KEYWORDS:
        if any(keyword in blob for keyword in keywords):
            return code, title, title_en, importance
    return None


def _reference_from_text(text: str) -> str | None:
    match = re.search(r"((?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я.\-]*\s+20\d{2})", text, re.I)
    if match:
        return match.group(1)
    match = re.search(r"(Q[1-4]\s+20\d{2}|[IVX]+\s+квартал\s+20\d{2})", text, re.I)
    if match:
        return match.group(1)
    match = re.search(r"(\d{2}\.\d{2}\.20\d{2})", text)
    if match:
        return match.group(1)
    return None


def _iter_reference_months(today: date, months_ahead: int):
    cursor = today.replace(day=1) - timedelta(days=1)
    cursor = cursor.replace(day=1)
    end = (today + timedelta(days=(months_ahead + 1) * 31)).replace(day=1)
    while cursor <= end:
        yield cursor.year, cursor.month
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)


def _quarter_ends(start_year: int, end_year: int) -> list[date]:
    values: list[date] = []
    for year in range(start_year, end_year + 1):
        values.extend([
            date(year, 3, 31),
            date(year, 6, 30),
            date(year, 9, 30),
            date(year, 12, 31),
        ])
    return values


def _month_ref(month: int, year: int) -> str:
    return f"{MONTH_NAMES_RU[month]} {year}"
