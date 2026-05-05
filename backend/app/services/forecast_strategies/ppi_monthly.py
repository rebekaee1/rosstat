"""Monthly PPI forecast (Никита's `Прогноз_ИЦП.ipynb`).

Прогноз индекса цен производителей, помесячно. Multi-window OLS на
log-diff без блендинга. Применяется к индикатору `ppi`.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import train_ppi_monthly

logger = logging.getLogger(__name__)


def ppi_monthly_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    result = train_ppi_monthly(
        list(dates), list(values), forecast_steps=ctx.forecast_steps,
    )
    logger.info(
        "ppi_monthly: %s → %d points", ctx.indicator_code, len(result.points),
    )
    return [StrategyOutput(result=result)]
