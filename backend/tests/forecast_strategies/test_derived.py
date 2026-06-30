"""Unit-тесты derived_from_source стратегии.

Чистая математика: yoy/qoq/real_from_yoy. БД не нужна.
"""

from datetime import date

from app.services.forecast_strategies.base import StrategyContext
from app.services.forecast_strategies.derived_from_source import (
    derived_from_source_strategy,
)


def _make_ctx(*, indicator_code="gdp-yoy", frequency="quarterly", cfg=None):
    return StrategyContext(
        indicator_code=indicator_code,
        indicator_frequency=frequency,
        forecast_steps=4,
        cfg=cfg or {},
    )


def test_yoy_quarterly_basic():
    """gdp-yoy = (gdp-nominal[t] / gdp-nominal[t-4year]) * 100 - 100.

    Источник: 8 квартальных точек, ровно 2 года.
    Прогноз источника на 4 квартала = +2% per quarter относительно последнего
    Y[t] для каждого нового квартала = (X[t] / X[t-4]) * 100 - 100.
    """
    actual_dates = [
        date(2023, 3, 1), date(2023, 6, 1), date(2023, 9, 1), date(2023, 12, 1),
        date(2024, 3, 1), date(2024, 6, 1), date(2024, 9, 1), date(2024, 12, 1),
    ]
    actual_values = [100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0, 114.0]
    forecast_source = [
        (date(2025, 3, 1), 116.0),
        (date(2025, 6, 1), 118.0),
        (date(2025, 9, 1), 120.0),
        (date(2025, 12, 1), 122.0),
    ]
    full_source = list(zip(actual_dates, actual_values)) + forecast_source

    ctx = _make_ctx(cfg={
        "derived_forecast": {
            "operation": "yoy_quarterly",
            "model_name": "GDP-YoY-Derived",
        },
        "_source_data": full_source,
    })
    own_actual_dates = actual_dates
    own_actual_values = [(v / actual_values[i - 4] - 1) * 100 if i >= 4 else None
                         for i, v in enumerate(actual_values)]
    valid_pairs = [(d, v) for d, v in zip(own_actual_dates, own_actual_values) if v is not None]
    own_dates = [d for d, _ in valid_pairs]
    own_values = [v for _, v in valid_pairs]

    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    assert len(outputs) == 1
    points = outputs[0].result.points

    # 4 будущих точки yoy:
    # 2025Q1: 116/108 - 1 = 7.41%
    # 2025Q2: 118/110 - 1 = 7.27%
    # 2025Q3: 120/112 - 1 = 7.14%
    # 2025Q4: 122/114 - 1 = 7.02%
    assert len(points) == 4
    expected = [
        (date(2025, 3, 1), 7.4074),
        (date(2025, 6, 1), 7.2727),
        (date(2025, 9, 1), 7.1429),
        (date(2025, 12, 1), 7.0175),
    ]
    for p, (exp_d, exp_v) in zip(points, expected):
        assert p.date == exp_d
        assert abs(p.value - exp_v) < 0.01


def test_qoq_basic():
    full_source = [
        (date(2024, 3, 1), 100.0),
        (date(2024, 6, 1), 105.0),
        (date(2024, 9, 1), 110.0),
        (date(2024, 12, 1), 115.0),
        (date(2025, 3, 1), 120.0),
    ]
    ctx = _make_ctx(cfg={
        "derived_forecast": {"operation": "qoq", "model_name": "X-QoQ"},
        "_source_data": full_source,
    })
    own_dates = [date(2024, 3, 1), date(2024, 6, 1), date(2024, 9, 1), date(2024, 12, 1)]
    own_values = [None, 5.0, 4.7619, 4.5455]  # placeholder actuals

    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    points = outputs[0].result.points
    # Только 2025-03-01 — будущая (после last_actual_date 2024-12-01).
    assert len(points) == 1
    assert points[0].date == date(2025, 3, 1)
    # 120/115 - 1 = 4.3478%
    assert abs(points[0].value - 4.3478) < 0.01


