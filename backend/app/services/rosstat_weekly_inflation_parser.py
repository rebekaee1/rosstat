"""ETL: Еженедельный ИПЦ → IndicatorData.

Источник: Росстат XLSX — rosstat.gov.ru/storage/mediabank/

Файлы:
  - Nedel_ipc.xlsx  — покомпонентные недельные ИПЦ (~110 товаров), листы по годам (2022-2026+)
  - ipc_spr_MM-YYYY.xlsx — помесячная справка с весами корзины (структура расходов)

Для каждой недели вычисляется взвешенное среднее ИПЦ по всем продуктам
из недельного файла, используя веса из справки.
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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.http_client import create_session
from app.services.upsert import upsert_indicator_data
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

NEDEL_IPC_URL = "https://rosstat.gov.ru/storage/mediabank/Nedel_ipc.xlsx"
IPC_SPR_URL = "https://rosstat.gov.ru/storage/mediabank/ipc_spr_{mm}-{yyyy}.xlsx"

_MONTH_MAP = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

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


def fetch_weekly_cpi(existing_dates: set[date] | None = None) -> list[WeeklyPoint]:
    """Fetch weekly CPI from Rosstat XLSX files."""
    session = create_session()
    try:
        session.verify = False

        logger.info("Downloading Nedel_ipc.xlsx from rosstat.gov.ru")
        r = session.get(NEDEL_IPC_URL, timeout=60)
        if r.status_code != 200:
            logger.warning("HTTP %d for %s", r.status_code, NEDEL_IPC_URL)
            return []
        weekly_content = r.content

        logger.info("Loading CPI weights from ipc_spr")
        weights = _load_weights(session)
        if not weights:
            logger.warning("No weights available — using equal weights")

        points = _parse_weekly_xlsx(weekly_content, weights)
        logger.info("Rosstat weekly CPI: parsed %d total points", len(points))

        if existing_dates:
            new_points = [p for p in points if p.date not in existing_dates]
            logger.info("Weekly CPI: %d new points (filtered from %d)", len(new_points), len(points))
            return new_points

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

            count_before = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            for p in points:
                await db.execute(upsert_indicator_data(indicator.id, p.date, p.value))

            await db.flush()
            count_after = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            records_added = count_after - count_before
            fetch_log.records_added = records_added
            logger.info("WeeklyCPI '%s': +%d rows (total %d)", code, records_added, count_after)

            if records_added > 0:
                await cache_invalidate_indicator(code)

            fetch_log.status = "success" if records_added > 0 else "no_new_data"
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
