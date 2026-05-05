"""Approved forecast: точки прогноза заданы вручную в model_config.

Используется для индикаторов, у которых прогноз — это прямой импорт
точек из блокнота Никиты (без локального пересчёта). Контракт точек:

    "approved_forecast_values": [
        {"date": "2026-04-01", "value": 100.5480},
        {"date": "2026-05-01", "value": 100.5182},
        ...
    ]

Имя модели берётся из `forecast_model_name` (по умолчанию `Approved-Forecast`).

Эта стратегия гарантирует совпадение «точь-в-точь» с блокнотом до
следующей перезагрузки точек.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import ForecastPoint, ForecastResult

logger = logging.getLogger(__name__)


def approved_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    approved = ctx.cfg.get("approved_forecast_values") or []
    if not approved:
        logger.warning(
            "approved_strategy: no approved_forecast_values for '%s'; returning empty",
            ctx.indicator_code,
        )
        return []

    model_name = str(ctx.cfg.get("forecast_model_name", "Approved-Forecast"))
    points = [
        ForecastPoint(
            date=date.fromisoformat(str(item["date"])),
            value=round(float(item["value"]), 4),
            lower_bound=None,
            upper_bound=None,
        )
        for item in approved
    ]
    result = ForecastResult(
        model_name=model_name,
        aic=None, bic=None,
        points=points,
    )
    logger.info(
        "approved_strategy: %s → %d approved points (%s)",
        ctx.indicator_code, len(points), model_name,
    )
    return [StrategyOutput(result=result)]
