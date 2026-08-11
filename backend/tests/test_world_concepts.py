from types import SimpleNamespace

from app.data.world_concepts import (
    CONCEPT_BY_SLUG,
    WORLD_CONCEPTS,
    concept_for_indicator,
    concept_matches_indicator,
)


def _indicator(dataset_id, unit, slice_json, unit_ru=""):
    return SimpleNamespace(
        dataset_id=dataset_id,
        unit=unit,
        unit_ru=unit_ru,
        slice_json=slice_json,
    )


def test_concept_catalog_is_small_and_explicitly_surface_gated():
    assert len(WORLD_CONCEPTS) <= 30
    assert all(concept.enabled_surfaces == {"resolve", "compare"} for concept in WORLD_CONCEPTS)
    assert CONCEPT_BY_SLUG["hicp-index"].aggregation_policy == "mean"
    assert CONCEPT_BY_SLUG["hicp-index"].frequency_policy == "official_then_calculated"
    assert CONCEPT_BY_SLUG["unemployment-rate"].aggregation_policy == "mean"
    assert CONCEPT_BY_SLUG["unemployment-rate"].frequency_policy == "official_then_calculated"
    assert CONCEPT_BY_SLUG["gdp-volume-quarterly"].aggregation_policy is None
    assert CONCEPT_BY_SLUG["population"].frequency_policy == "official_only"


def test_unemployment_requires_rate_total_population_slice():
    concept = CONCEPT_BY_SLUG["unemployment-rate"]
    assert concept_matches_indicator(
        concept,
        _indicator("une_rt_m", "PC_ACT", {"age": "Y15-74", "sex": "T", "s_adj": "SA"}),
    )
    assert not concept_matches_indicator(
        concept,
        _indicator("une_rt_m", "THS_PER", {"age": "Y15-74", "sex": "T", "s_adj": "SA"}),
    )
    assert not concept_matches_indicator(
        concept,
        _indicator("une_rt_m", "PC_ACT", {"age": "Y_LT25", "sex": "T", "s_adj": "SA"}),
    )
    assert not concept_matches_indicator(
        concept,
        _indicator("une_rt_m", "PC_ACT", {"age": "Y15-74", "sex": "T", "s_adj": "NSA"}),
    )


def test_hicp_concept_excludes_yoy_series_and_other_baskets():
    concept = CONCEPT_BY_SLUG["hicp-index"]
    assert concept_matches_indicator(
        concept,
        _indicator("prc_hicp_midx", "I15", {"coicop": "CP00"}),
    )
    assert not concept_matches_indicator(
        concept,
        _indicator("prc_hicp_manr", "RCH_A", {"coicop": "CP00"}),
    )
    assert not concept_matches_indicator(
        concept,
        _indicator("prc_hicp_midx", "I15", {"coicop": "CP01"}),
    )
    assert not concept_matches_indicator(
        concept,
        _indicator("prc_hicp_midx", "I15", {"coicop": "CP00", "partner": "WORLD"}),
    )


def test_concept_resolver_returns_only_a_unique_contract():
    indicator = _indicator("demo_pjan", "NR", {"age": "TOTAL", "sex": "T"})
    assert concept_for_indicator(indicator).slug == "population"
    assert concept_for_indicator(_indicator("demo_pjan", "PC_POP", {"age": "TOTAL", "sex": "T"})) is None
