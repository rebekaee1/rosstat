"""
ETL scheduler: daily check for new Rosstat data.
On new data: parse, upsert to DB, retrain forecast, invalidate cache.
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session
from app.models import Indicator, IndicatorData, Forecast, ForecastValue, FetchLog
from app.services.fetcher import RosstatFetcher
from app.services.parser import parse_cpi_sheet
from app.services.forecaster import train_and_forecast
from app.core.cache import cache_invalidate_indicator
from app.config import settings

logger = logging.getLogger(__name__)


async def run_etl_for_indicator(indicator_code: str):
    """Full ETL cycle for a single indicator."""
    async with async_session() as db:
        ind_q = await db.execute(select(Indicator).where(Indicator.code == indicator_code))
        indicator = ind_q.scalar_one_or_none()
        if not indicator:
            logger.error("Indicator '%s' not found", indicator_code)
            return

        started_at = datetime.utcnow()
        fetch_log = FetchLog(indicator_id=indicator.id, status="running", started_at=started_at)
        db.add(fetch_log)
        await db.flush()

        try:
            # 1. Fetch (sync HTTP — run in thread to avoid blocking event loop)
            fetcher = RosstatFetcher()
            content, source_url = await asyncio.to_thread(fetcher.fetch_latest)

            if not content:
                fetch_log.status = "failed"
                fetch_log.error_message = "No file available on Rosstat"
                fetch_log.completed_at = datetime.utcnow()
                await db.commit()
                return

            fetch_log.source_url = source_url

            # 2. Parse (pandas — run in thread)
            sheet = indicator.excel_sheet or "01"
            points = await asyncio.to_thread(parse_cpi_sheet, content, sheet)

            if not points:
                fetch_log.status = "failed"
                fetch_log.error_message = "Parser returned 0 data points"
                fetch_log.completed_at = datetime.utcnow()
                await db.commit()
                return

            # 3. Count existing, upsert, count again to detect new records
            from sqlalchemy import func
            count_before = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            for point in points:
                stmt = pg_insert(IndicatorData).values(
                    indicator_id=indicator.id,
                    date=point.date,
                    value=point.value,
                ).on_conflict_do_nothing(constraint="uq_indicator_date")
                await db.execute(stmt)

            await db.flush()
            count_after = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            records_added = count_after - count_before
            logger.info("Upserted %d new records for '%s' (total: %d)",
                        records_added, indicator_code, count_after)
            fetch_log.records_added = records_added

            # 4. Retrain forecast if new data was added
            if records_added > 0:
                await _retrain_forecast(db, indicator)
                await cache_invalidate_indicator(indicator_code)

            fetch_log.status = "success" if records_added > 0 else "no_new_data"
            fetch_log.completed_at = datetime.utcnow()
            await db.commit()

            logger.info("ETL complete for '%s': %d new records", indicator_code, records_added)

        except Exception as e:
            logger.exception("ETL failed for '%s'", indicator_code)
            fetch_log.status = "failed"
            fetch_log.error_message = str(e)[:500]
            fetch_log.completed_at = datetime.utcnow()
            await db.commit()


async def _retrain_forecast(db, indicator: Indicator):
    """Retrain OLS multi-window model and save new forecast."""
    data_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(IndicatorData.date)
    )
    all_data = data_q.scalars().all()

    if len(all_data) < 36:
        logger.warning("Not enough data for forecast (%d points)", len(all_data))
        return

    dates = [d.date for d in all_data]
    values = [float(d.value) for d in all_data]

    cfg = indicator.model_config_json or {}
    forecast_steps = cfg.get("forecast_steps", settings.forecast_steps)

    result = await asyncio.to_thread(train_and_forecast, dates, values, forecast_steps=forecast_steps)

    old_forecasts_q = await db.execute(
        select(Forecast).where(
            Forecast.indicator_id == indicator.id,
            Forecast.is_current.is_(True),
        )
    )
    for old_fc in old_forecasts_q.scalars().all():
        old_fc.is_current = False

    new_forecast = Forecast(
        indicator_id=indicator.id,
        model_name=result.model_name,
        model_params={"cumulative_12m": result.cumulative_12m},
        aic=result.aic,
        bic=result.bic,
        is_current=True,
    )
    db.add(new_forecast)
    await db.flush()

    for fp in result.points:
        db.add(ForecastValue(
            forecast_id=new_forecast.id,
            date=fp.date,
            value=fp.value,
            lower_bound=fp.lower_bound,
            upper_bound=fp.upper_bound,
        ))

    logger.info("New forecast saved: %s, cumulative 12m = %.2f%%",
                result.model_name, result.cumulative_12m or 0)


async def daily_update_job():
    """Scheduled job: update all active indicators."""
    logger.info("Starting daily ETL update...")

    async with async_session() as db:
        active_q = await db.execute(
            select(Indicator).where(Indicator.is_active.is_(True))
        )
        active_indicators = active_q.scalars().all()

    for indicator in active_indicators:
        try:
            await run_etl_for_indicator(indicator.code)
        except Exception:
            logger.exception("Failed to update indicator '%s'", indicator.code)

    logger.info("Daily ETL update complete.")
