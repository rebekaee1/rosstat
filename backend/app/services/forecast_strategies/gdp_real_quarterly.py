"""Quarterly real GDP forecast — прямая SARIMA на ряду реального ВВП.

Соответствует вызову `train_sarima_model(data, forecast_steps=4)` из
ноутбука Никиты, где `data` = реальный ВВП напрямую (без вычисления
через yoy от номинального). Это устраняет ошибку цепочки
`gdp-real ← real_from_yoy(gdp-yoy) ← yoy_quarterly(gdp-nominal SARIMA)`,
которая давала расхождение 4.5–7.5% по 2026 году.

Та же модель и те же параметры, что у `gdp_nominal_quarterly`,
отличается только применяемый ряд и `model_name`.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import train_gdp_real_quarterly

logger = logging.getLogger(__name__)


def gdp_real_quarterly_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    result = train_gdp_real_quarterly(
        list(dates), list(values), forecast_steps=ctx.forecast_steps,
    )
    logger.info(
        "gdp_real_quarterly: %s → %d points",
        ctx.indicator_code, len(result.points),
    )
    return [StrategyOutput(result=result)]
