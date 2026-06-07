"""Forecast enablement policy.

Only forecasts explicitly approved by Nikita's notebooks/reviews should be
enabled. Other indicators may have data and charts, but their forecast toggle
must stay off until a forecast file/spec is approved.
"""

from __future__ import annotations

from seed_data import (
    INDICATORS,
    MONTHLY_AUTO_FORECAST_CODES,
    _generated_sibling_codes,
)
from app.api.forecasts import DERIVED_CPI_FORECASTS
from app.services.forecast_pipeline import CPI_DERIVED_FORECAST_TARGETS


# Прогноз индикатора может быть включён тремя способами:
#  (1) Approved-direct — точки прогноза заданы вручную в model_config
#      из блокнота Никиты (полное соответствие «точь-в-точь»). Используется
#      для CPI и PPI, где каноничные значения важнее автоматического пересчёта.
#  (2) Live-SARIMA — стратегия пересчитывает прогноз byte-exact согласно
#      ноутбуку Никиты на каждом ETL. Гарантирует, что после публикации
#      новых фактов прогноз автоматически обновляется без правки notebook'а.
#      Используется для ВВП (номинальный/реальный) и цен на жильё.
#  (3) Derived-from-source — стратегия `derived_from_source` строит прогноз
#      математически от прогноза индикатора-источника.
APPROVED_DIRECT_FORECAST_CODES = {
    "cpi",
    "cpi-food",
    "cpi-nonfood",
    "cpi-services",
}

# Live SARIMA modeled on the indicator's own series (1:1 port of Никита's
# notebook). 2026-05: housing-price-*, gdp-nominal, gdp-real, gdp-consumption,
# gdp-government, ppi переведены сюда из APPROVED_DIRECT — прогноз
# пересчитывается автоматически на свежих данных, а не лежит хардкодом
# до следующего notebook-релиза. APPROVED_DIRECT теперь остался только
# для CPI семьи, где блокнот Никиты — единственный источник правды
# по неавторегрессионной декомпозиции (food/nonfood/services).
LIVE_SARIMA_FORECAST_CODES = {
    "gdp-nominal",
    "gdp-real",
    "gdp-consumption",
    "gdp-government",
    "housing-price-primary",
    "housing-price-secondary",
    "ppi",
}

DERIVED_FROM_SOURCE_FORECAST_CODES = {
    "gdp-yoy",
    "gdp-qoq",
    "gdp-real-yoy",
    "gdp-real-qoq",
    "gdp-real-annual",
    "gdp-nominal-annual",
    "housing-yoy-primary",
    "housing-yoy-secondary",
    "housing-qoq-primary",
    "housing-qoq-secondary",
    "ppi-yoy",
    "ppi-annual",
    "inflation-annual",
    "cpi-food-annual",
    "cpi-nonfood-annual",
    "cpi-services-annual",
    "cpi-yoy",
    "cpi-food-yoy",
    "cpi-nonfood-yoy",
    "cpi-services-yoy",
    "cpi-qoq",
    "cpi-food-qoq",
    "cpi-nonfood-qoq",
    "cpi-services-qoq",
    "cpi-period-weekly",
    "cpi-food-period-weekly",
    "cpi-nonfood-period-weekly",
    "cpi-services-period-weekly",
    "cpi-period-monthly",
    "cpi-food-period-monthly",
    "cpi-nonfood-period-monthly",
    "cpi-services-period-monthly",
}

# Generic OLS multi-window — fallback модель для индикаторов без
# именованного блокнота Никиты. Используется только там, где данных
# хватает (>=36 точек) и форма ряда совместима с cpi_index/percentage transform.
#
# Недельная инфляция: короткий OLS-горизонт (8 нед.) для UI «Рост за период /
# Недельная» и каскада «Месячная» через derived_from_source.
GENERIC_OLS_FORECAST_CODES: set[str] = {
    "inflation-weekly",
    "inflation-weekly-food",
    "inflation-weekly-nonfood",
    "inflation-weekly-services",
}

# Monthly-Auto — единый алгоритм месячного прогноза руководителя
# (Прогноз_месячных_данных.ipynb, июнь 2026): ADF-автотрансформ +
# multi-window OLS. Включён для всех месячных source-рядов, ранее
# стоявших с forecast_steps=0. Источник списка — seed_data.
MONTHLY_AUTO_CODES = set(MONTHLY_AUTO_FORECAST_CODES)

# Generic-propagated — view-mode sibling-агрегаты (квартал/год/приросты/индекс),
# сгенерированные из конфига view_model_families, чей базовый ряд forecastable:
# прогноз протягивается через generic-pipeline (derived_from_source,
# operation="pipeline"). Берём фактически сгенерированные siblings из seed
# (legacy-коды вроде exports-yoy сидятся отдельно и сюда не попадают).
_BY_CODE_ALL = {ind["code"]: ind for ind in INDICATORS}
GENERIC_PROPAGATED_FORECAST_CODES = {
    code for code in _generated_sibling_codes
    if int((_BY_CODE_ALL[code].get("model_config_json") or {}).get("forecast_steps", 0) or 0) > 0
}

