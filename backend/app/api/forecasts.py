import math
import re
from datetime import date
from typing import Sequence, TypeVar

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData, Forecast, ForecastValue
from app.schemas import (
    ForecastResponse, ForecastOut, ForecastValueOut,
    InflationResponse, InflationPoint, InflationForecastPoint,
)
from app.core.cache import cache_get, cache_set, versioned_key
from app.config import settings

router = APIRouter(prefix="/indicators", tags=["forecasts"])

_CODE_RE = re.compile(r'^[a-z0-9-]+$')

DERIVED_CPI_FORECASTS = {
    "inflation-quarterly",
    "cpi-food-quarterly",
    "cpi-nonfood-quarterly",
    "cpi-services-quarterly",
}


def _replaces_partial_actual(cfg: dict) -> bool:
    """Only derived forecasts that complete a partial sum/period may revise fact."""
    if cfg.get("forecast_strategy") != "derived_from_source":
        return False
    derived = cfg.get("derived_forecast") or {}
    if derived.get("monthly_tail_extrapolate"):
        return True
    if derived.get("operation") != "pipeline":
        return False
    return any(step and step[0] == "period_sum" for step in derived.get("pipeline") or [])


def _validate_code(code: str) -> None:
    if not _CODE_RE.match(code):
        raise HTTPException(status_code=400, detail="Invalid indicator code format")


_ForecastValueT = TypeVar("_ForecastValueT")


def _public_annual_values(
    values: Sequence[_ForecastValueT], last_actual: date | None, *, replaces_partial: bool,
) -> list[_ForecastValueT]:
    """One future calendar year after the latest fact; retain a partial-year revision."""
    if last_actual is None:
        return list(values[:1])
    anchor = [v for v in values if v.date == last_actual] if replaces_partial else []
    future = [v for v in values if v.date.year == last_actual.year + 1]
    return anchor + future[:1]


@router.get("/{code}/forecast", response_model=ForecastResponse)
async def get_forecast(code: str, db: AsyncSession = Depends(get_db)):
    _validate_code(code)
    cache_key = await versioned_key(code, "forecast:partial-v2")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    ind = await db.execute(select(Indicator).where(Indicator.code == code))
    indicator = ind.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    cfg = indicator.model_config_json or {}
    forecast_steps = int(cfg.get("forecast_steps", settings.forecast_steps) or 0)
    if forecast_steps <= 0 and code not in DERIVED_CPI_FORECASTS:
        response = ForecastResponse(indicator=code, forecast=None)
        await cache_set(cache_key, response.model_dump(mode="json"), settings.cache_ttl_data)
        return response

    fc = await db.execute(
        select(Forecast)
        .where(
            Forecast.indicator_id == indicator.id,
            Forecast.is_current,
            ~Forecast.model_name.like("Inflation-12M%"),
        )
        .order_by(desc(Forecast.created_at))
        .limit(1)
    )
    forecast = fc.scalar_one_or_none()

    if not forecast:
        response = ForecastResponse(indicator=code, forecast=None)
        await cache_set(cache_key, response.model_dump(mode="json"), 300)
        return response

    vals = await db.execute(
        select(ForecastValue)
        .where(ForecastValue.forecast_id == forecast.id)
        .order_by(ForecastValue.date)
    )
    values = vals.scalars().all()
    if indicator.frequency == "annual":
        last_actual = (
            await db.execute(
                select(func.max(IndicatorData.date))
                .where(IndicatorData.indicator_id == indicator.id)
            )
        ).scalar_one_or_none()
        values = _public_annual_values(
            values, last_actual, replaces_partial=_replaces_partial_actual(cfg),
        )

    out = ForecastOut(
        model_name=forecast.model_name,
        aic=float(forecast.aic) if forecast.aic is not None else None,
        bic=float(forecast.bic) if forecast.bic is not None else None,
        created_at=forecast.created_at,
        replaces_partial_actual=_replaces_partial_actual(cfg),
        values=[ForecastValueOut(
            date=v.date,
            value=float(v.value),
        ) for v in values],
    )

    response = ForecastResponse(indicator=code, forecast=out)
    await cache_set(cache_key, response.model_dump(mode="json"), settings.cache_ttl_data)
    return response


