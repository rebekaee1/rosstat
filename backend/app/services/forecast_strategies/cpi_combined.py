"""CPI combined: CPI-Monthly + Inflation-12M + propagate to derived.

Источник: блокноты Никиты `Прогноз_ИПЦ_помесячно (2).ipynb` и
`Прогноз_инфляции_12_мес (1).ipynb` (May 2026). Обе модели работают
параллельно для одного и того же CPI-индикатора:
- `CPI-Monthly-MW` — помесячный индекс к предыдущему месяцу × 100.
- `Inflation-12M-MW` — накопленная за 12 мес. инфляция, %.

Кроме того, прогноз CPI распространяется на 3 производных
индикатора (quarterly, annual): они физически живут как отдельные
ряды в БД, но прогноз для них считается тут же из родительского CPI.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import (
    aggregate_quarterly_from_monthly,
    train_inflation_12m,
    train_monthly_cpi,
    ForecastPoint,
    ForecastResult,
)

logger = logging.getLogger(__name__)


CPI_DERIVED_CODES: dict[str, dict[str, str]] = {
    "cpi": {"quarterly": "inflation-quarterly", "annual": "inflation-annual"},
    "cpi-food": {"quarterly": "cpi-food-quarterly", "annual": "cpi-food-annual"},
    "cpi-nonfood": {"quarterly": "cpi-nonfood-quarterly", "annual": "cpi-nonfood-annual"},
    "cpi-services": {"quarterly": "cpi-services-quarterly", "annual": "cpi-services-annual"},
}

CPI_DERIVED_TARGETS = {
    code for targets in CPI_DERIVED_CODES.values() for code in targets.values()
}


def cpi_combined_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    monthly = train_monthly_cpi(list(dates), list(values), forecast_steps=ctx.forecast_steps)
    inflation = train_inflation_12m(list(dates), list(values), forecast_steps=ctx.forecast_steps)

    outputs: list[StrategyOutput] = [
        StrategyOutput(result=monthly, model_name_prefix="CPI-Monthly"),
        StrategyOutput(result=inflation, model_name_prefix="Inflation-12M"),
    ]

    derived = CPI_DERIVED_CODES.get(ctx.indicator_code)
    if derived:
        quarterly_result = aggregate_quarterly_from_monthly(
            list(dates), list(values), monthly.points,
        )
        if quarterly_result.points:
            outputs.append(StrategyOutput(
                result=quarterly_result,
                target_indicator_code=derived["quarterly"],
            ))

        if inflation.points:
            annual_result = ForecastResult(
                model_name="Annual-From-12M-Rolling",
                aic=None, bic=None,
                points=[
                    ForecastPoint(
                        date=p.date, value=p.value,
                        lower_bound=p.lower_bound, upper_bound=p.upper_bound,
                    )
                    for p in inflation.points
                ],
            )
            outputs.append(StrategyOutput(
                result=annual_result,
                target_indicator_code=derived["annual"],
            ))

    logger.info(
        "cpi_combined: %s → %d outputs (incl. derived)",
        ctx.indicator_code, len(outputs),
    )
    return outputs
