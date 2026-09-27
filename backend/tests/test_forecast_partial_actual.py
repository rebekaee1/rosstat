from datetime import date
from types import SimpleNamespace

from app.api.forecasts import _public_annual_values, _replaces_partial_actual


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


def test_annual_api_shows_one_next_year_not_a_second_or_stale_year() -> None:
    values = [SimpleNamespace(date=date(year, 1, 1)) for year in (2026, 2027, 2028)]
    result = _public_annual_values(values, date(2026, 1, 1), replaces_partial=False)
    assert [row.date.year for row in result] == [2027]
    result = _public_annual_values(values[2:], date(2026, 1, 1), replaces_partial=False)
    assert result == []
    result = _public_annual_values(values, date(2026, 1, 1), replaces_partial=True)
    assert [row.date.year for row in result] == [2026, 2027]