def test_real_from_yoy():
    """real_from_yoy: real_GDP[t] = real_GDP[t - 4 quarters] * (1 + yoy[t] / 100).

    history real_GDP последние 4 квартала: [100, 102, 104, 106].
    yoy_source forecasted: [+3%, +3%, +3%, +3%] для следующих 4 кв.
    Ожидаем: 103.0, 105.06, 107.12, 109.18 (округление 4 знака).
    """
    own_dates = [
        date(2024, 3, 1), date(2024, 6, 1), date(2024, 9, 1), date(2024, 12, 1),
    ]
    own_values = [100.0, 102.0, 104.0, 106.0]

    yoy_source = [
        # actuals (тупо нули, нам не нужны)
        (date(2024, 3, 1), 0.0),
        (date(2024, 6, 1), 0.0),
        (date(2024, 9, 1), 0.0),
        (date(2024, 12, 1), 0.0),
        # forecast
        (date(2025, 3, 1), 3.0),
        (date(2025, 6, 1), 3.0),
        (date(2025, 9, 1), 3.0),
        (date(2025, 12, 1), 3.0),
    ]

    ctx = _make_ctx(
        indicator_code="gdp-real",
        cfg={
            "derived_forecast": {
                "operation": "real_from_yoy",
                "source_code": "gdp-yoy",
                "model_name": "GDP-Real-From-YoY",
            },
            "_source_data": yoy_source,
        },
    )

    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    points = outputs[0].result.points
    assert len(points) == 4
    expected = [
        (date(2025, 3, 1), 103.0),
        (date(2025, 6, 1), 105.06),
        (date(2025, 9, 1), 107.12),
        (date(2025, 12, 1), 109.18),
    ]
    for p, (exp_d, exp_v) in zip(points, expected):
        assert p.date == exp_d
        assert abs(p.value - exp_v) < 0.01


def test_no_source_data_returns_empty():
    ctx = _make_ctx(cfg={
        "derived_forecast": {"operation": "yoy_monthly", "model_name": "X"},
    })
    outputs = derived_from_source_strategy(
        [date(2024, 1, 1)], [100.0], ctx,
    )
    assert outputs == []


def test_unknown_operation_returns_empty():
    ctx = _make_ctx(cfg={
        "derived_forecast": {"operation": "????", "model_name": "X"},
        "_source_data": [(date(2024, 1, 1), 100.0)],
    })
    outputs = derived_from_source_strategy(
        [date(2024, 1, 1)], [100.0], ctx,
    )
    assert outputs == []


def test_december_to_december_emits_only_future_complete_year():
    """Source CPI: full 2024 monthly indices (actuals) + 12 monthly forecast for 2025.
    Indicator's own actuals: only 2024 annual point. Strategy must emit 2025.
    """
    cpi_actuals_2024 = [(date(2024, m, 1), 101.0) for m in range(1, 13)]
    cpi_actuals_2025_partial = [(date(2025, m, 1), 100.5) for m in range(1, 4)]  # Jan-Mar
    cpi_forecast_2025_rest = [(date(2025, m, 1), 100.5) for m in range(4, 13)]  # Apr-Dec
    full_source = cpi_actuals_2024 + cpi_actuals_2025_partial + cpi_forecast_2025_rest

    own_dates = [date(2024, 1, 1)]
    own_values = [(1.01 ** 12 - 1) * 100]

    ctx = _make_ctx(
        indicator_code="inflation-annual",
        frequency="annual",
        cfg={
            "derived_forecast": {
                "source_code": "cpi",
                "operation": "december_to_december",
                "model_name": "Annual-Dec2Dec-CPI",
            },
            "_source_data": full_source,
        },
    )

    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    assert len(outputs) == 1
    points = outputs[0].result.points
    assert [p.date for p in points] == [date(2025, 1, 1)]
    expected_2025 = round((1.005 ** 12 - 1) * 100, 4)
    assert abs(points[0].value - expected_2025) < 0.0001
    assert outputs[0].result.model_name == "Annual-Dec2Dec-CPI"


