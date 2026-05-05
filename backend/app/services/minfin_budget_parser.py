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
from datetime import date
from typing import ClassVar

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

CATALOG_URL = "https://minfin.gov.ru/opendata/7710168360-fedbud_month/"
_DATA_RE = re.compile(r"data-\d{8}T\d{4}-structure-\d{8}T\d{4}\.csv")

MONTH_MAP = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}

@dataclass
class BudgetPoint:
    date: date
    value: float


def _find_csv_url() -> str:
    """Discover the latest data CSV URL from the Minfin open data catalog page."""
    session = create_session()
    try:
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
    finally:
        session.close()


def _find_col_index(header: list[str], target: str) -> int | None:
    """Find column index by partial match in header."""
    for i, col in enumerate(header):
        col_clean = col.strip().replace("\ufeff", "")
        if target in col_clean:
            return i
    return None


def _parse_budget_csv(content: str, target: str = "deficit") -> list[BudgetPoint]:
    """Parse Minfin budget CSV.

    target: "deficit" (default), "revenue", "expenditure"
    All columns are cumulative from year start → convert to monthly.
    """
    reader = csv.reader(io.StringIO(content))
    header = next(reader)

    col_idx = None
    if target == "deficit":
        col_idx = _find_col_index(header, "Дефицит")
        if col_idx is None:
            _find_col_index(header, "Доходы, всего")
            _find_col_index(header, "Расходы, всего")
    elif target == "revenue":
        col_idx = _find_col_index(header, "Доходы, всего")
    elif target == "expenditure":
        col_idx = _find_col_index(header, "Расходы, всего")
    else:
        raise ValueError(f"Unknown budget target: {target}")

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
        if col_idx is not None and col_idx < len(row):
            raw = row[col_idx].strip().replace("\u2212", "-").replace(",", ".")
            if raw and raw != "":
                try:
                    cumulative = float(raw)
                except ValueError:
                    pass
        if cumulative is None and target == "deficit":
            rev = _find_col_index(header, "Доходы, всего")
            exp = _find_col_index(header, "Расходы, всего")
            if rev is not None and exp is not None:
                try:
                    rev_raw = row[rev].strip().replace("\u2212", "-").replace(",", ".")
                    exp_raw = row[exp].strip().replace("\u2212", "-").replace(",", ".")
                    cumulative = float(rev_raw) - float(exp_raw)
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


def fetch_and_parse_budget(target: str = "deficit") -> tuple[list[BudgetPoint], str]:
    """Download and parse budget CSV. Returns (points, source_url)."""
    csv_url = _find_csv_url()
    session = create_session()
    try:
        resp = session.get(csv_url, timeout=60)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        points = _parse_budget_csv(resp.text, target=target)
        return points, csv_url
    finally:
        session.close()


class MinfinBudgetParser(BaseParser):
    parser_type: ClassVar[str] = "minfin_budget_csv"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        budget_target = cfg.get("budget_target", "deficit")
        points, csv_url = await asyncio.to_thread(fetch_and_parse_budget, budget_target)
        return points, csv_url
