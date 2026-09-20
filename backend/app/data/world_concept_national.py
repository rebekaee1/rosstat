"""Явный crosswalk national passport → curated world concepts для карты/compare.

Только вручную сверенные ряды (ADR-0012 п.4). Несопоставимые абсолюты
(ВВП в нац. валюте) сюда не кладём. Национальные индексы цен с разными
базами допустимы только потому, что карта и рейтинг цен считают изменение
за год в процентах — уровень индекса между странами не сравнивается.
"""

from __future__ import annotations

from typing import Any, Sequence

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
    # Уровень экономической активности: у AU/UK/US национальное обследование
    # рабочей силы публикует долю экономически активного населения
    # (participation rate) в процентах — тот же смысл, что у Eurostat-среза
    # lfsi_emp_a ACT; возрастная база национальная (AU: 15+, UK/US: 16+).
    "activity-rate": {
        "AU": "au-participation-rate",
        "UK": "uk-participation-rate",
        "US": "us-labor-force-participation",
    },
    # 10-летняя доходность казначейских облигаций США — тот же смысл, что
    # Eurostat irt_lt_mcby (критерий конвергенции, ~10 лет).
    "long-term-interest-rate": {
        "US": "us-treasury-10y",
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


_CONCEPT_BY_NATIONAL_CODE: dict[str, str] = {
    code: slug
    for slug, mapping in NATIONAL_CONCEPT_INDICATOR_CODES.items()
    for code in mapping.values()
}


def concept_slug_for_national_code(indicator_code: str) -> str | None:
    """Концепт, к которому national-ряд привязан crosswalk'ом, или None.

    Обратный индекс к ``NATIONAL_CONCEPT_INDICATOR_CODES``: карточке
    национального ряда (безработица США, CPI Канады) он даёт блок «Сравнение
    стран» — без него `concept_for_indicator` видит только Eurostat/IMF-срезы.
    """
    return _CONCEPT_BY_NATIONAL_CODE.get(str(indicator_code or ""))


def hicp_national_yoy_kind(indicator_code: str) -> str:
    """Как считать YoY для национального (или уже-готового) ряда цен."""
    return HICP_NATIONAL_YOY_KIND.get(indicator_code) or HICP_YOY_KIND_LEVEL


def filter_weo_shadowed_from_country_listing(
    indicators: Sequence[Any],
    country_code: str,
) -> list[Any]:
    """Убрать WEO-карточки концепта, если у страны уже есть national/Eurostat ряд.

    Ряд МВФ остаётся в БД и доступен по URL, в рейтинге и на карте. Из каталога
    страны его не показываем, чтобы не дублировать месячный национальный ряд
    годовой оценкой фонда (безработица, население, ИПЦ).
    """
    from app.data.world_concepts import concept_for_indicator

    rows = list(indicators)
    if not rows:
        return rows
    cc = (country_code or "").strip().upper()
    listed_codes = {str(getattr(ind, "code", "") or "") for ind in rows}

    covered: set[str] = set()
    for slug, mapping in NATIONAL_CONCEPT_INDICATOR_CODES.items():
        national_code = mapping.get(cc)
        if national_code and national_code in listed_codes:
            covered.add(slug)

    for ind in rows:
        provider = str(getattr(ind, "provider", "") or "").strip().lower()
        if provider == "imf":
            continue
        concept = concept_for_indicator(ind)
        if concept is not None:
            covered.add(concept.slug)

    if not covered:
        return rows

    out: list[Any] = []
    for ind in rows:
        provider = str(getattr(ind, "provider", "") or "").strip().lower()
        if provider == "imf":
            concept = concept_for_indicator(ind)
            if concept is not None and concept.slug in covered:
                continue
        out.append(ind)
    return out
