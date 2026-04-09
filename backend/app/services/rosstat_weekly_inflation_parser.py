"""ETL: Еженедельный ИПЦ → IndicatorData.

Росстат публикует агрегатный недельный ИПЦ в пресс-релизах (не в XLSX).
XLSX `nedel_Ipc.xlsx` содержит только per-product индексы без итога.

Стратегия:
  Парсим inflation-monitor.ru/weekly_inflation — структурированное зеркало
  данных Росстата. Таблица 0 = агрегатный ИПЦ (столбец «За неделю Росстат»).
  Обходим пагинацию «Пред.» для backfill.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import ClassVar

import requests
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.http_client import create_session
from app.services.upsert import upsert_indicator_data
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

BASE_URL = "https://inflation-monitor.ru/weekly_inflation"
_DATE_RANGE_RE = re.compile(r"(\d{2}\.\d{2})(?:\.\d{4})?\s*-\s*(\d{2})\.(\d{2})\.(\d{4})")
_PREV_RE = re.compile(r"Пред", re.IGNORECASE)


@dataclass
class WeeklyPoint:
    date: date
    value: float


def _parse_page(html: bytes) -> tuple[WeeklyPoint | None, str | None]:
    """Parse one page → (data point, prev_page_url or None)."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()

    m = _DATE_RANGE_RE.search(text)
    if not m:
        return None, None

    end_day = int(m.group(2))
    end_month = int(m.group(3))
    end_year = int(m.group(4))
    try:
        end_date = date(end_year, end_month, end_day)
    except ValueError:
        return None, None

    tables = soup.find_all("table")
    point = None
    if tables:
        rows = tables[0].find_all("tr")
        if rows:
            cells = [td.get_text(strip=True) for td in rows[0].find_all(["td", "th"])]
            if len(cells) >= 3:
                raw = cells[2].replace("\u2212", "-").replace(",", ".")
                try:
                    val = float(raw)
                    if 98 < val < 105:
                        point = WeeklyPoint(date=end_date, value=val)
                except ValueError:
                    pass

    prev_url = None
    for a in soup.find_all("a", href=True):
        if _PREV_RE.search(a.get_text(strip=True)):
            href = a["href"]
            if href.startswith("/"):
                prev_url = f"https://inflation-monitor.ru{href}"
            elif href.startswith("http"):
                prev_url = href
            break

    return point, prev_url


def fetch_weekly_cpi(max_pages: int = 200, existing_dates: set[date] | None = None) -> list[WeeklyPoint]:
    """Follow pagination and collect weekly CPI points."""
    session = create_session()
    try:
        points: list[WeeklyPoint] = []
        url: str | None = BASE_URL
        seen_dates: set[date] = set()
        existing = existing_dates or set()

        for _ in range(max_pages):
            if not url:
                break
            try:
                resp = session.get(url, timeout=20)
                if resp.status_code != 200:
                    logger.warning("HTTP %d for %s", resp.status_code, url)
                    break
            except requests.RequestException as e:
                logger.warning("Request failed: %s", e)
                break

            point, prev_url = _parse_page(resp.content)
            if point and point.date not in seen_dates:
                seen_dates.add(point.date)
                points.append(point)
                if point.date in existing and len(points) > 4:
                    break
            elif point is None and prev_url is None:
                break

            url = prev_url
            time.sleep(0.3)

        points.sort(key=lambda p: p.date)
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

            cfg = indicator.model_config_json or {}
            max_pages = cfg.get("backfill_max_pages", 200)
            points = await asyncio.to_thread(
                fetch_weekly_cpi,
                max_pages=max_pages,
                existing_dates=existing_dates,
            )
            fetch_log.source_url = BASE_URL

            if not points:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "No weekly CPI data found on inflation-monitor.ru"
                fetch_log.completed_at = datetime.now(timezone.utc)
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
            fetch_log.completed_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            logger.exception("ETL failed for '%s'", code)
            await db.rollback()
            fetch_log.status = "failed"
            fetch_log.error_message = str(e)[:500]
            fetch_log.completed_at = datetime.now(timezone.utc)
            db.add(fetch_log)
            await db.commit()
