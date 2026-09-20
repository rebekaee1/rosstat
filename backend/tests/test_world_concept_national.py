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
    assert mapping["US"] == "us-labor-force-participation"
    codes = national_codes_for_concept("activity-rate")
    assert codes == frozenset({
        "au-participation-rate",
        "uk-participation-rate",
        "us-labor-force-participation",
    })


def test_us_long_term_rate_maps_to_treasury_10y():
    mapping = NATIONAL_CONCEPT_INDICATOR_CODES["long-term-interest-rate"]
    assert mapping["US"] == "us-treasury-10y"


def _ns(**kwargs):
    from types import SimpleNamespace

    return SimpleNamespace(**kwargs)


def test_filter_weo_shadowed_hides_lur_and_lp_keeps_gdp():
    from app.data.world_concept_national import filter_weo_shadowed_from_country_listing

    national_une = _ns(
        code="us-unemployment-rate", provider="fred", dataset_id="UNRATE",
        unit="PERCENT", unit_ru="%", slice_json={"freq": "M"},
    )
    weo_lur = _ns(
        code="us-weo-lur", provider="imf", dataset_id="weo",
        unit="PC_ACT", unit_ru="% экономически активного населения",
        slice_json={"weo_code": "LUR"},
    )
    weo_lp = _ns(
        code="us-weo-lp", provider="imf", dataset_id="weo",
        unit="NR", unit_ru="человек", slice_json={"weo_code": "LP"},
    )
    weo_gdp = _ns(
        code="us-weo-ngdpd", provider="imf", dataset_id="weo",
        unit="BN_USD", unit_ru="млрд $", slice_json={"weo_code": "NGDPD"},
    )
    national_pop = _ns(
        code="us-population-census", provider="fred", dataset_id="POPTHM",
        unit="THOUSANDS", unit_ru="тыс. человек", slice_json={"freq": "M"},
    )
    kept = filter_weo_shadowed_from_country_listing(
        [national_une, weo_lur, weo_lp, weo_gdp, national_pop],
        "US",
    )
    codes = [ind.code for ind in kept]
    assert "us-unemployment-rate" in codes
    assert "us-population-census" in codes
    assert "us-weo-ngdpd" in codes
    assert "us-weo-lur" not in codes
    assert "us-weo-lp" not in codes


def test_filter_weo_shadowed_eurostat_hides_weo_unemployment():
    from app.data.world_concept_national import filter_weo_shadowed_from_country_listing

    euro = _ns(
        code="de-une_rt_m-total-sa-t-pc-act",
        provider="eurostat",
        dataset_id="une_rt_m",
        unit="PC_ACT",
        unit_ru="% экономически активного населения",
        slice_json={"age": "TOTAL", "sex": "T", "s_adj": "SA", "freq": "M"},
    )
    weo = _ns(
        code="de-weo-lur", provider="imf", dataset_id="weo",
        unit="PC_ACT", unit_ru="% экономически активного населения",
        slice_json={"weo_code": "LUR"},
    )
    weo_gdp = _ns(
        code="de-weo-ngdpd", provider="imf", dataset_id="weo",
        unit="BN_USD", unit_ru="млрд $", slice_json={"weo_code": "NGDPD"},
    )
    kept = filter_weo_shadowed_from_country_listing([euro, weo, weo_gdp], "DE")
    codes = [ind.code for ind in kept]
    assert "de-une_rt_m-total-sa-t-pc-act" in codes
    assert "de-weo-ngdpd" in codes
    assert "de-weo-lur" not in codes


def test_filter_weo_keeps_weo_when_no_national_or_eurostat():
    from app.data.world_concept_national import filter_weo_shadowed_from_country_listing

    weo = _ns(
        code="ng-weo-lur", provider="imf", dataset_id="weo",
        unit="PC_ACT", unit_ru="% экономически активного населения",
        slice_json={"weo_code": "LUR"},
    )
    kept = filter_weo_shadowed_from_country_listing([weo], "NG")
    assert [ind.code for ind in kept] == ["ng-weo-lur"]
