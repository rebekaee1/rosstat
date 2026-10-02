"""Independent grammar/quantity/sector controls, without destination mappings."""
import pytest

from app.services.search_intent import match_score, parse_intent
from app.services.search_language import measure_matches, prepare_language
from app.services.search_units import unit_metadata
from app.services.search_vocabulary import prepare_subject_roles, prepare_temporal_roles, prepare_vocabulary


def eligible(query, title, metadata=""):
    intent = parse_intent(query, [])
    return (not intent.error and measure_matches(intent.terms, code="", names=(title,))
        and match_score(intent, names=(title,), metadata=metadata) is not None)


def keys(intent):
    return {group[0] for group in intent.terms}


@pytest.mark.parametrize("phrase", ["number of people", "number of persons", "in people", "in persons", "число человек"])
def test_human_count_unit_is_not_a_population_subject(phrase):
    query = "training masters " + phrase
    intent = parse_intent(query, [])
    assert "search-unit-persons" in keys(intent)
    assert "population" not in keys(intent)
    assert eligible(query, "Training masters", unit_metadata("people"))
    assert not eligible(query, "Training masters", unit_metadata("percent"))
    assert not eligible(query, "Training masters", unit_metadata("Dollars", native_currency="USD"))
    assert not eligible(query + " private", "Training masters", unit_metadata("people"))


@pytest.mark.parametrize("query", ["people", "residents", "сколько жителей"])
def test_population_subject_still_requires_population_identity(query):
    assert "population" in keys(parse_intent(query, []))
    assert eligible(query, "Resident population")
    assert not eligible(query, "Training masters", unit_metadata("people"))


@pytest.mark.parametrize("query", [
    "GDP per capita current prices in USD", "ВВП на душу населения в текущих долларах США",
    "per capita GDP nominal in USD",
])
def test_per_capita_and_valuation_are_independent_required_roles(query):
    intent = parse_intent(query, [])
    assert {"gdp-per-capita", "current-prices", "search-unit-usd"} <= keys(intent)
    assert not keys(intent).intersection({"gdp-nominal", "population"})
    metadata = unit_metadata("USD")
    assert eligible(query, "GDP per capita, current prices", metadata)
    assert not eligible(query, "GDP, current prices", metadata)
    assert not eligible(query, "Real GDP per capita, constant prices", metadata)
    assert not eligible(query, "GDP per capita, current prices", unit_metadata("EUR"))
    assert not eligible(query + " magical", "GDP per capita, current prices", metadata)


def test_conflicting_valuations_are_not_silently_resolved():
    query = "GDP per capita current prices constant prices"
    assert {"current-prices", "constant-prices"} <= keys(parse_intent(query, []))
    assert not eligible(query, "GDP per capita, current prices")
    assert not eligible(query, "Real GDP per capita, constant prices")
    assert not eligible(query, "GDP per capita, current prices and constant prices")


@pytest.mark.parametrize("query", [
    "industry contribution to GDP growth food manufacturing percentage points",
    "GDP by industry food manufacturing current prices in USD",
])
def test_food_sector_is_distinct_from_consumer_price_measure(query):
    intent = parse_intent(query, [])
    assert "food-industry" in keys(intent)
    assert "cpi-food" not in keys(intent)
    title = "Industry contribution to GDP growth: Food manufacturing" if "growth" in query else "GDP by industry: Food manufacturing, current prices"
    metadata = unit_metadata("Percentage points" if "growth" in query else "USD")
    assert eligible(query, title, metadata)
    assert not eligible(query, title.replace("Food", "Textile"), metadata)
    assert not eligible(query, "Consumer price index: Food manufacturing", metadata)
    assert not eligible(query + " net magical", title, metadata)


def test_explicit_food_price_measure_does_not_become_industry():
    intent = parse_intent("food prices", [])
    assert "cpi-food" in keys(intent)
    assert "food-industry" not in keys(intent)
    assert eligible("food prices", "Food price index")
    assert not eligible("food prices", "GDP of food manufacturing")
    assert "unknownsector" in prepare_language("GDP food manufacturing unknownsector")


@pytest.mark.parametrize("phrase", [
    "same quarter of the previous year", "same quarter last year", "same quarter a year earlier",
    "тому же кварталу прошлого года", "аналогичному кварталу прошлого года",
])
def test_same_quarter_comparison_keeps_mode_frequency_and_observation_year(phrase):
    query = "reservoir pressure " + phrase + " 2024"
    intent = parse_intent(query, [])
    assert intent.year == 2024 and not intent.error
    assert {"search-mode-yoy", "search-freq-quarterly"} <= keys(intent)
    assert eligible(query, "Reservoir pressure", "search-mode-yoy search-freq-quarterly")
    assert not eligible(query, "Reservoir pressure", "search-mode-pop search-freq-quarterly")
    assert not eligible(query, "Reservoir pressure", "search-mode-yoy search-freq-annual")
    assert not eligible(query + " magical", "Reservoir pressure", "search-mode-yoy search-freq-quarterly")


