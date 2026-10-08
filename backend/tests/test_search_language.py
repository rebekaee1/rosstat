"""Natural economic intent retains measure distinctions and explicit qualifiers."""
from collections import Counter

import pytest

from app.services.search_intent import match_score, parse_intent
from app.services.search_language import measure_matches, relevance_bonus, title_frequencies


@pytest.mark.parametrize('query, expected', [
    ('Что происходит с инфляцией', 'cpi'),
    ('курс доллара к рублю', 'usd-rub'),
    ('рост ценн', 'cpi'),
    ('Покажи реальную заработную плату', 'wages-real'),
    ('Can wages buy more or less after inflation', 'wages-real'),
    ('Экспорт товаров превышает импорт или наоборот', 'trade-balance'),
    ('Do goods exports exceed imports or is it the other way around', 'trade-balance'),
    ('Под какой процент банки дают деньги заемщикам', 'credit-rate'),
    ('How many residents live in the country', 'population'),
    ('Сколько зерна собрали с полей', 'grain-harvest'),
    # Real visitor phrasing (2026-10-02): the price verb is a price question, not a title word.
    ('сколько стоил бензин 95 в 2022', 'fuel-ai95'),
    ('сколько стоит дизель', 'fuel-diesel'),
])
def test_questions_keep_typed_economic_subject(query, expected):
    intent = parse_intent(query, [])
    assert intent.error is None
    assert next(group[0] for group in intent.terms if not group[0].startswith("search-")) == expected
    assert len([group for group in intent.terms if not group[0].startswith('search-')]) == 1


@pytest.mark.parametrize('query, noun', [
    ('Покажи inflation magical', 'magical'),
    ('real wages women', 'women'),
    ('births foreigners', 'foreigners'),
    ('mortgage rates fixed', 'fixed'),
    ('cpi without food', 'without'),
])
def test_unknown_and_measure_qualifiers_never_become_stop_words(query, noun):
    intent = parse_intent(query, [])
    assert (noun,) in intent.terms
    assert match_score(intent, code='cpi', names=('Consumer price index',)) is None


@pytest.mark.parametrize('query, expected', [
    ('usd', 'usd-rub'), ('USD', 'usd-rub'), ('dollar rate', 'usd-rub'), ('us dollar exchange rate', 'usd-rub'),
    ('usd rate', 'usd-rub'), ('курс доллара', 'usd-rub'), ('usd rub', 'usd-rub'),
    ('euro rate', 'eur-rub'), ('yuan rate', 'cny-rub'),
])
def test_bare_currency_request_means_exchange_rate(query, expected):
    intent = parse_intent(query, [])
    assert [group[0] for group in intent.terms] == [expected]


def test_currency_word_with_other_words_stays_a_unit_facet():
    keys = [group[0] for group in parse_intent('gdp usd', []).terms]
    assert 'usd-rub' not in keys and 'gdp' in keys
    assert 'usd-rub' not in [group[0] for group in parse_intent('dollar index', []).terms]


@pytest.mark.parametrize('topic, name, expected', [
    ('gas-price', 'Natural gas extraction', False),
    ('gas-price', 'Natural gas price', True),
    ('housing-price', 'Average gasoline prices', False),
    ('housing-price', 'Residential house prices', True),
    ('housing-completions', 'Ввод электрических мощностей', False),
    ('housing-completions', 'Ввод жилья в эксплуатацию', True),
    ('building-permits', 'Разрешения на торговлю', False),
    ('external-debt', 'Private corporate external debt', False),
    ('rent', 'Land rental value', False),
    ('rent', 'Residential housing rent', True),
    ('births', 'Unemployment by country of birth', False),
    ('births', 'Number of live births', True),
    ('labour-productivity', 'Electricity production capacity', False),
    ('labour-productivity', 'Labour productivity per hour worked', True),
    ('household-consumption', 'Government consumption expenditure', False),
    ('household-consumption', 'Household final consumption expenditure', True),
    ('capital-formation', 'Gross fixed capital formation', False),
    ('capital-formation', 'Gross capital formation', True),
    ('mortgage-rate', 'Consumer credit interest rate', False),
    ('mortgage-rate', 'Mortgage interest rate', True),
    ('mortgage-volume', 'Mortgage interest rate', False),
    ('mortgage-volume', 'Mortgage originations value', True),
])
def test_neighbouring_measures_are_not_substituted(topic, name, expected):
    assert measure_matches(((topic,),), code='', names=(name,)) is expected


