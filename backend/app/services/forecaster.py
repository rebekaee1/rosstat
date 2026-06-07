"""
Forecasting service.
- Original OLS multi-window model for non-CPI indicators.
- НА's Model 2: Monthly CPI forecast (multi-window OLS, df-100 transform).
- НА's Model 1: 12-month rolling inflation forecast (log-cumprod-diff transform + blend).
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import List

import numpy as np
import pandas as pd
import statsmodels.api as sm
from dateutil.relativedelta import relativedelta
from statsmodels.tsa.stattools import adfuller

logger = logging.getLogger(__name__)

CPI_INDICATOR_CODES = {'cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services'}


@dataclass
class ForecastPoint:
    date: date
    value: float
    lower_bound: float | None
    upper_bound: float | None


@dataclass
class ForecastResult:
    model_name: str
    aic: float | None
    bic: float | None
    points: List[ForecastPoint]
    cumulative_12m: float | None = None
    monthly_predictions: List[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
#  Shared helpers
# ---------------------------------------------------------------------------

def _remove_outliers(series: pd.Series, sigma: float = 3.0) -> pd.Series:
    """Outlier-clip identical to Никита's notebook (np.mean / np.std, ddof=0)."""
    s = series.copy()
    for _ in range(50):
        mean = float(np.mean(s))
        std = float(np.std(s))  # ddof=0 to match notebook (np.std default)
        if std == 0 or not np.isfinite(std):
            break
        mask_hi = (s - mean) / std > sigma
        mask_lo = (s - mean) / std < -sigma
        if not (mask_hi.any() or mask_lo.any()):
            break
        s[mask_hi] = mean + 1.9 * std
        s[mask_lo] = mean - 1.9 * std
    return s


def _get_horizon_lags(m: int) -> list[int]:
    if m <= 9:
        return [m, m + 1, m + 2, 12]
    elif m == 10:
        return [m, m + 1, 12]
    elif m == 11:
        return [m, 12]
    return [12]


def _ols_step(df_aux: pd.Series, lags: list[int], horizon_m: int,
              p_max: float = 0.01, cor_max: float = 0.7):
    """Single OLS model fit and predict for one window segment.

    Returns (prediction, mse_resid) or (None, None) on failure.
    """
    try:
        train = pd.DataFrame(df_aux)

        aux_list = list(df_aux)
        X_p = [1]
        for j in lags:
            train[f'y_lag{j}'] = df_aux.shift(j)
            idx = -j + horizon_m - 1
            if abs(idx) > len(aux_list) or (idx < 0 and abs(idx) > len(aux_list)):
                return None, None
            X_p.append(float(aux_list[idx]))

        X_p_df = pd.DataFrame(np.array(X_p).reshape(1, -1), columns=train.columns)

        drop_cols = set()
        corr = train.corr()
        target = 'value'
        for a in corr.columns:
            for b in corr.index:
                if a != b and a != target and b != target:
                    if abs(corr[a][b]) > cor_max:
                        if abs(corr[target][b]) > abs(corr[target][a]):
                            drop_cols.add(a)
                        else:
                            drop_cols.add(b)

        train = train.drop(columns=drop_cols, errors='ignore')
        X_p_df = X_p_df.drop(columns=drop_cols, errors='ignore')
        X_p_list = list(X_p_df.iloc[0])

        train = train.dropna()
        if len(train) < 10:
            return None, None

        y = train['value']
        X = sm.add_constant(train.drop('value', axis=1))
        model = sm.OLS(y, X).fit()

        X_feat = train.drop('value', axis=1)
        while True:
            pvalues_after_const = model.pvalues[1:]
            if len(pvalues_after_const) == 0:
                break
            max_p = np.max(pvalues_after_const)
            if not np.isfinite(max_p) or max_p <= p_max:
                break
            worst = int(np.argmax(pvalues_after_const))
            X_feat = X_feat.drop(X_feat.columns[worst], axis=1)
            X_p_list.pop(worst + 1)
            model = sm.OLS(y, sm.add_constant(X_feat, has_constant='add')).fit()

        pred = model.predict(X_p_list)[0]
        mse = model.mse_resid
        if mse <= 0 or not np.isfinite(pred):
            return None, None
        return float(pred), float(mse)
    except Exception:
        logger.debug("_ols_step failed for horizon=%d", horizon_m, exc_info=True)
        return None, None


