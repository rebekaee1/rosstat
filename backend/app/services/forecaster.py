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


def train_and_forecast(
    dates: List[date],
    values: List[float],
    forecast_steps: int = 12,
    confidence_z: float = 1.96,
    **_kwargs,
) -> ForecastResult:
    """Train OLS multi-window model and generate CPI forecast.

    Args:
        dates: sorted list of observation dates
        values: corresponding CPI index values (e.g. 100.5 = +0.5% m/m)
        forecast_steps: number of months to forecast (default 12)
        confidence_z: z-score for confidence intervals (1.96 = 95%)

    Returns:
        ForecastResult with model info and individual month forecast points
    """
    series = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float, name='value')
    data = series / 100 - 1  # CPI 100.5 → 0.005

    window_size = len(data)
    model_name = "OLS-MultiWindow"
    logger.info("Training %s on %d observations, horizon=%d...",
                model_name, len(data), forecast_steps)

    last_date = data.index[-1]
    monthly_dates = [last_date + relativedelta(months=i + 1) for i in range(forecast_steps)]

    forecasts_aux = []
    variances_aux = []

    for m in range(1, forecast_steps + 1):
        pred, var = _build_ols_forecast_for_horizon(data, window_size, m)
        forecasts_aux.append(pred)
        variances_aux.append(var)

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
        pred_frac = forecasts_aux[idx]
        var_frac = variances_aux[idx]
        std_frac = np.sqrt(var_frac)

        cpi_value = round((pred_frac + 1) * 100, 4)
        cpi_lower = round((pred_frac - confidence_z * std_frac + 1) * 100, 4)
        cpi_upper = round((pred_frac + confidence_z * std_frac + 1) * 100, 4)

        points.append(ForecastPoint(
            date=monthly_dates[idx].date(),
            value=cpi_value,
            lower_bound=cpi_lower,
            upper_bound=cpi_upper,
        ))

    logger.info("Forecast complete: %s, cumulative 12m = %.2f%%", model_name, cumulative_12m)

    return ForecastResult(
        model_name=model_name,
        aic=None,
        bic=None,
        points=points,
        cumulative_12m=round(cumulative_12m, 4),
        monthly_predictions=[round((f + 1) * 100, 4) for f in forecasts_aux],
    )