def test_inverse_frequency_bonus_is_bounded_title_evidence():
    terms = (('grain-harvest', 'grain', 'harvest'),)
    candidates = [{'name_en': 'Grain harvest'}, {'name_en': 'Harvest festival'}, {'name_en': 'School enrollment'}]
    frequencies = title_frequencies(terms, candidates)
    assert frequencies == Counter(grain=1, harvest=2)
    exact_subject = relevance_bonus(terms, names=('Grain harvest',), frequencies=frequencies, count=3)
    unrelated = relevance_bonus(terms, names=('School enrollment',), frequencies=frequencies, count=3)
    assert exact_subject > unrelated == 0
    assert exact_subject < 70  # cannot overpower one required title match


@pytest.mark.parametrize('query, expected', [
    # Круг 10 (звонок 23): разговорные русские вопросы не должны давать пустую выдачу.
    ('что такое инфляция', 'cpi'),
    ('что такое ввп', 'gdp'),
    ('расскажи про инфляцию', 'cpi'),
    ('почему растёт инфляция', 'cpi'),
    ('сколько стоит доллар', 'usd-rub'),
    ('сколько стоит евро', 'eur-rub'),
    ('сколько стоит биткоин', 'btc-usd'),
    ('динамика курса доллара', 'usd-rub'),
    ('что с курсом доллара', 'usd-rub'),
    ('курс доллара сегодня', 'usd-rub'),
    ('инфляция сегодня', 'cpi'),
])
def test_conversational_russian_questions_keep_one_economic_subject(query, expected):
    intent = parse_intent(query, [])
    assert intent.error is None
    subjects = [group[0] for group in intent.terms if not group[0].startswith('search-')]
    assert subjects == [expected]
    assert ('search-subject-price',) not in intent.terms or expected not in ('usd-rub', 'eur-rub', 'btc-usd')


def test_price_of_a_commodity_still_requires_the_price_word():
    intent = parse_intent('цена на золото', [])
    assert ('search-subject-price',) in intent.terms


def test_english_today_is_still_an_unsupported_day_request():
    assert parse_intent('usd rub today', []).error == 'unsupported_period'


@pytest.mark.parametrize('query', ['ставка ФРС', 'Ставка ФРС', 'ключевая ставка ФРС', 'fed funds rate', 'ставка федрезерва'])
def test_fed_rate_phrases_reach_the_us_policy_rate(query):
    intent = parse_intent(query, [])
    assert intent.error is None
    assert [group[0] for group in intent.terms] == ['us-policy-rate']
    names = ('Эффективная ставка по федеральным фондам', 'Federal Funds Effective Rate')
    assert match_score(intent, code='us-policy-rate', names=names, metadata='') is not None
    assert match_score(intent, code='key-rate', names=('Ключевая ставка ЦБ РФ', 'Key rate'), metadata='') is None


def test_key_rate_of_another_country_is_found_by_its_policy_rate_code():
    intent = parse_intent('ключевая ставка', [])
    names = ('Эффективная ставка по федеральным фондам', 'Federal Funds Effective Rate')
    assert match_score(intent, code='us-policy-rate', names=names, metadata='') is not None
    assert match_score(intent, code='key-rate', names=('Ключевая ставка ЦБ РФ', 'Key rate'), metadata='') > match_score(
        intent, code='us-policy-rate', names=names, metadata='')


@pytest.mark.parametrize('query, expected', [
    ('нефть брент', 'brent'),
    ('цена нефти брент', 'brent'),
    ('брент', 'brent'),
    ('курс йены', 'usd-jpy'),
    ('йена', 'usd-jpy'),
])
def test_everyday_russian_names_of_quotes_resolve_to_the_registered_series(query, expected):
    intent = parse_intent(query, [])
    assert intent.error is None
    assert [group[0] for group in intent.terms if not group[0].startswith('search-')] == [expected]
