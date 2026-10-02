"""Hermetic independent controls for calendar, nominal forms and native units."""
from dataclasses import replace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql

from app.models import WorldIndicator
from app.services.search import _world_lexical
from app.services.search_intent import match_score, matching_alternatives, nominal_variants, parse_intent
from app.services.search_language import measure_matches
from app.services.search_language_sql import measure_constraints
from app.services.search_units import price_base_unit_pattern, price_base_years, unit_metadata


def eligible(query, title, units, metadata=""):
    intent = parse_intent(query, [])
    return (not intent.error and measure_matches(intent.terms, code="", names=(title,), unit_names=(units,))
        and match_score(intent, names=(title,), metadata=units + " " + unit_metadata(units) + " " + metadata) is not None)


@pytest.mark.parametrize("word,form", [
    ("бобов", "бобы"), ("домов", "дома"), ("продавцов", "продавцы"),
    ("организациях", "организации"), ("магазинах", "магазины"), ("перевозках", "перевозки"),
    ("соевых", "соевые"), ("центральном", "центральный"),
    ("technology", "technologies"), ("technologies", "technology"),
    ("index", "indices"), ("indices", "index"), ("hospitals", "hospital"),
    ("hospital", "hospitals"), ("boxes", "box"),
])
def test_nominal_forms_are_complete_required_alternatives(word, form):
    variants = nominal_variants(word)
    assert variants[0] == word and form in variants
    # Build a required residual group directly: this tests morphology, without
    # a subject dictionary synonym or a hidden destination-code fixture.
    intent = replace(parse_intent("sample", []), terms=(variants,))
    assert match_score(intent, names=(form,)) is not None
    assert match_score(intent, names=("ant" + form,)) is None
    assert match_score(intent, names=(form + "other",)) is None
    assert match_score(replace(intent, terms=intent.terms + (("magical",),)), names=(form,)) is None


@pytest.mark.parametrize("token", ["montly", "percet", "millio", "averag", "rubels", "monthly", "annual", "persons", "yoy"])
def test_control_words_and_control_typos_do_not_gain_nominal_facets(token):
    assert nominal_variants(token) == (token,)
    intent = parse_intent("sample " + token, [])
    if token in ("montly", "percet", "millio", "averag", "rubels"):
        assert (token,) in intent.terms and intent.corrected is None
        assert match_score(intent, names=("sample",), metadata="search-freq-monthly search-unit-percent search-unit-million search-mode-avg search-unit-rub") is None


@pytest.mark.parametrize("word,form", [("бобов", "бобы"), ("соевых", "соевые"), ("technology", "technologies"), ("index", "indices"), ("boxes", "box")])
def test_nominal_sql_discovery_has_same_whole_forms_before_limit(word, form):
    engine = create_engine("sqlite://")
    WorldIndicator.__table__.create(engine)
    intent = replace(parse_intent("sample", []), terms=((word,),))
    with engine.begin() as connection:
        connection.execute(WorldIndicator.__table__.insert(), [
            dict(country_id=1, frequency="annual", code="aaa", slice_hash="prefix", dataset_id="synthetic", name_en="ant" + form, name_ru="", unit="Number"),
            dict(country_id=1, frequency="annual", code="bbb", slice_hash="suffix", dataset_id="synthetic", name_en=form + "other", name_ru="", unit="Number"),
            dict(country_id=1, frequency="annual", code="zzz", slice_hash="exact", dataset_id="synthetic", name_en=form, name_ru="", unit="Number"),
        ])
        query = select(WorldIndicator.code).where(*_world_lexical(intent, postgres=False)).order_by(WorldIndicator.code).limit(1)
        assert connection.execute(query).scalar_one() == "zzz"
    pg = str(select(WorldIndicator.code).where(*_world_lexical(intent, postgres=True)).compile(dialect=postgresql.dialect()))
    assert "~" in pg


