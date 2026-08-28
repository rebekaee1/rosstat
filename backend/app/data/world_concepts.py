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
    # Pinned dimensions per provider: если у провайдера свой набор измерений
    # среза (IMF weo_code vs Eurostat na_item/sector), матч идёт строго по
    # набору своего провайдера вместо required_slice.
    provider_required_slices: Mapping[str, Mapping[str, str]] | None = None
    name_en: str = ""
    unit_en: str = ""


_RATING_SURFACES = frozenset({"resolve", "compare", "rating"})

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
        enabled_surfaces=_RATING_SURFACES,
        name_en="Harmonised index of consumer prices",
        unit_en="index 2015=100",
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
        enabled_surfaces=_RATING_SURFACES,
        name_en="Unemployment rate",
        unit_en="% of the labour force",
    ),
    # Единицы национальные (евро, доллары, юани и т.п.) — рейтинг ждёт
    # пересчёта в доллары США; поверхность rating не включаем.
    WorldConcept(
        slug="gdp-volume-quarterly",
        name_ru="Валовой внутренний продукт в постоянных ценах, квартал",
        unit_ru="в постоянных ценах 2015 года, млн евро",
        dataset_ids=frozenset({"namq_10_gdp"}),
        measure="CLV15_MEUR",
        required_slice={"na_item": "B1GQ", "s_adj": "SCA"},
        name_en="Gross domestic product at constant prices, quarterly",
        unit_en="chain-linked volumes, 2015, million euro",
    ),
    # Единицы национальные — рейтинг ждёт пересчёта в доллары США.
    WorldConcept(
        slug="gdp-volume-annual",
        name_ru="Валовой внутренний продукт в постоянных ценах, год",
        unit_ru="в постоянных ценах 2015 года, млн евро",
        dataset_ids=frozenset({"nama_10_gdp"}),
        measure="CLV15_MEUR",
        required_slice={"na_item": "B1GQ"},
        frequency_policy="official_only",
        name_en="Gross domestic product at constant prices, annual",
        unit_en="chain-linked volumes, 2015, million euro",
    ),
    WorldConcept(
        slug="budget-balance-gdp",
        name_ru="Сальдо бюджета сектора государственного управления",
        unit_ru="% ВВП",
        dataset_ids=frozenset({"gov_10dd_edpt1"}),
        measure="PC_GDP",
        required_slice={"na_item": "B9", "sector": "S13"},
        frequency_policy="official_only",
        enabled_surfaces=_RATING_SURFACES,
        provider_dataset_ids={
            "eurostat": frozenset({"gov_10dd_edpt1"}),
            "imf": frozenset({"weo"}),
        },
        # Pinned dimensions per provider: Eurostat и IMF описывают срез
        # разными измерениями — матчим строго по набору своего провайдера.
        provider_required_slices={
            "imf": {"weo_code": "GGXCNL_NGDP"},
        },
        name_en="General government budget balance",
        unit_en="% of GDP",
    ),
    WorldConcept(
        slug="government-debt-gdp",
        name_ru="Государственный долг сектора государственного управления",
        unit_ru="% ВВП",
        dataset_ids=frozenset({"gov_10dd_edpt1"}),
        measure="PC_GDP",
        required_slice={"na_item": "GD", "sector": "S13"},
        frequency_policy="official_only",
        enabled_surfaces=_RATING_SURFACES,
        # Eurostat — долг по национальным определениям стран с полным
        # покрытием направления государственных финансов; IMF — оценка по
        # широкой классификации фонда для остальных. Разные меры одного
        # понятия, единица одна (% ВВП); смешение методологий оговаривается
        # в публичной методологии рейтинга.
        provider_dataset_ids={
            "eurostat": frozenset({"gov_10dd_edpt1"}),
            "imf": frozenset({"weo"}),
        },
        # Pinned dimensions per provider: Eurostat описывает срез измерениями
        # na_item/sector, IMF — своим кодом серии.
        provider_required_slices={
            "imf": {"weo_code": "GGXWDG_NGDP"},
        },
        name_en="General government gross debt",
        unit_en="% of GDP",
    ),
    WorldConcept(
        slug="population",
        name_ru="Численность населения",
        unit_ru="человек",
        dataset_ids=frozenset({"demo_pjan"}),
        measure="NR",
        required_slice={"age": "TOTAL", "sex": "T"},
        frequency_policy="official_only",
        enabled_surfaces=_RATING_SURFACES,
        name_en="Population",
        unit_en="persons",
    ),
    # Доходность длинных госбумаг по критерию конвергенции — одна единица (%).
    WorldConcept(
        slug="long-term-interest-rate",
        name_ru="Доходность долгосрочных государственных облигаций",
        unit_ru="%",
        dataset_ids=frozenset({"irt_lt_mcby_m"}),
        measure="PC",
        required_slice={"int_rt": "MCBY"},
        frequency_policy="official_then_calculated",
        aggregation_policy="mean",
        enabled_surfaces=_RATING_SURFACES,
        name_en="Long-term government bond yield",
        unit_en="%",
    ),
    # Уровень экономической активности 15–64 лет — доля населения, %.
    WorldConcept(
        slug="activity-rate",
        name_ru="Уровень экономической активности населения",
        unit_ru="% населения",
        dataset_ids=frozenset({"lfsi_emp_a"}),
        measure="PC_POP",
        required_slice={"age": "Y15-64", "sex": "T", "indic_em": "ACT"},
        frequency_policy="official_only",
        enabled_surfaces=_RATING_SURFACES,
        name_en="Economic activity rate",
        unit_en="% of population",
    ),
    # ВВП на душу относительно среднего по ЕС — относительный индекс, не валюта.
    WorldConcept(
        slug="gdp-per-capita-eu",
        name_ru="ВВП на душу населения относительно среднего по ЕС",
        unit_ru="% от среднего по ЕС на душу населения",
        dataset_ids=frozenset({"nama_10_pc"}),
        measure="PC_POP",
        required_slice={"na_item": "B1GQ"},
        frequency_policy="official_only",
        enabled_surfaces=_RATING_SURFACES,
        name_en="GDP per capita relative to the EU average",
        unit_en="% of EU average per capita",
    ),
    WorldConcept(
        slug="gdp-usd",
        name_ru="Валовой внутренний продукт в текущих ценах",
        unit_ru="млрд $",
        dataset_ids=frozenset(),
        measure="BN_USD",
        required_slice={"weo_code": "NGDPD"},
        frequency_policy="official_only",
        enabled_surfaces=_RATING_SURFACES,
        provider_dataset_ids={"imf": frozenset({"weo"})},
        name_en="Gross domestic product at current prices",
        unit_en="billion $",
    ),
    WorldConcept(
        slug="gdp-per-capita-usd",
        name_ru="Валовой внутренний продукт на душу населения в текущих ценах",
        unit_ru="$ на человека",
        dataset_ids=frozenset(),
        measure="USD_PC",
        required_slice={"weo_code": "NGDPDPC"},
        frequency_policy="official_only",
        enabled_surfaces=_RATING_SURFACES,
        provider_dataset_ids={"imf": frozenset({"weo"})},
        name_en="Gross domestic product per capita at current prices",
        unit_en="$ per person",
    ),
)


