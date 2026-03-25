"""ETL: Росстат weekly CPI press releases → IndicatorData.

Rosstat publishes weekly CPI estimates on Wednesdays at
ssl.rosstat.gov.ru/storage/mediabank/{id}_{date}.html

Strategy:
  1. Fetch the Rosstat prices section page to find links to weekly releases.
  2. For each new release, parse the HTML table for CPI value and date range.
  3. Store weekly CPI index (к предыдущей неделе, e.g. 100.13).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import ClassVar

import requests
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

ROSSTAT_PRICE_URL = "https://rosstat.gov.ru/statistics/price"
SSL_ROSSTAT_BASE = "https://ssl.rosstat.gov.ru"

CERT_PATH = Path(__file__).resolve().parents[2] / "certs" / "russiantrustedca2024.pem"

_DATE_RE = re.compile(
    r"с\s+(\d{1,2})\s+по\s+(\d{1,2})\s+"
    r"(январ[яь]|феврал[яь]|март[а]?|апрел[яь]|ма[яй]|июн[яь]|"
    r"июл[яь]|август[а]?|сентябр[яь]|октябр[яь]|ноябр[яь]|декабр[яь])\s+"
    r"(\d{4})",
    re.IGNORECASE,
)

_MONTH_MAP = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
    "ма": 5, "июн": 6, "июл": 7, "август": 8,
    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}

_LINK_RE = re.compile(r"оценк[еи]\s+индекс", re.IGNORECASE)
_CPI_VAL_RE = re.compile(r"(\d{2,3}[.,]\d{1,3})\s*%?")


@dataclass
class WeeklyPoint:
    date: date
    value: float


def _month_from_stem(stem: str) -> int | None:
    stem_lower = stem.lower()
    for prefix, month in _MONTH_MAP.items():
        if stem_lower.startswith(prefix):
            return month
    return None


def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })
    cert = str(CERT_PATH) if CERT_PATH.exists() else None
    if cert:
        s.verify = cert
    return s


def _discover_release_links(session: requests.Session) -> list[str]:
    """Fetch Rosstat prices page and find links to weekly CPI releases."""
    links: list[str] = []

    for url in [
        ROSSTAT_PRICE_URL,
        "https://rosstat.gov.ru/price",
        f"{SSL_ROSSTAT_BASE}/storage/mediabank/ind_potreb_cen_05.html",
    ]:
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                href = a["href"]
                if _LINK_RE.search(text) or ("потребительских цен" in text and "оценк" in text):
                    if href.startswith("http"):
                        links.append(href)
                    elif href.startswith("/"):
                        base = url.split("/")[0] + "//" + url.split("/")[2]
                        links.append(base + href)
            if links:
                break
        except requests.RequestException as e:
            logger.debug("Failed to fetch %s: %s", url, e)

    return list(dict.fromkeys(links))


def _parse_release_page(session: requests.Session, url: str) -> WeeklyPoint | None:
    """Parse a single weekly CPI release page for the CPI value and date."""
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return None
    except requests.RequestException:
        return None

    text = resp.text
    date_match = _DATE_RE.search(text)
    if not date_match:
        return None

    end_day = int(date_match.group(2))
    month_stem = date_match.group(3)
    year = int(date_match.group(4))
    month = _month_from_stem(month_stem)
    if not month:
        return None

    try:
        end_date = date(year, month, end_day)
    except ValueError:
        return None

    soup = BeautifulSoup(text, "html.parser")
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            cell_texts = [c.get_text(strip=True) for c in cells]
            for ct in cell_texts:
                if "предыдущ" in ct.lower() and "недел" in ct.lower():
                    for ct2 in cell_texts:
                        m = _CPI_VAL_RE.search(ct2.replace(",", "."))
                        if m:
                            val = float(m.group(1))
                            if 99 < val < 102:
                                return WeeklyPoint(date=end_date, value=val)
                    break

    return None


def fetch_weekly_cpi() -> list[WeeklyPoint]:
    """Discover and parse all available weekly CPI releases."""
    session = _get_session()
    links = _discover_release_links(session)
    if not links:
        logger.warning("No weekly CPI release links found on Rosstat")
        return []

    points: list[WeeklyPoint] = []
    for link in links[:52]:
        pt = _parse_release_page(session, link)
        if pt:
            points.append(pt)

    points.sort(key=lambda p: p.date)
    seen: dict[date, float] = {}
    for p in points:
        seen[p.date] = p.value
    return [WeeklyPoint(date=d, value=v) for d, v in sorted(seen.items())]


class RosstatWeeklyCpiParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_weekly_cpi"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            points = await asyncio.to_thread(fetch_weekly_cpi)
            fetch_log.source_url = ROSSTAT_PRICE_URL

            if not points:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "No weekly CPI data found"
                fetch_log.completed_at = datetime.utcnow()
                await db.commit()
                return

            count_before = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            for p in points:
                stmt = (
                    pg_insert(IndicatorData)
                    .values(indicator_id=indicator.id, date=p.date, value=p.value)
                    .on_conflict_do_nothing(constraint="uq_indicator_date")
                )
                await db.execute(stmt)

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
            fetch_log.completed_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            logger.exception("ETL failed for '%s'", code)
            fetch_log.status = "failed"
            fetch_log.error_message = str(e)[:500]
            fetch_log.completed_at = datetime.utcnow()
            await db.commit()
