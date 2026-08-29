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
    # Движок hicp всегда считает YoY от уровня индекса (`transform_yoy`).
    # CN `cn-cpi-all` — уже индекс «тот же месяц прошлого года = 100», не уровень.
    # BR: `br-cpi-ipca` — % к предыдущему месяцу; `br-cpi-ipca-yoy` — уже YoY %.
    # JP — национального CPI-ряда в world_indicators нет, пока e-Stat
    # не отдал ряд (`jp-cpi-all`); код в crosswalk, чтобы карта подхватила
    # его сразу после ingest. KR — то же для ECOS (`kr-cpi-all`).
    "hicp-index": {
        "AU": "au-cpi-all",
        "CA": "ca-cpi-all",
        "IN": "in-cpi-all",
        "JP": "jp-cpi-all",
        "KR": "kr-cpi-all",
        "MX": "mx-cpi-all",
        "UK": "uk-cpi-all",
        "US": "us-cpi-all",
    },
}


def national_codes_for_concept(concept_slug: str) -> frozenset[str]:
    mapping = NATIONAL_CONCEPT_INDICATOR_CODES.get(concept_slug) or {}
    return frozenset(mapping.values())
