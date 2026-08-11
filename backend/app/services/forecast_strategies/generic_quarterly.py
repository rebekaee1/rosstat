"""Generic quarterly forecast strategy.

Для квартальных source-рядов без собственного notebook'а Никиты, чей ряд
**строго положителен** и трендов (экспорт, импорт, внешний долг). Применяет
ту же методологию семейства ВВП (multi-window OLS на log-diff, без
блендинга), что и `gdp_nominal_quarterly`/`gdp_consumption_quarterly`, но
помечает прогноз именем модели, производным от кода индикатора.

НЕ применять к рядам со сменой знака (сальдо торгового баланса, счёт
текущих операций, дефицит бюджета): log-diff там неопределён. Для знаковых
квартальных рядов нужна отдельная level-diff стратегия — см. backlog.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import train_generic_quarterly

logger = logging.getLogger(__name__)


def generic_quarterly_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    model_name = ctx.cfg.get("model_name") or f"{ctx.indicator_code}-Quarterly-MW"
    result = train_generic_quarterly(
        list(dates), list(values),
        forecast_steps=ctx.forecast_steps or 4,
        model_name=model_name,
    )
    logger.info(
        "generic_quarterly: %s → %d points",
        ctx.indicator_code, len(result.points),
    )
    return [StrategyOutput(result=result)]
