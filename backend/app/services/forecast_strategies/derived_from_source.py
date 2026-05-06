"""Derived forecast: производный прогноз от прогноза другого индикатора.

Когда у индикатора X есть свой прогноз (например, gdp-nominal), а
индикатор Y — это его математическая производная (например, gdp-yoy =
yoy от gdp-nominal), нет смысла отдельно обучать модель Y.

Эта стратегия читает прогноз индикатора-источника из БД, применяет
формулу `op` к (история X + прогноз X) и выдаёт прогноз для Y.

Конфигурация в `model_config_json.derived_forecast`:
    {
        "source_code": "gdp-nominal",
        "operation": "yoy",      // см. список ниже
        "model_name": "GDP-YoY-Derived",
        "extra": {...}           // op-специфические аргументы
    }

Поддерживаемые operation (соответствуют DerivedSpec ops в БД):
    - yoy_quarterly       : Y[t] = (X[t] / X[t-4]) * 100 - 100   (квартальный yoy)
    - yoy_monthly         : Y[t] = (X[t] / X[t-12]) * 100 - 100  (месячный yoy)
    - qoq                 : Y[t] = (X[t] / X[t-1]) * 100 - 100
    - real_from_yoy       : Y[t] = Y[t-1y] * (1 + yoy_source[t]/100)
    - december_to_december: Y[year] = (∏ X[m]/100 за m=Jan..Dec) * 100 - 100
                            (1 точка/год, точка анкорится на date(year, 1, 1);
                            годы с неполными 12 мес. пропускаются)
    - annual_sum          : Y[year] = Σ X[q] за q ∈ year
                            (1 точка/год, для квартальных рядов нужны 4 кв.;
                            годы с неполным числом точек пропускаются)

ВАЖНО: эта стратегия — RUNTIME-only. Она не пишет в БД, она лишь
готовит точки прогноза, которые pipeline сохранит обычным образом.
БД-доступ принципиально нужен (читаем прогноз источника), поэтому
сигнатура стратегии расширена опциональным `db_session` через ctx.cfg.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import ForecastPoint, ForecastResult
from app.services.derived_ops import (
    annual_sum as ops_annual_sum,
    december_to_december as ops_december_to_december,
)

logger = logging.getLogger(__name__)


def _yoy(values_with_dates: list[tuple[date, float]], step: int) -> list[tuple[date, float]]:
    """Y[t] = (X[t] / X[t-step]) * 100 - 100. step=12 для месячного yoy, 4 для квартального."""
    by_date = {d: v for d, v in values_with_dates}
    out: list[tuple[date, float]] = []
    sorted_pairs = sorted(values_with_dates)
    for i, (d, v) in enumerate(sorted_pairs):
        if i < step or v is None:
            continue
        prev_d, prev_v = sorted_pairs[i - step]
        if prev_v in (None, 0):
            continue
        out.append((d, v / prev_v * 100.0 - 100.0))
    return out


def _qoq(values_with_dates: list[tuple[date, float]]) -> list[tuple[date, float]]:
    out: list[tuple[date, float]] = []
    sorted_pairs = sorted(values_with_dates)
    for i in range(1, len(sorted_pairs)):
        d, v = sorted_pairs[i]
        prev_d, prev_v = sorted_pairs[i - 1]
        if prev_v in (None, 0) or v is None:
            continue
        out.append((d, v / prev_v * 100.0 - 100.0))
    return out


def derived_from_source_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    """Derived forecast — нужен `_runtime_helpers.source_actuals_and_forecast` в ctx.cfg.

    Pipeline собирает источник перед вызовом этой стратегии и кладёт его в:
        ctx.cfg["_source_data"] = list[(date, float)]   # actuals + forecast вместе
    Если данных нет — возвращаем пустой результат (pipeline почистит старый прогноз).
    """
    derived_cfg = ctx.cfg.get("derived_forecast") or {}
    operation = derived_cfg.get("operation")
    model_name = str(derived_cfg.get("model_name", f"{ctx.indicator_code}-Derived"))

    source_data = ctx.cfg.get("_source_data") or []
    if not source_data:
        logger.warning(
            "derived_from_source: %s — no _source_data in ctx; pipeline must inject it",
            ctx.indicator_code,
        )
        return []

    last_actual_date = max(dates) if len(dates) else None

    if operation == "yoy_quarterly":
        derived_full = _yoy(source_data, step=4)
    elif operation == "yoy_monthly":
        derived_full = _yoy(source_data, step=12)
    elif operation == "qoq":
        derived_full = _qoq(source_data)
    elif operation == "real_from_yoy":
        # gdp-real[t] = gdp-real[t-1year] * (1 + gdp-yoy[t] / 100), при условии что
        # source_data == список (date, yoy_value).
        # ВАЖНО: исторические real-точки не перезаписываем (они factual),
        # только заполняем будущие даты, используя факт за tn-1y как базу.
        derived_full = []
        sorted_pairs = sorted(source_data)
        actual_real: dict[date, float] = {d: v for d, v in zip(dates, values)}
        running: dict[date, float] = dict(actual_real)
        for d, yoy_v in sorted_pairs:
            if d in actual_real or yoy_v is None:
                continue
            year_ago = date(d.year - 1, d.month, 1)
            base = running.get(year_ago)
            if base is None:
                continue
            new_val = base * (1.0 + yoy_v / 100.0)
            running[d] = new_val
            derived_full.append((d, new_val))
    elif operation == "december_to_december":
        # 1 точка на год: годовая инфляция = ∏ месячных индексов / 100 - 1.
        # Используем ту же чистую функцию, что и CalculationEngine для actuals,
        # — гарантирует, что forecast и historic считаются одинаково.
        derived_full = ops_december_to_december(list(source_data))
    elif operation == "annual_sum":
        # 1 точка на год: годовая сумма по календарному году. Для квартального
        # источника нужны 4 кв., для месячного — 12 мес. Год с неполным числом
        # точек игнорируется.
        derived_full = ops_annual_sum(list(source_data))
    else:
        logger.error("derived_from_source: unknown operation '%s'", operation)
        return []

    if last_actual_date is None:
        future_only = derived_full
    else:
        future_only = [(d, v) for d, v in derived_full if d > last_actual_date]

    if not future_only:
        logger.info(
            "derived_from_source: %s → 0 future points (op=%s)",
            ctx.indicator_code, operation,
        )
        return []

    points = [
        ForecastPoint(date=d, value=round(float(v), 4), lower_bound=None, upper_bound=None)
        for d, v in future_only
    ]
    result = ForecastResult(model_name=model_name, aic=None, bic=None, points=points)
    logger.info(
        "derived_from_source: %s → %d points (op=%s, model=%s)",
        ctx.indicator_code, len(points), operation, model_name,
    )
    return [StrategyOutput(result=result)]
