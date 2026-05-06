"""CPI combined: CPI-Monthly + Inflation-12M + propagate to quarterly derived.

Источник: блокноты Никиты `Прогноз_ИПЦ_помесячно (2).ipynb` и
`Прогноз_инфляции_12_мес (1).ipynb` (May 2026). Обе модели работают
параллельно для одного и того же CPI-индикатора:
- `CPI-Monthly-MW` — помесячный индекс к предыдущему месяцу × 100.
- `Inflation-12M-MW` — накопленная за 12 мес. (rolling) инфляция, %.

Прогноз CPI каскадно даёт прогноз квартальной инфляции (произведение 3 мес.
индексов). Годовые ряды (`*-annual`) с 2026-05-06 — отдельные индикаторы
с frequency=annual и собственным прогнозом через `derived_from_source` +
operation=`december_to_december`; этот файл больше их не пропагирует.
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
)

logger = logging.getLogger(__name__)


CPI_DERIVED_CODES: dict[str, dict[str, str]] = {
    "cpi": {"quarterly": "inflation-quarterly"},
    "cpi-food": {"quarterly": "cpi-food-quarterly"},
    "cpi-nonfood": {"quarterly": "cpi-nonfood-quarterly"},
    "cpi-services": {"quarterly": "cpi-services-quarterly"},
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

    logger.info(
        "cpi_combined: %s → %d outputs (incl. derived)",
        ctx.indicator_code, len(outputs),
    )
    return outputs
