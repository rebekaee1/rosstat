from app.api.forecasts import _replaces_partial_actual


def test_only_derived_partial_buckets_may_replace_actual() -> None:
    assert not _replaces_partial_actual({"forecast_strategy": "derived_from_source", "derived_forecast": {
        "operation": "pipeline",
        "pipeline": [["yoy", {"periods": 4}]],
    }})
    assert _replaces_partial_actual({"forecast_strategy": "derived_from_source", "derived_forecast": {
        "operation": "pipeline",
        "pipeline": [["period_sum", {"granularity": "quarter"}]],
    }})
    assert _replaces_partial_actual({"forecast_strategy": "derived_from_source", "derived_forecast": {
        "operation": "pipeline",
        "monthly_tail_extrapolate": True,
    }})
    assert not _replaces_partial_actual({"forecast_strategy": "monthly_auto", "derived_forecast": {
        "monthly_tail_extrapolate": True,
    }})
