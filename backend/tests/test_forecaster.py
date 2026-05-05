"""Tests for the forecaster module — transform, inverse, date stepping."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.services.forecaster import (
    _apply_transform,
    _inverse_transform,
    _date_step,
    _remove_outliers,
    train_and_forecast,
    train_monthly_cpi,
    train_inflation_12m,
    train_quarterly_housing,
    _MONTHLY_PRIOR,
    ANNUAL_PRIOR,
)


def test_apply_transform_cpi_index():
    s = pd.Series([100.5, 101.0, 99.8], dtype=float, name="value")
    out, meta = _apply_transform(s, "cpi_index")
    np.testing.assert_allclose(out.values, [0.005, 0.01, -0.002], atol=1e-6)
    assert meta == {}


def test_apply_transform_absolute():
    s = pd.Series([10.0, 20.0, 30.0], dtype=float, name="value")
    out, meta = _apply_transform(s, "absolute")
    assert "mean" in meta and "std" in meta
    np.testing.assert_allclose(out.mean(), 0.0, atol=1e-6)
    np.testing.assert_allclose(out.std(), 1.0, atol=0.1)


def test_inverse_transform_cpi_index():
    val, lo, hi = _inverse_transform(0.005, 0.001, "cpi_index", {})
    assert val == 100.5
    assert lo < val < hi


def test_inverse_transform_absolute():
    val, lo, hi = _inverse_transform(0.0, 0.5, "absolute", {"mean": 100, "std": 10})
    assert val == 100.0
    assert lo < 100.0 < hi


def test_date_step_monthly():
    from dateutil.relativedelta import relativedelta
    step = _date_step("monthly")
    assert step == relativedelta(months=1)


def test_date_step_quarterly():
    from dateutil.relativedelta import relativedelta
    step = _date_step("quarterly")
    assert step == relativedelta(months=3)


def test_date_step_daily():
    from dateutil.relativedelta import relativedelta
    step = _date_step("daily")
    assert step == relativedelta(days=1)


def test_date_step_annual():
    from dateutil.relativedelta import relativedelta
    step = _date_step("annual")
    assert step == relativedelta(years=1)


def test_remove_outliers_no_change():
    s = pd.Series([1.0, 2.0, 3.0, 2.5, 1.5])
    out = _remove_outliers(s)
    assert len(out) == 5
    assert abs(out.mean() - s.mean()) < 0.5


def test_remove_outliers_caps_extreme():
    s = pd.Series([1.0] * 100 + [1000.0])
    out = _remove_outliers(s)
    assert out.iloc[-1] < 1000.0


def test_train_and_forecast_produces_points():
    """Smoke test: forecaster produces correct number of points with correct dates."""
    np.random.seed(42)
    dates = [date(2020, m, 1) for m in range(1, 13)] + \
            [date(2021, m, 1) for m in range(1, 13)] + \
            [date(2022, m, 1) for m in range(1, 13)] + \
            [date(2023, m, 1) for m in range(1, 13)]
    values = list(100.3 + np.random.randn(48) * 0.2)

    result = train_and_forecast(
        dates, values,
        forecast_steps=6,
        forecast_transform="cpi_index",
        frequency="monthly",
    )
    assert len(result.points) == 6
    assert result.points[0].date == date(2024, 1, 1)
    assert result.points[5].date == date(2024, 6, 1)


def test_train_and_forecast_quarterly_dates():
    """Quarterly frequency should produce 3-month steps."""
    np.random.seed(42)
    dates = [date(2018 + i // 4, (i % 4) * 3 + 1, 1) for i in range(24)]
    values = list(1000 + np.random.randn(24) * 50)

    result = train_and_forecast(
        dates, values,
        forecast_steps=4,
        forecast_transform="absolute",
        frequency="quarterly",
    )
    assert len(result.points) == 4
    last_actual = date(2023, 10, 1)
    assert result.points[0].date == date(2024, 1, 1)


def test_train_monthly_cpi_smoke():
    np.random.seed(42)
    dates = [date(2020, m, 1) for m in range(1, 13)] + \
            [date(2021, m, 1) for m in range(1, 13)] + \
            [date(2022, m, 1) for m in range(1, 13)] + \
            [date(2023, m, 1) for m in range(1, 13)]
    values = list(100.5 + np.random.randn(48) * 0.3)

    result = train_monthly_cpi(dates, values, forecast_steps=6)
    assert len(result.points) == 6
    assert result.model_name == "CPI-Monthly-MW"
    for pt in result.points:
        assert 95 < pt.value < 110


def test_monthly_prior_matches_notebook_may_2026():
    """Никита's `Прогноз_ИПЦ_помесячно (2).ipynb`: prior = 4/1200."""
    assert _MONTHLY_PRIOR == pytest.approx(4.0 / 1200.0, abs=1e-12)


def test_annual_prior_matches_notebook():
    """Никита's `Прогноз_инфляции_12_мес (1).ipynb`: prior = 4/1200."""
    assert ANNUAL_PRIOR == pytest.approx(4.0 / 1200.0, abs=1e-12)


def test_train_inflation_12m_returns_full_horizon():
    """12-month inflation forecast must return a point per requested step."""
    np.random.seed(42)
    dates = [date(2018 + i // 12, (i % 12) + 1, 1) for i in range(120)]
    values = list(100.4 + np.random.randn(120) * 0.4)

    result = train_inflation_12m(dates, values, forecast_steps=12)
    assert len(result.points) == 12
    assert result.model_name == "Inflation-12M-MW"
    for pt in result.points:
        # Inflation in % yoy — sanity bounds for a synthetic random walk.
        assert -5 < pt.value < 30


def test_train_quarterly_housing_returns_4_quarters():
    """Quarterly housing model forecasts 4 quarters ahead at 3-month steps."""
    dates = [date(2015 + i // 4, (i % 4) * 3 + 3, 1) for i in range(40)]
    values = [120.0 + i * 1.5 for i in range(40)]

    result = train_quarterly_housing(dates, values, forecast_steps=4)
    assert len(result.points) == 4
    assert result.model_name == "Quarterly-Housing-MW"
    # All quarterly steps are 3 months apart.
    for prev, cur in zip(result.points, result.points[1:]):
        delta_months = (cur.date.year - prev.date.year) * 12 + (cur.date.month - prev.date.month)
        assert delta_months == 3
