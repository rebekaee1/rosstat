"""Independent role pairs: spelling, identity, denomination and geography."""
import pytest

from app.services.search_intent import literal_identifier, match_score, parse_intent


GEOMETRY = [
    dict(key=f"country:{slug}", kind="country", slug=slug, country_slug=slug,
        country_code=code, name_ru=ru, name_en=en)
    for slug, code, ru, en in (
        ("russia", "RU", "Россия", "Russia"),
        ("canada", "CA", "Канада", "Canada"),
        ("australia", "AU", "Австралия", "Australia"),
        ("united-states", "US", "США", "United States"),
        ("japan", "JP", "Япония", "Japan"),
    )
] + [dict(key="region:russia:yamalo-nenetskiy-ao", kind="region",
    slug="yamalo-nenetskiy-ao", country_slug="russia",
    name_ru="Ямало-Ненецкий автономный округ", name_en="Yamalo-Nenets Autonomous Okrug")]


def keys(intent):
    return {group[0] for group in intent.terms}


@pytest.mark.parametrize("query", ["businesses hold inventories", "цены"])
def test_ordinary_word_cannot_become_neighbouring_gold_or_currency(query):
    intent = parse_intent(query, GEOMETRY)
    assert not keys(intent).intersection({"gold", "search-unit-jpy"})
    assert intent.corrected is None
    assert match_score(intent, names=("Gold price",), metadata="search-unit-jpy") is None


def test_long_unique_subject_typo_keeps_unrelated_qualifier_required():
    intent = parse_intent("инфлция magical", GEOMETRY)
    assert "cpi" in keys(intent)
    assert intent.corrected == "инфляция magical"
    assert ("magical",) in intent.terms
    assert match_score(intent, names=("Consumer price index",)) is None
    assert match_score(intent, names=("Magical consumer price index",)) is not None


@pytest.mark.parametrize(("typo", "marker"), [
    ("montly", "search-freq-monthly"),
    ("percet", "search-unit-percent"),
    ("millio", "search-unit-million"),
    ("averag", "search-mode-avg"),
    ("rubels", "search-unit-rub"),
])
def test_control_typo_is_required_verbatim_and_cannot_fuzzy_match_marker(typo, marker):
    intent = parse_intent("population " + typo, GEOMETRY)
    assert marker not in keys(intent)
    assert (typo,) in intent.terms
    assert intent.corrected is None
    assert match_score(intent, names=("Population",), metadata=marker) is None


@pytest.mark.parametrize("query", ["credit short-term", "central-bank notes", "magical-compound population"])
def test_ordinary_alphabetic_hyphen_compound_is_not_an_atomic_code(query):
    intent = parse_intent(query, GEOMETRY)
    assert literal_identifier(query, GEOMETRY) is None
    assert intent.literal is None
    assert match_score(intent, names=("Population",)) is None


def test_actual_alphabetic_catalogue_code_needs_authoritative_preflight():
    code = "catalogue-measure"
    assert literal_identifier(code, GEOMETRY) is None
    intent = parse_intent(code + " Russia magical", GEOMETRY, literal_content=code)
    assert intent.literal == code
    assert intent.countries == frozenset(("russia",))
    assert match_score(intent, code=code) is None
    assert match_score(intent, code=code, names=("Magical measure",)) == 1000


@pytest.mark.parametrize("code", ["series_annual-2020", "series-123", "series-avg-quarter", "RU-series-native"])
def test_bounded_technical_syntax_still_protects_intrinsic_control_parts(code):
    intent = parse_intent(code + " Japan", GEOMETRY)
    assert intent.literal == code.casefold()
    assert intent.terms == ((code.casefold(),),)
    assert intent.year is None and intent.month is None and intent.error is None
    assert intent.countries == frozenset(("japan",))


def test_hyphenated_geo_prefix_does_not_hide_full_actual_place():
    intent = parse_intent("population Yamalo-Nenets Autonomous Okrug", GEOMETRY)
    assert intent.literal is None
    assert intent.regions == frozenset(("region:russia:yamalo-nenetskiy-ao",))
    assert match_score(intent, names=("Population",)) is not None


