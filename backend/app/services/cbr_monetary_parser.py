"""ETL: денежная база ЦБ с cbr.ru/hd_base/mb_nd/mb_nd_month → IndicatorData.

Источник: HTML-таблица https://www.cbr.ru/hd_base/mb_nd/mb_nd_month/
Колонки: дата | денежная база | наличные деньги в обращении | обяз. резервы
M0 = наличные деньги в обращении (col 1), денежная база (col 0)
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

DEFAULT_BACKFILL_FROM = date(2015, 1, 1)

_ROW_RE = re.compile(
    r"<td[^>]*>(\d{2}\.\d{2}\.\d{4})</td>"
    r"\s*<td[^>]*>([\d\s,.]+)</td>"
    r"\s*<td[^>]*>([\d\s,.]+)</td>"
    r"\s*<td[^>]*>([\d\s,.]+)</td>",
    re.IGNORECASE,
)


def _parse_ru_float(s: str) -> float:
    return float(s.strip().replace(" ", "").replace("\xa0", "").replace(",", "."))


def fetch_mb_html(date_from: date, date_to: date) -> tuple[str, str]:
    url = f"{settings.cbr_base_url.rstrip('/')}/hd_base/mb_nd/mb_nd_month/"
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


def parse_mb_html(html: str) -> list[tuple[date, float, float, float]]:
    """Parse денежная база. Returns list of (date, база, наличные M0, резервы)."""
    results: list[tuple[date, float, float, float]] = []
    for m in _ROW_RE.finditer(html):
        d_str = m.group(1)
        try:
            d, mo, y = (int(x) for x in d_str.split("."))
            base_val = _parse_ru_float(m.group(2))
            cash_val = _parse_ru_float(m.group(3))
            reserve_val = _parse_ru_float(m.group(4))
            results.append((date(y, mo, d), round(base_val, 2), round(cash_val, 2), round(reserve_val, 2)))
        except (ValueError, TypeError):
            continue
    results.sort(key=lambda x: x[0])
    return results


class CbrMonetaryParser(BaseParser):
    """Парсер для денежной базы / M0 (наличные). monetary_column: 0=денежная база, 1=M0 (наличные)."""
    parser_type: ClassVar[str] = "cbr_monetary_html"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            cfg = indicator.model_config_json or {}
            col_index = int(cfg.get("monetary_column", 0))
            date_to = date.today()

            existing_n = (await db.execute(
                select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            if cfg.get("backfill_from"):
                date_from = date.fromisoformat(cfg["backfill_from"])
            elif existing_n == 0:
                date_from = DEFAULT_BACKFILL_FROM
            else:
                win = int(cfg.get("incremental_fetch_days", 90))
                date_from = date_to - timedelta(days=win)

            html, final_url = await asyncio.to_thread(fetch_mb_html, date_from, date_to)
            fetch_log.source_url = final_url[:500]

            parsed = await asyncio.to_thread(parse_mb_html, html)
            if not parsed:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "No monetary data rows parsed"
                fetch_log.completed_at = datetime.utcnow()
                await db.commit()
                return

            count_before = (await db.execute(
                select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            for row in parsed:
                dt = row[0]
                val = row[col_index + 1]
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
            logger.info("Monetary '%s' (col=%d): +%d rows (total %d)", code, col_index, records_added, count_after)

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
