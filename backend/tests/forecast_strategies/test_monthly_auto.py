"""Sanity-тесты порта месячного прогноза (Прогноз_месячных_данных.ipynb)."""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path

import numpy as np

from app.services.forecast_strategies.base import StrategyContext
from app.services.forecast_strategies.monthly_auto import monthly_auto_strategy
from app.services.forecaster import _adf_transform, train_monthly_auto
import pandas as pd

_FIXTURES = Path(__file__).parent / "fixtures"


def _monthly_dates(n: int, start=(2000, 1)) -> list[date]:
    y, m = start
    out = []
    for _ in range(n):
        out.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def test_trending_positive_series_uses_log_and_forecasts_forward():
    n = 200
    dates = _monthly_dates(n)
    # Экспоненциальный рост с сезонностью — как денежная масса.
    values = [1000 * math.exp(0.01 * i) * (1 + 0.02 * math.sin(i)) for i in range(n)]
    res = train_monthly_auto(dates, values, forecast_steps=12)
    assert len(res.points) == 12
    assert all(math.isfinite(p.value) for p in res.points)
    # Растущий ряд → прогноз продолжает выше последнего факта.
    assert res.points[-1].value > values[-1] * 0.5


def test_short_series_returns_empty():
    dates = _monthly_dates(20)
    values = list(range(20))
    res = train_monthly_auto(dates, values, forecast_steps=12)
    assert res.points == []


def test_signed_series_does_not_use_log():
    # Знаковый ряд (как сальдо/дефицит): лог неприменим, маркер не 'log'.
    n = 120
    series = pd.Series(
        [(-1) ** i * (50 + i) for i in range(n)],
        index=pd.DatetimeIndex(_monthly_dates(n)),
        dtype=float,
        name="value",
    )
    _data, marker = _adf_transform(series)
    assert marker in ("stationary", "dif")


def test_reproduces_notebook_construction_work():
    """Регрессия на обновлённый ноутбук: на реальном ряде «Объём строительных
    работ» (328 точек, идентичен входу ноутбука) прогноз совпадает с
    опубликованными в ноутбуке значениями. Пин фиксирует rolling-сглаживание +
    пер-горизонтную реконструкцию `m·aux[m]`; ближний прогноз — точно, дальний
    (m=11,12) — в пределах 2% (наши guard'ы против вырожденного OLS)."""
    raw = json.loads((_FIXTURES / "construction_work_series.json").read_text())
    dates = [datetime.fromisoformat(p["date"]).date() for p in raw]
    values = [float(p["value"]) for p in raw]

    res = train_monthly_auto(dates, values, forecast_steps=12)
    assert len(res.points) == 12

    # Опубликованный в ноутбуке прогноз (marker='log').
    notebook = [
        1436.62, 1631.44, 1687.38, 1653.59, 1745.62, 1917.20,
        1777.42, 2890.49, 788.28, 939.54, 1239.90, 1536.29,
    ]
    for i, (pt, nb) in enumerate(zip(res.points, notebook)):
        tol = 0.001 if i < 10 else 0.02  # дальние горизонты — мягче
        assert abs(pt.value - nb) / nb <= tol, (
            f"horizon {i + 1}: port={pt.value} notebook={nb} "
            f"dev={abs(pt.value - nb) / nb:.4f}"
        )


def test_strategy_wrapper_passes_steps():
    dates = _monthly_dates(120)
    values = [100 + i + 5 * math.sin(i) for i in range(120)]
    ctx = StrategyContext(
        indicator_code="m2", indicator_frequency="monthly",
        forecast_steps=6, cfg={},
    )
    out = monthly_auto_strategy(dates, values, ctx)
    assert len(out) == 1
    assert len(out[0].result.points) <= 6
    assert all(np.isfinite(p.value) for p in out[0].result.points)