def test_comparison_change_grammar_requires_a_complete_known_window():
    query = "reservoir pressure change from the same quarter of the previous year"
    assert eligible(query, "Reservoir pressure", "search-mode-yoy search-freq-quarterly")
    assert not eligible("reservoir pressure change", "Reservoir pressure")
    assert prepare_temporal_roles("pressure change from the magical quarter") == "pressure change from the magical quarter"
    assert parse_intent(query + " Q1 2024", []).error == "unsupported_period"


def test_comparison_change_rewrite_keeps_explicit_percentage_unit():
    query = "reservoir pressure percentage change from the same quarter last year"
    intent = parse_intent(query, [])
    assert "search-unit-percent" in keys(intent)
    metadata = "search-mode-yoy search-freq-quarterly search-unit-percent"
    assert eligible(query, "Reservoir pressure", metadata)
    assert not eligible(query, "Reservoir pressure", "search-mode-yoy search-freq-quarterly")
    assert not eligible(query, "Reservoir pressure", "search-mode-yoy search-freq-quarterly search-unit-percentage-point")


@pytest.mark.parametrize("verb", ["contribute", "contributes", "contributed", "contributing"])
def test_contribution_verb_has_its_role_only_with_named_measure(verb):
    query = "insurance " + verb + " to GDP growth percentage points"
    metadata = unit_metadata("Percentage points")
    assert eligible(query, "Insurance contribution to GDP growth", metadata)
    assert not eligible(query, "Insurance GDP", metadata)
    assert not eligible(query, "Insurance contribution to GDP growth", unit_metadata("USD"))
    assert not eligible(query + " magical", "Insurance contribution to GDP growth", metadata)
    assert prepare_subject_roles("insurance " + verb) == "insurance " + verb


def test_generation_verb_is_question_grammar_only_with_explicit_gdp():
    assert eligible("how much GDP did shipbuilding generate current prices USD", "GDP of shipbuilding, current prices", unit_metadata("USD"))
    assert not eligible("how much GDP did shipbuilding generate current prices USD magical", "GDP of shipbuilding, current prices", unit_metadata("USD"))
    assert prepare_vocabulary("electricity generate") == "electricity generate"


@pytest.mark.parametrize("form", ["долларах США", "долларе США", "долларам США", "долларами США", "долларом США"])
def test_currency_inflection_protects_geography_and_remains_native_unit(form):
    geometry = [dict(key="country:russia", kind="country", slug="russia", country_slug="russia", name_ru="Россия", country_code="RU"),
        dict(key="country:united-states", kind="country", slug="united-states", country_slug="united-states", name_ru="США", country_code="US")]
    intent = parse_intent("Россия резерв в " + form, geometry)
    assert intent.countries == frozenset(("russia",))
    assert "search-unit-usd" in keys(intent)
    assert match_score(intent, names=("Резерв",), metadata=unit_metadata("USD")) is not None
    assert match_score(intent, names=("Резерв",), metadata=unit_metadata("CAD")) is None
    assert parse_intent("Россия резерв США", geometry).countries == frozenset(("russia", "united-states"))


@pytest.mark.parametrize("code", ["MX", "CA", "DE"])
def test_iso_case_rule_keeps_scientific_symbols_out_of_geography(code):
    geometry = [dict(key="country:synthetic", kind="country", slug="synthetic", country_slug="synthetic", country_code=code)]
    assert parse_intent("mortality " + code, geometry).countries == frozenset(("synthetic",))
    assert parse_intent("mortality " + code.lower(), geometry).countries == frozenset(("synthetic",))
    for symbol in (code.title(), code[0].lower() + code[1]):
        intent = parse_intent("mortality " + symbol, geometry)
        assert not intent.countries
        assert (symbol.casefold(),) in intent.terms


def test_plural_proper_name_declension_requires_actual_complete_native_entity():
    geometry = [dict(key="subnational_region:united-states:hawaii", kind="subnational_region", slug="hawaii", country_slug="united-states", name_ru="Гавайи")]
    assert parse_intent("population на Гавайях", geometry).regions == frozenset(("subnational_region:united-states:hawaii",))
    assert not parse_intent("population на Гавайях", []).regions
    assert not parse_intent("population на Лунайях", geometry).regions
    assert match_score(parse_intent("population на Гавайях magical", geometry), names=("Population",)) is None
