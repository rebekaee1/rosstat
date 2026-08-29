"""Crosswalk national passport codes → curated concepts (map/compare)."""

from app.data.world_concept_national import (
    NATIONAL_CONCEPT_INDICATOR_CODES,
    hicp_national_yoy_kind,
    national_codes_for_concept,
)


def test_national_unemployment_codes_are_explicit():
    codes = national_codes_for_concept("unemployment-rate")
    assert "us-unemployment-rate" in codes
    assert "uk-unemployment-rate" in codes
    assert "cn-urban-unemployment" in codes


def test_gdp_volume_has_no_national_absolute_alias():
    # Абсолютный ВВП в нац. валютах не мешаем с млн евро на одной шкале.
    assert national_codes_for_concept("gdp-volume-quarterly") == frozenset()
    assert national_codes_for_concept("gdp-volume-annual") == frozenset()


def test_hicp_national_yoy_kinds():
    # Уровень индекса — transform_yoy. CN — индекс «тот же месяц = 100».
    # BR IPCA 12m — уже YoY %. MoM IPCA в рейтинг не входит.
    mapping = NATIONAL_CONCEPT_INDICATOR_CODES["hicp-index"]
    codes = national_codes_for_concept("hicp-index")
    assert mapping["US"] == "us-cpi-all"
    assert mapping["CN"] == "cn-cpi-all"
    assert mapping["BR"] == "br-cpi-ipca-yoy"
    assert mapping["JP"] == "jp-cpi-all"
    assert mapping["KR"] == "kr-cpi-all"
    assert "cn-cpi-all" in codes
    assert "br-cpi-ipca-yoy" in codes
    assert "br-cpi-ipca" not in codes
    assert hicp_national_yoy_kind("cn-cpi-all") == "index_minus_100"
    assert hicp_national_yoy_kind("br-cpi-ipca-yoy") == "passthrough"
    assert hicp_national_yoy_kind("us-cpi-all") == "level"


def test_all_mapped_codes_unique_per_concept():
    for slug, mapping in NATIONAL_CONCEPT_INDICATOR_CODES.items():
        values = list(mapping.values())
        assert len(values) == len(set(values)), slug
        assert len(mapping) == len(set(mapping.keys())), slug


def test_activity_rate_national_participation_rates():
    """AU/UK: национальный participation rate = уровень экономической активности.

    Eurostat-срез lfsi_emp_a ACT (15–64) недоступен вне Eurostat-plane;
    официальный национальный ряд доли экономически активного населения
    в процентах сопоставим по смыслу и единице (возрастная база своя).
    """
    mapping = NATIONAL_CONCEPT_INDICATOR_CODES["activity-rate"]
    assert mapping["AU"] == "au-participation-rate"
    assert mapping["UK"] == "uk-participation-rate"
    codes = national_codes_for_concept("activity-rate")
    assert codes == frozenset({"au-participation-rate", "uk-participation-rate"})
