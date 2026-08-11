"""Курируемые межстрановые понятия для world блока.

Это не автоклассификатор и не публичный каталог. Понятие связывает только
строго эквивалентные Eurostat slices; карточечный `card_key` остаётся
внутристрановым механизмом частот.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.data.eurostat_listing import measure_class, normalize_age_code, normalize_sex_code


@dataclass(frozen=True)
class WorldConcept:
    slug: str
    name_ru: str
    unit_ru: str
    dataset_ids: frozenset[str]
    measure: str
    required_slice: Mapping[str, str]
    frequency_policy: str = "official_only"
    aggregation_policy: str | None = None
    enabled_surfaces: frozenset[str] = frozenset({"resolve", "compare"})
    # Provider aliases одного экономического понятия задаются только вручную
    # после методологической сверки. `dataset_ids` — Eurostat legacy shorthand.
    provider_dataset_ids: Mapping[str, frozenset[str]] | None = None


WORLD_CONCEPTS: tuple[WorldConcept, ...] = (
    WorldConcept(
        slug="hicp-index",
        name_ru="Гармонизированный индекс потребительских цен",
        unit_ru="индекс 2015=100",
        dataset_ids=frozenset({"prc_hicp_midx"}),
        measure="I15",
        required_slice={"coicop": "CP00"},
        frequency_policy="official_then_calculated",
        aggregation_policy="mean",
    ),
    WorldConcept(
        slug="unemployment-rate",
        name_ru="Уровень безработицы",
        unit_ru="% экономически активного населения",
        dataset_ids=frozenset({"une_rt_m"}),
        measure="PC_ACT",
        required_slice={"age": "TOTAL", "sex": "T", "s_adj": "SA"},
        frequency_policy="official_then_calculated",
        aggregation_policy="mean",
    ),
    WorldConcept(
        slug="gdp-volume-quarterly",
        name_ru="Валовой внутренний продукт в постоянных ценах, квартал",
        unit_ru="млн евро в постоянных ценах",
        dataset_ids=frozenset({"namq_10_gdp"}),
        measure="CLV15_MEUR",
        required_slice={"na_item": "B1GQ", "s_adj": "SCA"},
    ),
    WorldConcept(
        slug="gdp-volume-annual",
        name_ru="Валовой внутренний продукт в постоянных ценах, год",
        unit_ru="млн евро в постоянных ценах",
        dataset_ids=frozenset({"nama_10_gdp"}),
        measure="CLV15_MEUR",
        required_slice={"na_item": "B1GQ"},
        frequency_policy="official_only",
    ),
    WorldConcept(
        slug="budget-balance-gdp",
        name_ru="Сальдо бюджета сектора государственного управления",
        unit_ru="% ВВП",
        dataset_ids=frozenset({"gov_10dd_edpt1"}),
        measure="PC_GDP",
        required_slice={"na_item": "B9", "sector": "S13"},
        frequency_policy="official_only",
    ),
    WorldConcept(
        slug="population",
        name_ru="Численность населения",
        unit_ru="человек",
        dataset_ids=frozenset({"demo_pjan"}),
        measure="NR",
        required_slice={"age": "TOTAL", "sex": "T"},
        frequency_policy="official_only",
    ),
)

CONCEPT_BY_SLUG = {concept.slug: concept for concept in WORLD_CONCEPTS}
_NON_SEMANTIC_SLICE_KEYS = frozenset({"freq", "unit", "time", "geo"})


def concept_matches_indicator(concept: WorldConcept, indicator) -> bool:
    """Строгий match dataset + measure + pinned dimensions; никогда по имени."""
    provider = str(getattr(indicator, "provider", "eurostat") or "").lower()
    allowed_datasets = (
        (concept.provider_dataset_ids or {}).get(provider, frozenset())
        if concept.provider_dataset_ids is not None
        else concept.dataset_ids if provider == "eurostat" else frozenset()
    )
    if (indicator.dataset_id or "").lower() not in allowed_datasets:
        return False
    if measure_class(indicator.unit, indicator.unit_ru) != concept.measure:
        return False
    slice_json = indicator.slice_json or {}
    configured_keys = {key.lower() for key in concept.required_slice}
    for key, raw in slice_json.items():
        normalized_key = str(key).strip().lower()
        if not normalized_key or normalized_key in _NON_SEMANTIC_SLICE_KEYS:
            continue
        if normalized_key not in configured_keys and str(raw).strip():
            return False
    for key, expected in concept.required_slice.items():
        actual = slice_json.get(key)
        if key == "age":
            actual = normalize_age_code(actual)
            expected = normalize_age_code(expected)
        elif key == "sex":
            actual = normalize_sex_code(actual)
            expected = normalize_sex_code(expected)
        elif str(actual or "").strip().upper() != expected.upper():
            return False
        if key in {"age", "sex"} and actual != expected:
            return False
    return True


def concept_for_indicator(indicator) -> WorldConcept | None:
    """Возвращает единственный контракт или None; пересечение — ошибка реестра."""
    matches = [concept for concept in WORLD_CONCEPTS if concept_matches_indicator(concept, indicator)]
    if len(matches) > 1:
        slugs = ", ".join(concept.slug for concept in matches)
        raise ValueError(f"World indicator matches multiple concepts: {slugs}")
    return matches[0] if matches else None