@router.get("/{code}/inflation", response_model=InflationResponse)
async def get_inflation(code: str, db: AsyncSession = Depends(get_db)):
    """Cumulative trailing 12-month inflation: actuals + forecast."""
    _validate_code(code)
    cached = await cache_get(f"fe:{code}:inflation")
    if cached:
        return cached

    ind = await db.execute(select(Indicator).where(Indicator.code == code))
    indicator = ind.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    CPI_ALLOWED = {"cpi", "cpi-food", "cpi-nonfood", "cpi-services"}
    if indicator.code not in CPI_ALLOWED:
        raise HTTPException(
            status_code=400,
            detail="Endpoint /inflation is only available for CPI indicators (cpi, cpi-food, cpi-nonfood, cpi-services)",
        )

    data_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(IndicatorData.date)
    )
    all_data = data_q.scalars().all()

    if len(all_data) < 13:
        return InflationResponse(indicator=code, actuals=[], forecast=[])

    dates = [d.date for d in all_data]
    factors = [float(d.value) / 100.0 for d in all_data]

    actuals = []
    for i in range(11, len(factors)):
        cum = math.prod(factors[i - 11:i + 1]) * 100 - 100
        actuals.append(InflationPoint(date=dates[i], value=round(cum, 4)))

    # Check for dedicated Inflation-12M forecast (НА's Model 1)
    infl_fc_q = await db.execute(
        select(Forecast)
        .where(
            Forecast.indicator_id == indicator.id,
            Forecast.is_current,
            Forecast.model_name.like("Inflation-12M%"),
        )
        .order_by(desc(Forecast.created_at))
        .limit(1)
    )
    infl_forecast = infl_fc_q.scalar_one_or_none()

    forecast_points = []
    model_name = None

    if infl_forecast:
        model_name = infl_forecast.model_name
        vals_q = await db.execute(
            select(ForecastValue)
            .where(ForecastValue.forecast_id == infl_forecast.id)
            .order_by(ForecastValue.date)
        )
        for v in vals_q.scalars().all():
            forecast_points.append(InflationForecastPoint(
                date=v.date,
                value=round(float(v.value), 4),
            ))
    else:
        # Fallback: compute from monthly CPI forecast
        fc_q = await db.execute(
            select(Forecast)
            .where(
                Forecast.indicator_id == indicator.id,
                Forecast.is_current,
                ~Forecast.model_name.like("Inflation-12M%"),
            )
            .order_by(desc(Forecast.created_at))
            .limit(1)
        )
        forecast_obj = fc_q.scalar_one_or_none()

        if forecast_obj:
            model_name = forecast_obj.model_name
            vals_q = await db.execute(
                select(ForecastValue)
                .where(ForecastValue.forecast_id == forecast_obj.id)
                .order_by(ForecastValue.date)
            )
            fc_values = vals_q.scalars().all()

            if fc_values:
                fc_factors = [float(fv.value) / 100.0 for fv in fc_values]

                for m in range(len(fc_factors)):
                    n_actual = 12 - (m + 1)
                    actual_part = factors[-n_actual:] if n_actual > 0 else []

                    fc_part = fc_factors[:m + 1]
                    cum = math.prod(actual_part + fc_part) * 100 - 100

                    forecast_points.append(InflationForecastPoint(
                        date=fc_values[m].date,
                        value=round(cum, 4),
                    ))

    response = InflationResponse(
        indicator=code,
        model_name=model_name,
        actuals=actuals,
        forecast=forecast_points,
    )
    await cache_set(
        f"fe:{code}:inflation",
        response.model_dump(mode="json"),
        settings.cache_ttl_data,
    )
    return response
