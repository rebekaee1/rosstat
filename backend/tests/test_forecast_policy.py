"""Forecast enablement policy.

Only forecasts explicitly approved by Nikita's notebooks/reviews should be
enabled. Other indicators may have data and charts, but their forecast toggle
must stay off until a forecast file/spec is approved.
"""

from __future__ import annotations

from seed_data import INDICATORS
from app.api.forecasts import DERIVED_CPI_FORECASTS
from app.services.forecast_pipeline import CPI_DERIVED_FORECAST_TARGETS


# Прогноз индикатора может быть включён двумя способами:
#  (1) Approved-direct — точки прогноза заданы вручную в model_config
#      из блокнота Никиты (полное соответствие «точь-в-точь»).
#  (2) Derived-from-source — стратегия `derived_from_source` строит
#      прогноз математически от прогноза индикатора-источника.
#  (3) Live-models — CPI семья, где прогноз пересчитывается каждый раз.
APPROVED_DIRECT_FORECAST_CODES = {
    "cpi",
    "cpi-food",
    "cpi-nonfood",
    "cpi-services",
    "ppi",
    "gdp-nominal",
    "housing-price-primary",
    "housing-price-secondary",
}

DERIVED_FROM_SOURCE_FORECAST_CODES = {
    "gdp-yoy",
    "gdp-qoq",
    "gdp-real",
    "gdp-real-annual",
    "ppi-yoy",
    "ppi-annual",
    "inflation-annual",
    "cpi-food-annual",
    "cpi-nonfood-annual",
    "cpi-services-annual",
}

# Generic OLS multi-window — fallback модель для индикаторов без
# именованного блокнота Никиты. Используется только там, где данных
# хватает (>=36 точек) и форма ряда совместима с cpi_index/percentage transform.
#
# 2026-05-06: `inflation-weekly` исключён из списка по решению НА — Росстат
# публикует только за прошлую неделю с лагом, ранние дни новой недели не
# дают достаточного сигнала для обоснованного 8-недельного прогноза.
# В seed_data forecast_steps=0 → retrain очищает старые ряды,
# API возвращает forecast=None.
GENERIC_OLS_FORECAST_CODES: set[str] = set()

ALL_FORECAST_CODES = (
    APPROVED_DIRECT_FORECAST_CODES
    | DERIVED_FROM_SOURCE_FORECAST_CODES
    | GENERIC_OLS_FORECAST_CODES
)

APPROVED_NOTEBOOK_CODES = {
    "ppi": "Approved-PPI-Notebook",
    "gdp-nominal": "Approved-GDP-Nominal-Notebook",
    "housing-price-primary": "Approved-Housing-Primary-Notebook",
}

EXPECTED_DERIVED_CPI_FORECASTS = {
    "inflation-quarterly",
    "cpi-food-quarterly",
    "cpi-nonfood-quarterly",
    "cpi-services-quarterly",
}


def test_only_approved_or_derived_forecasts_are_enabled() -> None:
    enabled: set[str] = set()
    for ind in INDICATORS:
        if not ind.get("is_active"):
            continue
        cfg = ind.get("model_config_json") or {}
        forecast_steps = int(cfg.get("forecast_steps", 0) or 0)
        if forecast_steps > 0:
            enabled.add(ind["code"])

    assert enabled == ALL_FORECAST_CODES


def test_derived_forecasts_have_strategy_and_source() -> None:
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code in DERIVED_FROM_SOURCE_FORECAST_CODES:
        cfg = by_code[code]["model_config_json"]
        assert cfg.get("forecast_strategy") == "derived_from_source", \
            f"{code} must have forecast_strategy=derived_from_source"
        derived = cfg.get("derived_forecast") or {}
        assert derived.get("source_code"), f"{code} must have derived_forecast.source_code"
        assert derived.get("operation"), f"{code} must have derived_forecast.operation"


def test_approved_notebook_forecasts_are_explicit_values() -> None:
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code, model_name in APPROVED_NOTEBOOK_CODES.items():
        cfg = by_code[code]["model_config_json"]
        assert cfg["forecast_model_name"] == model_name
        assert cfg["approved_forecast_values"]


def test_all_derived_cpi_forecasts_are_api_whitelisted() -> None:
    assert DERIVED_CPI_FORECASTS == EXPECTED_DERIVED_CPI_FORECASTS
    assert CPI_DERIVED_FORECAST_TARGETS == EXPECTED_DERIVED_CPI_FORECASTS

