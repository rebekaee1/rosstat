"""Явный crosswalk national passport → curated world concepts для карты/compare.

Только вручную сверенные ряды (ADR-0012 п.4). Несопоставимые абсолюты
(ВВП в нац. валюте) сюда не кладём. Национальные индексы цен с разными
базами допустимы только потому, что карта и рейтинг цен считают изменение
за год в процентах — уровень индекса между странами не сравнивается.
"""

from __future__ import annotations

# concept_slug → { ISO alpha-2 → world_indicators.code }
NATIONAL_CONCEPT_INDICATOR_CODES: dict[str, dict[str, str]] = {
    "unemployment-rate": {
        "AU": "au-unemployment-rate",
        "BR": "br-unemployment-rate",
        "CA": "ca-unemployment-rate",
        "CN": "cn-urban-unemployment",
        "IN": "in-unemployment-rate",
        "JP": "jp-unemployment-rate",
        "KR": "kr-unemployment-rate",
        "UK": "uk-unemployment-rate",
        "US": "us-unemployment-rate",
    },
    "population": {
        "AU": "au-population",
        "CA": "ca-population",
        "UK": "uk-population",
        "US": "us-population-census",
        "BR": "br-population-ibge",
    },
    # Уровень экономической активности: у AU/UK национальное обследование
    # рабочей силы публикует долю экономически активного населения
    # (participation rate) в процентах — тот же смысл, что у Eurostat-среза
    # lfsi_emp_a ACT; возрастная база национальная (AU: 15+, UK: 16+).
    "activity-rate": {
        "AU": "au-participation-rate",
        "UK": "uk-participation-rate",
    },
    # Потребительские цены: национальные индексы с разными базами.
    # Карта/рейтинг отдают изменение за год (%), не уровень индекса.
    # По умолчанию hicp считает YoY от уровня индекса (`transform_yoy`).
    # CN `cn-cpi-all` — индекс «тот же месяц прошлого года = 100»: YoY % = значение − 100.
    # BR: `br-cpi-ipca` — % м/м, в рейтинг не берём; `br-cpi-ipca-yoy` — уже YoY %.
    # JP — национального CPI-ряда нет, пока нет `RUSTATS_ESTAT_APP_ID`;
    # код в crosswalk, чтобы карта подхватила ряд сразу после ingest. KR — то же
    # для ECOS (`RUSTATS_ECOS_API_KEY`). Пока ключей нет, дыру закрывает
    # годовая оценка МВФ (PCPIPCH) через концепт, не через этот словарь.
    "hicp-index": {
        "AU": "au-cpi-all",
        "BR": "br-cpi-ipca-yoy",
        "CA": "ca-cpi-all",
        "CN": "cn-cpi-all",
        "IN": "in-cpi-all",
        "JP": "jp-cpi-all",
        "KR": "kr-cpi-all",
        "MX": "mx-cpi-all",
        "UK": "uk-cpi-all",
        "US": "us-cpi-all",
    },
}

# Как национальный ряд hicp переводится в «изменение за год, %» на карте.
# Нет записи — уровень индекса, `transform_yoy`.
HICP_NATIONAL_YOY_KIND: dict[str, str] = {
    "cn-cpi-all": "index_minus_100",
    "br-cpi-ipca-yoy": "passthrough",
}

HICP_YOY_KIND_LEVEL = "level"
HICP_YOY_KIND_INDEX_MINUS_100 = "index_minus_100"
HICP_YOY_KIND_PASSTHROUGH = "passthrough"
WEO_INFLATION_CODE = "PCPIPCH"


def national_codes_for_concept(concept_slug: str) -> frozenset[str]:
    mapping = NATIONAL_CONCEPT_INDICATOR_CODES.get(concept_slug) or {}
    return frozenset(mapping.values())


def hicp_national_yoy_kind(indicator_code: str) -> str:
    """Как считать YoY для национального (или уже-готового) ряда цен."""
    return HICP_NATIONAL_YOY_KIND.get(indicator_code) or HICP_YOY_KIND_LEVEL
