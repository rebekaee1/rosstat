from types import SimpleNamespace

from app.data.world_concepts import (
    CONCEPT_BY_SLUG,
    WORLD_CONCEPTS,
    concept_for_indicator,
    concept_matches_indicator,
)


def _indicator(dataset_id, unit, slice_json, unit_ru="", provider="eurostat"):
    return SimpleNamespace(
        dataset_id=dataset_id,
        unit=unit,
        unit_ru=unit_ru,
        slice_json=slice_json,
        provider=provider,
    )


def test_concept_catalog_is_small_and_explicitly_surface_gated():
    assert len(WORLD_CONCEPTS) <= 30
    rating_slugs = {
        "hicp-index",
        "unemployment-rate",
        "budget-balance-gdp",
        "government-debt-gdp",
        "population",
        "long-term-interest-rate",
        "activity-rate",
        "gdp-per-capita-eu",
        "gdp-usd",
        "gdp-per-capita-usd",
    }
    for concept in WORLD_CONCEPTS:
        assert "resolve" in concept.enabled_surfaces
        assert "compare" in concept.enabled_surfaces
        if concept.slug in rating_slugs:
            assert "rating" in concept.enabled_surfaces
        else:
            assert "rating" not in concept.enabled_surfaces
    assert CONCEPT_BY_SLUG["hicp-index"].aggregation_policy == "mean"
    assert CONCEPT_BY_SLUG["hicp-index"].frequency_policy == "official_then_calculated"
    assert CONCEPT_BY_SLUG["unemployment-rate"].aggregation_policy == "mean"
    assert CONCEPT_BY_SLUG["unemployment-rate"].frequency_policy == "official_then_calculated"
    assert CONCEPT_BY_SLUG["gdp-volume-quarterly"].aggregation_policy is None
    assert CONCEPT_BY_SLUG["population"].frequency_policy == "official_only"
    assert CONCEPT_BY_SLUG["long-term-interest-rate"].required_slice["int_rt"] == "MCBY"
    assert CONCEPT_BY_SLUG["activity-rate"].required_slice["indic_em"] == "ACT"
    assert CONCEPT_BY_SLUG["gdp-per-capita-eu"].required_slice["na_item"] == "B1GQ"
    assert "government-debt-gdp" in CONCEPT_BY_SLUG
    assert CONCEPT_BY_SLUG["government-debt-gdp"].required_slice == {
        "na_item": "GD",
        "sector": "S13",
    }
    assert CONCEPT_BY_SLUG["government-debt-gdp"].measure == "PC_GDP"
    assert CONCEPT_BY_SLUG["government-debt-gdp"].dataset_ids == frozenset(
        {"gov_10dd_edpt1"}
    )


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


def test_government_debt_does_not_overlap_budget_balance():
    debt = CONCEPT_BY_SLUG["government-debt-gdp"]
    balance = CONCEPT_BY_SLUG["budget-balance-gdp"]
    gd = _indicator(
        "gov_10dd_edpt1",
        "PC_GDP",
        {"freq": "A", "unit": "PC_GDP", "sector": "S13", "na_item": "GD"},
        "% ВВП",
    )
    b9 = _indicator(
        "gov_10dd_edpt1",
        "PC_GDP",
        {"freq": "A", "unit": "PC_GDP", "sector": "S13", "na_item": "B9"},
        "% ВВП",
    )
    assert concept_matches_indicator(debt, gd)
    assert not concept_matches_indicator(debt, b9)
    assert concept_matches_indicator(balance, b9)
    assert not concept_matches_indicator(balance, gd)
    assert concept_for_indicator(gd).slug == "government-debt-gdp"
    assert concept_for_indicator(b9).slug == "budget-balance-gdp"


def test_concept_resolver_returns_only_a_unique_contract():
    indicator = _indicator("demo_pjan", "NR", {"age": "TOTAL", "sex": "T"})
    assert concept_for_indicator(indicator).slug == "population"
    assert concept_for_indicator(_indicator("demo_pjan", "PC_POP", {"age": "TOTAL", "sex": "T"})) is None


def test_imf_weo_gdp_matches_and_eurostat_b1gq_does_not():
    gdp = CONCEPT_BY_SLUG["gdp-usd"]
    pc = CONCEPT_BY_SLUG["gdp-per-capita-usd"]
    imf_ngdpd = _indicator(
        "WEO",
        "BN_USD",
        {"weo_code": "NGDPD"},
        "млрд $",
        provider="imf",
    )
    imf_pc = _indicator(
        "WEO",
        "USD_PC",
        {"weo_code": "NGDPDPC"},
        "$ на человека",
        provider="imf",
    )
    eurostat_b1gq = _indicator(
        "nama_10_gdp",
        "CLV15_MEUR",
        {"na_item": "B1GQ"},
        "в постоянных ценах 2015 года, млн евро",
        provider="eurostat",
    )
    assert gdp.dataset_ids == frozenset()
    assert gdp.provider_dataset_ids == {"imf": frozenset({"weo"})}
    assert concept_matches_indicator(gdp, imf_ngdpd)
    assert not concept_matches_indicator(gdp, eurostat_b1gq)
    assert not concept_matches_indicator(gdp, imf_pc)
    assert concept_matches_indicator(pc, imf_pc)
    assert not concept_matches_indicator(pc, imf_ngdpd)
    assert not concept_matches_indicator(pc, eurostat_b1gq)
    assert concept_for_indicator(imf_ngdpd).slug == "gdp-usd"
    assert concept_for_indicator(imf_pc).slug == "gdp-per-capita-usd"
    assert concept_for_indicator(eurostat_b1gq).slug == "gdp-volume-annual"
