"""Единица уже процентного ряда понятия «индекс цен» (IMF PCPIPCH).

Круг 08.10.2026: у Китая и Турции заголовок гласил «0,05 (индекс 2015 = 100)»,
хотя ряд — инфляция за год в процентах. Единица понятия подставлялась
в ответ данных без проверки ряда.
"""
from types import SimpleNamespace

from app.api.world import (
    _concept_unit_for_indicator,
    _indicator_public_unit,
)
from app.data.world_concepts import concept_for_indicator
from app.services.locale import reset_locale, set_locale


def _imf_inflation():
    return SimpleNamespace(
        code="tr-weo-pcpipch",
        provider="imf",
        dataset_id="weo",
        unit="PC",
        unit_ru="изменение за год, %",
        slice_json={"weo_code": "PCPIPCH"},
    )


def _eurostat_hicp():
    return SimpleNamespace(
        code="at-prc_hicp_midx-cp00-i15",
        provider="eurostat",
        dataset_id="prc_hicp_midx",
        unit="I15",
        unit_ru="индекс 2015=100",
        slice_json={"coicop": "CP00"},
    )


def _units(indicator, locale):
    token = set_locale(locale)
    try:
        concept = concept_for_indicator(indicator)
        return concept, _concept_unit_for_indicator(concept, indicator), _indicator_public_unit(indicator)
    finally:
        reset_locale(token)


def test_imf_inflation_is_percent_not_index_in_both_locales():
    for locale in ("ru", "en"):
        concept, data_unit, page_unit = _units(_imf_inflation(), locale)
        assert concept is not None and concept.slug == "hicp-index"
        for unit in (data_unit, page_unit):
            assert "%" in unit, (locale, unit)
            assert "2015" not in unit and "index" not in unit.lower() and "индекс" not in unit
    # английская подпись без кириллицы
    _concept, data_unit_en, page_unit_en = _units(_imf_inflation(), "en")
    assert not any("а" <= ch.lower() <= "я" for ch in data_unit_en + page_unit_en)


def test_eurostat_index_keeps_concept_unit():
    for locale, expected in (("ru", "индекс 2015=100"), ("en", "index 2015=100")):
        _concept, data_unit, page_unit = _units(_eurostat_hicp(), locale)
        assert data_unit == expected
        if locale == "en":
            assert page_unit == expected
