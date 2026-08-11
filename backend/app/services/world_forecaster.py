"""Единая авторская модель + строгий world quality gate.

Кандидат строится теми же зарегистрированными multi-window стратегиями, что
используются для российских рядов: ``monthly_auto`` для месячных данных и
``generic_quarterly``/``signed_quarterly`` для квартальных. World-контур
добавляет rolling-origin проверку против seasonal-naive и публикует только
ряды с MASE < 1 и доказанным выигрышем у ориентира.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Sequence

from app.services.forecast_strategies import StrategyContext, resolve
from app.services.forecaster import ForecastPoint, ForecastResult


@dataclass(frozen=True)
class WorldForecastGate:
    status: str
    reason: str
    strategy: str
    mase: float | None
    baseline_mase: float | None
    origins: int
    result: ForecastResult | None


def _month_index(value: date) -> int:
    return value.year * 12 + value.month


def _regular_cadence(dates: Sequence[date], step_months: int) -> bool:
    return all(
        _month_index(right) - _month_index(left) == step_months
        for left, right in zip(dates, dates[1:])
    )


def _seasonal_projection(
    values: Sequence[float],
    *,
    season: int,
    steps: int,
    drift: bool,
) -> list[float]:
    history = [float(value) for value in values]
    phase_drifts: dict[int, float] = {}
    if drift:
        for phase in range(season):
            changes = [
                history[index] - history[index - season]
                for index in range(season, len(history))
                if index % season == phase
            ]
            # Последние пять сопоставимых лет/циклов: устойчивее долгой истории
            # со структурными сдвигами, но не реагирует на один выброс.
            phase_drifts[phase] = median(changes[-5:]) if changes else 0.0

    predictions: list[float] = []
    for _ in range(steps):
        index = len(history)
        base = history[index - season]
        value = base + phase_drifts.get(index % season, 0.0)
        predictions.append(float(value))
        history.append(float(value))
    return predictions


def _mae(values: Sequence[float]) -> float:
    return sum(abs(value) for value in values) / len(values)


def _scale(values: Sequence[float], season: int) -> float | None:
    diffs = [
        float(values[index]) - float(values[index - season])
        for index in range(season, len(values))
    ]
    if not diffs:
        return None
    scale = _mae(diffs)
    return scale if math.isfinite(scale) and scale > 1e-12 else None


def _resolve_primary_strategy(
    requested: str,
    values: Sequence[float],
) -> str:
    """Разрешить policy-алиас в стратегию общего реестра.

    Для квартального уровня лог-модель допустима только на строго положительной
    истории. Знаковые и нулевые ряды используют тот же multi-window алгоритм
    на первой разности уровня.
    """
    if requested == "quarterly_auto":
        return "generic_quarterly" if all(float(value) > 0 for value in values) else "signed_quarterly"
    return requested


def _run_primary_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    *,
    frequency: str,
    horizon: int,
    strategy_name: str,
) -> ForecastResult | None:
    strategy = resolve(strategy_name)
    if strategy is None:
        return None
    ctx = StrategyContext(
        indicator_code="world",
        indicator_frequency=frequency,
        forecast_steps=horizon,
        cfg={"model_name": f"{strategy_name}-MW"},
    )
    outputs = strategy(dates, values, ctx)
    if len(outputs) != 1:
        return None
    result = outputs[0].result
    if len(result.points) < horizon:
        return None
    if any(not math.isfinite(float(point.value)) for point in result.points[:horizon]):
        return None
    return ForecastResult(
        model_name=f"World-{result.model_name}-v1",
        aic=result.aic,
        bic=result.bic,
        points=list(result.points[:horizon]),
        cumulative_12m=result.cumulative_12m,
        monthly_predictions=list(result.monthly_predictions),
    )


def train_quality_gated_world_forecast(
    dates: Sequence[date],
    values: Sequence[float],
    *,
    frequency: str,
    horizon: int,
    season: int,
    strategy: str,
) -> WorldForecastGate:
    resolved_strategy = _resolve_primary_strategy(strategy, values)
    if len(dates) != len(values) or len(values) < season * 6:
        return WorldForecastGate(
            "failed", "history_too_short", resolved_strategy, None, None, 0, None,
        )
    if any(not math.isfinite(float(value)) for value in values):
        return WorldForecastGate(
            "failed", "non_finite_history", resolved_strategy, None, None, 0, None,
        )

    step_months = 1 if frequency == "monthly" else 3
    if not _regular_cadence(dates, step_months):
        return WorldForecastGate(
            "failed", "irregular_calendar", resolved_strategy, None, None, 0, None,
        )

    test_horizon = 3 if frequency == "monthly" else 2
    requested_origins = 12 if frequency == "monthly" else 8
    first_origin = max(season * 4, len(values) - requested_origins - test_horizon + 1)
    origins = list(range(first_origin, len(values) - test_horizon + 1))
    if len(origins) < 6:
        return WorldForecastGate(
            "failed", "not_enough_backtest_origins",
            resolved_strategy, None, None, 0, None,
        )

    # Один общий denominator для всех rolling origins: seasonal-naive MAE по
    # полной доступной фактической истории. Это делает MASE сопоставимым между
    # origins и соответствует рекомендации Hyndman для rolling evaluation.
    scale = _scale(values, season)
    if scale is None:
        return WorldForecastGate(
            "failed", "constant_or_unscaled_series",
            resolved_strategy, None, None, 0, None,
        )

    candidate_errors: list[float] = []
    baseline_errors: list[float] = []
    for origin in origins:
        train_dates = dates[:origin]
        train = values[:origin]
        actual = [float(value) for value in values[origin:origin + test_horizon]]
        candidate_result = _run_primary_strategy(
            train_dates,
            train,
            frequency=frequency,
            horizon=test_horizon,
            strategy_name=resolved_strategy,
        )
        if candidate_result is None:
            return WorldForecastGate(
                "failed", "candidate_model_failed",
                resolved_strategy, None, None, len(candidate_errors), None,
            )
        candidate = [float(point.value) for point in candidate_result.points]
        baseline = _seasonal_projection(
            train, season=season, steps=test_horizon, drift=False,
        )
        candidate_errors.extend(
            predicted - observed for predicted, observed in zip(candidate, actual)
        )
        baseline_errors.extend(
            predicted - observed for predicted, observed in zip(baseline, actual)
        )

    mase = _mae(candidate_errors) / scale
    baseline_mase = _mae(baseline_errors) / scale
    if not math.isfinite(mase) or not math.isfinite(baseline_mase):
        return WorldForecastGate(
            "failed", "non_finite_backtest",
            resolved_strategy, None, None, len(origins), None,
        )
    if mase >= 1.0:
        return WorldForecastGate(
            "failed", "mase_not_below_one",
            resolved_strategy, mase, baseline_mase, len(origins), None,
        )
    if mase >= baseline_mase * 0.98:
        return WorldForecastGate(
            "failed", "not_better_than_seasonal_naive",
            resolved_strategy, mase, baseline_mase, len(origins), None,
        )

    candidate_result = _run_primary_strategy(
        dates,
        values,
        frequency=frequency,
        horizon=horizon,
        strategy_name=resolved_strategy,
    )
    if candidate_result is None:
        return WorldForecastGate(
            "failed", "candidate_model_failed",
            resolved_strategy, mase, baseline_mase, len(origins), None,
        )
    predictions = [float(point.value) for point in candidate_result.points]
    max_history = max(abs(float(value)) for value in values) or 1.0
    if any(abs(value) > max_history * 5 for value in predictions):
        return WorldForecastGate(
            "failed", "implausible_extrapolation",
            resolved_strategy, mase, baseline_mase, len(origins), None,
        )

    residual_mean = sum(candidate_errors) / len(candidate_errors)
    variance = sum(
        (error - residual_mean) ** 2 for error in candidate_errors
    ) / max(1, len(candidate_errors) - 1)
    sigma = math.sqrt(max(0.0, variance))
    non_negative = min(float(value) for value in values) >= 0
    points: list[ForecastPoint] = []
    for step, source_point in enumerate(candidate_result.points, start=1):
        prediction = float(source_point.value)
        uncertainty = 1.96 * sigma * math.sqrt(step)
        value = max(0.0, prediction) if non_negative else prediction
        lower = prediction - uncertainty
        upper = prediction + uncertainty
        if non_negative:
            lower = max(0.0, lower)
            upper = max(0.0, upper)
        points.append(ForecastPoint(
            date=source_point.date,
            value=float(value),
            lower_bound=float(lower),
            upper_bound=float(upper),
        ))

    result = ForecastResult(
        model_name=candidate_result.model_name,
        aic=candidate_result.aic,
        bic=candidate_result.bic,
        points=points,
    )
    return WorldForecastGate(
        "passed", "beats_seasonal_naive",
        resolved_strategy, mase, baseline_mase, len(origins), result,
    )
