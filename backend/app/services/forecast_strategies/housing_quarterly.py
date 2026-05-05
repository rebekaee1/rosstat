"""Quarterly housing-price index forecast.

Источник: блокнот Никиты `Прогнозы_цены_на_жилье (1).ipynb` (May 2026).
Применяется к индикаторам `housing-price-primary` и `housing-price-secondary`
(квартальные индексы, level=index).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import train_quarterly_housing

logger = logging.getLogger(__name__)


def housing_quarterly_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    result = train_quarterly_housing(
        list(dates), list(values), forecast_steps=ctx.forecast_steps,
    )
    logger.info(
        "housing_quarterly: %s → %d points", ctx.indicator_code, len(result.points),
    )
    return [StrategyOutput(result=result)]
