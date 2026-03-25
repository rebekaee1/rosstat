"""
OLS regression forecasting service.
Multi-window inverse-variance weighted OLS with lagged features.
Produces month-by-month CPI forecasts with confidence intervals.
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


@dataclass
class ForecastPoint:
    date: date
    value: float
    lower_bound: float
    upper_bound: float


@dataclass
class ForecastResult:
    model_name: str
    aic: float | None
    bic: float | None
    points: List[ForecastPoint]
    cumulative_12m: float | None = None
    monthly_predictions: List[float] = field(default_factory=list)


def _remove_outliers(series: pd.Series, sigma: float = 3.0) -> pd.Series:
    s = series.copy()
    while True:
        mean, std = s.mean(), s.std()
        if std == 0:
            break
        mask_hi = (s - mean) / std > sigma
        mask_lo = (s - mean) / std < -sigma
        if not (mask_hi.any() or mask_lo.any()):
            break
        s[mask_hi] = mean + 1.9 * std
        s[mask_lo] = mean - 1.9 * std
    return s


def _build_ols_forecast_for_horizon(
    data_series: pd.Series,
    window_size: int,
    horizon_m: int,
    p_max: float = 0.01,
    cor_max: float = 0.7,
) -> tuple[float, float]:
    """Build OLS prediction for a single horizon step using multiple window sizes.

    Returns (weighted_prediction, combined_variance).
    """
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


def _apply_transform(series: pd.Series, transform: str) -> tuple[pd.Series, dict]:
    """Forward transform before OLS. Returns (transformed, meta for inverse)."""
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
    """Inverse-transform a single prediction back to original scale. Returns (value, lower, upper)."""
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


def train_and_forecast(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 12,
    confidence_z: float = 1.96,
    forecast_transform: str = "cpi_index",
    **_kwargs,
) -> ForecastResult:
    """Train OLS multi-window model and generate forecast.

    Args:
        dates: sorted list of observation dates
        values: corresponding values
        forecast_steps: number of periods to forecast
        confidence_z: z-score for confidence intervals (1.96 = 95%)
        forecast_transform: "cpi_index" | "percentage" | "absolute" | "none"
    """
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
