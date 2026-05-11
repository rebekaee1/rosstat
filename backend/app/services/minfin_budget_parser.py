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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
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
    """Discover the latest data CSV URL from the Minfin open data catalog page.

    Если на странице несколько кандидатов (исторически Минфин публикует версии
    с разными timestamps), выбираем самый свежий по lexicographic max имени
    (timestamps в формате YYYYMMDDTHHMM — корректно сравниваются как строки).
    """
    session = create_session()
    try:
        resp = session.get(CATALOG_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        candidates: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if _DATA_RE.search(href):
                if not href.startswith("http"):
                    href = f"https://minfin.gov.ru{href}"
                candidates.append(href)
        if not candidates:
            raise RuntimeError("Minfin: could not find data CSV link on catalog page")
        candidates.sort(reverse=True)
        if len(candidates) > 1:
            logger.info(
                "Minfin: %d CSV candidates, picking latest: %s",
                len(candidates),
                candidates[0].rsplit("/", 1)[-1],
            )
        return candidates[0]
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
    """ETL для Минфин CSV (deficit/revenue/expenditure).

    Operational trap (см. enterprise_resilience.md): Минфин обновляет content
    CSV-файла `data-YYYYMMDDTHHMM-structure-…csv` *in-place*, не меняя URL.
    Timestamp в имени = дата создания паспорта, не snapshot content. Поэтому
    `_find_csv_url` всегда вернёт стабильный URL, и при scheduled ETL утром
    мы можем скачать ещё «вчерашнюю» версию content. Решение:
    1. 2x daily запуск (см. scheduler) — утренний + обеденный pass.
    2. Этот парсер логирует last_parsed_date + last_db_date — если
       last_parsed > last_db но bulk_upsert вернёт (0,0), это означает что
       upsert идемпотентен (значения совпали с БД) — но НЕ означает что
       новые данные были (это лог уровня INFO). Реальная аномалия — если
       last_parsed > last_db, но parser возвращает 0 точек.
    """

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

        last_db = (
            await db.execute(
                select(func.max(IndicatorData.date)).where(
                    IndicatorData.indicator_id == indicator.id
                )
            )
        ).scalar()
        last_parsed = max((p.date for p in points), default=None)
        logger.info(
            "Minfin budget '%s' (target=%s): parsed=%d points, last_parsed=%s, last_db=%s, csv=%s",
            indicator.code,
            budget_target,
            len(points),
            last_parsed,
            last_db,
            csv_url.rsplit("/", 1)[-1] if csv_url else "?",
        )
        if last_parsed and last_db and last_parsed > last_db:
            logger.warning(
                "Minfin budget '%s': source has newer data (%s) than DB (%s) — "
                "expected bulk_upsert to add at least 1 row; will verify post-upsert.",
                indicator.code,
                last_parsed,
                last_db,
            )
        return points, csv_url
