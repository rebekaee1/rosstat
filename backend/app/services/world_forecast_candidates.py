"""Дополнительные кандидаты статистического прогноза для world-рядов.

Главная модель (multi-window OLS из ``forecast_strategies``) на многих рядах не
проходит проверку: короткие тренды, медленно растущие показатели, ряды с
пропусками. Здесь лежат дешёвые замкнутые модели, которые дополняют её, а не
заменяют: сезонный наивный с дрейфом, дрейф, Theta, затухающий тренд Холта,
простое экспоненциальное сглаживание, AR(1) на разностях. Каждая считается и
на уровне, и на логарифме (если ряд строго положителен), при сезонности
сначала убираются сезонные индексы.

Модели чистые (numpy, без statsmodels): одна подгонка занимает доли
миллисекунды, поэтому полный перебор на окнах проверки укладывается в бюджет
плановой задачи. Выбор и проверка качества живут в ``world_forecaster``:
здесь только прогнозы.

Версия набора ``WORLD_CANDIDATE_SET_VERSION`` записывается в параметры
прогноза: смена набора возвращает в очередь ряды, у которых прошлая проверка
не удалась (уже опубликованные не трогаются).
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np
from scipy.signal import lfilter

WORLD_CANDIDATE_SET_VERSION = 1

# Окно подгонки (последние наблюдения): дальняя история с другим режимом
# только портит оценку тренда. Допущение этого модуля, не порог качества.
_FIT_WINDOW = {1: 40, 4: 60, 12: 96}
_DRIFT_WINDOW = {1: 5, 4: 8, 12: 24}
_MIN_FIT = {1: 8, 4: 16, 12: 36}

_SES_ALPHAS = (0.1, 0.2, 0.3, 0.5, 0.7, 0.9)
_HOLT_ALPHAS = (0.2, 0.5, 0.8)
_HOLT_BETAS = (0.05, 0.2)
_HOLT_PHIS = (0.8, 0.95)


def _fit_window(season: int) -> int:
    return _FIT_WINDOW.get(season, max(40, season * 8))


def min_fit_points(season: int) -> int:
    return _MIN_FIT.get(season, max(8, season * 3))


def _seasonal_indices(y: np.ndarray, season: int) -> np.ndarray:
    """Классическая декомпозиция: индексы по фазам (сумма нулевая)."""
    if season <= 1 or len(y) < 3 * season:
        return np.zeros(max(season, 1))
    if season % 2 == 0:
        kernel = np.r_[0.5, np.ones(season - 1), 0.5] / season
    else:
        kernel = np.ones(season) / season
    trend = np.convolve(y, kernel, mode="valid")
    offset = (len(y) - len(trend)) // 2
    resid = y[offset:offset + len(trend)] - trend
    phases = (np.arange(len(trend)) + offset) % season
    idx = np.zeros(season)
    for phase in range(season):
        part = resid[phases == phase]
        idx[phase] = float(np.mean(part)) if len(part) else 0.0
    return idx - float(np.mean(idx))


def _ses_level(y: np.ndarray, alpha: float) -> tuple[float, float]:
    """Уровень SES после последнего наблюдения и SSE одношаговых ошибок."""
    zi = np.array([(1.0 - alpha) * y[0]])
    levels, _ = lfilter([alpha], [1.0, -(1.0 - alpha)], y[1:], zi=zi)
    prev = np.r_[y[0], levels[:-1]]
    sse = float(np.sum((y[1:] - prev) ** 2))
    return float(levels[-1]) if len(levels) else float(y[0]), sse


def _best_ses(y: np.ndarray) -> tuple[float, float]:
    best = min(((_ses_level(y, a), a) for a in _SES_ALPHAS), key=lambda item: item[0][1])
    return best[0][0], best[1]


def _drift(y: np.ndarray, steps: int, season: int) -> list[float]:
    window = min(len(y) - 1, _DRIFT_WINDOW.get(season, max(5, season * 2)))
    slope = (y[-1] - y[-1 - window]) / window
    return [float(y[-1] + slope * k) for k in range(1, steps + 1)]


def _ses(y: np.ndarray, steps: int, season: int) -> list[float]:
    level, _ = _best_ses(y)
    return [float(level)] * steps


def _theta(y: np.ndarray, steps: int, season: int) -> list[float]:
    """Theta (Assimakopoulos-Nikolopoulos): SES + половина наклона тренда."""
    n = len(y)
    t = np.arange(n, dtype=float)
    slope = float(np.polyfit(t, y, 1)[0])
    level, alpha = _best_ses(y)
    return [
        float(level + 0.5 * slope * (k - 1 + 1.0 / alpha - ((1.0 - alpha) ** n) / alpha))
        for k in range(1, steps + 1)
    ]


def _holt_damped(y: np.ndarray, steps: int, season: int) -> list[float]:
    best_sse = math.inf
    best_state: tuple[float, float, float] | None = None
    values = [float(v) for v in y]
    for alpha in _HOLT_ALPHAS:
        for beta in _HOLT_BETAS:
            for phi in _HOLT_PHIS:
                level, trend = values[0], values[1] - values[0]
                sse = 0.0
                for observed in values[1:]:
                    fitted = level + phi * trend
                    err = observed - fitted
                    sse += err * err
                    new_level = fitted + alpha * err
                    trend = phi * trend + alpha * beta * err
                    level = new_level
                if sse < best_sse:
                    best_sse, best_state = sse, (level, trend, phi)
    if best_state is None:
        return [float(y[-1])] * steps
    level, trend, phi = best_state
    out: list[float] = []
    damp = 0.0
    for k in range(1, steps + 1):
        damp += phi ** k
        out.append(float(level + damp * trend))
    return out


def _ar1_diff(y: np.ndarray, steps: int, season: int) -> list[float]:
    d = np.diff(y)
    if len(d) < 6:
        return [float(y[-1])] * steps
    x, target = d[:-1], d[1:]
    var = float(np.var(x))
    phi = float(np.cov(x, target, bias=True)[0, 1] / var) if var > 1e-18 else 0.0
    phi = min(0.95, max(-0.5, phi))
    c = float(np.mean(target) - phi * np.mean(x))
    diff = float(d[-1])
    level = float(y[-1])
    out: list[float] = []
    for _ in range(steps):
        diff = c + phi * diff
        level += diff
        out.append(level)
    return out


_MODELS: dict[str, Callable[[np.ndarray, int, int], list[float]]] = {
    "drift": _drift,
    "ses": _ses,
    "theta": _theta,
    "holt-damped": _holt_damped,
    "ar1-diff": _ar1_diff,
}

# Устойчивый сезонный наивный с дрейфом живёт в world_forecaster
# (``_seasonal_projection``) и подключается там же под именем ниже.
SEASONAL_DRIFT_NAME = "seasonal-drift"


def candidate_names(*, positive: bool) -> list[str]:
    names = list(_MODELS)
    if positive:
        names += [f"{name}-log" for name in _MODELS]
    return names


def forecast_candidate(
    name: str,
    values: Sequence[float],
    *,
    season: int,
    steps: int,
) -> list[float] | None:
    """Прогноз одной модели на ``steps`` шагов или None, если не получилось."""
    log = name.endswith("-log")
    base = name[:-4] if log else name
    model = _MODELS.get(base)
    if model is None:
        return None
    window = _fit_window(season)
    y = np.asarray(values[-window:], dtype=float)
    if len(y) < min_fit_points(season):
        return None
    if log:
        if np.any(y <= 0):
            return None
        y = np.log(y)
    idx = _seasonal_indices(y, season)
    phase = np.arange(len(y)) % max(season, 1)
    adjusted = y - idx[phase] if season > 1 else y
    try:
        raw = model(adjusted, steps, season)
    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
        return None
    future_phase = (len(y) + np.arange(steps)) % max(season, 1)
    out: list[float] = []
    for k, value in enumerate(raw):
        value = float(value) + (float(idx[future_phase[k]]) if season > 1 else 0.0)
        if log:
            if value > 50:  # exp переполнит: модель ушла в абсурд
                return None
            value = math.exp(value)
        if not math.isfinite(value):
            return None
        out.append(value)
    return out
