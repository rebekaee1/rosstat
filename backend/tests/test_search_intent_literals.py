"""Regressions for literal identities, nested geography and lexical boundaries."""
import pytest

from app.services.search_intent import literal_identifier, match_score, parse_intent, phrase, strip_geography


GEOMETRY = [
    dict(key='country:russia', kind='country', slug='russia', name_ru='Россия', name_en='Russia', country_slug='russia', country_code='RU'),
    dict(key='country:iceland', kind='country', slug='iceland', name_ru='Исландия', name_en='Iceland', country_slug='iceland', country_code='IS'),
    dict(key='country:italy', kind='country', slug='italy', name_ru='Италия', name_en='Italy', country_slug='italy', country_code='IT'),
    dict(key='country:india', kind='country', slug='india', name_ru='Индия', name_en='India', country_slug='india', country_code='IN'),
    dict(key='country:austria', kind='country', slug='austria', name_ru='Австрия', name_en='Austria', country_slug='austria', country_code='AT'),
    dict(key='country:united-states', kind='country', slug='united-states', name_ru='США', name_en='United States', country_slug='united-states', country_code='US'),
    dict(key='region:russia:arhangelskaya-oblast', kind='region', slug='arhangelskaya-oblast', name_ru='Архангельская область', name_en='Arkhangelsk Oblast', country_slug='russia'),
    dict(key='region:russia:arhangelskaya-oblast-bez-ao', kind='region', slug='arhangelskaya-oblast-bez-ao', name_ru='Архангельская область (без автономного округа)', name_en='Arkhangelsk Oblast (excluding autonomous area)', country_slug='russia'),
    dict(key='region:united-states:wisconsin', kind='subnational_region', slug='wisconsin', name_ru='Висконсин', name_en='Wisconsin', country_slug='united-states'),
    dict(key='region:united-states:louisiana', kind='subnational_region', slug='louisiana', name_ru='Луизиана', name_en='Louisiana', country_slug='united-states'),
]


@pytest.mark.parametrize('code', ['fuel-ai95-eop-quarter', 'budget-expenditure-yoy-quarter', 'm0-avg-quarter', 'bea-sainc7n-1000', 'born-na-1000-naseleniya', 'rs-ei_bsco_m-bs-csmci-sa-bal', 'IT-industry-2020-quarter'])
def test_identifier_parts_are_not_period_or_aggregation_requests(code):
    intent = parse_intent(code + ' Wisconsin', GEOMETRY)
    assert intent.literal == code.casefold()
    assert intent.error is None
    assert intent.year is None and intent.month is None
    assert intent.terms == ((code.casefold(),),)
    assert intent.regions == frozenset(('region:united-states:wisconsin',))
    assert match_score(intent, code=code, names=('Native economic measure',)) == 1000


@pytest.mark.parametrize('title', ['Численность населения на 1 января', 'Average population at 1 January', 'Average annual rate of change', 'Quarter of birth'])
def test_catalogue_title_stays_atomic_when_authoritatively_recognized(title):
    intent = parse_intent(title + ' Россия', GEOMETRY, literal_content=title)
    assert intent.error is None
    assert intent.year is None and intent.month is None
    assert intent.literal == title.casefold()
    assert intent.terms == ((title.casefold(),),)
    assert match_score(intent, code='native-measure', names=(title,)) == 900


def test_literal_identity_keeps_additional_period_and_unit_constraints():
    intent = parse_intent('fuel-ai95-eop-quarter Russia 2024 %', GEOMETRY)
    assert intent.year == 2024 and intent.error is None
    assert intent.countries == frozenset(('russia',))
    assert ('search-unit-percent',) in intent.terms
    assert match_score(intent, code='fuel-ai95-eop-quarter', names=('Quarter end price',), metadata='rubles') is None
    assert match_score(intent, code='fuel-ai95-eop-quarter', names=('Quarter end price',), metadata='search-unit-percent') == 1000
    assert parse_intent('fuel-ai95-eop-quarter Russia q1 2024', GEOMETRY).error == 'unsupported_period'
    assert parse_intent('fuel-ai95-eop-quarter Russia 2024-13', GEOMETRY).error == 'unsupported_period'


def test_literal_identity_keeps_unknown_qualifier():
    intent = parse_intent('fuel-ai95-eop-quarter magical', GEOMETRY)
    assert match_score(intent, code='fuel-ai95-eop-quarter') is None


def test_longest_nested_geo_preserves_excluded_autonomous_area():
    intent = parse_intent('население Архангельская область (без автономного округа)', GEOMETRY)
    assert intent.regions == frozenset(('region:russia:arhangelskaya-oblast-bez-ao',))
    assert intent.countries == frozenset(('russia',))
    assert parse_intent('население Архангельская область', GEOMETRY).regions == frozenset(('region:russia:arhangelskaya-oblast',))


def test_exact_same_geo_span_preserves_real_ambiguity():
    geometry = GEOMETRY + [
        dict(key='country:georgia', kind='country', slug='georgia', name_ru='Грузия', name_en='Georgia', country_slug='georgia', country_code='GE'),
        dict(key='region:united-states:georgia', kind='subnational_region', slug='georgia', name_ru='Джорджия', name_en='Georgia', country_slug='united-states'),
    ]
    intent = parse_intent('population Georgia', geometry)
    assert intent.countries == frozenset(('georgia', 'united-states'))
    assert intent.regions == frozenset(('region:united-states:georgia',))


