"""Tests for the calculation_engine helpers and registration."""

from app.services.calculation_engine import calculation_engine


def test_all_derived_registered():
    """Verify all expected derived indicators are registered."""
    expected = {
        "inflation-quarterly", "inflation-annual", "wages-real",
        "cpi-food-quarterly", "cpi-food-annual",
        "cpi-nonfood-quarterly", "cpi-nonfood-annual",
        "cpi-services-quarterly", "cpi-services-annual",
        "gdp-yoy", "gdp-qoq",
        "unemployment-quarterly", "unemployment-annual",
        "current-account-yoy", "ipi-yoy",
        "exports-yoy", "imports-yoy", "ppi-yoy", "wages-yoy",
        "exports-qoq", "imports-qoq",
        "housing-yoy-primary", "housing-yoy-secondary",
    }
    assert set(calculation_engine._derived.keys()) == expected


def test_derived_sources_exist():
    for code, (sources, fn) in calculation_engine._derived.items():
        assert len(sources) > 0, f"{code} has no sources"
        assert callable(fn), f"{code} fn is not callable"
