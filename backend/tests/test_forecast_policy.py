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

# Generic-quarterly — та же методология семейства ВВП (multi-window OLS на
# log-diff), применённая к положительным трендовым квартальным source-рядам
# без своего notebook'а: экспорт, импорт, внешний долг. Закрывает запрос
# руководителя «у квартальных тоже должны быть прогнозы» (созвон 2026-06).
# Знаковые квартальные ряды (сальдо торгового баланса, счёт текущих операций)
# СЮДА НЕ ВХОДЯТ: log-diff для них неопределён — у них своя level-diff
# стратегия (см. SIGNED_QUARTERLY_FORECAST_CODES / тождество ниже).
GENERIC_QUARTERLY_FORECAST_CODES = {
    "exports",
    "imports",
    "external-debt",
    # Второй заход руководителя (2026-07): квартальные положительные трендовые
    # source-ряды, ранее стоявшие с forecast_steps=0. Та же multi-window OLS на
    # log-diff, что и у ВВП-семьи.
    "capital-investment",
    "services-exports",
    "services-imports",
    "gdp-investment",
}

# Signed-quarterly — level-diff вариант той же multi-window OLS методологии
# для квартальных ЗНАКОВЫХ рядов (счёт текущих операций), у которых нет
# точного тождества из компонент. current-account прогнозируется напрямую
# по первой разности уровня. trade-balance прогнозируется иначе — как
# тождество exports − imports (derived_from_source, operation="subtract"),
# поэтому он в DERIVED_FROM_SOURCE_FORECAST_CODES, а не здесь.
SIGNED_QUARTERLY_FORECAST_CODES = {
    "current-account",
    # Чистые прямые иностранные инвестиции — знаковый квартальный ряд (может
    # быть отрицательным при оттоке), log-diff неопределён → level-diff OLS.
    "fdi-net",
}