def _multi_window_predict(data_col: pd.Series, window_size: int,
                          horizon_m: int, lags: list[int],
                          apply_rolling: bool = False,
                          k_range: range = range(1, 5),
                          min_window: int = 24,
                          remove_outliers_after_rolling: bool = True):
    """Run OLS across multiple window sizes, return inverse-variance weighted prediction.

    Parameters mirror Никита's notebook variants:
    - k_range: window divisors loop. Monthly CPI / inflation-12m use k∈[1..4],
      quarterly housing uses k∈[1..3].
    - min_window: minimum segment length safeguard. The notebook does not enforce
      a minimum; we keep one to avoid degenerate OLS but it should be small enough
      to never bind for typical series lengths.
    - remove_outliers_after_rolling: if False, replicate notebook semantics for the
      12-month inflation model — outliers are not stripped on the rolling-mean
      transformed series (the notebook's while-loop becomes a no-op as soon as
      rolling introduces NaNs that break np.std/np.mean).
    """
    i = len(data_col)
    preds, varis = [], []

    for k in k_range:
        seg_size = max(min_window, window_size // k)
        start = max(0, i - seg_size)
        df_aux = data_col.iloc[start:i].copy()

        if apply_rolling and horizon_m > 1:
            df_aux = df_aux.rolling(horizon_m).mean()
            if remove_outliers_after_rolling:
                df_aux = _remove_outliers(df_aux.dropna())
            else:
                df_aux = df_aux.dropna()
        else:
            df_aux = _remove_outliers(df_aux.dropna())

        if len(df_aux) < 20:
            continue

        pred, mse = _ols_step(df_aux, lags, horizon_m)
        if pred is not None:
            preds.append(pred)
            varis.append(mse)

    if not preds:
        return None

    preds_a = np.array(preds)
    varis_a = np.array(varis)
    inv_var = 1.0 / varis_a
    return float(np.sum(preds_a * inv_var) / np.sum(inv_var))


# ---------------------------------------------------------------------------
#  НА Model 2: Monthly CPI forecast
# ---------------------------------------------------------------------------

def _monthly_blend_weights(m: int) -> tuple[float, float, float]:
    """НА's Model 2 (April 2026): weights for OLS-prediction blend with median and prior."""
    if m <= 4:
        return (1.0, 0.0, 0.0)
    if m <= 9:
        return (0.8, 0.0, 0.2)
    return (0.7, 0.0, 0.3)


_MONTHLY_PRIOR = 4.0 / 1200.0  # matches Никита's May 2026 notebook (`4 / 1200`)


def train_monthly_cpi(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 12,
) -> ForecastResult:
    """Multi-window OLS for monthly CPI. Transform: df - 100.

    Blend (per Никита's May 2026 notebook `Прогноз_ИПЦ_помесячно (2)`):
        m∈[1..4]   → 1.0 * OLS
        m∈[5..9]   → 0.8 * OLS + 0.2 * prior
        m∈[10..12] → 0.7 * OLS + 0.3 * prior
        prior      = 4 / 1200 (≈0.00333 pp/month)
    Trivial-median weight is kept zero (computed for reference only).
    """
    series = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name='value')
    data = pd.DataFrame(series - 100, columns=['value'])
    window_size = len(data)
    monthly_dates = [data.index[-1] + relativedelta(months=j + 1) for j in range(forecast_steps)]

    residual_std = float(data['value'].iloc[-24:].std()) if len(data) > 1 else 0.0
    trivial = float(np.median(data['value'].iloc[-12:]))
    z = 1.96

    points: list[ForecastPoint] = []
    monthly_preds: list[float] = []
    for m in range(1, forecast_steps + 1):
        lags = _get_horizon_lags(m)
        pred_ols = _multi_window_predict(data['value'], window_size, m, lags, apply_rolling=False)

        if pred_ols is None:
            pred_ols = trivial

        w = _monthly_blend_weights(m)
        pred = pred_ols * w[0] + trivial * w[1] + _MONTHLY_PRIOR * w[2]

        cpi_value = round(pred + 100, 4)
        monthly_preds.append(cpi_value)
        ci_width = z * residual_std * np.sqrt(m)
        points.append(ForecastPoint(
            date=monthly_dates[m - 1].date(),
            value=cpi_value,
            lower_bound=round(pred - ci_width + 100, 4),
            upper_bound=round(pred + ci_width + 100, 4),
        ))

    logger.info("CPI-Monthly-MW forecast: %d points, last=%.4f", len(points),
                points[-1].value if points else 0)
    return ForecastResult(
        model_name="CPI-Monthly-MW",
        aic=None,
        bic=None,
        points=points,
        monthly_predictions=monthly_preds,
    )


# ---------------------------------------------------------------------------
#  Quarterly inflation forecast — aggregation from monthly CPI forecast
# ---------------------------------------------------------------------------

def aggregate_quarterly_from_monthly(
    monthly_actual_dates: List[date],
    monthly_actual_values: List[float],
    monthly_forecast_points: List[ForecastPoint],
) -> ForecastResult:
    """Build quarterly inflation forecast as aggregation of monthly CPI forecast.

    For each upcoming calendar quarter, multiply 3 monthly CPI values
    (factual where available + forecast otherwise) and convert to %.

    Pure forecast quarters (all 3 months forecasted) are returned;
    a partial quarter (mix of actual + forecast) is also returned and
    will be re-computed on every monthly release.
    """
    if not monthly_forecast_points or not monthly_actual_dates:
        return ForecastResult(
            model_name="CPI-Quarterly-Agg", aic=None, bic=None, points=[],
        )

    actual_factors = {
        d.replace(day=1): v / 100.0
        for d, v in zip(monthly_actual_dates, monthly_actual_values)
    }
    forecast_factors = {
        p.date.replace(day=1): p.value / 100.0
        for p in monthly_forecast_points
    }

    all_dates = sorted(set(actual_factors) | set(forecast_factors))
    if not all_dates:
        return ForecastResult(
            model_name="CPI-Quarterly-Agg", aic=None, bic=None, points=[],
        )

    last_actual_month = max(actual_factors)
    quarters: dict[date, list[date]] = {}
    for d in all_dates:
        q_idx = (d.month - 1) // 3
        q_start = date(d.year, q_idx * 3 + 1, 1)
        quarters.setdefault(q_start, []).append(d)

    points: list[ForecastPoint] = []
    for q_start, months in sorted(quarters.items()):
        if len(months) != 3:
            continue
        if all(m <= last_actual_month for m in months):
            continue

        factors = [
            actual_factors.get(m, forecast_factors.get(m))
            for m in months
        ]
        if any(f is None for f in factors):
            continue
        product = 1.0
        for f in factors:
            product *= f
        value = round(product * 100, 4)
        points.append(ForecastPoint(
            date=q_start,
            value=value,
            lower_bound=None,
            upper_bound=None,
        ))

    logger.info("CPI-Quarterly-Agg: %d quarters", len(points))
    return ForecastResult(
        model_name="CPI-Quarterly-Agg", aic=None, bic=None, points=points,
    )