ALL_FORECAST_CODES = (
    APPROVED_DIRECT_FORECAST_CODES
    | LIVE_SARIMA_FORECAST_CODES
    | DERIVED_FROM_SOURCE_FORECAST_CODES
    | GENERIC_OLS_FORECAST_CODES
    | MONTHLY_AUTO_CODES
    | GENERIC_PROPAGATED_FORECAST_CODES
)

APPROVED_NOTEBOOK_CODES: dict[str, str] = {}

# Live SARIMA индикаторы должны иметь forecast_strategy с именем
# конкретной auto-стратегии (не approved). Это контракт seed_data.
LIVE_SARIMA_STRATEGY_NAMES = {
    "gdp-nominal": "gdp_nominal_quarterly",
    "gdp-real": "gdp_real_quarterly",
    "gdp-consumption": "gdp_consumption_quarterly",
    "gdp-government": "gdp_government_quarterly",
    "housing-price-primary": "housing_quarterly",
    "housing-price-secondary": "housing_quarterly",
    "ppi": "ppi_monthly",
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


def test_monthly_auto_forecasts_have_named_strategy() -> None:
    """Месячные показатели руководителя обязаны указывать
    forecast_strategy='monthly_auto' и forecast_steps>0 (контракт seed_data).
    """
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code in MONTHLY_AUTO_CODES:
        assert code in by_code, f"{code} missing from seed_data.INDICATORS"
        cfg = by_code[code]["model_config_json"]
        assert cfg.get("forecast_strategy") == "monthly_auto", (
            f"{code}: expected forecast_strategy='monthly_auto', "
            f"got '{cfg.get('forecast_strategy')}'"
        )
        assert int(cfg.get("forecast_steps", 0) or 0) > 0, \
            f"{code} must have forecast_steps>0"


def test_approved_notebook_forecasts_are_explicit_values() -> None:
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code, model_name in APPROVED_NOTEBOOK_CODES.items():
        cfg = by_code[code]["model_config_json"]
        assert cfg["forecast_model_name"] == model_name
        assert cfg["approved_forecast_values"]


def test_live_sarima_forecasts_have_named_strategy() -> None:
    """Live-SARIMA индикаторы обязаны указывать forecast_strategy с
    именем конкретной auto-стратегии (не legacy approved/OLS fallback).
    """
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code, strategy_name in LIVE_SARIMA_STRATEGY_NAMES.items():
        cfg = by_code[code]["model_config_json"]
        assert cfg.get("forecast_strategy") == strategy_name, (
            f"{code}: expected forecast_strategy='{strategy_name}', "
            f"got '{cfg.get('forecast_strategy')}'"
        )
        assert "approved_forecast_values" not in cfg, (
            f"{code}: live-SARIMA must not have approved_forecast_values "
            "(hardcode forbidden — model recomputes each ETL)"
        )


def test_all_derived_cpi_forecasts_are_api_whitelisted() -> None:
    assert DERIVED_CPI_FORECASTS == EXPECTED_DERIVED_CPI_FORECASTS
    assert CPI_DERIVED_FORECAST_TARGETS == EXPECTED_DERIVED_CPI_FORECASTS


# 8-индикатор контракт по семьям ВВП: оба «флагмана» (gdp-nominal, gdp-real)
# и шесть производных (yoy/qoq/annual для каждой семьи) обязаны иметь
# запитанный прогноз. Это контракт, защищающий от регрессий вида
# «после деплоя у одной из вкладок на /indicator/gdp-nominal пропал прогноз».
GDP_FAMILY_CODES = {
    "gdp-nominal",
    "gdp-yoy",
    "gdp-qoq",
    "gdp-nominal-annual",
    "gdp-real",
    "gdp-real-yoy",
    "gdp-real-qoq",
    "gdp-real-annual",
}


def test_all_gdp_family_indicators_have_active_forecast_config() -> None:
    """Каждый из 8 индикаторов GDP должен попасть в одну из forecast-веток.

    Это структурный тест: smoke API-проверка делается отдельно (см. README
    раздел про деплой). Здесь мы фиксируем, что seed_data корректно
    конфигурирует прогноз для всей семьи — иначе после `--forecast-only`
    retrain какой-то индикатор окажется без прогноза, и UI-вкладка пуста.
    """
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code in GDP_FAMILY_CODES:
        assert code in by_code, f"{code} missing from seed_data.INDICATORS"
        ind = by_code[code]
        assert ind.get("is_active"), f"{code} must be is_active=True"
        cfg = ind.get("model_config_json") or {}
        in_any_track = (
            code in APPROVED_DIRECT_FORECAST_CODES
            or code in LIVE_SARIMA_FORECAST_CODES
            or code in DERIVED_FROM_SOURCE_FORECAST_CODES
            or code in GENERIC_OLS_FORECAST_CODES
        )
        assert in_any_track, (
            f"{code} not registered in any forecast track "
            "(approved/live-sarima/derived/generic-ols)"
        )
        steps = int(cfg.get("forecast_steps", 0) or 0)
        assert steps > 0, f"{code} must have forecast_steps>0 (got {steps})"

