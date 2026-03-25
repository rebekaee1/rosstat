"""ETL: RUONIA (ставка однодневного MBK) с cbr.ru/hd_base/ruonia → IndicatorData.

Источник: HTML-таблица https://www.cbr.ru/hd_base/ruonia/
Аналогичен KeyRate — POST с датами DD.MM.YYYY.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta
from typing import ClassVar

import requests
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")

DEFAULT_BACKFILL_FROM = date(2015, 1, 1)


def _parse_ru_float(s: str) -> float:
    t = s.strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    return float(t)


def fetch_ruonia_html(date_from: date, date_to: date) -> tuple[str, str]:
    url = f"{settings.cbr_base_url.rstrip('/')}/hd_base/ruonia/"
    params = {
        "UniDbQuery.Posted": "True",
        "UniDbQuery.From": date_from.strftime("%d.%m.%Y"),
        "UniDbQuery.To": date_to.strftime("%d.%m.%Y"),
    }
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })
    resp = session.get(url, params=params, timeout=settings.cbr_request_timeout)
    resp.raise_for_status()
    return resp.text, str(resp.url)


def parse_ruonia_html(html: str) -> list[tuple[date, float]]:
    """Parse RUONIA transposed table: dates in first row, rates in second row."""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    if len(rows) < 2:
        return []

    def extract_cells(row_html: str) -> list[str]:
        return [
            re.sub(r"<[^>]+>", "", td).strip()
            for td in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        ]

    date_row = extract_cells(rows[0])
    rate_row = extract_cells(rows[1])

    results: list[tuple[date, float]] = []
    for i, cell in enumerate(date_row):
        if not _DATE_RE.match(cell):
            continue
        if i >= len(rate_row):
            break
        val_str = rate_row[i]
        try:
            d, mo, y = (int(x) for x in cell.split("."))
            val = _parse_ru_float(val_str)
            results.append((date(y, mo, d), round(val, 4)))
        except (ValueError, TypeError):
            continue

    by_date: dict[date, float] = {}
    for d, v in results:
        by_date[d] = v
    return sorted(by_date.items())


class CbrRuoniaParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_ruonia_html"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            cfg = indicator.model_config_json or {}
            date_to = date.today()

            existing_n = (await db.execute(
                select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            if cfg.get("backfill_from"):
                date_from = date.fromisoformat(cfg["backfill_from"])
            elif existing_n == 0:
                date_from = DEFAULT_BACKFILL_FROM
            else:
                win = int(cfg.get("incremental_fetch_days", 60))
                date_from = date_to - timedelta(days=win)

            html, final_url = await asyncio.to_thread(fetch_ruonia_html, date_from, date_to)
            fetch_log.source_url = final_url[:500]

            points = await asyncio.to_thread(parse_ruonia_html, html)
            if not points:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "No RUONIA rows parsed"
                fetch_log.completed_at = datetime.utcnow()
                await db.commit()
                return

            count_before = (await db.execute(
                select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            for dt, val in points:
                stmt = (
                    pg_insert(IndicatorData)
                    .values(indicator_id=indicator.id, date=dt, value=val)
                    .on_conflict_do_nothing(constraint="uq_indicator_date")
                )
                await db.execute(stmt)

            await db.flush()
            count_after = (await db.execute(
                select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            records_added = count_after - count_before
            fetch_log.records_added = records_added
            logger.info("RUONIA '%s': +%d rows (total %d)", code, records_added, count_after)

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