# ---------------------------------------------------------------------------
#  НА Model 1: 12-month rolling inflation forecast
# ---------------------------------------------------------------------------

_INFLATION_BLEND_WEIGHTS = {
    1: [1, 0, 0],
    2: [0.7, 0.2, 0.1],
    3: [0.5, 0.2, 0.3],
    4: [0.4, 0.3, 0.3],
}
_DEFAULT_BLEND = [0.4, 0.4, 0.2]
_BLEND_M12 = [0.3, 0.5, 0.2]
ANNUAL_PRIOR = 4 / 1200  # ~4% annual inflation prior in log space


def train_inflation_12m(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 12,
) -> ForecastResult:
    """Multi-window OLS for 12-month rolling inflation.

    Direct port of Никита's `Прогноз_инфляции_12_мес (1).ipynb` (May 2026).
    Transform: np.log((df / 100).cumprod()).diff(1)
    Output: cumulative 12-month inflation % for each horizon.

    The notebook's outlier-removal `while`-loop is a no-op once
    `df_aux.rolling(m).mean()` introduces NaNs (NaN breaks np.std/mean,
    the condition `np.sum(... > 3) > 0` evaluates to False and the loop
    exits). We replicate that by skipping outlier removal entirely on the
    transformed series — preserves notebook fidelity.
    """
    series = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name='value')
    log_cum = np.log((series / 100).cumprod())
    data = log_cum.diff(1)  # keep leading NaN to match notebook segment sizing (`window_size // k`).
    window_size = len(data)

    monthly_dates = [data.index[-1] + relativedelta(months=j + 1) for j in range(forecast_steps)]
    i = len(data)

    median_val = float(np.median(data.iloc[-12:]))
    residual_std = float(data.iloc[-24:].std()) if len(data) > 1 else 0.0
    z = 1.96

    points: list[ForecastPoint] = []

    for m in range(1, forecast_steps + 1):
        lags = _get_horizon_lags(m)

        forc: list[float] = []
        var: list[float] = []
        for k in range(1, 5):
            seg_size = window_size // k
            if seg_size < 24:
                continue
            df_aux = data.iloc[i - seg_size:i].copy()
            df_aux = df_aux.rolling(m).mean()
            # Outlier-removal on rolling-transformed series — pandas mean/std
            # skip NaN, so the loop is meaningful (matches notebook semantics).
            df_aux = _remove_outliers(df_aux)
            # IMPORTANT: do NOT dropna here — the notebook keeps NaN-prefix
            # so that shift(j) inside _ols_step yields the same lag indices
            # as `for j in lags: train['y_lag'+j] = df_aux.shift(j)`.
            pred_k, mse_k = _ols_step(df_aux, lags, m)
            if pred_k is not None:
                forc.append(pred_k)
                var.append(mse_k)

        if forc:
            forc_arr = np.array(forc)
            var_arr = np.array(var)
            pred = float(np.sum(forc_arr / var_arr) / np.sum(1.0 / var_arr))
        else:
            pred = median_val

        w = _INFLATION_BLEND_WEIGHTS.get(m, _BLEND_M12 if m == 12 else _DEFAULT_BLEND)
        blend = pred * w[0] + median_val * w[1] + ANNUAL_PRIOR * w[2]

        actual_sum = float(np.sum(data.iloc[i - (12 - m):i])) if m < 12 else 0.0
        inflation_pct = float(np.exp(actual_sum + m * blend) * 100 - 100)

        ci_margin = z * residual_std * np.sqrt(m)
        lo_pct = float(np.exp(actual_sum + m * (blend - ci_margin)) * 100 - 100)
        hi_pct = float(np.exp(actual_sum + m * (blend + ci_margin)) * 100 - 100)

        points.append(ForecastPoint(
            date=monthly_dates[m - 1].date(),
            value=round(inflation_pct, 4),
            lower_bound=round(lo_pct, 4),
            upper_bound=round(hi_pct, 4),
        ))

    logger.info("Inflation-12M-MW forecast: %d points, last=%.2f%%", len(points),
                points[-1].value if points else 0)
    return ForecastResult(model_name="Inflation-12M-MW", aic=None, bic=None, points=points)


# ---------------------------------------------------------------------------
#  НА Model 3: Quarterly housing-price index forecast (May 2026 notebook)
# ---------------------------------------------------------------------------

def _housing_horizon_lags(m: int) -> list[int]:
    """Lag set used by `Прогнозы_цены_на_жилье (1)` for quarterly horizons."""
    if m < 2:
        return [m, m + 1, m + 2, 4]
    if m == 2:
        return [m, m + 1, 4]
    if m == 3:
        return [m, 4]
    return [4]


def _housing_blend_weights(m: int) -> list[float]:
    return {
        1: [0.8, 0.2],
        2: [0.7, 0.3],
        3: [0.5, 0.5],
        4: [0.3, 0.7],
    }.get(m, [0.5, 0.5])


