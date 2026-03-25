"""Пересчёт прогноза OLS после обновления ряда (выделено из scheduler)."""

import asyncio
import logging
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator, IndicatorData, Forecast, ForecastValue
from app.services.forecaster import train_and_forecast
from app.config import settings

logger = logging.getLogger(__name__)


async def clear_current_forecasts(db: AsyncSession, indicator: Indicator) -> int:
    """Удалить текущие прогнозы для индикатора, если прогнозирование отключено."""
    old_forecasts_q = await db.execute(
        select(Forecast).where(
            Forecast.indicator_id == indicator.id,
            Forecast.is_current.is_(True),
        )
    )
    old_forecasts = old_forecasts_q.scalars().all()
    for old_fc in old_forecasts:
        await db.delete(old_fc)
    return len(old_forecasts)


async def retrain_indicator_forecast(db: AsyncSession, indicator: Indicator) -> None:
    """Переобучить модель и сохранить текущий прогноз для индикатора."""
    cfg = indicator.model_config_json or {}
    if int(cfg.get("forecast_steps", settings.forecast_steps) or 0) <= 0:
        removed = await clear_current_forecasts(db, indicator)
        logger.info(
            "forecast_steps<=0 for '%s', skipping OLS retrain and removed %d stale forecast(s)",
            indicator.code,
            removed,
        )
        return

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

    forecast_steps = cfg.get("forecast_steps", settings.forecast_steps)
    forecast_transform = cfg.get("forecast_transform", "cpi_index")

    result = await asyncio.to_thread(
        train_and_forecast, dates, values,
        forecast_steps=forecast_steps,
        forecast_transform=forecast_transform,
    )

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
