"""
Ключевая ставка Банка России — загрузка с официальной базы cbr.ru.

Источники:
1. https://www.cbr.ru/hd_base/KeyRate/ — фактический ряд (HTML-таблица UniDbQuery,
   даты DD.MM.YYYY, значение с запятой как десятичный разделитель).
2. https://cbr.ru/press/keypr/ — пресс-релиз последнего решения Совета директоров.
   Используется для **опережающей** точки: после решения СД и до даты вступления
   в силу новая ставка появляется на этой странице, но ещё отсутствует в hd_base.
   Например, решение 24.04.2026 (снижение до 14,50%) → действует с 27.04.2026,
   но в hd_base появится только 27.04. Без опережающего парсера сайт ~3 дня
   показывает старую ставку, что воспринимается как баг.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from app.config import settings
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

# Строки таблицы: дата и значение % годовых
_ROW_RE = re.compile(
    r"<td>(\d{2}\.\d{2}\.\d{4})</td>\s*<td>([\d\s,\.]+)</td>",
    re.IGNORECASE,
)


@dataclass
class DataPoint:
    date: date
    value: float


def _parse_ru_float(s: str) -> float:
    t = s.strip().replace("\u2212", "-").replace(" ", "").replace("\xa0", "")
    t = t.replace(",", ".")
    return float(t)


def parse_keyrate_html(html: str) -> List[DataPoint]:
    """Разобрать тело ответа страницы KeyRate. Даты по возрастанию, без дубликатов по дате (берём последнее)."""
    raw: list[tuple[date, float]] = []
    for m in _ROW_RE.finditer(html):
        d_str, v_str = m.group(1), m.group(2)
        d, mth, y = (int(x) for x in d_str.split("."))
        raw.append((date(y, mth, d), _parse_ru_float(v_str)))

    if not raw:
        raise ValueError("No key rate rows matched in HTML")

    raw.sort(key=lambda x: x[0])
    by_date: dict[date, float] = {}
    for d, v in raw:
        by_date[d] = v

    points = [DataPoint(date=d, value=round(v, 4)) for d, v in sorted(by_date.items())]
    logger.info("Parsed %d key-rate points (%s — %s)", len(points), points[0].date, points[-1].date)
    return points


def assert_keyrate_response_plausible(html: str, final_url: str) -> None:
    """Защита от HTML-заглушек, DDOS-страниц и пустых ответов (enterprise sanity-check)."""
    if not html or len(html) < 2500:
        raise ValueError(f"KeyRate HTML слишком короткий ({len(html or '')} bytes), URL={final_url[:120]}")
    lower = html.lower()
    if "cbr.ru/error" in lower or "страница не найдена" in lower:
        raise ValueError(f"Похоже на страницу ошибки ЦБ: {final_url[:120]}")
    if "unidbquery" not in lower and "ключев" not in lower:
        raise ValueError("Ответ не похож на страницу ключевой ставки (разметка изменилась?)")


def fetch_key_rate_html(date_from: date, date_to: date) -> tuple[str, str]:
    """GET страницы KeyRate; возвращает (html, final_url)."""
    url = f"{settings.cbr_base_url.rstrip('/')}/hd_base/KeyRate/"
    params = {
        "UniDbQuery.Posted": "True",
        "UniDbQuery.From": date_from.strftime("%d.%m.%Y"),
        "UniDbQuery.To": date_to.strftime("%d.%m.%Y"),
    }
    session = create_session()
    try:
        resp = session.get(url, params=params, timeout=settings.cbr_request_timeout)
        resp.raise_for_status()
        assert_keyrate_response_plausible(resp.text, resp.url)
        return resp.text, resp.url
    finally:
        session.close()


# ---- Анонс решения СД (пресс-релиз) -----------------------------------------

@dataclass
class KeyRateAnnouncement:
    """Решение Совета директоров ЦБ по ключевой ставке."""
    decision_date: date
    effective_date: date
    rate: float

    def __str__(self) -> str:
        return f"СД {self.decision_date}: {self.rate:.2f}% с {self.effective_date}"


_RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

# Извлечение значения новой ставки из пресс-релиза:
#   «...снизить/повысить ключевую ставку на 50 б.п., до 14,50% годовых»
#   «...сохранить/оставить ключевую ставку на уровне 21,00% годовых»
# В тексте встречаются точки внутри «б.п.», поэтому ищем ключевые слова
# «до» и «на уровне» как отдельные токены, без длинных гринго-паттернов.
_RATE_FROM_HEADLINE = re.compile(
    r"(?:до|на\s+уровне)\s+(\d{1,2}[.,]\d{1,2})\s*%\s*годов",
    re.IGNORECASE,
)
# Дата принятия решения: «Совет директоров Банка России 24 апреля 2026 года принял решение»
_DECISION_DATE_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(_RU_MONTHS.keys()) + r")\s+(\d{4})\s*года?\s+принял",
    re.IGNORECASE,
)


def _next_business_day(d: date) -> date:
    """Следующий рабочий день (пн-пт, без учёта праздников ЦБ — для биржевого календаря этого достаточно)."""
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:  # 5=сб, 6=вс
        nxt += timedelta(days=1)
    return nxt


def _normalize_html_whitespace(html: str) -> str:
    """Заменить HTML-сущности и неразрывные пробелы на обычные.

    Без этого `\\s+` в регэкспе не матчит ни `\\xa0`, ни последовательность `&nbsp;`,
    которыми ЦБ разделяет числа и слова в шаблоне CMS.
    """
    return (
        html.replace("&nbsp;", " ")
            .replace("\xa0", " ")
            .replace("&ndash;", "-")
            .replace("&mdash;", "-")
    )


def parse_keyrate_press_release(html: str) -> Optional[KeyRateAnnouncement]:
    """Извлечь (decision_date, effective_date, rate) из пресс-релиза cbr.ru/press/keypr/.

    Возвращает None, если не удалось распарсить (например, страница пустая
    или формат изменился) — это не критическая ошибка для основного ETL.
    """
    if not html or len(html) < 800:
        return None

    norm = _normalize_html_whitespace(html)

    m_rate = _RATE_FROM_HEADLINE.search(norm)
    if not m_rate:
        return None
    rate = _parse_ru_float(m_rate.group(1))

    m_date = _DECISION_DATE_RE.search(norm)
    if not m_date:
        return None
    day, month_ru, year = m_date.group(1), m_date.group(2).lower(), m_date.group(3)
    decision = date(int(year), _RU_MONTHS[month_ru], int(day))

    # Эффективная дата = следующий рабочий день (соглашение ЦБ для решений с 2023 г.).
    effective = _next_business_day(decision)

    return KeyRateAnnouncement(decision_date=decision, effective_date=effective, rate=round(rate, 4))


def fetch_keyrate_press_release() -> Optional[str]:
    """GET https://cbr.ru/press/keypr/ — последняя пресс-конференция СД по ставке."""
    url = f"{settings.cbr_base_url.rstrip('/')}/press/keypr/"
    session = create_session()
    try:
        resp = session.get(url, timeout=settings.cbr_request_timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        logger.warning("Failed to fetch press release at %s", url, exc_info=True)
        return None
    finally:
        session.close()


def get_latest_keyrate_announcement() -> Optional[KeyRateAnnouncement]:
    """Совмещает fetch + parse; молча возвращает None при любой ошибке (best-effort)."""
    html = fetch_keyrate_press_release()
    if not html:
        return None
    try:
        return parse_keyrate_press_release(html)
    except Exception:
        logger.warning("Failed to parse press release HTML", exc_info=True)
        return None