@pytest.mark.parametrize("phrase,freq", [
    ("at the end of the year", "annual"), ("at end of 2025", "annual"),
    ("end 2025", "annual"), ("на конец 2025 года", "annual"),
    ("at the end of each quarter", "quarterly"), ("на конец квартала", "quarterly"),
    ("end of month", "monthly"), ("на конец месяца", "monthly"),
])
def test_end_period_role_requires_mode_and_frequency(phrase, freq):
    query = "inventory " + phrase + ("" if "2025" in phrase else " 2025")
    intent = parse_intent(query, [])
    assert intent.year == 2025 and not intent.error
    assert {"search-mode-eop", "search-freq-" + freq} <= {x[0] for x in intent.terms}
    assert eligible(query, "Inventory", "Number", "search-mode-eop search-freq-" + freq)
    assert not eligible(query, "Inventory", "Number", "search-mode-avg search-freq-" + freq)
    assert not eligible(query, "Inventory", "Number", "search-mode-eop search-freq-daily")
    assert not eligible(query + " magical", "Inventory", "Number", "search-mode-eop search-freq-" + freq)
    assert parse_intent(query + " Q1", []).error == "unsupported_period"


@pytest.mark.parametrize("phrase", ["year on year change", "change year on year", "изменение к предыдущему году", "изменение относительно предыдущего года"])
def test_change_is_redundant_only_inside_complete_yoy_clause(phrase):
    query = "inventory monthly " + phrase + " percent during 2025 observations"
    intent = parse_intent(query, [])
    assert not intent.error and intent.year == 2025
    assert {"search-mode-yoy", "search-freq-monthly", "search-unit-percent"} <= {x[0] for x in intent.terms}
    assert eligible(query, "Inventory", "%", "search-mode-yoy search-freq-monthly search-unit-percent")
    assert not eligible(query, "Inventory", "Number", "search-mode-yoy search-freq-monthly")
    assert not eligible("inventory change", "Inventory", "Number")
    assert not eligible(query + " magical", "Inventory", "%", "search-mode-yoy search-freq-monthly search-unit-percent")


