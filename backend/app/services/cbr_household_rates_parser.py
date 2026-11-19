"""Банк России: максимальная ставка по вкладам 10 банков (HTML) и инфляционные ожидания населения (xlsx).

Реестр рядов и тексты — ``app.data.cbr_household_rates`` (19.11.2026).

``cbr_deposit_max_html`` — таблица «Декада / Ставка, %» на ``/statistics/avgprocstav/``. Без параметров страница
отдаёт два последних года; с ``UniDbQuery.From/To`` — любой период (с 01.07.2009 — вся история, 624 декады на
19.11.2026, ~95 КБ). Первая загрузка — вся история; дальше запрос «последние 120 дней», на который страница
отвечает не меньше чем двумя последними годами (живой запрос 19.11.2026: 67 декад с января 2025) — запас на
пропущенные прогоны есть, повтор идемпотентен. Декада «I.11.2026» → 01.11.2026, «II» → 11-е, «III» → 21-е.

``cbr_inflation_expectations_xlsx`` — файл «Инфляционные ожидания и потребительские настроения» к каждому месяцу.
Адрес файла меняется каждый месяц (``/Collection/Collection/File/<id>/Infl_exp_YY-MM.xlsx``), поэтому путь такой:
страница раздела → самая поздняя страница выпуска ``Infl_exp_YY-MM/`` → ссылка на xlsx. Файл ~2 МБ, в нём вся
история с декабря 2009 года (лист «Данные за все годы»: строка 2 — даты столбцов, дальше блоки вопросов). Три ряда
читают один файл: загрузка кэшируется в процессе на 30 минут. Ячейка без числа — опроса в тот месяц не было
(до 2014 года), точка не пишется.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import time
from datetime import date, datetime, timedelta
from math import isfinite
from typing import ClassVar

from sqlalchemy import func, select

from app.config import settings
from app.data import cbr_household_rates as spec
from app.models import IndicatorData
from app.services.base_parser import BaseParser
from app.services.http_client import create_session
from app.services.rosstat_labor_parser import DataPoint

logger = logging.getLogger(__name__)

_DECADE_ROW = re.compile(r"<td>\s*(I{1,3})\.(\d{2})\.(\d{4})\s*</td>\s*<td>\s*([\d\s\xa0]+,?\d*)\s*</td>")
_DECADE_DAY = {"I": 1, "II": 11, "III": 21}
_INCREMENTAL_DAYS = 120


def _base() -> str:
    return settings.cbr_base_url.rstrip("/")


def _get(url: str, params: dict | None = None) -> tuple[bytes, str]:
    session = create_session()
    try:
        resp = session.get(url, params=params, timeout=settings.cbr_request_timeout)
        resp.raise_for_status()
        return resp.content, str(resp.url)
    finally:
        session.close()


# ── Максимальная ставка по вкладам ───────────────────────────────────────────


def parse_deposit_max_html(html: str) -> list[DataPoint]:
    """Таблица декад → точки на первый день декады, по возрастанию даты."""
    out: dict[date, float] = {}
    for decade, month, year, raw in _DECADE_ROW.findall(html):
        value = float(raw.replace(" ", "").replace("\xa0", "").replace(",", "."))
        out[date(int(year), int(month), _DECADE_DAY[decade])] = round(value, 4)
    return [DataPoint(d, v) for d, v in sorted(out.items())]


class CbrDepositMaxParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_deposit_max_html"

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        latest = await db.scalar(
            select(func.max(IndicatorData.date)).where(IndicatorData.indicator_id == indicator.id)
        )
        today = date.today()
        start = (today - timedelta(days=_INCREMENTAL_DAYS)).strftime("%d.%m.%Y") if latest else spec.DEPOSIT_MAX_FIRST
        params = {"UniDbQuery.Posted": "True", "UniDbQuery.From": start, "UniDbQuery.To": today.strftime("%d.%m.%Y")}
        body, url = await asyncio.to_thread(_get, f"{_base()}/statistics/avgprocstav/", params)
        points = parse_deposit_max_html(body.decode("utf-8", errors="replace"))
        if not points:
            raise ValueError("avgprocstav: в ответе нет строк «декада — ставка»; вероятно, сменилась вёрстка")
        return points, url


# ── Инфляционные ожидания и настроения населения ─────────────────────────────

_RELEASE_HREF = re.compile(r"/analytics/dkp/inflationary_expectations/Infl_exp_(\d{2})-(\d{2})/")
_XLSX_HREF = re.compile(r'href="([^"]*Infl_exp_\d{2}-\d{2}\.xlsx)"', re.IGNORECASE)
_CACHE_TTL_S = 30 * 60
_cache: dict[str, tuple[float, bytes, str]] = {}


def latest_release_path(html: str) -> str | None:
    """Самая поздняя страница выпуска ``Infl_exp_YY-MM/`` на странице раздела."""
    found = {(int(yy), int(mm)) for yy, mm in _RELEASE_HREF.findall(html)}
    if not found:
        return None
    yy, mm = max(found)
    return f"/analytics/dkp/inflationary_expectations/Infl_exp_{yy:02d}-{mm:02d}/"


def xlsx_href(html: str) -> str | None:
    match = _XLSX_HREF.search(html)
    return match.group(1) if match else None


def _download_expectations() -> tuple[bytes, str]:
    cached = _cache.get("file")
    if cached and time.monotonic() - cached[0] < _CACHE_TTL_S:
        return cached[1], cached[2]
    page, _ = _get(spec.EXPECTATIONS_PAGE.replace("https://www.cbr.ru", _base()))
    release = latest_release_path(page.decode("utf-8", errors="replace"))
    if not release:
        raise ValueError("инфляционные ожидания: на странице раздела нет ссылок на выпуски Infl_exp_YY-MM")
    release_page, _ = _get(f"{_base()}{release}")
    href = xlsx_href(release_page.decode("utf-8", errors="replace"))
    if not href:
        raise ValueError(f"инфляционные ожидания: на странице {release} нет файла xlsx")
    body, url = _get(href if href.startswith("http") else f"{_base()}{href}")
    _cache["file"] = (time.monotonic(), body, url)
    return body, url


def _norm(text: object) -> str:
    return " ".join(str(text or "").replace("\xa0", " ").split()).lower()


def parse_expectations_xlsx(content: bytes) -> dict[str, list[DataPoint]]:
    """Лист «Данные за все годы» → {код ряда: точки}. Строка ряда ищется после строки-заголовка её блока."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        if spec.EXPECTATIONS_SHEET not in wb.sheetnames:
            raise ValueError(f"инфляционные ожидания: нет листа «{spec.EXPECTATIONS_SHEET}»")
        rows = list(wb[spec.EXPECTATIONS_SHEET].iter_rows(values_only=True))
    finally:
        wb.close()
    header = next((r for r in rows[:5] if sum(isinstance(c, datetime) for c in r) > 12), None)
    if header is None:
        raise ValueError("инфляционные ожидания: нет строки с датами опросов")
    dates = {i: date(c.year, c.month, 1) for i, c in enumerate(header) if isinstance(c, datetime)}
    out: dict[str, list[DataPoint]] = {}
    for code, s in spec.SURVEY.items():
        section, label = _norm(s.section), _norm(s.label)
        start = next((i for i, r in enumerate(rows) if r and _norm(r[0]).startswith(section)), None)
        row = None
        if start is not None:
            row = next((r for r in rows[start + 1:start + 4] if r and _norm(r[0]).startswith(label)), None)
        if row is None:
            raise ValueError(f"инфляционные ожидания: нет строки «{s.label}» после «{s.section}»")
        points = []
        for i, d in dates.items():
            value = row[i] if i < len(row) else None
            if isinstance(value, (int, float)) and isfinite(value):
                points.append(DataPoint(d, round(float(value), 4)))
        out[code] = sorted(points, key=lambda p: p.date)
    return out


class CbrInflationExpectationsParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_inflation_expectations_xlsx"
    # Файл каждый месяц несёт всю историю — источник целиком; ревизии прошлых месяцев приходят вместе с ним.

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        content, url = await asyncio.to_thread(_download_expectations)
        series = await asyncio.to_thread(parse_expectations_xlsx, content)
        points = series.get(indicator.code) or []
        if not points:
            raise ValueError(f"инфляционные ожидания: нет точек ряда {indicator.code}")
        return points, url
