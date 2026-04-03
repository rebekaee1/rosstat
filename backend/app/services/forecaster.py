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
    s = series.copy()
    for _ in range(50):
        mean, std = s.mean(), s.std()
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
        while len(model.pvalues) > 1 and np.max(model.pvalues[1:]) > p_max:
            worst = np.argmax(model.pvalues[1:])
            X_feat = X_feat.drop(X_feat.columns[worst], axis=1)
            X_p_list.pop(worst + 1)
            if len(X_feat.columns) == 0:
                break
            model = sm.OLS(y, sm.add_constant(X_feat)).fit()

        pred = model.predict(X_p_list)[0]
        mse = model.mse_resid
        if mse <= 0 or not np.isfinite(pred):
            return None, None
        return float(pred), float(mse)
    except Exception:
        return None, None


def _multi_window_predict(data_col: pd.Series, window_size: int,
                          horizon_m: int, lags: list[int],
                          apply_rolling: bool = False):
    """Run OLS across 4 window sizes, return inverse-variance weighted prediction."""
    i = len(data_col)
    preds, varis = [], []

    for k in range(1, 5):
        seg_size = max(24, window_size // k)
        start = max(0, i - seg_size)
        df_aux = data_col.iloc[start:i].copy()

        if apply_rolling and horizon_m > 1:
            df_aux = df_aux.rolling(horizon_m).mean()

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

def train_monthly_cpi(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 12,
) -> ForecastResult:
    """Multi-window OLS for monthly CPI. Transform: df - 100."""
    series = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name='value')
    data = pd.DataFrame(series - 100, columns=['value'])
    window_size = len(data)
    monthly_dates = [data.index[-1] + relativedelta(months=j + 1) for j in range(forecast_steps)]

    points = []
    for m in range(1, forecast_steps + 1):
        lags = _get_horizon_lags(m)
        pred = _multi_window_predict(data['value'], window_size, m, lags, apply_rolling=False)

        if pred is None:
            pred = float(np.median(data['value'].iloc[-12:]))

        cpi_value = round(pred + 100, 4)
        points.append(ForecastPoint(
            date=monthly_dates[m - 1].date(),
            value=cpi_value,
            lower_bound=None,
            upper_bound=None,
        ))

    logger.info("CPI-Monthly-MW forecast: %d points, last=%.4f", len(points),
                points[-1].value if points else 0)
    return ForecastResult(model_name="CPI-Monthly-MW", aic=None, bic=None, points=points)


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

    Transform: np.log((df / 100).cumprod()).diff(1)
    Output: cumulative 12-month inflation % for each horizon.
    """
    series = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name='value')
    log_cum = np.log((series / 100).cumprod())
    log_diff = log_cum.diff(1).dropna()
    data = pd.DataFrame(log_diff, columns=['value'])
    window_size = len(data)

    monthly_dates = [data.index[-1] + relativedelta(months=j + 1) for j in range(forecast_steps)]
    i = len(data)

    median_val = float(np.median(data.iloc[-12:, 0]))
    forecasts_aux = []
    points = []

    for m in range(1, forecast_steps + 1):
        lags = _get_horizon_lags(m)
        pred = _multi_window_predict(data['value'], window_size, m, lags, apply_rolling=True)

        if pred is None:
            pred = median_val

        forecasts_aux.append(pred)

        w = _INFLATION_BLEND_WEIGHTS.get(m, _BLEND_M12 if m == 12 else _DEFAULT_BLEND)
        blend = pred * w[0] + median_val * w[1] + ANNUAL_PRIOR * w[2]

        actual_sum = float(np.sum(data.iloc[i - (12 - m):i, 0])) if m < 12 else 0.0
        inflation_pct = float(np.exp(actual_sum + m * blend) * 100 - 100)

        points.append(ForecastPoint(
            date=monthly_dates[m - 1].date(),
            value=round(inflation_pct, 4),
            lower_bound=None,
            upper_bound=None,
        ))

    logger.info("Inflation-12M-MW forecast: %d points, last=%.2f%%", len(points),
                points[-1].value if points else 0)
    return ForecastResult(model_name="Inflation-12M-MW", aic=None, bic=None, points=points)


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
        return 0.0, 1.0

    preds = np.array(predictions)
    varis = np.array(variances)
    inv_var = 1.0 / varis
    weighted_pred = np.sum(preds * inv_var) / np.sum(inv_var)
    combined_var = 1.0 / np.sum(inv_var)

    return float(weighted_pred), float(combined_var)


def train_and_forecast(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 12,
    confidence_z: float = 1.96,
    forecast_transform: str = "cpi_index",
    **_kwargs,
) -> ForecastResult:
    """Original OLS multi-window model for non-CPI indicators."""
    series = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name='value')
    data, meta = _apply_transform(series, forecast_transform)

    window_size = len(data)
    model_name = "OLS-MultiWindow"
    logger.info("Training %s on %d observations, horizon=%d, transform=%s...",
                model_name, len(data), forecast_steps, forecast_transform)

    last_date = data.index[-1]
    monthly_dates = [last_date + relativedelta(months=i + 1) for i in range(forecast_steps)]

    forecasts_aux = []
    variances_aux = []

    for m in range(1, forecast_steps + 1):
        pred, var = _build_ols_forecast_for_horizon(data, window_size, m)
        forecasts_aux.append(pred)
        variances_aux.append(var)

    cumulative_12m = None
    if forecast_transform == "cpi_index":
        recent_actuals = data.iloc[-(12 - 1):].values
        cumulative_product = 1.0
        for v in recent_actuals:
            cumulative_product *= (v + 1)
        forecast_product = 1.0
        for v in forecasts_aux:
            forecast_product *= (v + 1)
        cumulative_12m = cumulative_product * forecast_product * 100 - 100

    points = []
    for idx in range(forecast_steps):
        val, lo, hi = _inverse_transform(
            forecasts_aux[idx], np.sqrt(variances_aux[idx]),
            forecast_transform, meta,
        )
        points.append(ForecastPoint(
            date=monthly_dates[idx].date(), value=val,
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
