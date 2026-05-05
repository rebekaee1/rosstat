"""Smoke + детерминированные регрессионные тесты для новых моделей PPI и GDP-nominal.

Без живых данных Никиты (xlsx-файлы лежат у него) — тестируем на
синтетических входах с фиксированным random seed. Цель:
1. Модели не падают и возвращают корректное число точек.
2. Output воспроизводим (одни и те же входные данные → одни и те же выходные).
3. Output в разумных границах (не NaN, не отрицательный для индекса).

После того как Никита пришлёт реальные xlsx (или мы выгрузим с прода
полные данные) — добавим snapshot-тесты как у CPI.
"""

from datetime import date

import numpy as np

from app.services.forecaster import train_gdp_nominal_quarterly, train_ppi_monthly


def _synthetic_monthly_index(n_points=180, seed=42, base=100.0):
    """Синтетика: PPI-подобный индекс, ~5% годовой инфляции + шум."""
    rng = np.random.default_rng(seed)
    monthly_growth = rng.normal(loc=0.004, scale=0.005, size=n_points)
    series = [base]
    for g in monthly_growth:
        series.append(series[-1] * (1.0 + g))
    series = series[1:]
    dates = [date(2010 + i // 12, (i % 12) + 1, 1) for i in range(n_points)]
    return dates, series


def _synthetic_quarterly_value(n_points=60, seed=43, base=20000.0):
    rng = np.random.default_rng(seed)
    qoq_growth = rng.normal(loc=0.012, scale=0.02, size=n_points)
    series = [base]
    for g in qoq_growth:
        series.append(series[-1] * (1.0 + g))
    series = series[1:]
    dates = [date(2010 + i // 4, (i % 4) * 3 + 1, 1) for i in range(n_points)]
    return dates, series


def test_ppi_monthly_runs():
    dates, values = _synthetic_monthly_index()
    result = train_ppi_monthly(dates, values, forecast_steps=12)
    assert result.model_name == "PPI-Monthly-MW"
    assert len(result.points) == 12
    for p in result.points:
        assert p.value > 0, f"PPI {p.date} negative: {p.value}"
        assert not np.isnan(p.value)


def test_ppi_monthly_deterministic():
    """Один и тот же seed → один и тот же output."""
    d1, v1 = _synthetic_monthly_index(seed=7)
    d2, v2 = _synthetic_monthly_index(seed=7)
    r1 = train_ppi_monthly(d1, v1, forecast_steps=12)
    r2 = train_ppi_monthly(d2, v2, forecast_steps=12)
    for p1, p2 in zip(r1.points, r2.points):
        assert p1.value == p2.value


def test_gdp_nominal_quarterly_runs():
    dates, values = _synthetic_quarterly_value()
    result = train_gdp_nominal_quarterly(dates, values, forecast_steps=4)
    assert result.model_name == "GDP-Nominal-Quarterly-MW"
    assert len(result.points) == 4
    for p in result.points:
        assert p.value > 0
        assert not np.isnan(p.value)


def test_ppi_monthly_short_input_returns_empty():
    """Меньше 24 точек → пустой ForecastResult без падения."""
    dates = [date(2024, m + 1, 1) for m in range(12)]
    values = [100.0 + m * 0.1 for m in range(12)]
    result = train_ppi_monthly(dates, values, forecast_steps=12)
    assert result.points == []


def test_gdp_short_input_returns_empty():
    dates = [date(2023 + m // 4, ((m % 4) * 3) + 1, 1) for m in range(8)]
    values = [20000.0 + m * 100 for m in range(8)]
    result = train_gdp_nominal_quarterly(dates, values, forecast_steps=4)
    assert result.points == []
