"""Пересчёт прогнозов после обновления ряда."""

import asyncio
import logging
from datetime import date
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator, IndicatorData, Forecast, ForecastValue
from app.services.forecaster import (
    train_and_forecast,
    train_monthly_cpi,
    train_inflation_12m,
    aggregate_quarterly_from_monthly,
    ForecastResult,
    ForecastPoint,
    CPI_INDICATOR_CODES,
)
from app.config import settings

logger = logging.getLogger(__name__)


async def clear_current_forecasts(db: AsyncSession, indicator: Indicator) -> int:
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


async def _save_forecast(db: AsyncSession, indicator: Indicator,
                         result, model_name_prefix: str | None = None) -> None:
    """Deactivate old forecasts with matching model prefix and save new one."""
    old_q = select(Forecast).where(
        Forecast.indicator_id == indicator.id,
        Forecast.is_current.is_(True),
    )
    if model_name_prefix:
        old_q = old_q.where(Forecast.model_name.like(f"{model_name_prefix}%"))
    else:
        old_q = old_q.where(~Forecast.model_name.like("Inflation-12M%"))

    old_forecasts = (await db.execute(old_q)).scalars().all()
    for old_fc in old_forecasts:
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

    logger.info("Saved forecast '%s' for %s (%d points)",
                result.model_name, indicator.code, len(result.points))


async def retrain_indicator_forecast(db: AsyncSession, indicator: Indicator) -> None:
    cfg = indicator.model_config_json or {}
    forecast_steps = int(cfg.get("forecast_steps", settings.forecast_steps) or 0)

    if forecast_steps <= 0:
        removed = await clear_current_forecasts(db, indicator)
        logger.info(
            "forecast_steps<=0 for '%s', skipping retrain and removed %d stale forecast(s)",
            indicator.code, removed,
        )
        return

    approved_values = cfg.get("approved_forecast_values")
    if approved_values:
        result = ForecastResult(
            model_name=str(cfg.get("forecast_model_name", "Approved-Forecast")),
            aic=None,
            bic=None,
            points=[
                ForecastPoint(
                    date=date.fromisoformat(str(item["date"])),
                    value=round(float(item["value"]), 4),
                    lower_bound=None,
                    upper_bound=None,
                )
                for item in approved_values
            ],
        )
        await _save_forecast(db, indicator, result)
        logger.info("Saved approved forecast for '%s'", indicator.code)
        return

    data_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(IndicatorData.date)
    )
    all_data = data_q.scalars().all()

    if len(all_data) < 36:
        removed = await clear_current_forecasts(db, indicator)
        logger.warning(
            "Not enough data for forecast (%d points), removed %d stale forecast(s)",
            len(all_data), removed,
        )
        return

    dates = [d.date for d in all_data]
    values = [float(d.value) for d in all_data]

    if indicator.code in CPI_INDICATOR_CODES:
        monthly_result = await asyncio.to_thread(
            train_monthly_cpi, dates, values, forecast_steps=forecast_steps,
        )
        await _save_forecast(db, indicator, monthly_result, model_name_prefix="CPI-Monthly")

        inflation_result = await asyncio.to_thread(
            train_inflation_12m, dates, values, forecast_steps=forecast_steps,
        )
        await _save_forecast(db, indicator, inflation_result, model_name_prefix="Inflation-12M")

        if indicator.code == "cpi":
            await _propagate_cpi_forecast_to_derived(
                db, dates, values, monthly_result, inflation_result,
            )
    else:
        forecast_transform = cfg.get("forecast_transform", "absolute")
        result = await asyncio.to_thread(
            train_and_forecast, dates, values,
            forecast_steps=forecast_steps,
            forecast_transform=forecast_transform,
            frequency=indicator.frequency or "monthly",
        )
        await _save_forecast(db, indicator, result)

    logger.info("Retrain complete for '%s'", indicator.code)


async def _propagate_cpi_forecast_to_derived(
    db: AsyncSession,
    dates: list[date],
    values: list[float],
    monthly_result: ForecastResult,
    inflation_result: ForecastResult,
) -> None:
    """Save quarterly/annual aggregated forecasts under their dedicated indicators.

    Quarterly: aggregated from monthly CPI forecast (Никита's spec, April 2026).
    Annual: identical to Inflation-12M-MW result — published as forecast for
    `inflation-annual` indicator so the frontend can read it via the standard
    /forecast endpoint.
    """
    quarterly_result = await asyncio.to_thread(
        aggregate_quarterly_from_monthly,
        dates, values, monthly_result.points,
    )
    quarterly_indicator = (await db.execute(
        select(Indicator).where(Indicator.code == "inflation-quarterly")
    )).scalar_one_or_none()
    if quarterly_indicator is not None and quarterly_result.points:
        await _save_forecast(db, quarterly_indicator, quarterly_result)

    annual_indicator = (await db.execute(
        select(Indicator).where(Indicator.code == "inflation-annual")
    )).scalar_one_or_none()
    if annual_indicator is not None:
        # The annual chart shows one point per calendar year (December cumulative).
        # Keep only December points from the rolling 12-month forecast so the
        # forecast granularity matches the historical series. With forecast_steps=12
        # (e.g. apr-2026..mar-2027) this yields exactly one annual point (dec-2026).
        december_points = [
            ForecastPoint(
                date=p.date,
                value=p.value,
                lower_bound=p.lower_bound,
                upper_bound=p.upper_bound,
            )
            for p in inflation_result.points
            if p.date.month == 12
        ]
        if december_points:
            annual_result = ForecastResult(
                model_name="Annual-From-12M-Rolling",
                aic=None,
                bic=None,
                points=december_points,
            )
            await _save_forecast(db, annual_indicator, annual_result)
        else:
            removed = await clear_current_forecasts(db, annual_indicator)
            logger.info(
                "No December points in 12-month forecast horizon; cleared %d "
                "stale annual forecast(s) for inflation-annual",
                removed,
            )