DERIVED_FROM_SOURCE_FORECAST_CODES = {
    # Торговый баланс: прогноз = тождество exports − imports (subtract).
    "trade-balance",
    # Бюджетное сальдо: прогноз = тождество revenue − expenditure (subtract).
    "budget-deficit",
    "gdp-yoy",
    "gdp-qoq",
    "gdp-real-yoy",
    "gdp-real-qoq",
    "gdp-real-annual",
    "gdp-nominal-annual",
    # Средняя зарплата «По годам» (avg-year override, wages-nominal →
    # wages-nominal-annual, созвон «На правки 13» 2026-07-08): тот же паттерн,
    # что gdp-nominal-annual — pipeline period_avg/year поверх месячного прогноза.
    "wages-nominal-annual",
    "housing-yoy-primary",
    "housing-yoy-secondary",
    "housing-qoq-primary",
    "housing-qoq-secondary",
    "housing-annual-primary",
    "housing-annual-secondary",
    "ppi-yoy",
    "ppi-qoq",
    "ppi-mom",
    "ppi-annual",
    "ipi-yoy",
    "wages-yoy",
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
    # Топливо (fuel-ai92/95/diesel) больше НЕ прогнозируется на недельной
    # частоте (профанация < месяца). Прогноз — на месячной средней (monthly_auto)
    # с протяжкой в квартал/год; эти sibling-коды попадают в
    # GENERIC_PROPAGATED_FORECAST_CODES автоматически.
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
    | GENERIC_QUARTERLY_FORECAST_CODES
    | SIGNED_QUARTERLY_FORECAST_CODES
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

# Generic-quarterly индикаторы обязаны указывать forecast_strategy=
# 'generic_quarterly' и forecast_steps>0 (контракт seed_data).
GENERIC_QUARTERLY_STRATEGY_NAMES = {
    code: "generic_quarterly" for code in GENERIC_QUARTERLY_FORECAST_CODES
}

# Signed-quarterly индикаторы обязаны указывать forecast_strategy=
# 'signed_quarterly' и forecast_steps>0 (контракт seed_data).
SIGNED_QUARTERLY_STRATEGY_NAMES = {
    code: "signed_quarterly" for code in SIGNED_QUARTERLY_FORECAST_CODES
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


def test_generic_quarterly_forecasts_have_named_strategy() -> None:
    """Квартальные положительные ряды (экспорт/импорт/внешний долг) обязаны
    указывать forecast_strategy='generic_quarterly', forecast_steps>0 и быть
    квартальными. Знаковые ряды (сальдо/счета) сюда попасть не должны.
    """
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code, strategy_name in GENERIC_QUARTERLY_STRATEGY_NAMES.items():
        assert code in by_code, f"{code} missing from seed_data.INDICATORS"
        ind = by_code[code]
        assert ind.get("frequency") == "quarterly", f"{code} must be quarterly"
        cfg = ind["model_config_json"]
        assert cfg.get("forecast_strategy") == strategy_name, (
            f"{code}: expected forecast_strategy='{strategy_name}', "
            f"got '{cfg.get('forecast_strategy')}'"
        )
        assert int(cfg.get("forecast_steps", 0) or 0) > 0, \
            f"{code} must have forecast_steps>0"
        assert "approved_forecast_values" not in cfg, \
            f"{code}: generic_quarterly recomputes each ETL, no hardcode"


def test_signed_quarterly_forecasts_have_named_strategy() -> None:
    """Квартальные ЗНАКОВЫЕ ряды (счёт текущих операций) обязаны указывать
    forecast_strategy='signed_quarterly', forecast_steps>0 и быть квартальными.
    """
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code, strategy_name in SIGNED_QUARTERLY_STRATEGY_NAMES.items():
        assert code in by_code, f"{code} missing from seed_data.INDICATORS"
        ind = by_code[code]
        assert ind.get("frequency") == "quarterly", f"{code} must be quarterly"
        cfg = ind["model_config_json"]
        assert cfg.get("forecast_strategy") == strategy_name, (
            f"{code}: expected forecast_strategy='{strategy_name}', "
            f"got '{cfg.get('forecast_strategy')}'"
        )
        assert int(cfg.get("forecast_steps", 0) or 0) > 0, \
            f"{code} must have forecast_steps>0"
        assert "approved_forecast_values" not in cfg, \
            f"{code}: signed_quarterly recomputes each ETL, no hardcode"


def test_trade_balance_forecast_is_identity() -> None:
    """trade-balance прогнозируется как тождество exports − imports."""
    by_code = {ind["code"]: ind for ind in INDICATORS}
    cfg = by_code["trade-balance"]["model_config_json"]
    assert cfg.get("forecast_strategy") == "derived_from_source"
    derived = cfg.get("derived_forecast") or {}
    assert derived.get("operation") == "subtract"
    assert derived.get("source_code") == "exports"
    assert derived.get("source_code_2") == "imports"
    assert int(cfg.get("forecast_steps", 0) or 0) > 0


def test_budget_deficit_forecast_is_identity() -> None:
    """budget-deficit прогнозируется как тождество revenue − expenditure."""
    by_code = {ind["code"]: ind for ind in INDICATORS}
    cfg = by_code["budget-deficit"]["model_config_json"]
    assert cfg.get("forecast_strategy") == "derived_from_source"
    derived = cfg.get("derived_forecast") or {}
    assert derived.get("operation") == "subtract"
    assert derived.get("source_code") == "budget-revenue"
    assert derived.get("source_code_2") == "budget-expenditure"
    assert int(cfg.get("forecast_steps", 0) or 0) > 0
    # Не должен остаться в независимом monthly_auto — иначе сальдо ≠ R−E.
    assert "budget-deficit" not in MONTHLY_AUTO_CODES


def test_wages_real_yoy_has_derived_forecast() -> None:
    """YoY реальной зарплаты протягивается из monthly_auto базы."""
    by_code = {ind["code"]: ind for ind in INDICATORS}
    base = by_code["wages-real"]["model_config_json"]
    assert base.get("forecast_strategy") == "monthly_auto"
    assert base.get("forecast_transform") == "absolute"
    yoy = by_code["wages-real-yoy"]["model_config_json"]
    assert yoy.get("forecast_strategy") == "derived_from_source"
    derived = yoy.get("derived_forecast") or {}
    assert derived.get("source_code") == "wages-real"
    assert derived.get("operation") == "pipeline"
    assert int(yoy.get("forecast_steps", 0) or 0) > 0


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