def test_function_words_do_not_invent_countries():
    _content, countries, _regions, _corrections = strip_geography('How is it measured in Russia and what is at stake for us?', GEOMETRY)
    assert countries == frozenset(('russia',))


@pytest.mark.parametrize(('code', 'slug'), [('IS', 'iceland'), ('IT', 'italy'), ('IN', 'india'), ('AT', 'austria'), ('US', 'united-states')])
def test_ambiguous_iso_code_remains_available_when_explicit(code, slug):
    assert parse_intent('GDP ' + code, GEOMETRY).countries == frozenset((slug,))


def test_sport_cannot_match_interior_of_transport():
    intent = parse_intent('спорт Луизиана', GEOMETRY)
    assert match_score(intent, code='transport-spending', names=('Транспорт и связь',)) is None
    assert match_score(intent, code='sports-spending', names=('Расходы на спорт',)) is not None
    assert match_score(parse_intent('sport Louisiana', GEOMETRY), code='transport', names=('Transport',)) is None


def test_meaningful_stem_prefix_stays_available():
    intent = parse_intent('население', GEOMETRY)
    assert match_score(intent, code='native-population', names=('Численность населения',)) is not None


def test_natural_hyphenated_alias_is_not_an_identifier():
    assert literal_identifier('year-on-year') is None
    assert ('search-mode-yoy',) in parse_intent('CPI year-on-year Russia', GEOMETRY).terms


def test_geo_only_helper_keeps_intrinsic_native_date_words():
    content, countries, _regions, _corrections = strip_geography('Численность населения на 1 января Россия', GEOMETRY)
    assert phrase(content) == 'численность населения на 1 января'
    assert countries == frozenset(('russia',))


def test_literal_title_country_mention_is_not_an_outer_geo_facet():
    title = 'Migration from India by country of birth'
    intent = parse_intent(title + ' Russia', GEOMETRY, literal_content=title)
    assert intent.literal == title.casefold()
    assert intent.countries == frozenset(('russia',))
    assert intent.terms == ((title.casefold(),),)
    assert match_score(intent, code='native-migration', names=(title,)) == 900


def test_indicator_literal_and_hyphenated_region_slug_are_separate():
    intent = parse_intent('fuel-ai95-eop-quarter arhangelskaya-oblast', GEOMETRY)
    assert intent.literal == 'fuel-ai95-eop-quarter'
    assert intent.terms == (('fuel-ai95-eop-quarter',),)
    assert intent.regions == frozenset(('region:russia:arhangelskaya-oblast',))
    intent = parse_intent('population arhangelskaya-oblast', GEOMETRY)
    assert intent.literal is None
    assert intent.regions == frozenset(('region:russia:arhangelskaya-oblast',))


@pytest.mark.parametrize('query', ['родившиеся на 1000 населения', 'births per 1000 population'])
def test_measure_denominator_is_not_a_year(query):
    intent = parse_intent(query, GEOMETRY)
    assert intent.year is None
    assert intent.error is None
    assert ('search-denominator-1000-persons',) in intent.terms
    intent = parse_intent(query + ' 2024', GEOMETRY)
    assert intent.year == 2024
    assert ('search-denominator-1000-persons',) in intent.terms


def test_ordinary_comparison_words_do_not_fuzzy_match_poland():
    geometry = GEOMETRY + [dict(key='country:poland', kind='country', slug='poland', name_ru='Польша', name_en='Poland', country_slug='poland', country_code='PL')]
    intent = parse_intent('На зарплату можно купить больше или меньше после роста цен Россия', geometry)
    assert intent.countries == frozenset(('russia',))
    assert intent.corrected is None
    assert parse_intent('инфляция Польше', geometry).countries == frozenset(('poland',))


def test_common_republic_name_uses_actual_catalogue_entity():
    geometry = GEOMETRY + [dict(key='region:russia:respublika-mariy-el', kind='region', slug='respublika-mariy-el', name_ru='Республика Марий Эл', name_en='Republic of Mari El', country_slug='russia')]
    for query in ('Сколько зерна собрали с полей Марий Эл', 'grain Mari El'):
        assert parse_intent(query, geometry).regions == frozenset(('region:russia:respublika-mariy-el',))


def test_nonunique_geography_typo_does_not_arbitrarily_choose_place():
    geometry = GEOMETRY + [
        dict(key='region:russia:alaba', kind='region', slug='alaba', name_ru='Alaba', name_en='Alaba', country_slug='russia'),
        dict(key='region:russia:alaca', kind='region', slug='alaca', name_ru='Alaca', name_en='Alaca', country_slug='russia'),
    ]
    intent = parse_intent('population alada', geometry)
    assert not intent.regions
    assert ('alada',) in intent.terms


@pytest.mark.parametrize('query', ['ипотека проценты', 'банки проценты кредит', 'mortgage interest percentage', 'ипотечные ставки в процентах', 'CPI percent %'])
def test_rate_question_keeps_explicit_percentage_unit(query):
    intent = parse_intent(query, GEOMETRY)
    assert intent.terms.count(('search-unit-percent',)) == 1


def test_percentage_word_inside_atomic_native_title_is_not_a_second_facet():
    title = 'Consumer credit percentage point spread'
    intent = parse_intent(title, GEOMETRY, literal_content=title)
    assert ('search-unit-percent',) not in intent.terms
