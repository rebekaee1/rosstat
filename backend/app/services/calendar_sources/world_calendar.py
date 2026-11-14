"""Мировые выпуски в календаре: ФРС, BEA (США) и Eurostat (с 14.11.2026).

Сверено с боевого сервера 14.11.2026 (только чтение):
- ФРС, календарь заседаний FOMC — ``federalreserve.gov/monetarypolicy/fomccalendars.htm``, 200;
- BEA, расписание выпусков — ``bea.gov/news/schedule/ics/online-calendar-subscription.ics``, 200;
- Eurostat, лента «евроиндикаторов» — ``ec.europa.eu/eurostat/o/calendars/eventsJson``, 200.
Не показываются, потому что с сервера недоступны: BLS (403 на расписание — CPI и занятость США),
ЕЦБ (сайт не отвечает), FRED (публичный календарь без ключа рвёт соединения после нескольких
запросов, ключа API на сервере нет). Источник, который не ответил, не создаёт событий.

Время: FOMC объявляет решение в 14:00 по Нью-Йорку (переводится в МСК с учётом летнего
времени США), BEA и Eurostat отдают UTC. Ссылки ведут на карточки рядов США, если такой ряд
есть в каталоге; у Eurostat собственной страницы еврозоны на сайте нет — ссылка на источник.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from app.services.calendar_sources.common import CalendarCandidate, stable_key

logger = logging.getLogger(__name__)

FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BEA_ICS_URL = "https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics"
BEA_SCHEDULE_URL = "https://www.bea.gov/news/schedule"
EUROSTAT_EVENTS_URL = "https://ec.europa.eu/eurostat/o/calendars/eventsJson"
EUROSTAT_CALENDAR_URL = "https://ec.europa.eu/eurostat/news/release-calendar"
WORLD_SOURCES = ("fed", "bea", "eurostat")
_UA = {"User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)"}

_NY = ZoneInfo("America/New_York")
_MSK = ZoneInfo("Europe/Moscow")
_MONTHS_EN = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"), start=1)}
_MONTHS_RU = ("", "январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
              "сентябрь", "октябрь", "ноябрь", "декабрь")
_QUARTER_WORD = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4}


def _utc_to_msk(moment: datetime) -> datetime:
    return moment.astimezone(_MSK)


def _window(today: date, months_ahead: int, history_days: int = 14) -> tuple[date, date]:
    return today - timedelta(days=history_days), today + timedelta(days=months_ahead * 31)


def _month_ref(month: int, year: int) -> str:
    return f"{_MONTHS_RU[month]} {year}"


def _world_meta(feed: str, *, country_slug: str | None, country_ru: str, country_en: str,
                world_code: str | None, **extra) -> dict:
    meta = {"feed": feed, "world": True, "country_ru": country_ru, "country_en": country_en}
    if country_slug and world_code:
        meta.update({"world_country_slug": country_slug, "world_code": world_code})
    meta.update(extra)
    return meta


# --- ФРС ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class FomcMeeting:
    decision_date: date
    has_projections: bool


def parse_fomc_calendar(html: str) -> list[FomcMeeting]:
    """Страница FOMC → заседания по всем годам на странице (день решения = последний день)."""
    soup = BeautifulSoup(html, "html.parser")
    meetings: list[FomcMeeting] = []
    for heading in soup.find_all(string=re.compile(r"^\s*20\d{2} FOMC Meetings\s*$")):
        year = int(re.search(r"20\d{2}", heading).group(0))
        panel = heading.find_parent("div", class_="panel")
        if panel is None:
            continue
        for row in panel.select("div.fomc-meeting"):
            month_node = row.select_one(".fomc-meeting__month")
            date_node = row.select_one(".fomc-meeting__date")
            if not month_node or not date_node:
                continue
            month_text = month_node.get_text(" ", strip=True).lower()
            day_text = date_node.get_text(" ", strip=True)
            if "notation" in day_text.lower() or "unscheduled" in day_text.lower():
                continue
            days = re.findall(r"\d{1,2}", day_text)
            months = [m for m in re.split(r"[/\-]", month_text) if m.strip()]
            if not days or not months:
                continue
            month_name = months[-1].strip()
            month = _MONTHS_EN.get(month_name)
            if not month:
                continue
            try:
                decision = date(year, month, int(days[-1]))
            except ValueError:
                continue
            meetings.append(FomcMeeting(decision, "*" in day_text))
    return sorted(set(meetings), key=lambda m: m.decision_date)


def build_fomc_candidates(meetings: list[FomcMeeting], *, today: date, months_ahead: int) -> list[CalendarCandidate]:
    start, end = _window(today, months_ahead)
    out = []
    for meeting in meetings:
        day = meeting.decision_date
        if not (start <= day <= end):
            continue
        local = datetime(day.year, day.month, day.day, 14, 0, tzinfo=_NY).astimezone(_MSK)
        out.append(CalendarCandidate(
            event_key=stable_key("world", "fed", "decision", day.isoformat()),
            title="ФРС США: решение по ставке",
            title_en="Fed Interest Rate Decision",
            event_type="rate_decision",
            source="fed",
            scheduled_date=local.date(),
            scheduled_time=local.strftime("%H:%M"),
            date_confidence="official_explicit",
            importance=3,
            source_url=FOMC_URL,
            source_event_uid=f"fed-fomc-{day.isoformat()}",
            description=(
                "Комитет по операциям на открытом рынке ФРС объявляет целевой диапазон ставки по федеральным фондам."
                + (" С экономическими прогнозами членов комитета." if meeting.has_projections else "")
            ),
            metadata=_world_meta("fed", country_slug="united-states", country_ru="США",
                                 country_en="United States", world_code="us-policy-rate",
                                 has_projections=meeting.has_projections),
        ))
    return out


# --- BEA ---------------------------------------------------------------------------------------

_BEA_RULES = (
    # (шаблон названия, ряд, заголовок RU, заголовок EN, важность, вид отчётного периода)
    (re.compile(r"^GDP \((Advance|Second|Third) Estimate\).*?(1st|2nd|3rd|4th) Quarter(?: and Year)? (20\d{2})", re.I),
     "us-gdp-real-growth", "США: ВВП", "US GDP", 3, "quarter"),
    (re.compile(r"^Personal Income and Outlays,\s+([A-Za-z]+) (20\d{2})", re.I),
     "us-pce-price", "США: личные доходы и расходы, индекс цен PCE", "US Personal Income and Outlays (PCE)", 2, "month"),
    (re.compile(r"^U\.S\. International Trade in Goods and Services,\s+([A-Za-z]+) (20\d{2})", re.I),
     "us-trade-balance", "США: внешняя торговля товарами и услугами", "US International Trade", 1, "month"),
)
_ESTIMATE_RU = {"advance": "первая оценка", "second": "вторая оценка", "third": "третья оценка"}


def parse_bea_ics(text: str, *, today: date, months_ahead: int) -> list[CalendarCandidate]:
    from app.services.calendar_sources.official_calendar import _parse_ics_events

    start, end = _window(today, months_ahead)
    out = []
    for ev in _parse_ics_events(text):
        summary = ev.get("SUMMARY", "")
        raw = (ev.get("DTSTART") or "").strip()
        try:
            moment = datetime.strptime(raw.rstrip("Z")[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        local = _utc_to_msk(moment)
        if not (start <= local.date() <= end):
            continue
        for pattern, code, title, title_en, importance, kind in _BEA_RULES:
            m = pattern.search(summary)
            if not m:
                continue
            if kind == "quarter":
                estimate, q_word, year = m.group(1).lower(), m.group(2).lower(), m.group(3)
                ref = f"Q{_QUARTER_WORD[q_word]} {year}"
                full_title = f"{title} ({_ESTIMATE_RU[estimate]})"
                full_title_en = f"{title_en} ({estimate.capitalize()} Estimate)"
                key_tail = estimate
                imp = importance if estimate == "advance" else 2
            else:
                month = _MONTHS_EN.get(m.group(1).lower())
                if not month:
                    continue
                ref = _month_ref(month, int(m.group(2)))
                full_title, full_title_en, key_tail, imp = title, title_en, "r1", importance
            out.append(CalendarCandidate(
                event_key=stable_key("world", "bea", code, ref, key_tail),
                title=full_title,
                title_en=full_title_en,
                event_type="data_release",
                source="bea",
                scheduled_date=local.date(),
                scheduled_time=local.strftime("%H:%M"),
                date_confidence="official_explicit",
                reference_period=ref,
                importance=imp,
                source_url=BEA_SCHEDULE_URL,
                source_event_uid=f"bea-{code}-{local.date().isoformat()}",
                description=None,
                metadata=_world_meta("bea", country_slug="united-states", country_ru="США",
                                     country_en="United States", world_code=code, raw_summary=summary[:200]),
            ))
            break
    return out


# --- Eurostat ----------------------------------------------------------------------------------

_EUROSTAT_RULES = (
    # (начало названия у Eurostat, ключ, заголовок RU, EN, важность)
    ("flash estimate inflation euro area", "hicp-flash", "Еврозона: инфляция, предварительная оценка",
     "Euro Area Inflation Flash Estimate", 3),
    ("inflation (hicp)", "hicp", "ЕС и еврозона: инфляция", "EU and Euro Area Inflation (HICP)", 2),
    ("preliminary flash estimate gdp", "gdp-flash", "ЕС и еврозона: ВВП, предварительная оценка",
     "EU and Euro Area GDP Preliminary Flash Estimate", 3),
    ("gdp and employment flash estimates", "gdp-flash2", "ЕС и еврозона: ВВП и занятость, экспресс-оценка",
     "EU and Euro Area GDP and Employment Flash Estimates", 2),
    ("gdp main aggregates and employment", "gdp", "ЕС и еврозона: ВВП и занятость",
     "EU and Euro Area GDP and Employment", 2),
    ("unemployment", "unemployment", "ЕС и еврозона: безработица", "EU and Euro Area Unemployment", 2),
    ("retail trade", "retail", "ЕС и еврозона: розничная торговля", "EU and Euro Area Retail Trade", 1),
    ("industrial production", "industry", "ЕС и еврозона: промышленное производство",
     "EU and Euro Area Industrial Production", 1),
    ("industrial producer prices, domestic market", "ppi", "ЕС и еврозона: цены производителей",
     "EU and Euro Area Industrial Producer Prices", 1),
    ("international trade in goods", "trade", "ЕС и еврозона: внешняя торговля товарами",
     "EU and Euro Area International Trade in Goods", 1),
)


def _eurostat_ref(period: str) -> str | None:
    text = (period or "").strip()
    q = re.search(r"Q([1-4])/(20\d{2})", text)
    if q and not re.search(r"[A-Za-z]{3,}", text.replace(q.group(0), "")):
        return f"Q{q.group(1)} {q.group(2)}"
    m = re.match(r"([A-Za-z]+)\.?\s+(20\d{2})$", text)
    if m:
        for name, num in _MONTHS_EN.items():
            if name.startswith(m.group(1).lower()[:3]):
                return _month_ref(num, int(m.group(2)))
    if q:
        return f"Q{q.group(1)} {q.group(2)}"
    return None


def parse_eurostat_events(payload: list[dict], *, today: date, months_ahead: int) -> list[CalendarCandidate]:
    start, end = _window(today, months_ahead)
    out = []
    for item in payload or []:
        if not item.get("euroind"):
            continue
        title = (item.get("title") or "").strip()
        low = title.lower()
        rule = next((r for r in _EUROSTAT_RULES if low.startswith(r[0])), None)
        if rule is None:
            continue
        _, slug, title_ru, title_en, importance = rule
        if "update" in low:
            # «GDP main aggregates and employment - update» — второй выпуск того же квартала.
            slug += "-update"
            title_ru += " (уточнение)"
            title_en += " (Update)"
        try:
            moment = datetime.strptime(item["start"].rstrip("Z")[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        local = _utc_to_msk(moment)
        if not (start <= local.date() <= end):
            continue
        ref = _eurostat_ref(item.get("period", ""))
        record = str(item.get("recordid") or "")
        out.append(CalendarCandidate(
            event_key=stable_key("world", "eurostat", slug, ref or local.date().isoformat()),
            title=title_ru,
            title_en=title_en,
            event_type="data_release",
            source="eurostat",
            scheduled_date=local.date(),
            scheduled_time=local.strftime("%H:%M"),
            date_confidence="official_explicit",
            reference_period=ref,
            importance=importance,
            source_url=EUROSTAT_CALENDAR_URL,
            source_event_uid=f"eurostat-{record or slug}-{local.date().isoformat()}",
            description=None,
            metadata=_world_meta("eurostat", country_slug=None, country_ru="ЕС и еврозона",
                                 country_en="EU and euro area", world_code=None,
                                 raw_title=title[:200], datasets=(item.get("datasetCodes") or "")[:200]),
        ))
    return out


# --- Загрузка ------------------------------------------------------------------------------------

def fetch_world_candidates(*, today: date, months_ahead: int) -> dict[str, list[CalendarCandidate]]:
    """{источник: кандидаты}; источник, который не ответил, в словарь не попадает."""
    result: dict[str, list[CalendarCandidate]] = {}
    try:
        resp = requests.get(FOMC_URL, headers=_UA, timeout=25)
        resp.raise_for_status()
        meetings = parse_fomc_calendar(resp.text)
        if len(meetings) >= 8:
            result["fed"] = build_fomc_candidates(meetings, today=today, months_ahead=months_ahead)
        else:
            logger.warning("FOMC calendar: only %d meetings parsed", len(meetings))
    except Exception:
        logger.warning("FOMC calendar fetch failed", exc_info=True)
    try:
        resp = requests.get(BEA_ICS_URL, headers=_UA, timeout=25)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        bea = parse_bea_ics(resp.text, today=today, months_ahead=months_ahead)
        if bea:
            result["bea"] = bea
    except Exception:
        logger.warning("BEA schedule fetch failed", exc_info=True)
    try:
        start, end = _window(today, months_ahead)
        params = {"start": f"{start.isoformat()}T00:00:00Z", "end": f"{end.isoformat()}T00:00:00Z",
                  "theme": "", "category": "", "keywords": "", "isEuroindicator": "true",
                  "authorInclude": "", "authorExclude": ""}
        resp = requests.get(EUROSTAT_EVENTS_URL, params=params, headers=_UA, timeout=25)
        resp.raise_for_status()
        events = parse_eurostat_events(json.loads(resp.text or "[]"), today=today, months_ahead=months_ahead)
        if events:
            result["eurostat"] = events
    except Exception:
        logger.warning("Eurostat release calendar fetch failed", exc_info=True)
    return result
