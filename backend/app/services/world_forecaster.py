"""Единая авторская модель + world quality gate.

Кандидат строится теми же зарегистрированными multi-window стратегиями, что
используются для российских рядов: ``monthly_auto`` / ``annual_auto`` и
``generic_quarterly``/``signed_quarterly``. Rolling-origin MASE сохраняется
в метаданных. Публичным является только прогноз, прошедший гейт качества.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Sequence

from dateutil.relativedelta import relativedelta

from app.services.forecast_strategies import StrategyContext, resolve
from app.services.forecaster import ForecastPoint, ForecastResult
from app.services.world_forecast_candidates import (
    SEASONAL_DRIFT_NAME,
    WORLD_CANDIDATE_SET_VERSION,
    candidate_names,
    forecast_candidate,
    min_fit_points,
)


from app.services.world_forecast_gate import (  # noqa: E402,F401 — реэкспорт: старые импорты работают
    PUBLISHED_GATE_STATUSES,
    WORLD_FORECAST_METHOD_VERSION,
    publishable_world_forecast,
)

logger = logging.getLogger(__name__)


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
    # Параметры выбора модели (кандидатный путь); пишутся в model_params.
    details: dict | None = None


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


# Допущения круга 12 (не пороги качества): короткие дыры в самом ряду
# (например, октябрь 2025 в данных США из-за остановки госорганов: нет ИПЦ и
# безработицы за месяц) раньше отбрасывали всю историю до дыры и ряд падал с
# ``recent_history_gap``. Теперь дыры не длиннее MAX_GAP_STEPS периодов
# заполняются линейной интерполяцией, если заполненных точек не больше 5% ряда
# (минимум 2). Заполненные точки не участвуют в ошибках проверки (целевыми
# значениями служат только реальные наблюдения), число записывается в
# параметры прогноза (``imputed_points``). Дыры длиннее по-прежнему режут
# историю: берётся отрезок после последней такой дыры.
MAX_GAP_STEPS = {1: 2, 3: 1, 12: 1}
MAX_IMPUTED_SHARE = 0.05


@dataclass(frozen=True)
class _RegularSeries:
    dates: list[date]
    values: list[float]
    observed: list[bool]
    imputed: int
    cut: bool  # история обрезана после слишком длинной дыры


def _regularize_tail(
    dates: Sequence[date], values: Sequence[float], step_months: int,
    *, fill_gaps: bool = True,
) -> _RegularSeries | None:
    """Непрерывный хвост ряда с заполненными короткими дырами; None — календарь неровный."""
    gaps: list[tuple[int, int]] = []
    for index, (left, right) in enumerate(zip(dates, dates[1:]), start=1):
        delta = _month_index(right) - _month_index(left)
        if delta <= 0 or delta % step_months != 0:
            return None
        if delta > step_months:
            gaps.append((index, delta // step_months - 1))
    allowed = max(2, int(MAX_IMPUTED_SHARE * len(values)))
    limit = MAX_GAP_STEPS.get(step_months, 1) if fill_gaps else 0
    start, imputed = 0, 0
    for index, missing in reversed(gaps):
        if missing > limit or imputed + missing > allowed:
            start = index
            break
        imputed += missing
    out_dates: list[date] = []
    out_values: list[float] = []
    observed: list[bool] = []
    for index in range(start, len(values)):
        if index > start:
            delta = _month_index(dates[index]) - _month_index(dates[index - 1])
            missing = delta // step_months - 1
            previous, current = float(values[index - 1]), float(values[index])
            for k in range(1, missing + 1):
                out_dates.append(dates[index - 1] + relativedelta(months=step_months * k))
                out_values.append(previous + (current - previous) * k / (missing + 1))
                observed.append(False)
        out_dates.append(dates[index])
        out_values.append(float(values[index]))
        observed.append(True)
    return _RegularSeries(out_dates, out_values, observed, imputed, start > 0)


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
    try:
        outputs = strategy(dates, values, ctx)
    except (ValueError, ArithmeticError, LookupError) as exc:
        # Вырожденный ряд (почти константа, лишний регрессор) ронял обучение исключением statsmodels
        # («shapes (1,5) and (4,) not aligned», de-ert_bil_conv_q-avg на стенде 12.10): ряд не записывался,
        # возвращался в очередь и падал каждый день. Теперь это обычный отказ модели с записью причины.
        logger.warning("world forecast: strategy %s failed on a degenerate series: %s", strategy_name, exc)
        return None
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


def _train_primary_gate(
    dates: Sequence[date],
    values: Sequence[float],
    *,
    frequency: str,
    horizon: int,
    season: int,
    strategy: str,
    strict: bool = True,
    fill_gaps: bool = True,
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

    regular = _regularize_tail(dates, values, step_months, fill_gaps=fill_gaps)
    if regular is None:
        return WorldForecastGate(
            "failed", "irregular_calendar", resolved_strategy, None, None, 0, None,
        )
    dates, values, observed = regular.dates, regular.values, regular.observed
    if regular.cut and len(values) < min_history:
        return WorldForecastGate(
            "failed", "recent_history_gap", resolved_strategy, None, None, 0, None,
        )
    details = {"imputed_points": regular.imputed} if regular.imputed else None

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
        target_ok = observed[origin:origin + test_horizon]
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
            predicted - truth
            for predicted, truth, real in zip(candidate, actual, target_ok) if real
        )
        candidate_scaled_errors.extend(
            abs(predicted - truth) / scale
            for predicted, truth, real in zip(candidate, actual, target_ok) if real
        )
        baseline_scaled_errors.extend(
            abs(predicted - truth) / scale
            for predicted, truth, real in zip(baseline, actual, target_ok) if real
        )

    if not candidate_scaled_errors:
        return WorldForecastGate(
            "failed", "not_enough_backtest_origins",
            resolved_strategy, None, None, 0, None,
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
            resolved_strategy, mase, baseline_mase, len(origins), None, details,
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
        resolved_strategy, mase, baseline_mase, len(origins), result, details,
    )


# ---------------------------------------------------------------------------
# Кандидатный путь: дополнительные модели с вложенным выбором
# ---------------------------------------------------------------------------
#
# Главная стратегия (multi-window OLS) остаётся первой и неизменной: всё, что
# она публиковала, публикуется так же. Кандидаты пробуются только когда она не
# прошла по качеству (``mase_not_below_one``, ``not_better_than_seasonal_naive``)
# или не смогла посчитать. Чтобы выбор лучшей из многих моделей не раздувал
# качество, выбор и проверка разведены по времени:
#
#   1. модель выбирается на «окнах выбора» — прошлых точках отсчёта, чьи
#      целевые значения лежат СТРОГО до первого окна гейта; допускаются
#      только модели с MASE < 1 на этих окнах, берётся лучшая по MASE;
#   2. выбранная одна модель сдаёт тот же гейт на окнах гейта (MASE < 1 и
#      ошибка минимум на 2% меньше сезонного наивного, пороги не менялись).
#      Окна гейта выбору недоступны, поэтому результат на них не завышен
#      отбором из многих моделей (проверено на отложенных данных, см. отчёт
#      круга 12: опубликованные так прогнозы лучше наивного в 71% случаев
#      против 57% у главной модели).
#
# Допущения без порога качества: число окон выбора (annual 5, quarterly 6,
# monthly 6; минимум 3/4/4, иначе ряд остаётся с прежним отказом) и окно
# подгонки моделей (см. world_forecast_candidates).

RETRYABLE_QUALITY_REASONS = frozenset({
    "mase_not_below_one",
    "not_better_than_seasonal_naive",
    "candidate_model_failed",
})
_SELECTION_ORIGINS = {"annual": (5, 3), "quarterly": (6, 4), "monthly": (6, 4)}
_MASE_LIMIT = 1.0
_NAIVE_MARGIN = 0.98
# Допуск модели к гейту по результату на окнах выбора: "naive" — MASE < 1 и
# ошибка минимум на 2% меньше наивного (как сам гейт); "mase" — только MASE < 1;
# "none" — берётся минимум MASE без порога. Меняется только в бенчмарках.
SELECTION_RULE = "mase"


def _candidate_forecast(
    name: str, train: Sequence[float], *, season: int, steps: int,
) -> list[float] | None:
    if name == SEASONAL_DRIFT_NAME:
        if len(train) < season * 3:
            return None
        return _seasonal_projection(train, season=season, steps=steps, drift=True)
    return forecast_candidate(name, train, season=season, steps=steps)


def _score_candidates(
    names: Sequence[str],
    values: Sequence[float],
    origins: Sequence[int],
    *,
    season: int,
    test_horizon: int,
    observed: Sequence[bool] | None = None,
) -> tuple[dict[str, tuple[float, list[float]]], float] | None:
    """MASE каждой модели на окнах ``origins`` и MASE сезонного наивного.

    Целевыми значениями считаются только реальные наблюдения (``observed``);
    интерполированные точки в ошибки не входят.
    """
    scaled: dict[str, list[float] | None] = {name: [] for name in names}
    signed: dict[str, list[float]] = {name: [] for name in names}
    baseline_scaled: list[float] = []
    for origin in origins:
        train = values[:origin]
        actual = [float(value) for value in values[origin:origin + test_horizon]]
        real = (
            list(observed[origin:origin + test_horizon])
            if observed is not None else [True] * len(actual)
        )
        scale = _scale(train, season)
        if scale is None:
            return None
        baseline = _seasonal_projection(train, season=season, steps=test_horizon, drift=False)
        baseline_scaled.extend(
            abs(p - a) / scale for p, a, ok in zip(baseline, actual, real) if ok
        )
        for name in names:
            if scaled[name] is None:
                continue
            forecast = _candidate_forecast(name, train, season=season, steps=test_horizon)
            if forecast is None or len(forecast) < test_horizon:
                scaled[name] = None
                continue
            scaled[name].extend(
                abs(p - a) / scale for p, a, ok in zip(forecast, actual, real) if ok
            )
            signed[name].extend(p - a for p, a, ok in zip(forecast, actual, real) if ok)
    if not baseline_scaled:
        return None
    baseline_mase = sum(baseline_scaled) / len(baseline_scaled)
    scores = {
        name: (sum(errors) / len(errors), signed[name])
        for name, errors in scaled.items()
        if errors
    }
    return scores, baseline_mase


def _beats_naive(mase: float, baseline: float) -> bool:
    return (
        math.isfinite(mase) and math.isfinite(baseline)
        and mase < _MASE_LIMIT and mase < baseline * _NAIVE_MARGIN
    )


def _candidate_gate(
    dates: Sequence[date],
    values: Sequence[float],
    *,
    frequency: str,
    horizon: int,
    season: int,
    primary: WorldForecastGate,
    bounds: tuple[float, float] | None,
    fill_gaps: bool = True,
) -> WorldForecastGate:
    """Вложенный выбор дополнительной модели; при отказе возвращает ``primary``."""
    (
        step_months, test_horizon, requested_origins,
        _min_origins, _min_history, origin_floor,
    ) = _backtest_layout(frequency, season, horizon)
    regular = _regularize_tail(dates, values, step_months, fill_gaps=fill_gaps)
    if regular is None:
        return primary
    dates, values, observed = regular.dates, regular.values, regular.observed

    gate_first = max(origin_floor, len(values) - requested_origins - test_horizon + 1)
    gate_origins = list(range(gate_first, len(values) - test_horizon + 1))
    want, need = _SELECTION_ORIGINS[frequency]
    selection_last = gate_first - test_horizon
    selection_floor = max(min_fit_points(season), season * 3)
    selection_first = max(selection_floor, selection_last - want + 1)
    selection_origins = list(range(selection_first, selection_last + 1))
    details = {
        "candidate_set": WORLD_CANDIDATE_SET_VERSION,
        "candidate_selection_origins": len(selection_origins),
    }
    if regular.imputed:
        details["imputed_points"] = regular.imputed
    if len(selection_origins) < need or not gate_origins:
        return WorldForecastGate(
            primary.status, primary.reason, primary.strategy, primary.mase,
            primary.baseline_mase, primary.origins, None, details,
        )

    positive = all(float(value) > 0 for value in values)
    names = [SEASONAL_DRIFT_NAME] + candidate_names(positive=positive)
    selected = _score_candidates(
        names, values, selection_origins,
        season=season, test_horizon=test_horizon, observed=observed,
    )
    rejected = WorldForecastGate(
        primary.status, primary.reason, primary.strategy, primary.mase,
        primary.baseline_mase, primary.origins, None, details,
    )
    if selected is None:
        return rejected
    selection_scores, selection_baseline = selected
    eligible = {
        name: score for name, (score, _errors) in selection_scores.items()
        if math.isfinite(score) and (
            SELECTION_RULE == "none"
            or (SELECTION_RULE == "mase" and score < _MASE_LIMIT)
            or (SELECTION_RULE == "naive" and _beats_naive(score, selection_baseline))
        )
    }
    if not eligible:
        return rejected
    chosen = min(eligible, key=lambda name: (eligible[name], name))

    gated = _score_candidates(
        [chosen], values, gate_origins,
        season=season, test_horizon=test_horizon, observed=observed,
    )
    if gated is None or chosen not in gated[0]:
        return rejected
    gate_scores, gate_baseline = gated
    mase, errors = gate_scores[chosen]
    details.update({
        "candidate_model": chosen,
        "candidate_selection_mase": round(eligible[chosen], 6),
        "candidate_selection_baseline_mase": round(selection_baseline, 6),
    })
    if not _beats_naive(mase, gate_baseline):
        return WorldForecastGate(
            "failed",
            "mase_not_below_one" if mase >= _MASE_LIMIT else "not_better_than_seasonal_naive",
            f"candidate:{chosen}", mase, gate_baseline, len(gate_origins), None, details,
        )

    forecast = _candidate_forecast(chosen, values, season=season, steps=horizon)
    if forecast is None or len(forecast) < horizon:
        return rejected
    max_history = max(abs(float(value)) for value in values) or 1.0
    if any(abs(value) > max_history * 5 for value in forecast):
        return WorldForecastGate(
            "failed", "implausible_extrapolation", f"candidate:{chosen}",
            mase, gate_baseline, len(gate_origins), None, details,
        )
    if bounds is not None and any(not bounds[0] <= value <= bounds[1] for value in forecast):
        return WorldForecastGate(
            "failed", "out_of_range", f"candidate:{chosen}",
            mase, gate_baseline, len(gate_origins), None, details,
        )
    sigma = math.sqrt(sum(error * error for error in errors) / max(1, len(errors)))
    last = dates[-1]
    points = []
    for step, value in enumerate(forecast, start=1):
        uncertainty = 1.96 * sigma * math.sqrt(step)
        points.append(ForecastPoint(
            date=last + relativedelta(months=step_months * step),
            value=float(value),
            lower_bound=float(value - uncertainty),
            upper_bound=float(value + uncertainty),
        ))
    result = ForecastResult(
        model_name=f"World-{chosen}-v1", aic=None, bic=None, points=points,
    )
    return WorldForecastGate(
        "passed", "beats_seasonal_naive", f"candidate:{chosen}",
        mase, gate_baseline, len(gate_origins), result, details,
    )


def train_quality_gated_world_forecast(
    dates: Sequence[date],
    values: Sequence[float],
    *,
    frequency: str,
    horizon: int,
    season: int,
    strategy: str,
    strict: bool = True,
    candidates: bool = True,
    bounds: tuple[float, float] | None = None,
    fill_gaps: bool = True,
) -> WorldForecastGate:
    """Главная модель, затем (если не прошла по качеству) кандидатный путь.

    ``bounds`` — допустимый диапазон значений (для процентов 0..100): прогноз
    вне него не публикуется. Применяется и к главной модели.
    ``fill_gaps=False`` возвращает прежнее поведение: любая дыра режет историю.
    """
    gate = _gate_with_fallbacks(
        dates, values,
        frequency=frequency, horizon=horizon, season=season, strategy=strategy,
        strict=strict, candidates=candidates, bounds=bounds, fill_gaps=fill_gaps,
    )
    if (
        fill_gaps
        and gate.result is None
        and (gate.details or {}).get("imputed_points")
    ):
        # Интерполяция удлинила историю, но ряд не прошёл: даём шанс прежнему
        # пути (история после последней дыры), чтобы заполнение дыр никогда не
        # отнимало прогноз, который раньше публиковался.
        legacy = _gate_with_fallbacks(
            dates, values,
            frequency=frequency, horizon=horizon, season=season, strategy=strategy,
            strict=strict, candidates=candidates, bounds=bounds, fill_gaps=False,
        )
        if legacy.result is not None:
            return legacy
    return gate


def _gate_with_fallbacks(
    dates: Sequence[date],
    values: Sequence[float],
    *,
    frequency: str,
    horizon: int,
    season: int,
    strategy: str,
    strict: bool,
    candidates: bool,
    bounds: tuple[float, float] | None,
    fill_gaps: bool,
) -> WorldForecastGate:
    gate = _train_primary_gate(
        dates, values,
        frequency=frequency, horizon=horizon, season=season,
        strategy=strategy, strict=strict, fill_gaps=fill_gaps,
    )
    if (
        gate.result is not None
        and bounds is not None
        and any(not bounds[0] <= point.value <= bounds[1] for point in gate.result.points)
    ):
        gate = WorldForecastGate(
            "failed", "out_of_range", gate.strategy, gate.mase,
            gate.baseline_mase, gate.origins, None, gate.details,
        )
    if (
        not candidates
        or gate.result is not None
        or gate.reason not in RETRYABLE_QUALITY_REASONS
    ):
        return gate
    return _candidate_gate(
        dates, values,
        frequency=frequency, horizon=horizon, season=season,
        primary=gate, bounds=bounds, fill_gaps=fill_gaps,
    )
