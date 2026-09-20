"""Sanity-тесты порта годового прогноза (Прогноз_годовых_данных.ipynb)."""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

from app.services.forecast_strategies.base import StrategyContext
from app.services.forecast_strategies.annual_auto import annual_auto_strategy
from app.services.forecaster import _adf_transform, train_annual_auto


_BIRTH_RATE = [
    (1990, 15.5), (1995, 10.9), (2000, 9.8), (2001, 10.0), (2002, 10.5),
    (2003, 11.1), (2004, 11.2), (2005, 11.0), (2006, 11.4), (2007, 12.9),
    (2008, 13.7), (2009, 13.9), (2010, 14.0), (2011, 14.1), (2012, 14.7),
    (2013, 14.5), (2014, 14.6), (2015, 12.8), (2016, 12.2), (2017, 11.1),
    (2018, 10.6), (2019, 9.8), (2020, 9.6), (2021, 9.4), (2022, 8.8), (2023, 8.6),
]


def _annual_dates(n: int, start_year: int = 1990) -> list[date]:
    return [date(start_year + i, 1, 1) for i in range(n)]


def test_trending_positive_series_forecasts_forward():
    n = 30
    dates = _annual_dates(n)
    values = [1000 * math.exp(0.03 * i) for i in range(n)]
    res = train_annual_auto(dates, values, forecast_steps=2)
    assert len(res.points) == 2
    assert all(math.isfinite(p.value) for p in res.points)
    assert res.points[0].date == date(dates[-1].year + 1, 1, 1)
    assert res.points[-1].value > values[-1] * 0.5


def test_short_series_returns_empty():
    dates = _annual_dates(8)
    values = list(range(8))
    res = train_annual_auto(dates, values, forecast_steps=2)
    assert res.points == []


def test_horizon_capped_at_four():
    dates = _annual_dates(20)
    values = [10.0 + 0.2 * i for i in range(20)]
    res = train_annual_auto(dates, values, forecast_steps=8)
    assert len(res.points) == 4


def test_signed_series_does_not_use_log():
    n = 24
    series = pd.Series(
        [(-1) ** i * (20 + i) for i in range(n)],
        index=pd.DatetimeIndex(_annual_dates(n)),
        dtype=float,
        name="value",
    )
    _data, marker = _adf_transform(series)
    assert marker in ("stationary", "dif")


def test_reproduces_notebook_birth_rate():
    """Ряд рождаемости из ноутбука, включая неравномерный шаг 1990→1995→2000.

    Ноутбук (marker='dif') даёт 2024 ≈ 8.5478.
    """
    dates = [date(year, 1, 1) for year, _ in _BIRTH_RATE]
    values = [float(value) for _, value in _BIRTH_RATE]
    res = train_annual_auto(dates, values, forecast_steps=2)
    assert len(res.points) == 2
    assert res.points[0].date == date(2024, 1, 1)
    assert res.points[1].date == date(2025, 1, 1)
    assert abs(res.points[0].value - 8.5478) < 1e-3
    assert 6.0 < res.points[1].value < 11.0


def test_strategy_wrapper_passes_steps():
    dates = _annual_dates(20)
    values = [100 + i + 2 * math.sin(i) for i in range(20)]
    ctx = StrategyContext(
        indicator_code="birth-rate", indicator_frequency="annual",
        forecast_steps=2, cfg={},
    )
    out = annual_auto_strategy(dates, values, ctx)
    assert len(out) == 1
    assert len(out[0].result.points) <= 2
    assert all(np.isfinite(p.value) for p in out[0].result.points)
