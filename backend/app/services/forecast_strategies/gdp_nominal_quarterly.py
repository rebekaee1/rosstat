"""Quarterly nominal GDP forecast (Никита's `Прогноз_номинальный_ВВП.ipynb`).

Прогноз номинального ВВП, квартально. Multi-window OLS на log-diff
без блендинга. Применяется к индикатору `gdp-nominal`.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import train_gdp_nominal_quarterly

logger = logging.getLogger(__name__)


def gdp_nominal_quarterly_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    result = train_gdp_nominal_quarterly(
        list(dates), list(values), forecast_steps=ctx.forecast_steps,
    )
    logger.info(
        "gdp_nominal_quarterly: %s → %d points",
        ctx.indicator_code, len(result.points),
    )
    return [StrategyOutput(result=result)]
