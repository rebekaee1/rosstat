"""Forecast enablement policy.

Only forecasts explicitly approved by Nikita's notebooks/reviews should be
enabled. Other indicators may have data and charts, but their forecast toggle
must stay off until a forecast file/spec is approved.
"""

from __future__ import annotations

from seed_data import INDICATORS
from app.api.forecasts import DERIVED_CPI_FORECASTS


DIRECT_FORECAST_CODES = {
    "cpi",
    "cpi-food",
    "cpi-nonfood",
    "cpi-services",
    "ppi",
    "gdp-nominal",
}

APPROVED_NOTEBOOK_CODES = {
    "ppi": "Approved-PPI-Notebook",
    "gdp-nominal": "Approved-GDP-Nominal-Notebook",
}

EXPECTED_DERIVED_CPI_FORECASTS = {
    "inflation-quarterly",
    "inflation-annual",
    "cpi-food-quarterly",
    "cpi-food-annual",
    "cpi-nonfood-quarterly",
    "cpi-nonfood-annual",
    "cpi-services-quarterly",
    "cpi-services-annual",
}


def test_only_approved_direct_forecasts_are_enabled() -> None:
    enabled: set[str] = set()
    for ind in INDICATORS:
        if not ind.get("is_active"):
            continue
        cfg = ind.get("model_config_json") or {}
        forecast_steps = int(cfg.get("forecast_steps", 0) or 0)
        if forecast_steps > 0:
            enabled.add(ind["code"])

    assert enabled == DIRECT_FORECAST_CODES


def test_approved_notebook_forecasts_are_explicit_values() -> None:
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code, model_name in APPROVED_NOTEBOOK_CODES.items():
        cfg = by_code[code]["model_config_json"]
        assert cfg["forecast_model_name"] == model_name
        assert cfg["approved_forecast_values"]


def test_all_derived_cpi_forecasts_are_api_whitelisted() -> None:
    assert DERIVED_CPI_FORECASTS == EXPECTED_DERIVED_CPI_FORECASTS

