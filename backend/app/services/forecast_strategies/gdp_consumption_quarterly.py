"""Quarterly forecast strategy for `gdp-consumption`.

Использует то же ядро (`_train_gdp_quarterly_port`), что и nominal/real GDP.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import train_gdp_consumption_quarterly

logger = logging.getLogger(__name__)


def gdp_consumption_quarterly_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    result = train_gdp_consumption_quarterly(
        list(dates), list(values), forecast_steps=ctx.forecast_steps,
    )
    logger.info(
        "gdp_consumption_quarterly: %s → %d points",
        ctx.indicator_code, len(result.points),
    )
    return [StrategyOutput(result=result)]
