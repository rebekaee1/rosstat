"""
Ключевая ставка Банка России — загрузка с официальной базы cbr.ru.

Проверено 2026-03-20: HTML-таблица на
https://www.cbr.ru/hd_base/KeyRate/ (UniDbQuery, даты DD.MM.YYYY, значение с запятой как десятичный разделитель).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import List

import requests

from app.config import settings

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
    t = s.strip().replace(" ", "").replace("\xa0", "")
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


def fetch_key_rate_html(date_from: date, date_to: date) -> tuple[str, str]:
    """GET страницы KeyRate; возвращает (html, final_url)."""
    url = f"{settings.cbr_base_url.rstrip('/')}/hd_base/KeyRate/"
    params = {
        "UniDbQuery.Posted": "True",
        "UniDbQuery.From": date_from.strftime("%d.%m.%Y"),
        "UniDbQuery.To": date_to.strftime("%d.%m.%Y"),
    }
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9",
        }
    )
    resp = session.get(url, params=params, timeout=settings.cbr_request_timeout)
    resp.raise_for_status()
    if "charset" not in resp.headers.get("Content-Type", "").lower() and len(resp.text) < 5000:
        logger.warning("Short response from CBR KeyRate (%d bytes)", len(resp.text))
    return resp.text, resp.url