def test_december_to_december_no_complete_future_year_returns_empty():
    """Source forecast covers only Q1 of next year → no annual point can be made."""
    cpi_actuals = [(date(2024, m, 1), 101.0) for m in range(1, 13)]
    cpi_actuals += [(date(2025, m, 1), 100.4) for m in range(1, 7)]  # Jan-Jun 2025
    cpi_forecast = [(date(2025, m, 1), 100.4) for m in range(7, 13)]  # Jul-Dec 2025
    cpi_forecast += [(date(2026, 1, 1), 100.4), (date(2026, 2, 1), 100.4)]  # only 2 months 2026

    own_dates = [date(2024, 1, 1)]
    own_values = [12.6825]

    ctx = _make_ctx(
        indicator_code="inflation-annual",
        frequency="annual",
        cfg={
            "derived_forecast": {
                "source_code": "cpi",
                "operation": "december_to_december",
                "model_name": "Annual-Dec2Dec-CPI",
            },
            "_source_data": cpi_actuals + cpi_forecast,
        },
    )

    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    points = outputs[0].result.points
    assert [p.date for p in points] == [date(2025, 1, 1)]


def test_annual_sum_quarterly_emits_complete_future_year():
    """gdp-real-annual: 4 quarters of 2024 actuals + 4 quarters 2025 forecast → 1 future point."""
    actuals_2023 = [
        (date(2023, 3, 1), 8000.0), (date(2023, 6, 1), 9000.0),
        (date(2023, 9, 1), 9500.0), (date(2023, 12, 1), 10000.0),
    ]
    actuals_2024 = [
        (date(2024, 3, 1), 8500.0), (date(2024, 6, 1), 9300.0),
        (date(2024, 9, 1), 9800.0), (date(2024, 12, 1), 10400.0),
    ]
    forecast_2025 = [
        (date(2025, 3, 1), 8800.0), (date(2025, 6, 1), 9600.0),
        (date(2025, 9, 1), 10100.0), (date(2025, 12, 1), 10700.0),
    ]

    own_dates = [date(2023, 1, 1), date(2024, 1, 1)]
    own_values = [36500.0, 38000.0]

    ctx = _make_ctx(
        indicator_code="gdp-real-annual",
        frequency="annual",
        cfg={
            "derived_forecast": {
                "source_code": "gdp-real",
                "operation": "annual_sum",
                "model_name": "GDP-Real-Annual-Sum",
            },
            "_source_data": actuals_2023 + actuals_2024 + forecast_2025,
        },
    )

    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    points = outputs[0].result.points
    assert len(points) == 1
    assert points[0].date == date(2025, 1, 1)
    assert abs(points[0].value - 39200.0) < 0.01  # sum of 2025 quarters


def test_annual_sum_drops_incomplete_future_year():
    """If forecast for 2026 covers only Q1+Q2, 2026 yearly point is NOT emitted."""
    full_2024 = [
        (date(2024, q, 1), 1000.0) for q in (3, 6, 9, 12)
    ]
    full_2025 = [
        (date(2025, q, 1), 1100.0) for q in (3, 6, 9, 12)
    ]
    partial_2026 = [(date(2026, 3, 1), 1200.0), (date(2026, 6, 1), 1200.0)]

    own_dates = [date(2024, 1, 1)]
    own_values = [4000.0]

    ctx = _make_ctx(
        indicator_code="gdp-real-annual",
        frequency="annual",
        cfg={
            "derived_forecast": {
                "source_code": "gdp-real",
                "operation": "annual_sum",
                "model_name": "GDP-Real-Annual-Sum",
            },
            "_source_data": full_2024 + full_2025 + partial_2026,
        },
    )

    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    points = outputs[0].result.points
    assert [p.date for p in points] == [date(2025, 1, 1)]


def test_cpi_mom_yoy_emits_only_future_months():
    """cpi-yoy: прогноз строится на цепочке уровней из месячных ИПЦ (~100)."""
    actuals = [(date(2024, m, 1), 100.5) for m in range(1, 13)]
    forecast = [(date(2025, m, 1), 100.4) for m in range(1, 4)]
    full_source = actuals + forecast
    own_dates = [d for d, _ in actuals]
    own_values = [8.0] * 12

    ctx = _make_ctx(
        indicator_code="cpi-yoy",
        frequency="monthly",
        cfg={
            "derived_forecast": {
                "operation": "cpi_mom_yoy",
                "model_name": "CPI-YoY-Derived",
            },
            "_source_data": full_source,
        },
    )
    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    assert len(outputs) == 1
    points = outputs[0].result.points
    assert all(p.date > date(2024, 12, 1) for p in points)
    assert len(points) == 3


