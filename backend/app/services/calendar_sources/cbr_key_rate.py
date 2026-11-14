"""Календарь решений Банка России по ключевой ставке — со страницы cbr.ru/dkp/cal_mp/.

До 14.11.2026 даты заседаний и резюме лежали в коде только за 2026 год. ЦБ к этому дню уже
опубликовал 2027 год, а три даты резюме 2026 года у нас расходились с его страницей
(12.05 вместо 07.05, 04.11 вместо 05.11, 29.12 вместо 30.12). Теперь страница читается при
каждом обновлении календаря; список в коде остаётся запасным, если сайт ЦБ не ответил.

Разметка (живая проверка 14.11.2026): блоки ``div.main-events_day`` с датой в ``div.date``
(«12 февраля 2027 года») и текстом событий. Заседание — «Заседание Совета директоров … по
ключевой ставке»; опорное — если в блоке есть «Среднесрочный прогноз». Резюме — «Резюме
обсуждения ключевой ставки».
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CBR_MONETARY_POLICY_CALENDAR_URL = "https://cbr.ru/dkp/cal_mp/"

_MONTHS_GEN = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_DATE_RE = re.compile(r"(\d{1,2})\s+([а-я]+)\s+(20\d{2})", re.IGNORECASE)


@dataclass(frozen=True)
class KeyRateMeeting:
    date: date
    has_forecast: bool
    summary_date: date | None


# Запасной список: страница ЦБ на 14.11.2026. Используется, только если страница недоступна
# или не разобралась; при удачном чтении страница главнее.
FALLBACK_MEETINGS: tuple[KeyRateMeeting, ...] = (
    KeyRateMeeting(date(2026, 2, 13), True, date(2026, 2, 26)),
    KeyRateMeeting(date(2026, 3, 20), False, date(2026, 4, 1)),
    KeyRateMeeting(date(2026, 4, 24), True, date(2026, 5, 7)),
    KeyRateMeeting(date(2026, 6, 19), False, date(2026, 7, 1)),
    KeyRateMeeting(date(2026, 7, 24), True, date(2026, 8, 5)),
    KeyRateMeeting(date(2026, 9, 11), False, date(2026, 9, 23)),
    KeyRateMeeting(date(2026, 10, 23), True, date(2026, 11, 5)),
    KeyRateMeeting(date(2026, 12, 18), False, date(2026, 12, 30)),
    KeyRateMeeting(date(2027, 2, 12), True, date(2027, 2, 25)),
    KeyRateMeeting(date(2027, 3, 19), False, date(2027, 3, 31)),
    KeyRateMeeting(date(2027, 4, 30), True, date(2027, 5, 14)),
    KeyRateMeeting(date(2027, 6, 11), False, date(2027, 6, 24)),
    KeyRateMeeting(date(2027, 7, 30), True, date(2027, 8, 11)),
    KeyRateMeeting(date(2027, 9, 10), False, date(2027, 9, 22)),
    KeyRateMeeting(date(2027, 10, 22), True, date(2027, 11, 3)),
    KeyRateMeeting(date(2027, 12, 17), False, date(2027, 12, 29)),
)


def _parse_ru_date(text: str) -> date | None:
    m = _DATE_RE.search(" ".join(text.replace("\xa0", " ").split()))
    if not m:
        return None
    month = _MONTHS_GEN.get(m.group(2).lower())
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def parse_key_rate_calendar(html: str) -> list[KeyRateMeeting]:
    """HTML страницы → заседания по возрастанию даты, у каждого — ближайшее следующее резюме."""
    soup = BeautifulSoup(html, "html.parser")
    meetings: dict[date, bool] = {}
    summaries: set[date] = set()
    for day in soup.select("div.main-events_day"):
        date_node = day.select_one("div.date")
        if date_node is None:
            continue
        day_date = _parse_ru_date(date_node.get_text(" "))
        if day_date is None:
            continue
        text = " ".join(day.get_text(" ").replace("\xa0", " ").split()).lower()
        if "заседание" in text and "ключев" in text:
            meetings[day_date] = meetings.get(day_date, False) or "среднесрочный прогноз" in text
        if "резюме обсуждения" in text:
            summaries.add(day_date)

    ordered = sorted(meetings)
    result: list[KeyRateMeeting] = []
    for idx, meeting_date in enumerate(ordered):
        next_meeting = ordered[idx + 1] if idx + 1 < len(ordered) else None
        summary = min(
            (s for s in summaries if s > meeting_date and (next_meeting is None or s < next_meeting)),
            default=None,
        )
        result.append(KeyRateMeeting(meeting_date, meetings[meeting_date], summary))
    return result


def fetch_key_rate_calendar(session: requests.Session | None = None) -> list[KeyRateMeeting] | None:
    """Заседания со страницы ЦБ; None — страница недоступна или разметка сменилась."""
    try:
        getter = session.get if session is not None else requests.get
        resp = getter(CBR_MONETARY_POLICY_CALENDAR_URL, timeout=20,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0)"})
        resp.raise_for_status()
        resp.encoding = resp.encoding or "utf-8"
        meetings = parse_key_rate_calendar(resp.text)
    except Exception:
        logger.warning("CBR key rate calendar page fetch failed", exc_info=True)
        return None
    # Разумный минимум: на странице всегда есть текущий год (8 заседаний). Меньше — разметка сменилась.
    if len(meetings) < 6:
        logger.warning("CBR key rate calendar: only %d meetings parsed, using fallback list", len(meetings))
        return None
    return meetings
