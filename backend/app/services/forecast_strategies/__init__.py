"""Forecast strategies registry.

См. `registry.py` для контракта стратегии и списка зарегистрированных.
"""

from app.services.forecast_strategies.base import (
    ForecastStrategy,
    StrategyContext,
    StrategyOutput,
)
from app.services.forecast_strategies.registry import STRATEGIES, resolve

__all__ = [
    "ForecastStrategy",
    "StrategyContext",
    "StrategyOutput",
    "STRATEGIES",
    "resolve",
]