def test_monthly_tail_extrapolate_eop_year_from_last_forecast_month():
    """Ставка/уровень: последний месяц прогноза → годовой прогноз тем же значением.

    Источник покрывает год целиком (факт Jan-Feb + прогноз Mar-Dec): только тогда
    отдаём годовую точку (guard полноты bucket'а = 12 месяцев по ритму источника).
    """
    actuals = [(date(2026, m, 1), 16.0 + m * 0.1) for m in range(1, 3)]
    forecast = [(date(2026, m, 1), 17.5) for m in range(3, 13)]
    full_source = actuals + forecast
    own_dates = [date(2026, 1, 1)]
    own_values = [16.1]

    ctx = _make_ctx(
        indicator_code="auto-loan-rate-eop-year",
        frequency="annual",
        cfg={
            "derived_forecast": {
                "operation": "pipeline",
                "pipeline": [["period_last", {"granularity": "year"}]],
                "monthly_tail_extrapolate": True,
                "model_name": "auto-loan-rate-eop-year-derived",
            },
            "_source_data": full_source,
            "_source_actual_dates": [d for d, _ in actuals],
        },
    )
    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    points = outputs[0].result.points
    assert len(points) == 1
    assert points[0].date == date(2026, 1, 1)
    assert points[0].value == 17.5


def test_monthly_tail_extrapolate_sum_quarter_ytd_plus_remainder():
    """Поток sum-quarter: незавершённый квартал = факт месяцев + прогноз остатка;
    будущий полный квартал = сумма прогнозных месяцев; частичный квартал на конце
    горизонта не отдаём."""
    actuals = [(date(2026, 1, 1), 100.0), (date(2026, 2, 1), 110.0)]
    # Q1: факт Jan+Feb + прогноз Mar; Q2: полный прогноз Apr-Jun; Jul — частичный
    # хвост (Q3 неполный) → не должен попасть в прогноз.
    forecast = [
        (date(2026, 3, 1), 200.0),
        (date(2026, 4, 1), 250.0),
        (date(2026, 5, 1), 250.0),
        (date(2026, 6, 1), 250.0),
        (date(2026, 7, 1), 250.0),
    ]
    full_source = actuals + forecast
    own_dates = [date(2026, 3, 1)]
    own_values = [210.0]

    ctx = _make_ctx(
        indicator_code="retail-trade-sum-quarter",
        frequency="quarterly",
        cfg={
            "derived_forecast": {
                "operation": "pipeline",
                "pipeline": [["period_sum", {"granularity": "quarter"}]],
                "monthly_tail_extrapolate": True,
                "model_name": "retail-trade-sum-quarter-derived",
            },
            "_source_data": full_source,
            "_source_actual_dates": [d for d, _ in actuals],
        },
    )
    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    points = {p.date: p.value for p in outputs[0].result.points}
    # Q1 = 100 + 110 + 200 (YTD факт + прогноз остатка квартала)
    assert points[date(2026, 3, 1)] == 410.0
    # Q2 = 250 * 3 (полный прогнозный квартал)
    assert points[date(2026, 6, 1)] == 750.0
    # Q3 неполный (только Jul) → не отдаём
    assert date(2026, 9, 1) not in points


def test_period_sum_year_revises_partial_ytd_anchor():
    """sum-year: partial YTD на 01-01 пересчитывается в полный годовой прогноз."""
    actuals = [(date(2026, 1, 1), 100.0), (date(2026, 2, 1), 200.0)]
    forecast = [(date(2026, m, 1), 300.0) for m in range(3, 13)]
    forecast += [(date(2027, 1, 1), 250.0), (date(2027, 2, 1), 250.0)]
    full_source = actuals + forecast

    own_dates = [date(2026, 1, 1)]
    own_values = [300.0]  # partial Jan+Feb actual

    ctx = _make_ctx(
        indicator_code="budget-revenue-sum-year",
        frequency="annual",
        cfg={
            "derived_forecast": {
                "operation": "pipeline",
                "pipeline": [["period_sum", {"granularity": "year"}]],
                "complete_bucket": "year",
                "min_periods": 12,
                "model_name": "budget-revenue-sum-year-derived",
            },
            "_source_data": full_source,
        },
    )
    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    points = outputs[0].result.points
    assert len(points) == 1
    assert points[0].date == date(2026, 1, 1)
    assert points[0].value == round(100.0 + 200.0 + 300.0 * 10, 4)


