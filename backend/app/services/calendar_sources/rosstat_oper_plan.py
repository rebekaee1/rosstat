"""График оперативных публикаций Росстата → даты безработицы, зарплат, розницы и стройки.

До 14.11.2026 у этих рядов на сайте не было ни одного события: в графике срочных информаций
(rosstat_plan.py) их нет, а оценки «N-й рабочий день» скрыты с витрины как неофициальные.
Росстат публикует их в докладе «Социально-экономическое положение России» и в сборнике
«Краткосрочные экономические показатели», а даты выхода обоих — в документе
«График размещения оперативных публикаций на сайте Росстата»
(``/storage/mediabank/Grafic_oper_public_YYYY.doc``, ссылка в разделе плана публикаций
``/publications-plans/getPage?type=52``).

Документ — двоичный .doc (Word 97). Текст в нём лежит в UTF-16LE, ячейки таблицы разделены
символом ``\\x07``: «Январь-сентябрь | 28 октября | 30 октября | 28 октября». Столбцы: доклад,
краткосрочные показатели, мониторинг регионов. Внешние программы не нужны.

Отчётный месяц — последний месяц периода строки. Зарплата в докладе отстаёт на месяц:
в докладе за январь-сентябрь — зарплата за август (так её грузит и наш парсер).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta

import requests

from app.services.calendar_sources.common import CalendarCandidate, stable_key

logger = logging.getLogger(__name__)

PLAN_TYPE_OPERATIVE = "52"
PUBLICATIONS_PLANS_API = "https://rosstat.gov.ru/publications-plans/getPage"
DOKLAD_URL = "https://rosstat.gov.ru/compendium/document/50801"
KEP_URL = "https://rosstat.gov.ru/compendium/document/50802"

_DOC_HREF_RE = re.compile(r"href=[\"']([^\"']*Grafic_oper_public_(20\d{2})\.docx?)[\"']", re.IGNORECASE)
_MONTHS_GEN = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_MONTH_STEMS = ("январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август",
                "сентябр", "октябр", "ноябр", "декабр")
_MONTH_NAMES = ("", "январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
                "сентябрь", "октябрь", "ноябрь", "декабрь")
_DAY = r"(\d{1,2}\s+[а-я]+)"
_ROW_RE = re.compile(
    r"(Январ[ья](?:\s*[-–—]\s*[а-я]+)?)(?:\s+(20\d{2})\s+года)?\s*\x07\s*"
    + _DAY + r"\s*\x07\s*" + _DAY + r"\s*\x07\s*" + _DAY,
    re.IGNORECASE,
)

HISTORY_DAYS = 75

DOKLAD = "doklad"
KEP = "kep"


@dataclass(frozen=True)
class _Series:
    code: str
    title: str
    title_en: str
    publication: str  # DOKLAD или KEP — откуда ряд грузит наш парсер
    lag_months: int = 0
    importance: int = 2


SERIES: tuple[_Series, ...] = (
    _Series("unemployment", "Уровень безработицы", "Unemployment Rate", DOKLAD),
    _Series("wages-nominal", "Средняя номинальная заработная плата", "Average Nominal Wages", DOKLAD,
            lag_months=1),
    _Series("retail-trade", "Оборот розничной торговли", "Retail Trade Turnover", KEP),
    _Series("housing-commissioned", "Ввод в действие жилых домов", "Housing Commissioned", KEP,
            importance=1),
    _Series("construction-work", "Объём работ по виду деятельности «Строительство»",
            "Construction Work Volume", KEP, importance=1),
)


@dataclass(frozen=True)
class OperRow:
    ref_year: int
    ref_month: int
    doklad: date
    kep: date


def _text_variants(content: bytes) -> list[str]:
    return [content.decode("utf-16-le", errors="ignore"), content[1:].decode("utf-16-le", errors="ignore")]


def _parse_day(text: str, year: int) -> date | None:
    parts = text.split()
    if len(parts) != 2:
        return None
    month = _MONTHS_GEN.get(parts[1].lower())
    if not month:
        return None
    try:
        return date(year, month, int(parts[0]))
    except ValueError:
        return None


def _last_month(period: str) -> int | None:
    last = re.split(r"[-–—]", period)[-1].strip().lower()
    for idx, stem in enumerate(_MONTH_STEMS, start=1):
        if last.startswith(stem):
            return idx
    return None


def parse_oper_schedule_doc(content: bytes, *, year: int) -> list[OperRow]:
    """.doc графика года ``year`` → строки (отчётный месяц, дата доклада, дата сборника)."""
    for text in _text_variants(content):
        rows: list[OperRow] = []
        for m in _ROW_RE.finditer(text):
            month = _last_month(m.group(1))
            if month is None:
                continue
            ref_year = int(m.group(2)) if m.group(2) else year
            doklad = _parse_day(m.group(3), year)
            kep = _parse_day(m.group(4), year)
            if doklad is None or kep is None:
                continue
            rows.append(OperRow(ref_year, month, doklad, kep))
        if rows:
            return rows
    return []


def resolve_oper_doc_urls(html: str) -> list[tuple[int, str]]:
    found: dict[int, str] = {}
    for m in _DOC_HREF_RE.finditer(html):
        url = m.group(1)
        if not url.startswith("http"):
            url = "https://rosstat.gov.ru" + (url if url.startswith("/") else "/" + url)
        found.setdefault(int(m.group(2)), url)
    return sorted(found.items())


def _shift_month(year: int, month: int, back: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) - back
    return idx // 12, idx % 12 + 1


def build_oper_candidates(
    rows: list[OperRow],
    *,
    doc_url: str,
    schedule_year: int,
    today: date,
    months_ahead: int,
) -> list[CalendarCandidate]:
    from app.services.calendar_sources.official_calendar import _event_description

    horizon = today + timedelta(days=months_ahead * 31)
    # История за ~2,5 месяца: источник новый (14.11.2026), прошедшие выпуски показываются с фактом.
    cutoff = today - timedelta(days=HISTORY_DAYS)
    out: list[CalendarCandidate] = []
    for row in rows:
        for series in SERIES:
            day = row.doklad if series.publication == DOKLAD else row.kep
            if not (cutoff <= day <= horizon):
                continue
            ref_y, ref_m = _shift_month(row.ref_year, row.ref_month, series.lag_months)
            ref = f"{_MONTH_NAMES[ref_m]} {ref_y}"
            note = (
                "Публикуется в докладе Росстата «Социально-экономическое положение России»."
                if series.publication == DOKLAD else
                "Публикуется в сборнике Росстата «Краткосрочные экономические показатели»."
            )
            out.append(CalendarCandidate(
                event_key=stable_key("rosstat", "sep", series.code, ref),
                title=series.title,
                title_en=series.title_en,
                event_type="data_release",
                source="rosstat",
                indicator_code=series.code,
                scheduled_date=day,
                date_confidence="official_explicit",
                reference_period=ref,
                importance=series.importance,
                source_url=DOKLAD_URL if series.publication == DOKLAD else KEP_URL,
                source_event_uid=f"rosstat-{series.code}-{day.isoformat()}",
                description=_event_description(series.code, note),
                metadata={
                    "feed": "rosstat_oper",
                    "schedule_doc": doc_url,
                    "schedule_year": schedule_year,
                    "publication": series.publication,
                },
            ))
    return out


def fetch_rosstat_oper_candidates(
    *,
    today: date,
    months_ahead: int,
    session: requests.Session | None = None,
) -> list[CalendarCandidate]:
    """Скачать и разобрать графики текущего и следующего года. [] — источник недоступен."""
    from app.config import settings
    from app.services.http_client import create_session

    try:
        sess = session or create_session(timeout=30)
        if not session:
            sess.verify = settings.rosstat_ca_cert
        resp = sess.get(PUBLICATIONS_PLANS_API, params={"type": PLAN_TYPE_OPERATIVE, "page": "1"}, timeout=30)
        resp.raise_for_status()
        try:
            payload = resp.json()
            html = (payload.get("html") or "") if isinstance(payload, dict) else ""
        except ValueError:
            html = resp.text
        out: list[CalendarCandidate] = []
        for year, url in resolve_oper_doc_urls(html):
            if year not in (today.year, today.year + 1):
                continue
            doc = sess.get(url, timeout=30)
            doc.raise_for_status()
            rows = parse_oper_schedule_doc(doc.content, year=year)
            if not rows:
                logger.warning("Rosstat oper schedule %s: no rows parsed", url)
                continue
            out.extend(build_oper_candidates(rows, doc_url=url, schedule_year=year,
                                             today=today, months_ahead=months_ahead))
        return out
    except Exception:
        logger.warning("Rosstat operative publications schedule fetch failed", exc_info=True)
        return []
