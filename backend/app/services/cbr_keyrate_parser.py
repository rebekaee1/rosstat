"""ETL: ключевая ставка ЦБ (cbr.ru hd_base/KeyRate) → IndicatorData."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import ClassVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.upsert import upsert_indicator_data
from app.services.cbr_keyrate import DataPoint, fetch_key_rate_html, parse_keyrate_html
from app.services.data_validator import validate_points
from app.services.forecast_pipeline import clear_current_forecasts, retrain_indicator_forecast
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

# Старт публичного ряда «ключевой ставки» в текущем смысле (база ЦБ)
DEFAULT_BACKFILL_FROM = date(2013, 9, 13)


class CbrKeyRateParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_keyrate_html"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            cfg = indicator.model_config_json or {}
            date_to = date.today()

            existing_n = (
                await db.execute(
                    select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
                )
            ).scalar() or 0

            if cfg.get("backfill_from"):
                date_from = date.fromisoformat(cfg["backfill_from"])
            elif existing_n == 0:
                date_from = DEFAULT_BACKFILL_FROM
            else:
                # Инкремент: только свежее окно (полная история при пустой БД)
                win = int(cfg.get("incremental_fetch_days", 150))
                date_from = date_to - timedelta(days=win)

            html, final_url = await asyncio.to_thread(fetch_key_rate_html, date_from, date_to)
            fetch_log.source_url = final_url[:500]

            points: list[DataPoint] = await asyncio.to_thread(parse_keyrate_html, html)
            points = validate_points(points, cfg)

            if not points:
                logger.warning("No data points parsed for %s", code)
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "Parser returned 0 data points"
                fetch_log.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            count_before = (
                await db.execute(
                    select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
                )
            ).scalar() or 0

            for point in points:
                await db.execute(upsert_indicator_data(indicator.id, point.date, point.value))

            await db.flush()
            count_after = (
                await db.execute(
                    select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
                )
            ).scalar() or 0

            records_added = count_after - count_before
            fetch_log.records_added = records_added
            logger.info("Key rate '%s': +%d rows (total %d)", code, records_added, count_after)

            steps = int((indicator.model_config_json or {}).get("forecast_steps", 12) or 0)
            removed_forecasts = 0
            if steps > 0:
                if records_added > 0:
                    await retrain_indicator_forecast(db, indicator)
            else:
                removed_forecasts = await clear_current_forecasts(db, indicator)
                if removed_forecasts:
                    logger.info("Removed %d stale forecast(s) for '%s'", removed_forecasts, code)

            if records_added > 0 or removed_forecasts > 0:
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
