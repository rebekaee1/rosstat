"""Единая авторская модель + world quality gate.

Кандидат строится теми же зарегистрированными multi-window стратегиями, что
используются для российских рядов: ``monthly_auto`` / ``annual_auto`` и
``generic_quarterly``/``signed_quarterly``. Rolling-origin MASE сохраняется
в метаданных. Публичным является только прогноз, прошедший гейт качества.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Sequence

from app.services.forecast_strategies import StrategyContext, resolve
from app.services.forecaster import ForecastPoint, ForecastResult


WORLD_FORECAST_METHOD_VERSION = 2
PUBLISHED_GATE_STATUSES: frozenset[str] = frozenset({"passed"})


def publishable_world_forecast(forecast: object) -> bool:
    """Old gate versions did not backtest the full published horizon."""
    params = getattr(forecast, "model_params", None)
    return (
        getattr(forecast, "gate_status", None) in PUBLISHED_GATE_STATUSES
        and isinstance(params, dict)
        and params.get("method_version") == WORLD_FORECAST_METHOD_VERSION
    )


def is_percentage_unit(unit: str | None) -> bool:
    normalized = (unit or "").strip().upper()
    return "%" in normalized or normalized in {"PERCENT", "PERCENTAGE"}


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


def _contiguous_tail_start(dates: Sequence[date], step_months: int) -> int | None:
    """Последний непрерывный отрезок факта; пропущенные периоды не выдумываем."""
    start = 0
    for index, (left, right) in enumerate(zip(dates, dates[1:]), start=1):
        delta = _month_index(right) - _month_index(left)
        if delta <= 0 or delta % step_months != 0:
            return None
        if delta > step_months:
            start = index
    return start


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


def _backtest_layout(frequency: str, season: int, horizon: int) -> tuple[int, int, int, int, int, int]:
    """step_months, test_horizon, requested_origins, min_origins, min_history, origin_floor."""
    if frequency == "annual":
        return 12, horizon, 4, 3, 14, 10
    if frequency == "monthly":
        return 1, horizon, 6, 6, season * 6, season * 4
    return 3, horizon, 6, 6, season * 6, season * 5


def train_quality_gated_world_forecast(
    dates: Sequence[date],
    values: Sequence[float],
    *,
    frequency: str,
    horizon: int,
    season: int,
    strategy: str,
    strict: bool = True,
) -> WorldForecastGate:
    resolved_strategy = _resolve_primary_strategy(strategy, values)
    (
        step_months, test_horizon, requested_origins,
        min_origins, min_history, origin_floor,
    ) = _backtest_layout(frequency, season, horizon)
    if horizon < 1 or season < 1:
        return WorldForecastGate(
            "failed", "invalid_forecast_horizon", resolved_strategy, None, None, 0, None,
        )
    if len(dates) != len(values) or len(values) < min_history:
        return WorldForecastGate(
            "failed", "history_too_short", resolved_strategy, None, None, 0, None,
        )
    if any(not math.isfinite(float(value)) for value in values):
        return WorldForecastGate(
            "failed", "non_finite_history", resolved_strategy, None, None, 0, None,
        )

    tail_start = _contiguous_tail_start(dates, step_months)
    if tail_start is None:
        return WorldForecastGate(
            "failed", "irregular_calendar", resolved_strategy, None, None, 0, None,
        )
    if tail_start:
        dates = dates[tail_start:]
        values = values[tail_start:]
        if len(values) < min_history:
            return WorldForecastGate(
                "failed", "recent_history_gap", resolved_strategy, None, None, 0, None,
            )

    first_origin = max(
        origin_floor,
        len(values) - requested_origins - test_horizon + 1,
    )
    origins = list(range(first_origin, len(values) - test_horizon + 1))
    if len(origins) < min_origins:
        return WorldForecastGate(
            "failed", "not_enough_backtest_origins",
            resolved_strategy, None, None, 0, None,
        )

    candidate_errors: list[float] = []
    candidate_scaled_errors: list[float] = []
    baseline_scaled_errors: list[float] = []
    for origin in origins:
        train_dates = dates[:origin]
        train = values[:origin]
        actual = [float(value) for value in values[origin:origin + test_horizon]]
        # MASE denominator известен только в точке origin. Полная история
        # включала test targets и меняла решение гейта задним числом.
        scale = _scale(train, season)
        if scale is None:
            return WorldForecastGate(
                "failed", "constant_or_unscaled_series",
                resolved_strategy, None, None, len(candidate_errors), None,
            )
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
        if any(
            _month_index(point.date) - _month_index(train_dates[-1]) != step_months * step
            for step, point in enumerate(candidate_result.points, start=1)
        ):
            return WorldForecastGate(
                "failed", "invalid_backtest_dates",
                resolved_strategy, None, None, len(candidate_errors), None,
            )
        candidate = [float(point.value) for point in candidate_result.points]
        baseline = _seasonal_projection(
            train, season=season, steps=test_horizon, drift=False,
        )
        candidate_errors.extend(
            predicted - observed for predicted, observed in zip(candidate, actual)
        )
        candidate_scaled_errors.extend(
            abs(predicted - observed) / scale for predicted, observed in zip(candidate, actual)
        )
        baseline_scaled_errors.extend(
            abs(predicted - observed) / scale for predicted, observed in zip(baseline, actual)
        )

    mase = sum(candidate_scaled_errors) / len(candidate_scaled_errors)
    baseline_mase = sum(baseline_scaled_errors) / len(baseline_scaled_errors)
    if not math.isfinite(mase) or not math.isfinite(baseline_mase):
        return WorldForecastGate(
            "failed", "non_finite_backtest",
            resolved_strategy, None, None, len(origins), None,
        )

    quality_ok = mase < 1.0 and mase < baseline_mase * 0.98
    if mase >= 1.0:
        quality_reason = "mase_not_below_one"
    elif mase >= baseline_mase * 0.98:
        quality_reason = "not_better_than_seasonal_naive"
    else:
        quality_reason = "beats_seasonal_naive"
    if not quality_ok and strict:
        return WorldForecastGate(
            "failed", quality_reason,
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
    if any(
        _month_index(point.date) - _month_index(dates[-1]) != step_months * step
        for step, point in enumerate(candidate_result.points, start=1)
    ):
        return WorldForecastGate(
            "failed", "invalid_forecast_dates",
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
    points: list[ForecastPoint] = []
    for step, source_point in enumerate(candidate_result.points, start=1):
        prediction = float(source_point.value)
        uncertainty = 1.96 * sigma * math.sqrt(step)
        lower = prediction - uncertainty
        upper = prediction + uncertainty
        if not all(math.isfinite(item) for item in (prediction, lower, upper)):
            return WorldForecastGate(
                "failed", "non_finite_forecast_interval",
                resolved_strategy, mase, baseline_mase, len(origins), None,
            )
        points.append(ForecastPoint(
            date=source_point.date,
            value=prediction,
            lower_bound=float(lower),
            upper_bound=float(upper),
        ))

    result = ForecastResult(
        model_name=candidate_result.model_name,
        aic=candidate_result.aic,
        bic=candidate_result.bic,
        points=points,
    )
    status = "passed" if quality_ok else "advisory"
    return WorldForecastGate(
        status, quality_reason,
        resolved_strategy, mase, baseline_mase, len(origins), result,
    )
