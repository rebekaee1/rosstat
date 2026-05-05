"""Generic OLS multi-window: универсальная модель для остальных индикаторов.

Это «безопасный fallback», переиспользует `train_and_forecast` —
тот же OLS multi-window, что был у нас исторически. `forecast_transform`
и частота берутся из `model_config`.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import train_and_forecast

logger = logging.getLogger(__name__)


def generic_ols_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    forecast_transform = ctx.cfg.get("forecast_transform", "absolute")
    result = train_and_forecast(
        list(dates), list(values),
        forecast_steps=ctx.forecast_steps,
        forecast_transform=forecast_transform,
        frequency=ctx.indicator_frequency or "monthly",
    )
    logger.info(
        "generic_ols: %s (transform=%s) → %d points",
        ctx.indicator_code, forecast_transform, len(result.points),
    )
    return [StrategyOutput(result=result)]
