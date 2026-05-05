"""Sanity-тесты реестра forecast-стратегий."""

from datetime import date

from app.services.forecast_strategies import STRATEGIES, resolve, StrategyContext


def test_all_strategies_resolvable():
    for name in STRATEGIES:
        assert resolve(name) is not None, f"strategy '{name}' not resolvable"


def test_unknown_strategy_returns_none():
    assert resolve("some_made_up_name") is None


def test_none_strategy_returns_none():
    assert resolve(None) is None


def test_approved_strategy_with_no_data():
    """approved-стратегия без точек → пустой list (не падает)."""
    from app.services.forecast_strategies.approved import approved_strategy

    ctx = StrategyContext(
        indicator_code="test",
        indicator_frequency="monthly",
        forecast_steps=12,
        cfg={},  # без approved_forecast_values
    )
    outputs = approved_strategy([date(2024, 1, 1)], [100.0], ctx)
    assert outputs == []


def test_approved_strategy_with_data():
    from app.services.forecast_strategies.approved import approved_strategy

    ctx = StrategyContext(
        indicator_code="test",
        indicator_frequency="monthly",
        forecast_steps=12,
        cfg={
            "approved_forecast_values": [
                {"date": "2026-01-01", "value": 100.5},
                {"date": "2026-02-01", "value": 100.6},
            ],
            "forecast_model_name": "Approved-Test",
        },
    )
    outputs = approved_strategy([], [], ctx)
    assert len(outputs) == 1
    result = outputs[0].result
    assert result.model_name == "Approved-Test"
    assert len(result.points) == 2
    assert result.points[0].value == 100.5
