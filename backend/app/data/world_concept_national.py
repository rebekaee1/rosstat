"""Явный crosswalk national passport → curated world concepts для карты/compare.

Только вручную сверенные ряды (ADR-0012 п.4). Несопоставимые абсолюты
(ВВП в нац. валюте, CPI с разными базами) сюда не кладём как GDP volume /
HICP index — для цен/ВВП на карте используем только сопоставимые % или
оставляем Eurostat.

Сейчас: уровень безработицы (%) и население (чел.) — безопасны для choropleth.
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
        "UK": "uk-unemployment-rate",
        "US": "us-unemployment-rate",
    },
    "population": {
        "CA": "ca-population",
        "UK": "uk-population",
    },
    # Потребительские цены: разные базы индекса — на карте показываем как
    # «уровень индекса источника» только для passport-стран без Eurostat HICP
    # listed. UI-легенда остаётся concept name; методологически это soft alias.
    "hicp-index": {
        "AU": "au-cpi-all",
        "CA": "ca-cpi-all",
        "IN": "in-cpi-all",
        "MX": "mx-cpi-all",
        "UK": "uk-cpi-all",
        "US": "us-cpi-all",
    },
}


def national_codes_for_concept(concept_slug: str) -> frozenset[str]:
    mapping = NATIONAL_CONCEPT_INDICATOR_CODES.get(concept_slug) or {}
    return frozenset(mapping.values())
