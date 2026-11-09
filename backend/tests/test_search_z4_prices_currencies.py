"""Z4 (08.11.2026): формы слов товаров, регион по началу слова, латиница валют, свёртка регионов."""
import pytest

from app.services.search_intent import match_score, parse_intent
from app.services.search_price_goods import prepare_price_goods
from app.services.search_regional_groups import group_regional_rows
from app.services.search_region_hint import region_prefix_keys

GEOMETRY = [
    dict(key='country:russia', kind='country', slug='russia', name_ru='Россия', name_en='Russia', country_slug='russia', country_code='RU'),
    dict(key='region:russia:moskva', kind='region', slug='moskva', name_ru='Москва', name_en='Moscow', country_slug='russia'),
    dict(key='region:russia:novosibirskaya-oblast', kind='region', slug='novosibirskaya-oblast', name_ru='Новосибирская область', name_en='Novosibirsk Oblast', country_slug='russia'),
    dict(key='region:russia:novgorodskaya-oblast', kind='region', slug='novgorodskaya-oblast', name_ru='Новгородская область', name_en='Novgorod Oblast', country_slug='russia'),
    dict(key='region:russia:rostovskaya-oblast', kind='region', slug='rostovskaya-oblast', name_ru='Ростовская область', name_en='Rostov Oblast', country_slug='russia'),
    dict(key='region:russia:tverskaya-oblast', kind='region', slug='tverskaya-oblast', name_ru='Тверская область', name_en='Tver Oblast', country_slug='russia'),
]

EGGS = 'Средняя цена: яйца куриные, рублей за 10 штук'


def _score(query, code, name):
    return match_score(parse_intent(query, GEOMETRY), code=code, names=(name,))


@pytest.mark.parametrize('query', ['яйца', 'цена яиц', 'стоимость яиц', 'средняя цена яйца', 'сколько стоят яйца', 'яйцо цена'])
def test_egg_forms_find_the_price_series_without_average_mode(query):
    intent = parse_intent(query, GEOMETRY)
    assert intent.error is None
    assert all(not term[0].startswith('search-mode-') for term in intent.terms)
    assert _score(query, 'ceni-yaytsa', EGGS) is not None


def test_average_price_of_goods_with_region_keeps_region_and_drops_average_mode():
    intent = parse_intent('средняя цена яйца москва', GEOMETRY)
    assert intent.regions == frozenset(('region:russia:moskva',))
    assert [term for term in intent.terms if term[0].startswith('search-')] == []


def test_average_price_of_non_goods_is_unchanged():
    assert prepare_price_goods('средняя цена жилья') == 'средняя цена жилья'


@pytest.mark.parametrize('query, code, name', [
    ('аренда однокомнатной квартиры', 'ceni-arenda-1k', 'Средняя цена: аренда однокомнатной квартиры у частных лиц, рублей в месяц'),
    ('проезд в метро', 'ceni-proezd-metro', 'Средняя цена: проезд в метро, рублей за поездку'),
    ('коммуналка', 'ceni-otoplenie', 'Средняя цена: отопление, рублей за Гкал'),
    ('жкх', 'ceni-voda-holodnaya', 'Средняя цена: водоснабжение холодное, рублей за м3'),
    ('стоимость хлеба', 'ceni-hleb-rzhanoy', 'Средняя цена: хлеб из ржаной и ржано-пшеничной муки, рублей за кг'),
    ('цена молока', 'ceni-moloko', 'Средняя цена: молоко питьевое пастеризованное 2,5–3,2% жирности, рублей за литр'),
])
def test_everyday_phrases_reach_price_series(query, code, name):
    assert _score(query, code, name) is not None


def test_goods_do_not_match_unrelated_series():
    assert _score('цена яиц', 'cpi', 'Индекс потребительских цен') is None


def test_region_prefix_and_city_name_pick_regions():
    intent = parse_intent('яйца нов', GEOMETRY)
    assert intent.regions == frozenset(('region:russia:novosibirskaya-oblast', 'region:russia:novgorodskaya-oblast'))
    city = parse_intent('хлеб новосибирск', GEOMETRY)
    assert city.regions == frozenset(('region:russia:novosibirskaya-oblast',))
    assert parse_intent('молоко тверь', GEOMETRY).regions == frozenset(('region:russia:tverskaya-oblast',))


def test_short_prefix_needs_a_price_good_and_never_hijacks_economy_words():
    assert parse_intent('рост ввп', GEOMETRY).regions == frozenset()
    assert region_prefix_keys('рост', GEOMETRY, goods=False) == frozenset()
    assert region_prefix_keys('рост', GEOMETRY, goods=True) == frozenset(('region:russia:rostovskaya-oblast',))


@pytest.mark.parametrize('query, iso', [
    ('uzbek', 'uzs'), ('uzbek som', 'uzs'), ('uzbekistani som', 'uzs'), ('dirham', 'aed'), ('dram', 'amd'),
    ('tenge', 'kzt'), ('hryvnia', 'uah'), ('kyrgyz som', 'kgs'), ('baht', 'thb'),
])
def test_latin_currency_names_find_their_rate(query, iso):
    intent = parse_intent(query, GEOMETRY)
    assert intent.error is None
    assert len(intent.terms) == 1 and f'{iso} rub' in intent.terms[0]


def test_shared_currency_word_is_not_a_single_currency():
    assert parse_intent('som', GEOMETRY).terms == (('som',),)


def _row(slug, code='ceni-yaytsa'):
    return dict(key=f'region:{slug}:{code}', kind='region_indicator', code=code, region_slug=slug, region_name=slug.title(),
        path=f'/russia/region/{slug}/{code}', navigation='spa', frequency='monthly', score=100)


def test_many_regions_become_one_group_with_russia_on_top():
    rows = [_row('altay'), _row('amur'), _row('moskva'), {'key': 'ru:cpi', 'kind': 'russia', 'code': 'cpi'}]
    out = group_regional_rows(rows, has_regions=False, locale='ru')
    assert [item['key'] for item in out] == ['region-group:ceni-yaytsa', 'ru:cpi']
    lead = out[0]
    assert lead['region_name'] == 'Россия' and lead['path'] == '/russia/region-rating/ceni-yaytsa'
    assert lead['regional_group']['count'] == 3
    assert [entry['slug'] for entry in lead['regional_group']['regions']] == ['moskva', 'altay', 'amur']


def test_named_region_and_single_rows_stay_as_they_are():
    rows = [_row('moskva'), _row('altay')]
    assert group_regional_rows(rows, has_regions=True, locale='ru') == rows
    assert group_regional_rows(rows[:1], has_regions=False, locale='ru') == rows[:1]