def train_quarterly_housing(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 4,
) -> ForecastResult:
    """Quarterly housing-price index forecast — 1:1 port of Никита's notebook.

    Source: `Прогнозы_цены_на_жилье (1).ipynb` (May 2026).

    Алгоритм воспроизводится строкой-в-строку (без `_multi_window_predict` /
    `_ols_step` обобщений), чтобы numerics совпадали byte-exact. Шаги:

    1. Transform: `data = np.log(series).diff(1).dropna()`.
    2. Для каждого горизонта `m ∈ [1..forecast_steps]`:
       a. По окнам `k ∈ [1..3]` (segment = `window_size // k`):
          - outlier-clip (mean ± 3σ → mean ± 1.9σ) до сходимости,
          - построить lag-features (`y_lag{j}` для `j ∈ lags(m)`),
          - удалить мультиколлинеарные фичи (|corr| > 0.7), выбирая ту,
            что слабее связана с таргетом,
          - OLS с константой → дроп фич с p > 0.01 (одна за раз).
          - сохранить `model.predict(X_p)` и `model.mse_resid`.
       b. `forecasts_aux[m] = Σ(forc/var) / Σ(1/var)` (inverse-variance mean).
       c. `trivial_aux[m] = median(data[-12:])`.
       d. blend per step:
          m=1: [0.8, 0.2]  m=2: [0.7, 0.3]  m=3: [0.5, 0.5]  m=4: [0.3, 0.7].
       e. `forecast[m] = first_index · exp( Σ all_log_diffs
                                          + Σ_{j≤m} forecasts_aux · w[0]
                                          + Σ_{j≤m} trivial_aux  · w[1] )`.

    Lag set (notebook): m=1 → [1,2,3,4], m=2 → [2,3,4], m=3 → [3,4], m=4 → [4].

    Точно воспроизводит блокнот: тесты `tests/forecast_strategies/test_housing_quarterly.py`
    проверяют byte-exact совпадение по фиксированному snapshot.
    """
    target = 'value'
    series = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name=target)
    if len(series) < 8:
        return ForecastResult(
            model_name="Quarterly-Housing-MW", aic=None, bic=None, points=[],
        )

    first_index = float(series.iloc[0])
    data = np.log(series).diff(1).dropna()
    window_size = len(data)

    quarterly_dates = [
        series.index[-1] + relativedelta(months=j * 3)
        for j in range(1, forecast_steps + 1)
    ]

    forecasts_aux: list[float] = []
    trivial_aux: list[float] = []
    points: list[ForecastPoint] = []

    i = len(data)
    for m in range(1, forecast_steps + 1):
        forc: list[float] = []
        var: list[float] = []
        for k in range(1, 4):
            p_max = 0.01
            df_aux = data.iloc[i - window_size // k:i].copy()
            while np.sum(np.abs(df_aux - np.mean(df_aux)) / np.std(df_aux) > 3) > 0:
                m_, s_ = float(np.mean(df_aux)), float(np.std(df_aux))
                df_aux[(df_aux - m_) / s_ > 3] = m_ + 1.9 * s_
                df_aux[(df_aux - m_) / s_ < -3] = m_ - 1.9 * s_
            train = pd.DataFrame(df_aux)
            if m < 2:
                lags = [m, m + 1, m + 2, 4]
            elif m == 2:
                lags = [m, m + 1, 4]
            elif m == 3:
                lags = [m, 4]
            else:
                lags = [4]
            X_p = [1]
            for j in lags:
                train[f'y_lag{j}'] = df_aux.shift(j)
                X_p.append(float(list(df_aux)[-j + m - 1]))
            X_p = pd.DataFrame(np.array(X_p).reshape(1, -1), columns=train.columns)

            drop_cols: set[str] = set()
            corr = train.corr()
            cor_max = 0.7
            for a in corr.columns:
                for b in corr.index:
                    if a != b and a != target and b != target:
                        if abs(corr[a][b]) > cor_max:
                            if abs(corr[target][b]) > abs(corr[target][a]):
                                drop_cols.add(a)
                            else:
                                drop_cols.add(b)
            train = train.drop(columns=drop_cols)
            X_p = X_p.drop(columns=drop_cols)
            X_p_list = list(X_p.iloc[0])
            train = train.dropna()
            model = sm.OLS(
                train[target], sm.add_constant(train.drop(target, axis=1)),
            ).fit()
            X = train.drop(target, axis=1)
            while len(model.pvalues) > 1 and np.max(model.pvalues[1:]) > p_max:
                drop_idx = int(np.argmax(model.pvalues[1:]))
                X = X.drop(X.columns[drop_idx], axis=1)
                X_p_list.pop(drop_idx + 1)
                model = sm.OLS(train[target], sm.add_constant(X)).fit()
            forc.append(float(model.predict(X_p_list)[0]))
            var.append(float(model.mse_resid))

        forc_a = np.array(forc)
        var_a = np.array(var)
        forecasts_aux.append(float(np.sum(forc_a / var_a) / np.sum(1.0 / var_a)))
        trivial_aux.append(float(np.median(data.iloc[i - 12:i])))

        w = _housing_blend_weights(m)
        accumulated = (
            float(np.sum(data.iloc[:i]))
            + float(np.sum(forecasts_aux)) * w[0]
            + float(np.sum(trivial_aux)) * w[1]
        )
        value = first_index * float(np.exp(accumulated))
        points.append(ForecastPoint(
            date=quarterly_dates[m - 1].date(),
            value=round(value, 4),
            lower_bound=None,
            upper_bound=None,
        ))

    logger.info("Quarterly-Housing-MW forecast: %d points, last=%.2f",
                len(points), points[-1].value if points else 0)
    return ForecastResult(
        model_name="Quarterly-Housing-MW", aic=None, bic=None, points=points,
    )


# ---------------------------------------------------------------------------
#  НА Models 4 & 5: log-difference multi-window without blend
#  (PPI, nominal GDP — Никита's notebooks `Прогноз_ИЦП` / `Прогноз_номинальный_ВВП`)
# ---------------------------------------------------------------------------

def _log_diff_no_blend_forecast(
    dates: List[date],
    values: List[float],
    forecast_steps: int,
    lags_fn,
    k_range: range,
    step_freq: str,  # "monthly" or "quarterly"
    model_name: str,
) -> ForecastResult:
    """Multi-window OLS on log-difference, NO blend with median or prior.

    Replicates the structure of `train_sarima_model` from Никита's
    `Прогноз_ИЦП.ipynb` and `Прогноз_номинальный_ВВП.ipynb`:

        forecast[m] = first_value · exp( Σ all_log_diffs + Σ_{j≤m} forecasts_aux[j] )

    The two notebooks differ only in `forecast_steps`, lag sets, k range,
    and date stepping; the rest is identical. We share the implementation
    and parametrise these axes.
    """
    series = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name='value')
    if len(series) < 24:
        return ForecastResult(model_name=model_name, aic=None, bic=None, points=[])

    first_value = float(series.iloc[0])
    log_diff = np.log(series).diff(1).dropna()
    window_size = len(log_diff)
    sum_all_log_diffs = float(np.sum(log_diff))

    if step_freq == "quarterly":
        future_dates = [
            series.index[-1] + relativedelta(months=j * 3)
            for j in range(1, forecast_steps + 1)
        ]
    else:
        future_dates = [
            series.index[-1] + relativedelta(months=j)
            for j in range(1, forecast_steps + 1)
        ]

    forecasts_aux: list[float] = []
    points: list[ForecastPoint] = []

    for m in range(1, forecast_steps + 1):
        lags = lags_fn(m)
        pred = _multi_window_predict(
            log_diff, window_size, m, lags,
            apply_rolling=False,
            k_range=k_range,
            min_window=12,
        )
        if pred is None:
            pred = float(np.median(log_diff.iloc[-12:]))
        forecasts_aux.append(pred)

        accumulated = sum_all_log_diffs + sum(forecasts_aux)
        value = first_value * float(np.exp(accumulated))
        points.append(ForecastPoint(
            date=future_dates[m - 1].date(),
            value=round(value, 4),
            lower_bound=None,
            upper_bound=None,
        ))

    logger.info("%s forecast: %d points, last=%.2f",
                model_name, len(points), points[-1].value if points else 0)
    return ForecastResult(model_name=model_name, aic=None, bic=None, points=points)


