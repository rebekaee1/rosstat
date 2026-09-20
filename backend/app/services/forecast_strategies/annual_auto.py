"""Annual-Auto: generic year forecast for annual source indicators.

Порт `Прогноз_годовых_данных.ipynb` (руководитель): ADF-автотрансформ
(уровень / первая разность / лог-разность) + multi-window OLS по лагам
горизонта, отсев мультиколлинеарности и backward-elimination, окна
взвешиваются обратно дисперсии. Горизонт не больше 4 лет.

См. `forecaster.train_annual_auto`.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import train_annual_auto

logger = logging.getLogger(__name__)


def annual_auto_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    result = train_annual_auto(
        list(dates), list(values),
        forecast_steps=ctx.forecast_steps or 2,
    )
    logger.info("annual_auto: %s → %d points", ctx.indicator_code, len(result.points))
    return [StrategyOutput(result=result)]
