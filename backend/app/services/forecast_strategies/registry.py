"""Реестр forecast-стратегий: имя → callable.

Добавление новой стратегии:
1. Создать модуль `forecast_strategies/<name>.py` со стратегией —
   функцией с сигнатурой `ForecastStrategy`.
2. Зарегистрировать её в `STRATEGIES` ниже.
3. В seed_data.py / БД проставить `model_config.forecast_strategy = "<name>"`
   у соответствующего индикатора.
4. Добавить snapshot-тест в `backend/tests/forecast_strategies/`.

Если у индикатора `forecast_strategy` не задан, pipeline использует
fallback `legacy_resolve(indicator)`, который копирует if-цепочку из
старого `forecast_pipeline.py`. Это позволяет мигрировать постепенно,
индикатор за индикатором, без big-bang.
"""

from __future__ import annotations

import logging

from app.services.forecast_strategies.approved import approved_strategy
from app.services.forecast_strategies.base import ForecastStrategy
from app.services.forecast_strategies.cpi_combined import cpi_combined_strategy
from app.services.forecast_strategies.derived_from_source import derived_from_source_strategy
from app.services.forecast_strategies.generic_ols import generic_ols_strategy
from app.services.forecast_strategies.gdp_consumption_quarterly import gdp_consumption_quarterly_strategy
from app.services.forecast_strategies.gdp_government_quarterly import gdp_government_quarterly_strategy
from app.services.forecast_strategies.gdp_nominal_quarterly import gdp_nominal_quarterly_strategy
from app.services.forecast_strategies.gdp_real_quarterly import gdp_real_quarterly_strategy
from app.services.forecast_strategies.housing_quarterly import housing_quarterly_strategy
from app.services.forecast_strategies.ppi_monthly import ppi_monthly_strategy

logger = logging.getLogger(__name__)


STRATEGIES: dict[str, ForecastStrategy] = {
    "approved": approved_strategy,
    "cpi_combined": cpi_combined_strategy,
    "derived_from_source": derived_from_source_strategy,
    "generic_ols": generic_ols_strategy,
    "gdp_consumption_quarterly": gdp_consumption_quarterly_strategy,
    "gdp_government_quarterly": gdp_government_quarterly_strategy,
    "gdp_nominal_quarterly": gdp_nominal_quarterly_strategy,
    "gdp_real_quarterly": gdp_real_quarterly_strategy,
    "housing_quarterly": housing_quarterly_strategy,
    "ppi_monthly": ppi_monthly_strategy,
}


def resolve(name: str | None) -> ForecastStrategy | None:
    """Найти стратегию по имени. None → None (включает legacy-fallback)."""
    if not name:
        return None
    strategy = STRATEGIES.get(name)
    if strategy is None:
        logger.warning(
            "Unknown forecast_strategy='%s'; falling back to legacy resolver", name,
        )
    return strategy


__all__ = ["STRATEGIES", "resolve"]