def _ppi_lags(m: int) -> list[int]:
    if m <= 9:
        return [m, m + 1, m + 2, 12]
    if m == 10:
        return [m, m + 1, 12]
    if m == 11:
        return [m, 12]
    return [12]


def _gdp_quarterly_lags(m: int) -> list[int]:
    if m < 2:
        return [m, m + 1, m + 2, 4]
    if m == 2:
        return [m, m + 1, 4]
    if m == 3:
        return [m, 4]
    return [4]


def train_ppi_monthly(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 12,
) -> ForecastResult:
    """Port of Никита's `Прогноз_ИЦП.ipynb` (April 2026).

    PPI index, monthly. Multi-window OLS on log-diff, k∈[1..4],
    monthly lag set, no blend.
    """
    return _log_diff_no_blend_forecast(
        dates, values, forecast_steps,
        lags_fn=_ppi_lags,
        k_range=range(1, 5),
        step_freq="monthly",
        model_name="PPI-Monthly-MW",
    )


def _train_gdp_quarterly_port(
    dates: List[date],
    values: List[float],
    forecast_steps: int,
    model_name: str,
) -> ForecastResult:
    """1:1 port of Никита's `train_sarima_model` (`Прогноз_номинальный_ВВП.ipynb`).

    Никита запускает один и тот же ноутбук на номинальном и на реальном
    ВВП — `train_sarima_model(data, forecast_steps=4)`. Чтобы наши прогнозы
    совпадали с блокнотом byte-exact, мы вызываем эту функцию из обеих
    стратегий, передавая `model_name` для маркировки. Алгоритм идентичен
    `train_quarterly_housing`, но БЕЗ блендинга с медианой:

        forecast[m] = first_value · exp( Σ all_log_diffs + Σ_{j≤m} forecasts_aux )
    """
    target = 'value'
    series = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name=target)
    if len(series) < 24:
        return ForecastResult(model_name=model_name, aic=None, bic=None, points=[])

    first_value = float(series.iloc[0])
    data = np.log(series).diff(1).dropna()
    window_size = len(data)

    future_dates = [
        series.index[-1] + relativedelta(months=j * 3)
        for j in range(1, forecast_steps + 1)
    ]

    forecasts_aux: list[float] = []
    points: list[ForecastPoint] = []

    i = len(data)
    for m in range(1, forecast_steps + 1):
        forc: list[float] = []
        var: list[float] = []
        for k in range(1, 4):
            p_max = 0.01
            df_aux = data.iloc[i - window_size // k:i].copy()
            while np.sum(np.abs(df_aux - np.mean(df_aux)) / np.std(df_aux) > 3) > 0:
                m_, s_ = float(np.mean(df_aux)), float(np.std(df_aux))
                df_aux[(df_aux - m_) / s_ > 3] = m_ + 1.9 * s_
                df_aux[(df_aux - m_) / s_ < -3] = m_ - 1.9 * s_
            train = pd.DataFrame(df_aux)
            if m < 2:
                lags = [m, m + 1, m + 2, 4]
            elif m == 2:
                lags = [m, m + 1, 4]
            elif m == 3:
                lags = [m, 4]
            else:
                lags = [4]
            X_p = [1]
            for j in lags:
                train[f'y_lag{j}'] = df_aux.shift(j)
                X_p.append(float(list(df_aux)[-j + m - 1]))
            X_p = pd.DataFrame(np.array(X_p).reshape(1, -1), columns=train.columns)

            drop_cols: set[str] = set()
            corr = train.corr()
            cor_max = 0.7
            for a in corr.columns:
                for b in corr.index:
                    if a != b and a != target and b != target:
                        if abs(corr[a][b]) > cor_max:
                            if abs(corr[target][b]) > abs(corr[target][a]):
                                drop_cols.add(a)
                            else:
                                drop_cols.add(b)
            train = train.drop(columns=drop_cols)
            X_p = X_p.drop(columns=drop_cols)
            X_p_list = list(X_p.iloc[0])
            train = train.dropna()
            model = sm.OLS(
                train[target], sm.add_constant(train.drop(target, axis=1)),
            ).fit()
            X = train.drop(target, axis=1)
            while len(model.pvalues) > 1 and np.max(model.pvalues[1:]) > p_max:
                drop_idx = int(np.argmax(model.pvalues[1:]))
                X = X.drop(X.columns[drop_idx], axis=1)
                X_p_list.pop(drop_idx + 1)
                model = sm.OLS(train[target], sm.add_constant(X)).fit()
            forc.append(float(model.predict(X_p_list)[0]))
            var.append(float(model.mse_resid))

        forc_a = np.array(forc)
        var_a = np.array(var)
        forecasts_aux.append(float(np.sum(forc_a / var_a) / np.sum(1.0 / var_a)))

        accumulated = (
            float(np.sum(data.iloc[:i]))
            + float(np.sum(forecasts_aux))
        )
        value = first_value * float(np.exp(accumulated))
        points.append(ForecastPoint(
            date=future_dates[m - 1].date(),
            value=round(value, 4),
            lower_bound=None,
            upper_bound=None,
        ))

    logger.info("%s forecast: %d points, last=%.2f",
                model_name, len(points), points[-1].value if points else 0)
    return ForecastResult(model_name=model_name, aic=None, bic=None, points=points)


def train_gdp_nominal_quarterly(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 4,
) -> ForecastResult:
    """Quarterly nominal GDP forecast — 1:1 port of `Прогноз_номинальный_ВВП.ipynb`."""
    return _train_gdp_quarterly_port(
        dates, values, forecast_steps, model_name="GDP-Nominal-Quarterly-MW",
    )


def train_gdp_real_quarterly(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 4,
) -> ForecastResult:
    """Quarterly real GDP forecast — 1:1 port of `Прогноз_номинальный_ВВП.ipynb`.

    Никита запускает один и тот же `train_sarima_model(data, forecast_steps=4)`
    сначала на номинальном, потом на реальном ВВП. Раньше мы прогнозировали
    `gdp-real` через цепочку `gdp-real ← real_from_yoy(gdp-yoy)` с
    накопленной ошибкой 4.5–7.5%. Прямой запуск алгоритма ноутбука на ряду
    реального ВВП восстанавливает byte-exact совпадение с эталонными значениями.
    """
    return _train_gdp_quarterly_port(
        dates, values, forecast_steps, model_name="GDP-Real-Quarterly-MW",
    )


def train_gdp_consumption_quarterly(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 4,
) -> ForecastResult:
    """Quarterly forecast для `gdp-consumption` (расходы домохозяйств).

    Использует ту же методологию multi-window OLS на log-diff, что и
    `train_gdp_nominal_quarterly`. У этого ряда нет отдельного notebook'а
    Никиты — применяем согласованный алгоритм семейства ВВП к собственному
    ряду. Структурно зеркалит nominal/real.
    """
    return _train_gdp_quarterly_port(
        dates, values, forecast_steps, model_name="GDP-Consumption-Quarterly-MW",
    )


def train_gdp_government_quarterly(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 4,
) -> ForecastResult:
    """Quarterly forecast для `gdp-government` (государственное потребление).

    Та же методология семейства ВВП (multi-window OLS на log-diff,
    без блендинга). См. `train_gdp_consumption_quarterly`.
    """
    return _train_gdp_quarterly_port(
        dates, values, forecast_steps, model_name="GDP-Government-Quarterly-MW",
    )


# ---------------------------------------------------------------------------
#  Original OLS model (for non-CPI indicators)
# ---------------------------------------------------------------------------

def _apply_transform(series: pd.Series, transform: str) -> tuple[pd.Series, dict]:
    if transform == "cpi_index":
        return series / 100 - 1, {}
    if transform == "percentage":
        return series / 100, {}
    if transform == "absolute":
        mean, std = series.mean(), series.std()
        if std == 0:
            std = 1.0
        return (series - mean) / std, {"mean": mean, "std": std}
    return series.copy(), {}


def _inverse_transform(pred: float, std_pred: float, transform: str, meta: dict) -> tuple[float, float, float]:
    z = 1.96
    if transform == "cpi_index":
        val = round((pred + 1) * 100, 4)
        lo = round((pred - z * std_pred + 1) * 100, 4)
        hi = round((pred + z * std_pred + 1) * 100, 4)
    elif transform == "percentage":
        val = round(pred * 100, 4)
        lo = round((pred - z * std_pred) * 100, 4)
        hi = round((pred + z * std_pred) * 100, 4)
    elif transform == "absolute":
        m, s = meta["mean"], meta["std"]
        val = round(pred * s + m, 4)
        lo = round((pred - z * std_pred) * s + m, 4)
        hi = round((pred + z * std_pred) * s + m, 4)
    else:
        val = round(pred, 4)
        lo = round(pred - z * std_pred, 4)
        hi = round(pred + z * std_pred, 4)
    return val, lo, hi


def _build_ols_forecast_for_horizon(
    data_series: pd.Series,
    window_size: int,
    horizon_m: int,
    p_max: float = 0.01,
    cor_max: float = 0.7,
) -> tuple[float, float]:
    predictions = []
    variances = []
    i = len(data_series)

    for k in range(1, 5):
        seg = data_series.iloc[i - window_size // k:i].copy()
        seg = _remove_outliers(seg)
        train = pd.DataFrame(seg)

        X_p = [1]
        lags = range(horizon_m, horizon_m + 3)
        for j in lags:
            train[f'y_lag{j}'] = data_series.iloc[i - window_size // k:i].shift(j)
            X_p.append(float(data_series.iloc[-j + horizon_m - 1]))

        X_p = pd.DataFrame(
            np.array(X_p).reshape(1, -1),
            columns=train.columns,
        )

        corr_matrix = train.corr()
        drop_cols = set()
        target = 'value'
        for col_a in corr_matrix.columns:
            for col_b in corr_matrix.index:
                if col_a != col_b and col_a != target and col_b != target:
                    if abs(corr_matrix[col_a][col_b]) > cor_max:
                        if abs(corr_matrix[target][col_b]) > abs(corr_matrix[target][col_a]):
                            drop_cols.add(col_a)
                        else:
                            drop_cols.add(col_b)

        train = train.drop(columns=drop_cols, errors='ignore')
        X_p = X_p.drop(columns=drop_cols, errors='ignore')
        X_p_list = list(X_p.iloc[0])

        train = train.dropna()
        if len(train) < 5:
            continue

        y = train['value']
        X = sm.add_constant(train.drop('value', axis=1))
        model = sm.OLS(y, X).fit()

        X_feat = train.drop('value', axis=1)
        while len(model.pvalues) > 1 and np.max(model.pvalues[1:]) > p_max:
            worst_idx = np.argmax(model.pvalues[1:])
            X_feat = X_feat.drop(X_feat.columns[worst_idx], axis=1)
            X_p_list.pop(worst_idx + 1)
            model = sm.OLS(y, sm.add_constant(X_feat)).fit()

        pred = model.predict(X_p_list)[0]
        mse = model.mse_resid
        if mse > 0:
            predictions.append(pred)
            variances.append(mse)

    if not predictions:
        fallback = float(data_series.iloc[-1]) if len(data_series) > 0 else 0.0
        fallback_var = float(data_series.var()) if len(data_series) > 1 and data_series.var() > 0 else 1.0
        return fallback, fallback_var

    preds = np.array(predictions)
    varis = np.array(variances)
    inv_var = 1.0 / varis
    weighted_pred = np.sum(preds * inv_var) / np.sum(inv_var)
    combined_var = 1.0 / np.sum(inv_var)

    return float(weighted_pred), float(combined_var)


def _date_step(frequency: str) -> relativedelta:
    """Return the appropriate date step for a given frequency."""
    if frequency == "daily":
        return relativedelta(days=1)
    if frequency == "weekly":
        return relativedelta(weeks=1)
    if frequency == "quarterly":
        return relativedelta(months=3)
    if frequency == "annual":
        return relativedelta(years=1)
    return relativedelta(months=1)


# ---------------------------------------------------------------------------
#  Руководитель's `Прогноз_месячных_данных.ipynb` (June 2026):
#  generic monthly forecaster with ADF-driven transform selection.
# ---------------------------------------------------------------------------

def _adf_transform(level: pd.Series) -> tuple[pd.Series, str]:
    """ADF-driven transform selection (1:1 с ноутбуком `train_model`).

    Уровень стационарен (ADF p<=0.05) → 'stationary' (ряд как есть).
    Иначе первая разность; если стационарна → 'dif'.
    Иначе лог-разность → 'log' (только если ряд строго положителен;
    для знаковых рядов лог неприменим — остаёмся на 'dif').
    """
    try:
        p = adfuller(level, regression="c")[1]
    except Exception:
        p = 1.0
    if p <= 0.05:
        return level, "stationary"

    diffed = level.diff().dropna()
    try:
        p2 = adfuller(diffed, regression="c")[1] if len(diffed) > 3 else 1.0
    except Exception:
        p2 = 1.0
    if p2 <= 0.05:
        return diffed, "dif"

    if bool((level > 0).all()):
        return np.log(level).diff(1).dropna(), "log"
    return diffed, "dif"


def train_monthly_auto(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 12,
) -> ForecastResult:
    """Generic monthly forecast — порт `Прогноз_месячных_данных.ipynb`.

    Алгоритм (для любого месячного ряда):
      1. ADF выбирает трансформ: уровень / первая разность / лог-разность.
      2. На трансформированном ряду — multi-window OLS по лагам
         `[m, m+1, m+2, 12]` (с убыванием к горизонту), отсев
         мультиколлинеарности (|corr|>0.7) и backward-elimination по
         p-value (<0.01); прогнозы окон взвешиваются обратно дисперсии.
      3. Уровень восстанавливается согласно маркеру трансформа.

    Переиспользует те же чистые блоки (`_ols_step`, `_multi_window_predict`,
    `_remove_outliers`, `_get_horizon_lags`), что и ранее портированные
    ноутбуки Никиты — отличие только в ADF-автовыборе трансформа.
    """
    model_name = "Monthly-Auto-MW"
    level = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name="value")
    if len(level) < 36:
        logger.info("%s: %d obs < 36, skipping", model_name, len(level))
        return ForecastResult(model_name=model_name, aic=None, bic=None, points=[])

    data, marker = _adf_transform(level)
    window_size = len(data)
    k_max = max(window_size // 60, 2)
    k_range = range(1, k_max)

    first_value = float(level.iloc[0])
    sum_transformed = float(np.sum(data))
    future_dates = [
        level.index[-1] + relativedelta(months=j) for j in range(1, forecast_steps + 1)
    ]

    forecasts_aux: list[float] = []
    points: list[ForecastPoint] = []
    for m in range(1, forecast_steps + 1):
        lags = _get_horizon_lags(m)
        pred = _multi_window_predict(
            data, window_size, m, lags,
            apply_rolling=False, k_range=k_range, min_window=12,
        )
        if pred is None:
            pred = float(np.median(data.iloc[-12:]))
        forecasts_aux.append(pred)

        if marker == "stationary":
            value = forecasts_aux[-1]
        elif marker == "dif":
            value = first_value + sum_transformed + float(np.sum(forecasts_aux))
        else:  # log
            value = first_value * float(np.exp(sum_transformed + float(np.sum(forecasts_aux))))

        if not np.isfinite(value):
            continue
        points.append(ForecastPoint(
            date=future_dates[m - 1].date(), value=round(value, 4),
            lower_bound=None, upper_bound=None,
        ))

    logger.info("%s forecast (marker=%s): %d points, last=%.2f",
                model_name, marker, len(points), points[-1].value if points else 0)
    return ForecastResult(model_name=model_name, aic=None, bic=None, points=points)


def train_and_forecast(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 12,
    confidence_z: float = 1.96,
    forecast_transform: str = "cpi_index",
    frequency: str = "monthly",
    **_kwargs,
) -> ForecastResult:
    """Original OLS multi-window model for non-CPI indicators."""
    series = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name='value')
    data, meta = _apply_transform(series, forecast_transform)

    window_size = len(data)
    model_name = "OLS-MultiWindow"
    logger.info("Training %s on %d observations, horizon=%d, transform=%s, freq=%s...",
                model_name, len(data), forecast_steps, forecast_transform, frequency)

    last_date = data.index[-1]
    step = _date_step(frequency)
    forecast_dates = [last_date + step * (i + 1) for i in range(forecast_steps)]

    forecasts_aux = []
    variances_aux = []

    for m in range(1, forecast_steps + 1):
        pred, var = _build_ols_forecast_for_horizon(data, window_size, m)
        forecasts_aux.append(pred)
        variances_aux.append(var)

    cumulative_12m = None
    if forecast_transform == "cpi_index" and forecast_steps <= 12:
        n_actual = max(0, 12 - forecast_steps)
        recent = list(data.iloc[-n_actual:].values) if n_actual > 0 else []
        fc_part = list(forecasts_aux[:min(forecast_steps, 12)])
        factors_12 = (recent + fc_part)[-12:]
        cumulative_12m = 1.0
        for v in factors_12:
            cumulative_12m *= (v + 1)
        cumulative_12m = cumulative_12m * 100 - 100

    points = []
    for idx in range(forecast_steps):
        val, lo, hi = _inverse_transform(
            forecasts_aux[idx], np.sqrt(variances_aux[idx]),
            forecast_transform, meta,
        )
        points.append(ForecastPoint(
            date=forecast_dates[idx].date(), value=val,
            lower_bound=lo, upper_bound=hi,
        ))

    logger.info("Forecast complete: %s, cumulative 12m = %s", model_name,
                f"{cumulative_12m:.2f}%" if cumulative_12m is not None else "N/A")

    monthly_preds = []
    for f in forecasts_aux:
        if forecast_transform == "cpi_index":
            monthly_preds.append(round((f + 1) * 100, 4))
        elif forecast_transform == "percentage":
            monthly_preds.append(round(f * 100, 4))
        elif forecast_transform == "absolute":
            monthly_preds.append(round(f * meta["std"] + meta["mean"], 4))
        else:
            monthly_preds.append(round(f, 4))

    return ForecastResult(
        model_name=model_name,
        aic=None,
        bic=None,
        points=points,
        cumulative_12m=round(cumulative_12m, 4) if cumulative_12m is not None else None,
        monthly_predictions=monthly_preds,
    )
