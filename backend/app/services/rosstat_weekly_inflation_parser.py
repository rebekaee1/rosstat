"""ETL: Еженедельный ИПЦ → IndicatorData.

Источники (по приоритету):

1. HTML-бюллетени «Об оценке индекса потребительских цен с N по M месяца YYYY г»
   на `rosstat.gov.ru/storage/mediabank/<num>_<DD-MM-YYYY>.html`.
   Публикуются каждую неделю (обычно в среду) и содержат официальный
   агрегированный недельный ИПЦ. Это основной источник для актуальных недель.

2. Фоллбэк — `Nedel_ipc.xlsx` (~110 товаров, листы по годам) + `ipc_spr_MM-YYYY.xlsx`
   (веса). Используется для построения исторического ряда там, где HTML-бюллетени
   ещё не найдены. Взвешенное среднее по продовольственной корзине — приближение,
   но закрывает период 2022-01-10 .. сегодня.

HTML-источник имеет приоритет: если одна и та же дата есть в обеих коллекциях —
берётся значение из бюллетеня (оно совпадает с официальным Росстатом).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from difflib import get_close_matches
from io import BytesIO
from typing import ClassVar

import openpyxl
import requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.http_client import create_session
from app.services.upsert import bulk_upsert
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

NEDEL_IPC_URL = "https://rosstat.gov.ru/storage/mediabank/nedel_Ipc.xlsx"
NEDEL_IPC_URL_FALLBACK = "https://rosstat.gov.ru/storage/mediabank/Nedel_ipc.xlsx"
IPC_SPR_URL = "https://rosstat.gov.ru/storage/mediabank/ipc_spr_{mm}-{yyyy}.xlsx"

ROSSTAT_SEARCH_URL = "https://rosstat.gov.ru/search"
BULLETIN_URL_RE = re.compile(r"/storage/mediabank/\d+_\d{2}-\d{2}-\d{4}\.html?")

_MONTH_MAP = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

_BULLETIN_RANGE_RE = re.compile(
    r"с\s+\d{1,2}\s+(?:[а-яё]+\s+)?по\s+(\d{1,2})\s+([а-яё]+)\s+(\d{4})\s*г",
    re.IGNORECASE,
)
_BULLETIN_VALUE_RE = re.compile(r"составил\s+(\d+[,.]?\d*)\s*%")

_HEADER_RE = re.compile(
    r"на\s+(\d{1,2})\s+("
    + "|".join(_MONTH_MAP.keys())
    + r")",
    re.IGNORECASE,
)


@dataclass
class WeeklyPoint:
    date: date
    value: float


def _parse_column_date(header: str, year: int) -> date | None:
    """Parse 'на 10 января **' → date(year, 1, 10)."""
    m = _HEADER_RE.search(header)
    if not m:
        return None
    day = int(m.group(1))
    month = _MONTH_MAP.get(m.group(2).lower())
    if month is None:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _load_weights(session: requests.Session) -> dict[str, float]:
    """Download ipc_spr and extract per-product weights.

    Tries recent months (descending) to find the latest available file.
    Returns {product_name: weight}.
    """
    today = date.today()
    for month_offset in range(0, 6):
        m = today.month - month_offset
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        url = IPC_SPR_URL.format(mm=f"{m:02d}", yyyy=y)
        try:
            r = session.get(url, timeout=30, verify=False)
            if r.status_code == 200 and len(r.content) > 5000:
                break
        except requests.RequestException:
            continue
    else:
        logger.warning("Could not download ipc_spr for weights")
        return {}

    wb = openpyxl.load_workbook(BytesIO(r.content), data_only=True)
    sheet_name = None
    for sn in reversed(wb.sheetnames):
        if sn != "Содержание":
            sheet_name = sn
            break
    if not sheet_name:
        return {}

    ws = wb[sheet_name]
    weights: dict[str, float] = {}
    for ri in range(7, ws.max_row + 1):
        name = str(ws.cell(ri, 1).value or "").strip()
        w_raw = ws.cell(ri, 3).value
        if not name or w_raw is None:
            continue
        try:
            w = float(w_raw)
        except (ValueError, TypeError):
            continue
        if w > 0:
            weights[name] = w
    return weights


def _match_weight(name: str, weights: dict[str, float],
                  cache: dict[str, float | None]) -> float | None:
    """Find the weight for a weekly product name, caching fuzzy results."""
    if name in cache:
        return cache[name]
    w = weights.get(name)
    if w is not None:
        cache[name] = w
        return w
    close = get_close_matches(name, weights.keys(), n=1, cutoff=0.75)
    if close:
        w = weights[close[0]]
        cache[name] = w
        return w
    cache[name] = None
    return None


def _parse_weekly_xlsx(weekly_content: bytes, weights: dict[str, float]) -> list[WeeklyPoint]:
    """Parse Nedel_ipc.xlsx and compute weighted-average weekly CPI."""
    wb = openpyxl.load_workbook(BytesIO(weekly_content), data_only=True)
    points: list[WeeklyPoint] = []
    match_cache: dict[str, float | None] = {}

    for sheet_name in wb.sheetnames:
        if sheet_name == "Содержание":
            continue
        try:
            year = int(sheet_name)
        except ValueError:
            continue

        ws = wb[sheet_name]
        header_row = 4

        col_dates: list[tuple[int, date]] = []
        for ci in range(2, ws.max_column + 1):
            hdr = str(ws.cell(header_row, ci).value or "")
            d = _parse_column_date(hdr, year)
            if d:
                col_dates.append((ci, d))

        if not col_dates:
            continue

        products: list[tuple[int, str, float]] = []
        for ri in range(5, ws.max_row + 1):
            name = str(ws.cell(ri, 1).value or "").strip()
            if not name or name.startswith("*") or name.startswith("…"):
                continue
            w = _match_weight(name, weights, match_cache)
            if w is None:
                continue
            products.append((ri, name, w))

        for ci, d in col_dates:
            weighted_sum = 0.0
            weight_sum = 0.0
            for ri, name, w in products:
                raw = ws.cell(ri, ci).value
                if raw is None or raw == "…" or raw == "":
                    continue
                try:
                    val = float(str(raw).replace(",", ".").replace("\u2212", "-"))
                except (ValueError, TypeError):
                    continue
                if 95 < val < 110:
                    weighted_sum += w * val
                    weight_sum += w

            if weight_sum > 0:
                aggregate = weighted_sum / weight_sum
                points.append(WeeklyPoint(date=d, value=round(aggregate, 2)))

    points.sort(key=lambda p: p.date)
    return points


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text)


def _parse_bulletin_html(html: str) -> WeeklyPoint | None:
    """Extract (end_date, value) from a weekly CPI bulletin HTML."""
    text = _strip_html(html)
    m_range = _BULLETIN_RANGE_RE.search(text)
    m_val = _BULLETIN_VALUE_RE.search(text)
    if not m_range or not m_val:
        return None
    end_day = int(m_range.group(1))
    month = _MONTH_MAP.get(m_range.group(2).lower())
    year = int(m_range.group(3))
    if month is None:
        return None
    try:
        d = date(year, month, end_day)
    except ValueError:
        return None
    try:
        v = float(m_val.group(1).replace(",", "."))
    except ValueError:
        return None
    if not (95 < v < 110):
        return None
    return WeeklyPoint(date=d, value=round(v, 2))


def _find_bulletin_urls(session: requests.Session, year: int) -> list[str]:
    """Search Rosstat for weekly CPI bulletin URLs for a given year.

    Rosstat's search returns a limited page of results, so we query per-month
    (genitive month names) and union the results.
    """
    found: set[str] = set()
    today = date.today()
    month_range = range(1, 13) if year < today.year else range(1, today.month + 1)
    for month in month_range:
        month_name = next(
            (name for name, num in _MONTH_MAP.items() if num == month), None,
        )
        if not month_name:
            continue
        q = f"оценке индекса потребительских цен {month_name} {year}"
        try:
            r = session.get(
                ROSSTAT_SEARCH_URL, params={"q": q}, timeout=30, verify=False,
            )
            if r.status_code != 200:
                continue
            for m in BULLETIN_URL_RE.finditer(r.text):
                path = m.group(0)
                if f"-{year}." in path:
                    found.add("https://rosstat.gov.ru" + path)
        except requests.RequestException as exc:
            logger.warning("Rosstat search failed for %s %d: %s", month_name, year, exc)
    return sorted(found)


def fetch_bulletin_points(session: requests.Session, years: list[int]) -> list[WeeklyPoint]:
    """Fetch weekly CPI from Rosstat HTML bulletins for the given years."""
    points: list[WeeklyPoint] = []
    seen_dates: set[date] = set()
    for year in years:
        urls = _find_bulletin_urls(session, year)
        logger.info("Weekly CPI bulletins for %d: %d URLs", year, len(urls))
        for url in urls:
            try:
                r = session.get(url, timeout=30, verify=False)
                if r.status_code != 200:
                    continue
                html = r.content.decode("utf-8", errors="replace")
                pt = _parse_bulletin_html(html)
                if pt and pt.date not in seen_dates:
                    seen_dates.add(pt.date)
                    points.append(pt)
            except requests.RequestException as exc:
                logger.warning("Failed to fetch bulletin %s: %s", url, exc)
    points.sort(key=lambda p: p.date)
    return points


def fetch_weekly_cpi(existing_dates: set[date] | None = None) -> list[WeeklyPoint]:
    """Fetch weekly CPI: HTML bulletins (primary) + XLSX (fallback/history).

    HTML values take precedence for overlapping dates — они совпадают с
    официальными Росстата, XLSX-взвешенное среднее — лишь приближение
    по продовольственной корзине.
    """
    session = create_session()
    try:
        session.verify = False

        today = date.today()
        bulletin_years = [today.year]
        if today.month <= 2:
            bulletin_years.append(today.year - 1)

        logger.info("Fetching weekly CPI bulletins for years %s", bulletin_years)
        bulletin_points = fetch_bulletin_points(session, bulletin_years)
        logger.info("Weekly CPI: parsed %d points from HTML bulletins", len(bulletin_points))

        xlsx_points: list[WeeklyPoint] = []
        for xlsx_url in (NEDEL_IPC_URL, NEDEL_IPC_URL_FALLBACK):
            logger.info("Downloading weekly XLSX: %s", xlsx_url)
            try:
                r = session.get(xlsx_url, timeout=60)
                if r.status_code != 200:
                    logger.warning("HTTP %d for %s", r.status_code, xlsx_url)
                    continue
                weights = _load_weights(session)
                if not weights:
                    logger.warning("No weights available — XLSX fallback skipped")
                    break
                xlsx_points = _parse_weekly_xlsx(r.content, weights)
                logger.info("Weekly CPI: parsed %d points from %s", len(xlsx_points), xlsx_url)
                break
            except requests.RequestException as exc:
                logger.warning("XLSX fetch failed for %s: %s", xlsx_url, exc)

        merged: dict[date, float] = {p.date: p.value for p in xlsx_points}
        for p in bulletin_points:
            merged[p.date] = p.value
        points = [WeeklyPoint(date=d, value=v) for d, v in sorted(merged.items())]
        logger.info(
            "Weekly CPI: merged %d points (HTML: %d, XLSX: %d)",
            len(points), len(bulletin_points), len(xlsx_points),
        )

        if existing_dates:
            points = [p for p in points if p.date not in existing_dates]
            logger.info("Weekly CPI: %d new points after filtering existing", len(points))

        return points
    finally:
        session.close()


class RosstatWeeklyCpiParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_weekly_cpi"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            existing_q = await db.execute(
                select(IndicatorData.date)
                .where(IndicatorData.indicator_id == indicator.id)
            )
            existing_dates = {row[0] for row in existing_q.fetchall()}

            points = await asyncio.to_thread(
                fetch_weekly_cpi,
                existing_dates=None,
            )
            fetch_log.source_url = NEDEL_IPC_URL

            if not points:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "No weekly CPI data parsed from Rosstat XLSX"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.commit()
                return

            records_added, records_updated = await bulk_upsert(db, indicator.id, points)
            logger.info(
                "Upserted %d new, %d updated for '%s'",
                records_added, records_updated, code,
            )
            fetch_log.records_added = records_added

            if records_added > 0 or records_updated > 0:
                await cache_invalidate_indicator(code)

            fetch_log.status = "success" if (records_added > 0 or records_updated > 0) else "no_new_data"
            fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()

        except Exception as e:
            logger.exception("ETL failed for '%s'", code)
            await db.rollback()
            fetch_log.status = "failed"
            fetch_log.error_message = str(e)[:500]
            fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(fetch_log)
            await db.commit()