@pytest.mark.parametrize(("denominator", "number"), [
    ("per 1000 people", 1000), ("per 1,000 inhabitants", 1000),
    ("per thousand persons", 1000), ("per one thousand population", 1000),
    ("на тысячу жителей", 1000), ("на 1000 человек населения", 1000),
    ("per 10000 residents", 10000), ("per ten thousand people", 10000),
    ("на десять тысяч жителей", 10000), ("per 100000 persons", 100000),
    ("per hundred thousand inhabitants", 100000), ("на сто тысяч человек", 100000),
])
def test_complete_person_denominator_is_one_ratio_role(denominator, number):
    intent = parse_intent("incidents " + denominator + " Russia 2024", GEOMETRY)
    marker = f"search-denominator-{number}-persons"
    assert intent.year == 2024 and intent.error is None
    assert intent.countries == frozenset(("russia",))
    assert intent.terms == ((marker,), ("incidents",))
    assert not keys(intent).intersection({"population", "search-unit-thousand", "search-unit-persons"})
    assert match_score(intent, names=("Incidents",), metadata=marker) is not None
    assert match_score(intent, names=("Incidents",), metadata="search-unit-persons") is None
    wrong_number = 10000 if number == 1000 else 1000
    assert match_score(intent, names=("Incidents",), metadata=f"search-denominator-{wrong_number}-persons") is None


def test_denominator_does_not_consume_unknown_qualifier_or_literal_content():
    intent = parse_intent("incidents per 1000 people magical", GEOMETRY)
    assert ("magical",) in intent.terms
    assert match_score(intent, names=("Incidents",), metadata="search-denominator-1000-persons") is None
    title = "Incidents per 1000 people"
    literal = parse_intent(title, GEOMETRY, literal_content=title)
    assert literal.terms == ((title.casefold(),),)
    assert literal.year is None


@pytest.mark.parametrize("query", ["incidents per 1200 people", "incidents per 1000 unknown people", "incidents per 1000 vehicles"])
def test_unknown_denominator_keeps_its_number_and_other_constraints(query):
    intent = parse_intent(query, GEOMETRY)
    assert intent.year is None
    assert not any(key.startswith("search-denominator-") for key in keys(intent))
    assert any(group[0].isdigit() for group in intent.terms)
    assert match_score(intent, names=("Incidents",), metadata="search-denominator-1000-persons") is None


def test_distinct_denominators_fail_closed_instead_of_selecting_one():
    intent = parse_intent("incidents per 1000 people per 10000 people", GEOMETRY)
    assert intent.error == "unsupported_query"
    assert keys(intent) >= {"search-denominator-1000-persons", "search-denominator-10000-persons"}
    repeated = parse_intent("incidents per 1000 people per 1000 people", GEOMETRY)
    assert repeated.error is None
    assert repeated.terms.count(("search-denominator-1000-persons",)) == 1


@pytest.mark.parametrize(("currency", "marker"), [
    ("Canadian dollars", "search-unit-cad"),
    ("Australian dollars", "search-unit-aud"),
    ("US dollars", "search-unit-usd"),
])
def test_currency_demonym_span_is_a_unit_while_outer_country_remains_geo(currency, marker):
    intent = parse_intent("population Japan " + currency, GEOMETRY)
    assert intent.countries == frozenset(("japan",))
    assert marker in keys(intent)
    if marker != "search-unit-usd":
        assert "search-unit-usd" not in keys(intent)
    assert match_score(intent, names=("Population",), metadata=marker) is not None
    assert match_score(intent, names=("Population",), metadata="search-unit-rub") is None


@pytest.mark.parametrize(("demonym", "country"), [("Canadian", "canada"), ("Australian", "australia"), ("American", "united-states")])
def test_demonym_outside_known_currency_phrase_remains_geography(demonym, country):
    intent = parse_intent(demonym + " population", GEOMETRY)
    assert intent.countries == frozenset((country,))
    assert not any(key.startswith("search-unit-") for key in keys(intent))


