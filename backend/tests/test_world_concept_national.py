"""Crosswalk national passport codes → curated concepts (map/compare)."""

from app.data.world_concept_national import (
    NATIONAL_CONCEPT_INDICATOR_CODES,
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


def test_all_mapped_codes_unique_per_concept():
    for slug, mapping in NATIONAL_CONCEPT_INDICATOR_CODES.items():
        values = list(mapping.values())
        assert len(values) == len(set(values)), slug
        assert len(mapping) == len(set(mapping.keys())), slug