@pytest.mark.parametrize("clause,source", [("from the monthly source series", "monthly"), ("estimated from weekly observations", "weekly")])
def test_source_method_and_observation_frequency_are_independent(clause, source):
    query = "inventory " + clause + " quarterly year on year change percent 2025"
    intent = parse_intent(query, [])
    assert not intent.error
    assert {"search-source-freq-" + source, "search-freq-quarterly", "search-mode-yoy"} <= {x[0] for x in intent.terms}
    assert "search-freq-" + source not in {x[0] for x in intent.terms}
    md = "search-freq-quarterly search-mode-yoy search-unit-percent search-source-freq-" + source
    assert eligible(query, "Inventory", "%", md)
    assert not eligible(query, "Inventory", "%", "search-freq-quarterly search-mode-yoy search-unit-percent")
    assert not eligible(query, "Inventory", "%", md.replace("search-freq-quarterly", "search-freq-annual"))
    assert not eligible(query + " magical", "Inventory", "%", md)
    # A world observation frequency cannot satisfy absent source provenance.
    sql = str(select(WorldIndicator.code).where(*_world_lexical(intent, postgres=True)).compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "false" in sql.lower()


@pytest.mark.parametrize("query,basis", [
    ("inventory 2024 constant 2017 dollars", "constant"),
    ("inventory 2024 chained 2017 dollars", "chained"),
    ("inventory 2024 в цепных долларах 2017 года", "chained"),
    ("inventory 2024 в цепных ценах 2017 года", "chained"),
])
def test_native_price_base_year_is_separate_from_observation_year(query, basis):
    intent = parse_intent(query, [])
    assert not intent.error and intent.year == 2024
    assert ("search-price-base-2017",) in intent.terms
    units = "Millions of " + basis + " 2017 USD dollars"
    # Current native title/unit does not manufacture an alternate currency or
    # observation year; all unit/basis/year descriptors remain mandatory.
    assert eligible(query, "Inventory", units)
    assert not eligible(query, "Inventory", units.replace("2017", "2010"))
    assert not eligible(query, "Inventory 2017", "USD")
    assert not eligible(query, "Inventory", units.replace("USD dollars", "EUR euros")) if "dollar" in query else True
    assert not eligible(query + " magical", "Inventory", units)
    assert parse_intent(query + " 2025", []).error == "unsupported_period"


@pytest.mark.parametrize("unit", ["Millions of chained 2017 dollars", "Млн. цепных долларов (2017 г.)", "USD, constant 2017 prices", "EUR in constant prices (2017)"])
def test_price_base_unit_requires_whole_year_and_monetary_basis(unit):
    assert price_base_years(unit) == (2017,)
    assert "search-price-base-2017" in unit_metadata(unit)
    assert not price_base_years(unit.replace("2017", "20170"))
    assert not price_base_years("2017 Number")
    assert not price_base_years("current 2017 dollars")
    assert not price_base_years("Chained 2017 hectares")
    with pytest.raises(ValueError):
        price_base_unit_pattern(999)


def test_price_base_sql_uses_actual_unit_before_limit_not_native_title_or_seo():
    engine = create_engine("sqlite://")
    WorldIndicator.__table__.create(engine)
    intent = replace(parse_intent("sample", []), terms=(("search-price-base-2017",),))
    with engine.begin() as connection:
        connection.execute(WorldIndicator.__table__.insert(), [
            dict(country_id=1, frequency="annual", code="aaa", slice_hash="wrong-unit", dataset_id="synthetic", name_en="Chained 2017 dollars", name_ru="", unit="Number", seo_keywords="constant 2017 dollars"),
            dict(country_id=1, frequency="annual", code="bbb", slice_hash="long-year", dataset_id="synthetic", name_en="", name_ru="", unit="Chained 20170 dollars", seo_keywords="constant 2017 dollars"),
            dict(country_id=1, frequency="annual", code="zzz", slice_hash="correct-unit", dataset_id="synthetic", name_en="", name_ru="", unit="Millions of chained 2017 dollars", seo_keywords=""),
        ])
        query = select(WorldIndicator.code).where(*_world_lexical(intent, postgres=False)).order_by(WorldIndicator.code).limit(1)
        assert connection.execute(query).scalar_one() == "zzz"


@pytest.mark.parametrize("key,units,wrong", [
    ("current-prices", "Millions of current dollars", "Millions of constant dollars"),
    ("constant-prices", "Millions of constant dollars", "Millions of current dollars"),
])
def test_scoped_valuation_unit_witness_has_python_and_sql_parity(key, units, wrong):
    terms = ((key,),)
    assert measure_matches(terms, code="", names=("Household consumption",), unit_names=(units,))
    assert not measure_matches(terms, code="", names=("Household consumption",), unit_names=(wrong,))
    assert not measure_matches((("population",),), code="", names=("Household consumption",), unit_names=("Population current dollars",))
    assert not measure_matches((("search-subject-price",),), code="", names=("Household consumption",), unit_names=("current prices",))
    engine = create_engine("sqlite://")
    WorldIndicator.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(WorldIndicator.__table__.insert(), [
            dict(country_id=1, frequency="annual", code="aaa", slice_hash="wrong", dataset_id="synthetic", name_en="Household consumption", name_ru="", unit=wrong),
            dict(country_id=1, frequency="annual", code="zzz", slice_hash="correct", dataset_id="synthetic", name_en="Household consumption", name_ru="", unit=units),
        ])
        query = select(WorldIndicator.code).where(*measure_constraints(terms, WorldIndicator.code, (WorldIndicator.name_en,), postgres=False, unit_columns=(WorldIndicator.unit,))).order_by(WorldIndicator.code).limit(1)
        assert connection.execute(query).scalar_one() == "zzz"


@pytest.mark.parametrize("query,unit,marker", [
    ("inventory долларах", "USD", "search-unit-usd"),
    ("inventory million BTU", "USD/MMBtu", "search-unit-btu"),
    ("inventory MMBtu", "USD/MMBtu", "search-unit-million"),
    ("inventory cubic metres", "Cubic metres", "search-unit-cubic-metre"),
    ("inventory solid cubic metres", "Thousand solid cubic metres", "search-unit-solid-cubic-metre"),
])
def test_new_quantity_words_remain_actual_native_units(query, unit, marker):
    intent = parse_intent(query, [])
    assert (marker,) in intent.terms
    assert eligible(query, "Inventory", unit)
    assert not eligible(query, "Inventory", "percent")
    assert not eligible(query + " magical", "Inventory", unit)
    if marker == "search-unit-usd":
        assert not eligible(query, "Inventory", "CAD")
        assert not eligible(query, "Inventory USD", "Dollars")
    if marker == "search-unit-solid-cubic-metre":
        assert not eligible(query, "Inventory", "Cubic metres")
    if marker == "search-unit-cubic-metre":
        assert not eligible(query, "Inventory", "Cubic kilometres")
        assert not eligible(query, "Inventory", "Square metres")


def test_generic_price_marker_requires_actual_price_subject():
    terms = parse_intent("inventory price", []).terms
    assert ("search-subject-price",) in terms
    assert measure_matches(terms, code="", names=("Inventory price",))
    assert not measure_matches(terms, code="", names=("Inventory",), unit_names=("USD price per tonne",))
    assert not measure_matches(terms, code="", names=("Inventory",))


def test_subject_typo_cannot_be_blocked_by_a_component_of_compound_unit():
    assert parse_intent("рост ценн", []).terms[0][0] == "cpi"
    assert not eligible("inventory chainned prices", "Inventory", "chained 2017 dollars")


def test_parser_keeps_unknown_identity_while_shared_match_expands_complete_nominals():
    intent = parse_intent("technology magical", [])
    assert ("technology",) in intent.terms and ("magical",) in intent.terms
    assert matching_alternatives(("technology",)) == ("technology", "technologies")
    assert matching_alternatives(("technology",), literal="technology") == ("technology",)
    assert matching_alternatives(("search-unit-percent",)) == ("search-unit-percent",)
    assert not eligible("technology magical", "Technologies", "Number")


def test_price_base_rewrite_preserves_independent_iso_month_and_invalid_full_dates():
    intent = parse_intent("inventory constant 2017 dollars 2024-02", [])
    assert (intent.year, intent.month, intent.error) == (2024, 2, None)
    assert ("search-price-base-2017",) in intent.terms
    assert parse_intent("inventory constant 2017 dollars 2024-13", []).error == "unsupported_period"
    assert parse_intent("inventory constant 2017 dollars 2024-02-01", []).error == "unsupported_period"


@pytest.mark.parametrize("currency", ["USD", "RUB", "EUR", "CAD", "GBP"])
def test_valuation_native_currency_codes_do_not_require_english_dollars(currency):
    units = "constant 2017 " + currency
    assert measure_matches((("constant-prices",),), code="", names=("Inventory",), unit_names=(units,))
    assert not measure_matches((("current-prices",),), code="", names=("Inventory",), unit_names=(units,))
    assert "constant-prices" in unit_metadata(units)
    assert "current-prices" not in unit_metadata(units)
    assert not measure_matches((("population",),), code="", names=("Inventory",), unit_names=("Population " + units,))
    assert eligible("inventory constant 2017 euros", "Inventory", units) if currency == "EUR" else not eligible("inventory constant 2017 euros", "Inventory", units)


def test_pure_nominal_caches_are_bounded_and_do_not_change_required_terms():
    assert nominal_variants.cache_parameters()["maxsize"] == 2048
    assert matching_alternatives.cache_parameters()["maxsize"] == 4096
    before = parse_intent("technology magical", [])
    matching_alternatives(("technology",))
    assert parse_intent("technology magical", []) == before


@pytest.mark.parametrize("constant,current,currency", [
    ("Млн постоянных рублей (2017 г)", "Млн текущих рублей", "rubles"),
    ("Млн постоянных долларов USD (2017 г)", "Млн текущих долларов USD", "dollars"),
    ("Млн постоянных EUR (2017 г)", "Млн текущих EUR", "euros"),
])
def test_russian_native_valuation_currency_has_scoped_python_sql_and_matcher_parity(constant, current, currency):
    terms = (("constant-prices",),)
    assert measure_matches(terms, code="", names=("Inventory",), unit_names=(constant,))
    assert not measure_matches(terms, code="", names=("Inventory",), unit_names=(current,))
    assert not measure_matches((("current-prices",),), code="", names=("Inventory",), unit_names=(constant,))
    assert "constant-prices" in unit_metadata(constant)
    assert "current-prices" not in unit_metadata(constant)
    assert eligible("inventory constant 2017 " + currency, "Inventory", constant)
    assert not eligible("inventory constant 2017 " + currency, "Inventory", current)
    assert not measure_matches((("population",),), code="", names=("Inventory",), unit_names=("Population " + constant,))
    engine = create_engine("sqlite://")
    WorldIndicator.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(WorldIndicator.__table__.insert(), [
            dict(country_id=1, frequency="annual", code="aaa", slice_hash="current", dataset_id="synthetic", name_en="Inventory", name_ru="", unit=current),
            dict(country_id=1, frequency="annual", code="zzz", slice_hash="constant", dataset_id="synthetic", name_en="Inventory", name_ru="", unit=constant),
        ])
        query = select(WorldIndicator.code).where(*measure_constraints(terms, WorldIndicator.code, (WorldIndicator.name_en,), postgres=False, unit_columns=(WorldIndicator.unit,))).order_by(WorldIndicator.code).limit(1)
        assert connection.execute(query).scalar_one() == "zzz"


def test_russian_bare_dollars_valuation_does_not_manufacture_usd_denomination():
    units = "Млн постоянных долларов (2017 г)"
    query = "inventory constant 2017 dollars"
    intent = parse_intent(query, [])
    assert measure_matches(intent.terms, code="", names=("Inventory",), unit_names=(units,))
    assert not eligible(query, "Inventory", units)
    assert match_score(intent, names=("Inventory",), metadata=unit_metadata(units, native_currency="USD")) is not None
    assert match_score(intent, names=("Inventory",), metadata=unit_metadata(units, native_currency="CAD")) is None


@pytest.mark.parametrize("key,title,currency,valid_unit,opposite", [
    ("current-prices", "Current transfers", "USD", "Millions of current USD", "Millions of constant USD"),
    ("constant-prices", "Constant workforce", "EUR", "Millions of constant 2017 EUR", "Millions of current EUR"),
])
def test_valuation_witness_cannot_cross_title_unit_or_separate_unit_fields(key, title, currency, valid_unit, opposite):
    terms = ((key,),)
    assert not measure_matches(terms, code="", names=(title,), unit_names=(currency,))
    assert not measure_matches(terms, code="", names=(title + " to " + currency + " bank",))
    assert not measure_matches(terms, code="", names=("Inventory",), unit_names=(key.split("-")[0], currency))
    assert measure_matches(terms, code="", names=("Inventory",), unit_names=(valid_unit,))
    assert not measure_matches(terms, code="", names=("Inventory",), unit_names=(valid_unit, opposite))
    assert key not in unit_metadata(key.split("-")[0], currency)
    engine = create_engine("sqlite://")
    WorldIndicator.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(WorldIndicator.__table__.insert(), [
            dict(country_id=1, frequency="annual", code="aaa", slice_hash="crossfields", dataset_id="synthetic", name_en=title, name_ru="", unit=currency),
            dict(country_id=1, frequency="annual", code="bbb", slice_hash="wrong-title", dataset_id="synthetic", name_en=title + " to " + currency + " bank", name_ru="", unit="Number"),
            dict(country_id=1, frequency="annual", code="ccc", slice_hash="crossunits", dataset_id="synthetic", name_en="Inventory", name_ru="", unit=key.split("-")[0], unit_ru=currency),
            dict(country_id=1, frequency="annual", code="zzz", slice_hash="correct", dataset_id="synthetic", name_en="Inventory", name_ru="", unit=valid_unit),
        ])
        query = select(WorldIndicator.code).where(*measure_constraints(terms, WorldIndicator.code, (WorldIndicator.name_en,), postgres=False, unit_columns=(WorldIndicator.unit, WorldIndicator.unit_ru))).order_by(WorldIndicator.code).limit(1)
        assert connection.execute(query).scalar_one() == "zzz"
