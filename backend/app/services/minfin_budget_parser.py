"""ETL: Минфин open data CSV → IndicatorData (monthly budget deficit/surplus).

Source: https://minfin.gov.ru/OpenData/7710168360-fedbud_month/
Format: CSV (comma-separated, UTF-8 BOM), cumulative from year start.
Columns: Год, Месяц, Доходы всего, ..., Расходы всего, ..., Дефицит/Профицит, ...
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar

import requests
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

CATALOG_URL = "https://minfin.gov.ru/opendata/7710168360-fedbud_month/"
_DATA_RE = re.compile(r"data-\d{8}T\d{4}-structure-\d{8}T\d{4}\.csv")

MONTH_MAP = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}

_SESSION_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)",
}


@dataclass
class BudgetPoint:
    date: date
    value: float


def _find_csv_url() -> str:
    """Discover the latest data CSV URL from the Minfin open data catalog page."""
    session = requests.Session()
    session.headers.update(_SESSION_HEADERS)
    resp = session.get(CATALOG_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if _DATA_RE.search(href):
            if href.startswith("http"):
                return href
            return f"https://minfin.gov.ru{href}"
    raise RuntimeError("Minfin: could not find data CSV link on catalog page")


def _parse_budget_csv(content: str) -> list[BudgetPoint]:
    """Parse Minfin budget CSV, return monthly deficit/surplus values."""
    reader = csv.reader(io.StringIO(content))
    header = next(reader)

    deficit_col = None
    revenue_col = None
    expense_col = None
    for i, col in enumerate(header):
        col_clean = col.strip().replace("\ufeff", "")
        if "Дефицит" in col_clean or "Профицит" in col_clean:
            deficit_col = i
            break
    if deficit_col is None:
        for i, col in enumerate(header):
            col_clean = col.strip().replace("\ufeff", "")
            if col_clean.startswith("Доходы") and "всего" in col_clean:
                revenue_col = i
            if col_clean.startswith("Расходы") and "всего" in col_clean:
                expense_col = i

    rows_by_year: dict[int, list[tuple[int, float]]] = {}
    for row in reader:
        if len(row) < 3:
            continue
        try:
            year = int(row[0].strip())
        except (ValueError, IndexError):
            continue
        month_str = row[1].strip().lower()
        month = MONTH_MAP.get(month_str)
        if not month:
            continue

        cumulative = None
        if deficit_col is not None and deficit_col < len(row):
            raw = row[deficit_col].strip().replace(",", ".")
            if raw and raw != "":
                try:
                    cumulative = float(raw)
                except ValueError:
                    pass
        if cumulative is None and revenue_col is not None and expense_col is not None:
            try:
                rev = float(row[revenue_col].strip().replace(",", "."))
                exp = float(row[expense_col].strip().replace(",", "."))
                cumulative = rev - exp
            except (ValueError, IndexError):
                continue
        if cumulative is None:
            continue

        rows_by_year.setdefault(year, []).append((month, cumulative))

    points: list[BudgetPoint] = []
    for year, month_data in sorted(rows_by_year.items()):
        month_data.sort()
        prev_cumulative = 0.0
        for month, cumulative in month_data:
            if month == 1:
                monthly = cumulative
            else:
                monthly = cumulative - prev_cumulative
            prev_cumulative = cumulative
            points.append(BudgetPoint(date=date(year, month, 1), value=round(monthly, 1)))

    return points


def fetch_and_parse_budget() -> tuple[list[BudgetPoint], str]:
    """Download and parse budget CSV. Returns (points, source_url)."""
    csv_url = _find_csv_url()
    session = requests.Session()
    session.headers.update(_SESSION_HEADERS)
    resp = session.get(csv_url, timeout=60)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    points = _parse_budget_csv(resp.text)
    return points, csv_url


class MinfinBudgetParser(BaseParser):
    parser_type: ClassVar[str] = "minfin_budget_csv"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            points, csv_url = await asyncio.to_thread(fetch_and_parse_budget)
            fetch_log.source_url = csv_url[:500]

            if not points:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "CSV parsed but 0 budget points extracted"
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
            logger.info("MinfinBudget '%s': +%d rows (total %d)", code, records_added, count_after)

            cfg = indicator.model_config_json or {}
            steps = int(cfg.get("forecast_steps", 0) or 0)
            if steps > 0 and records_added > 0:
                await retrain_indicator_forecast(db, indicator)

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
