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


def _parse_week_catalog(html: bytes) -> list[tuple[str, date]]:
    """Extract all available weeks from the <select> dropdown.

    Returns list of (url_slug, period_end_date) sorted newest-first.
    """
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select")
    if not select:
        return []

    weeks: list[tuple[str, date]] = []
    for opt in select.find_all("option"):
        slug = opt.get("value", "").strip()
        text = opt.get_text(strip=True)
        m = _DATE_RANGE_RE.search(text)
        if not m or not slug:
            continue
        try:
            end_date = date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
        except ValueError:
            continue
        weeks.append((slug, end_date))
    return weeks


def _parse_page_value(html: bytes) -> float | None:
    """Extract the Rosstat weekly CPI value from the ipc-table."""
    soup = BeautifulSoup(html, "html.parser")
    td = soup.find("td", class_="col-prod-week-rosstat")
    if td:
        raw = td.get_text(strip=True).replace("\u2212", "-").replace(",", ".")
        try:
            val = float(raw)
            if 98 < val < 105:
                return val
        except ValueError:
            pass

    tables = soup.find_all("table")
    if tables:
        rows = tables[0].find_all("tr")
        if rows:
            cells = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]
            if len(cells) >= 3:
                raw = cells[2].replace("\u2212", "-").replace(",", ".")
                try:
                    val = float(raw)
                    if 98 < val < 105:
                        return val
                except ValueError:
                    pass
    return None


def fetch_weekly_cpi(max_pages: int = 900, existing_dates: set[date] | None = None) -> list[WeeklyPoint]:
    """Fetch all available weekly CPI data points from inflation-monitor.ru.

    Strategy: parse the week-selector dropdown on the first page to discover
    all available weeks, then fetch only the pages for dates not yet in DB.
    Follows "Пред" (prev-year) pagination to backfill prior years.
    """
    session = create_session()
    try:
        points: list[WeeklyPoint] = []
        existing = existing_dates or set()
        seen_dates: set[date] = set()

        resp = session.get(BASE_URL, timeout=20)
        if resp.status_code != 200:
            logger.warning("HTTP %d for %s", resp.status_code, BASE_URL)
            return []

        all_weeks = _parse_week_catalog(resp.content)
        if not all_weeks:
            logger.warning("No weeks found in <select> dropdown")
            return []
        logger.info("Weekly CPI: found %d weeks in catalog", len(all_weeks))

        first_val = _parse_page_value(resp.content)
        if first_val is not None and all_weeks:
            first_date = all_weeks[0][1]
            if first_date not in seen_dates:
                seen_dates.add(first_date)
                points.append(WeeklyPoint(date=first_date, value=first_val))

        new_count = 0
        for slug, end_date in all_weeks[1:]:
            if end_date in seen_dates:
                continue
            if end_date in existing:
                continue

            url = f"{BASE_URL}/{slug}"
            try:
                r = session.get(url, timeout=20)
                if r.status_code != 200:
                    logger.debug("HTTP %d for %s", r.status_code, url)
                    continue
            except requests.RequestException as e:
                logger.debug("Request failed for %s: %s", url, e)
                continue

            val = _parse_page_value(r.content)
            if val is not None:
                seen_dates.add(end_date)
                points.append(WeeklyPoint(date=end_date, value=val))
                new_count += 1

            time.sleep(0.25)

        prev_url = None
        soup_first = BeautifulSoup(resp.content, "html.parser")
        for a in soup_first.find_all("a", href=True):
            if _PREV_RE.search(a.get_text(strip=True)):
                href = a["href"]
                if href.startswith("/"):
                    prev_url = f"https://inflation-monitor.ru{href}"
                elif href.startswith("http"):
                    prev_url = href
                break

        pages_crawled = 0
        while prev_url and pages_crawled < max_pages:
            try:
                r = session.get(prev_url, timeout=20)
                if r.status_code != 200:
                    break
            except requests.RequestException:
                break

            year_weeks = _parse_week_catalog(r.content)
            if not year_weeks:
                break

            all_existing = all(d in existing for _, d in year_weeks)
            if all_existing and pages_crawled > 0:
                break

            for slug, end_date in year_weeks:
                if end_date in seen_dates or end_date in existing:
                    continue
                page_url = f"{BASE_URL}/{slug}"
                try:
                    pr = session.get(page_url, timeout=20)
                    if pr.status_code != 200:
                        continue
                except requests.RequestException:
                    continue
                val = _parse_page_value(pr.content)
                if val is not None:
                    seen_dates.add(end_date)
                    points.append(WeeklyPoint(date=end_date, value=val))
                    new_count += 1
                time.sleep(0.25)

            prev_url = None
            for a in BeautifulSoup(r.content, "html.parser").find_all("a", href=True):
                if _PREV_RE.search(a.get_text(strip=True)):
                    href = a["href"]
                    if href.startswith("/"):
                        prev_url = f"https://inflation-monitor.ru{href}"
                    elif href.startswith("http"):
                        prev_url = href
                    break

            pages_crawled += 1
            time.sleep(0.3)

        logger.info("Weekly CPI: collected %d total points (%d new)", len(points), new_count)
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