@pytest.mark.parametrize(("demonym", "slug"), [
    ("Japanese", "japan"), ("Chinese", "china"), ("Indian", "india"),
    ("British", "united-kingdom"), ("French", "france"), ("German", "germany"),
])
def test_known_country_demonym_requires_the_actual_country(demonym, slug):
    geometry = [dict(key=f"country:{slug}", kind="country", slug=slug,
        country_slug=slug, name_en=slug)]
    intent = parse_intent(demonym + " population", geometry)
    assert intent.countries == frozenset((slug,))
    assert not intent.corrected
    assert not parse_intent(demonym + " population", []).countries
    title = demonym + " population density"
    protected = parse_intent(title, geometry, literal_content=title)
    assert not protected.countries
    assert protected.terms == ((title.casefold(),),)


def test_unknown_word_between_demonym_and_currency_is_not_masked():
    intent = parse_intent("Canadian magical dollars population", GEOMETRY)
    assert intent.countries == frozenset(("canada",))
    assert ("magical",) in intent.terms
    assert match_score(intent, names=("Population",), metadata="search-unit-usd") is None


@pytest.mark.parametrize("currency", ["Canadan dollars", "Canadian dolar", "Canadian dollrs", "Australan dollars", "Australian dollrs"])
def test_near_currency_phrase_is_not_corrected_into_a_geography(currency):
    intent = parse_intent("population " + currency, GEOMETRY)
    assert not intent.countries
    assert not intent.corrected
    assert match_score(intent, names=("Population",), metadata="search-unit-usd search-unit-cad search-unit-aud") is None
    assert match_score(intent, names=("Population",), metadata="Canadian dollars Australian dollars search-unit-cad search-unit-aud") is None
    exact_place = parse_intent("population Australia dollars", GEOMETRY)
    assert exact_place.countries == frozenset(("australia",))
    assert "search-unit-usd" in keys(exact_place)


def test_currency_words_inside_authoritative_literal_have_no_outer_facets():
    title = "Balances in Canadian dollars"
    intent = parse_intent(title + " Japan", GEOMETRY, literal_content=title)
    assert intent.countries == frozenset(("japan",))
    assert intent.terms == ((title.casefold(),),)


@pytest.mark.parametrize(("query", "subject", "countries"), [
    ("Индекс доллара США", "usd-index", {"united-states"}),
    ("Курс доллара США к иене Япония", "usd-jpy", {"united-states", "japan"}),
    ("US dollar index", "usd-index", {"united-states"}),
])
def test_currency_inside_known_fx_subject_keeps_issuer_geography(query, subject, countries):
    intent = parse_intent(query, GEOMETRY)
    assert subject in keys(intent)
    assert intent.countries == frozenset(countries)
    assert not any(key.startswith("search-unit-") for key in keys(intent))


def test_known_quarter_frequency_does_not_become_unsupported_point_period():
    intent = parse_intent("incidents each quarter", GEOMETRY)
    assert intent.error is None
    assert "search-freq-quarterly" in keys(intent)
    assert match_score(intent, names=("Incidents",), metadata="search-freq-quarterly") is not None
    assert match_score(intent, names=("Incidents",), metadata="search-freq-annual") is None
    for query in ("incidents quarter 2024", "incidents q1 2024", "incidents each quarter q1"):
        assert parse_intent(query, GEOMETRY).error == "unsupported_period"


def test_interest_inside_known_monetary_income_subject_is_not_percent_unit():
    intent = parse_intent("дивиденды, проценты и рента", GEOMETRY)
    assert "dividend-interest-rent-income" in keys(intent)
    assert "search-unit-percent" not in keys(intent)
    assert match_score(intent, names=("Dividends, interest, and rent",)) is not None
    for suffix in (" %", " percent", " в процентах"):
        qualified = parse_intent("дивиденды, проценты и рента" + suffix, GEOMETRY)
        assert "search-unit-percent" in keys(qualified)
        assert match_score(qualified, names=("Dividends, interest, and rent",)) is None
    assert "search-unit-percent" in keys(parse_intent("ипотека проценты", GEOMETRY))
