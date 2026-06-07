"""Monthly-Auto: generic month forecast for all monthly source indicators.

Порт `Прогноз_месячных_данных.ipynb` (руководитель, июнь 2026): один
универсальный алгоритм для всех месячных показателей (денежная масса,
ставки, кредиты, депозиты, рынок труда, бюджет, торговля и т.п.).
ADF выбирает трансформ (уровень/разность/лог-разность), дальше —
multi-window OLS по лагам с отсевом мультиколлинеарности и
backward-elimination, прогнозы окон взвешиваются обратно дисперсии.

См. `forecaster.train_monthly_auto`.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import train_monthly_auto

logger = logging.getLogger(__name__)


def monthly_auto_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    result = train_monthly_auto(
        list(dates), list(values),
        forecast_steps=ctx.forecast_steps or 12,
    )
    logger.info("monthly_auto: %s → %d points", ctx.indicator_code, len(result.points))
    return [StrategyOutput(result=result)]