def concept_public_name(concept: WorldConcept, *, locale: str | None = None) -> str:
    """Locale-facing concept name (EN prefers name_en)."""
    from app.services.locale import get_locale

    loc = locale or get_locale()
    if loc == "en" and (concept.name_en or "").strip():
        return concept.name_en
    return concept.name_ru


def concept_public_unit(concept: WorldConcept, *, locale: str | None = None) -> str:
    """Locale-facing concept unit (EN prefers unit_en)."""
    from app.services.locale import get_locale

    loc = locale or get_locale()
    if loc == "en" and (concept.unit_en or "").strip():
        return concept.unit_en
    return concept.unit_ru

CONCEPT_BY_SLUG = {concept.slug: concept for concept in WORLD_CONCEPTS}
_NON_SEMANTIC_SLICE_KEYS = frozenset({"freq", "unit", "time", "geo"})


def _concept_pinned_slice(concept: WorldConcept, provider: str) -> Mapping[str, str]:
    """Pinned dimensions для провайдера; по умолчанию — общий required_slice."""
    per_provider = concept.provider_required_slices or {}
    pinned = per_provider.get(provider)
    return pinned if pinned is not None else concept.required_slice


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
    required_slice = _concept_pinned_slice(concept, provider)
    slice_json = indicator.slice_json or {}
    configured_keys = {key.lower() for key in required_slice}
    for key, raw in slice_json.items():
        normalized_key = str(key).strip().lower()
        if not normalized_key or normalized_key in _NON_SEMANTIC_SLICE_KEYS:
            continue
        if normalized_key not in configured_keys and str(raw).strip():
            return False
    for key, expected in required_slice.items():
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
