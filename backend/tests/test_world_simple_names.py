"""БД4: короткое «простое название» мирового ряда выводится только из сверенного концепта."""

from __future__ import annotations

from types import SimpleNamespace

from app.data.world_simple_names import SIMPLE_NAMES, simple_indicator_name, simple_name_for_concept


def _ind(**kw):
    base = dict(
        provider="eurostat", dataset_id="", slice_json={}, unit="", unit_ru="",
        code="x", frequency="annual",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_eurostat_hicp_is_just_prices_and_real_gdp_is_gdp_without_inflation():
    hicp = _ind(
        dataset_id="prc_hicp_midx", slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
        unit="I15", unit_ru="индекс 2015=100", frequency="monthly",
    )
    assert simple_indicator_name(hicp, "ru") == "Цены"
    assert simple_indicator_name(hicp, "en") == "Consumer prices"
    gdp = _ind(
        dataset_id="namq_10_gdp", slice_json={"na_item": "B1GQ", "s_adj": "SCA", "unit": "CLV15_MEUR"},
        unit="CLV15_MEUR", unit_ru="в постоянных ценах 2015 года, млн евро", frequency="quarterly",
    )
    assert simple_indicator_name(gdp, "ru") == "ВВП без инфляции"
    assert simple_indicator_name(gdp, "en") == "Real GDP"


def test_national_series_use_the_reviewed_crosswalk():
    us = _ind(provider="bls", code="us-unemployment-rate", frequency="monthly")
    assert simple_indicator_name(us, "ru") == "Безработица"
    assert simple_indicator_name(us, "en") == "Unemployment"


def test_unreviewed_series_get_no_invented_name():
    other = _ind(dataset_id="zz_unknown", code="de-zz_unknown")
    assert simple_indicator_name(other, "ru") is None
    assert simple_name_for_concept("not-a-concept", "ru") is None


def test_short_names_are_short_and_without_jargon():
    for slug, (ru, en) in SIMPLE_NAMES.items():
        assert len(ru) <= 32 and len(en) <= 32, slug
        assert "сектор" not in ru.lower() and "sector" not in en.lower()
        assert "·" not in ru + en
    assert SIMPLE_NAMES["government-debt-gdp"][0] == "Госдолг"
    assert SIMPLE_NAMES["budget-balance-gdp"][0] == "Баланс бюджета"
    assert SIMPLE_NAMES["gdp-per-capita-usd"][0] == "ВВП на душу"