def test_period_sum_quarter_revises_partial_quarter_anchor():
    """sum-quarter: неполный квартал на якоре пересчитывается с прогнозом месяцев."""
    actuals = [(date(2026, 1, 1), 100.0), (date(2026, 2, 1), 150.0)]
    forecast = [(date(2026, 3, 1), 200.0)] + [
        (date(2026, m, 1), 250.0) for m in range(4, 13)
    ]
    full_source = actuals + forecast

    own_dates = [date(2026, 3, 1)]
    own_values = [250.0]  # partial Q1 (Jan+Feb only)

    ctx = _make_ctx(
        indicator_code="budget-revenue-sum-quarter",
        frequency="quarterly",
        cfg={
            "derived_forecast": {
                "operation": "pipeline",
                "pipeline": [["period_sum", {"granularity": "quarter"}]],
                "complete_bucket": "quarter",
                "min_periods": 3,
                "model_name": "budget-revenue-sum-quarter-derived",
            },
            "_source_data": full_source,
        },
    )
    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    points = outputs[0].result.points
    assert points[0].date == date(2026, 3, 1)
    assert points[0].value == 450.0
    assert len(points) >= 2  # Q1 revision + future quarters


def test_empty_target_actuals_cuts_by_source_last_actual():
    """Регрессия (ИПП-компоненты, 2026-06-30): если у derived-ряда ещё нет
    собственного факта (own_dates=[]), стратегия не должна выдавать ВСЮ историю
    как прогноз. Прогноз = только точки за пределами факта источника
    (_source_actual_dates), а не 148 точек = вся история + хвост.
    """
    actuals = [(date(2024, m, 1), 100.0 + m) for m in range(1, 13)]  # факт источника
    forecast = [(date(2025, m, 1), 113.0 + m) for m in range(1, 4)]  # прогноз источника
    full_source = actuals + forecast

    ctx = _make_ctx(
        indicator_code="ipi-energy-mom",
        frequency="monthly",
        cfg={
            "derived_forecast": {
                "operation": "pipeline",
                "pipeline": [["mom", {}]],
                "model_name": "ipi-energy-mom-derived",
            },
            "_source_data": full_source,
            "_source_actual_dates": [d for d, _ in actuals],
        },
    )
    # own_dates пуст — derived-актуалы ещё не посчитаны.
    outputs = derived_from_source_strategy([], [], ctx)
    assert len(outputs) == 1
    points = outputs[0].result.points
    # Только 3 будущих mom-точки (Jan-Mar 2025), не вся история.
    assert all(p.date > date(2024, 12, 1) for p in points)
    assert len(points) == 3


def test_weekly_inflation_by_calendar_month_forecast():
    """cpi-period-monthly: агрегация недельного прогноза в месячные точки."""
    actuals = [
        (date(2025, 1, 6), 100.2),
        (date(2025, 1, 13), 100.1),
        (date(2025, 1, 20), 100.3),
        (date(2025, 1, 27), 100.2),
        (date(2025, 2, 3), 100.4),
        (date(2025, 2, 10), 100.3),
    ]
    forecast = [
        (date(2025, 2, 17), 100.2),
        (date(2025, 2, 24), 100.1),
        (date(2025, 3, 3), 100.3),
    ]
    full_source = actuals + forecast
    own_dates = [date(2025, 1, 27), date(2025, 2, 10)]
    own_values = [0.8, 0.7]

    ctx = _make_ctx(
        indicator_code="cpi-period-monthly",
        frequency="monthly",
        cfg={
            "derived_forecast": {
                "operation": "weekly_inflation_by_calendar_month",
                "model_name": "CPI-Period-Monthly-Derived",
            },
            "_source_data": full_source,
        },
    )
    outputs = derived_from_source_strategy(own_dates, own_values, ctx)
    points = outputs[0].result.points
    assert len(points) >= 1
    assert all(p.date > date(2025, 2, 10) for p in points)
