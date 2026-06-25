"""Signed quarterly forecast strategy.

Для квартальных рядов со СМЕНОЙ ЗНАКА (сальдо текущего счёта и любое
квартальное сальдо, для которого нет более точного тождества из компонент).
Применяет ту же multi-window OLS методологию семейства ВВП, но на ПЕРВОЙ
РАЗНОСТИ уровня (`transform="level"`), а не на log-diff: реконструкция
аддитивная, поэтому прогноз свободно пересекает ноль.

Для `trade-balance` предпочтительнее тождество exports − imports
(`derived_from_source` operation="subtract") — оно согласовано с прогнозами
компонент. Эта стратегия — для рядов без такого тождества (current-account).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import train_signed_quarterly

logger = logging.getLogger(__name__)


def signed_quarterly_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    model_name = f"{ctx.indicator_code}-Quarterly-MW"
    result = train_signed_quarterly(
        list(dates), list(values),
        forecast_steps=ctx.forecast_steps or 4,
        model_name=model_name,
    )
    logger.info(
        "signed_quarterly: %s → %d points",
        ctx.indicator_code, len(result.points),
    )
    return [StrategyOutput(result=result)]
