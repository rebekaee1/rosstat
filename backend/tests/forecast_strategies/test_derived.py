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
