"""Hermetic synthetic paths for geography, periods and truthful coverage."""
import asyncio
from datetime import date
import pytest
from fastapi.testclient import TestClient
from app.services.search_intent import match_score, parse_intent

GEOMETRY = [
    dict(key='country:germany', kind='country', slug='germany', name_ru='Германия', name_en='Germany', country_slug='germany', country_code='DE'),
    dict(key='country:united-states', kind='country', slug='united-states', name_ru='США', name_en='United States', country_slug='united-states', country_code='US'),
    dict(key='region:russia:moskva', kind='region', slug='moskva', name_ru='г. Москва', name_en='Moscow', country_slug='russia'),
    dict(key='region:russia:moskovskaya-oblast', kind='region', slug='moskovskaya-oblast', name_ru='Московская область', name_en='Moscow Oblast', country_slug='russia'),
]

@pytest.mark.parametrize('q', ['CPI Germany', 'инфляция Германии', 'инфляция в Германии', 'cpi DE'])
def test_country_facet(q):
    intent = parse_intent(q, GEOMETRY)
    assert intent.countries == frozenset(('germany',))
    assert len(intent.terms) == 1

def test_specific_alias():
    intent = parse_intent('ввп на душу Германия', GEOMETRY)
    assert match_score(intent, code='gdp', names=('Gross domestic product',)) is None
    assert match_score(intent, code='gdp-per-capita', names=('GDP per capita',)) is not None

def test_longest_geo():
    assert parse_intent('population Moscow Oblast', GEOMETRY).regions == frozenset(('region:russia:moskovskaya-oblast',))

@pytest.mark.parametrize('q', ['зарплата Москва 2024', 'зарплата Москвы 2024', 'CPI Germany', 'инфляция Германии'])
def test_valid_geo_spelling_is_not_a_correction(q):
    assert parse_intent(q, GEOMETRY).corrected is None

@pytest.mark.parametrize('q', ['мрот', 'minimum wage'])
def test_minimum_wage_not_average(q):
    assert match_score(parse_intent(q, GEOMETRY), code='wages', names=('Average wages', 'Средняя зарплата')) is None

def test_deposits_not_key_rate():
    intent = parse_intent('ставка по вкладам', GEOMETRY)
    assert match_score(intent, code='key-rate', names=('Ключевая ставка Банка России',)) is None
    assert match_score(intent, code='deposit-rate', names=('Ставка по вкладам',)) is not None

def test_layout_and_raw():
    intent = parse_intent('byakzwbz', GEOMETRY)
    assert intent.query == 'byakzwbz'
    assert intent.corrected == 'инфляция'
    assert match_score(intent, code='cpi') is not None
    assert parse_intent('CPI', GEOMETRY).corrected is None
    assert parse_intent('ddg', GEOMETRY).corrected == 'ввп'

def test_issuer_and_institution_aliases():
    intent = parse_intent('Central bank rate', GEOMETRY)
    assert match_score(intent, code='key-rate', names=('Ключевая ставка',)) is not None
    assert match_score(intent, code='deposit-rate', names=('Bank of Russia deposit interest rate',)) is None

def test_shared_family_mode_metadata():
    from app.services.search import _family_metadata
    metadata = _family_metadata()['usd-rub-yoy-year']
    assert 'search-mode-yoy' in metadata
    assert 'search-mode-pop' in metadata

def test_geography_typo_and_conflicting_frequency():
    geometry = GEOMETRY + [dict(key='region:russia:respublika-bashkortostan', kind='region', slug='respublika-bashkortostan', name_ru='Республика Башкортостан', name_en='Republic of Bashkortostan', country_slug='russia')]
    intent = parse_intent('Башкортостар', geometry)
    assert intent.regions == frozenset(('region:russia:respublika-bashkortostan',))
    assert intent.corrected == 'башкортостан'
    assert parse_intent('population annual monthly', geometry).error == 'unsupported_query'

def test_base_year_not_period():
    intent = parse_intent('cpi Germany 2015=100', GEOMETRY)
    assert intent.year is None
    assert ('2015=100', '2015 100', 'i15') in intent.terms

@pytest.mark.parametrize('q', ['CPI Germany 2020 2024', 'CPI May', 'CPI 2024-13', 'CPI 2024-01-03', 'CPI q1 2024'])
def test_unsupported_period(q):
    assert parse_intent(q, GEOMETRY).error == 'unsupported_period'

def test_unknown_term_retained():
    assert match_score(parse_intent('CPI magical', GEOMETRY), code='cpi') is None

@pytest.fixture
def search_client(auth_env, monkeypatch):
    from app.models import Indicator, IndicatorData, Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint, SubnationalDataPoint, SubnationalIndicator, SubnationalRegion, WorldCountry, WorldDataPoint, WorldIndicator
    async def seed():
        async with auth_env['session_maker']() as db:
            de = WorldCountry(code='DE', slug='germany', name_ru='Германия', name_en='Germany')
            us = WorldCountry(code='US', slug='united-states', name_ru='США', name_en='United States')
            dead = WorldCountry(code='XX', slug='inactive', name_ru='Inactive', name_en='Inactive', is_active=False)
            br = WorldCountry(code='BR', slug='brazil', name_ru='Бразилия', name_en='Brazil', is_active=True)
            jp = WorldCountry(code='JP', slug='japan', name_ru='Япония', name_en='Japan', is_active=True)
            db.add_all((de, us, dead, br, jp))
            await db.flush()
            def world(country, code, listed=True):
                return WorldIndicator(country_id=country.id, code=code, name_ru='Consumer price index', name_en='Consumer price index', dataset_id='national-'+code, slice_hash=code, unit='%', frequency='monthly', is_listed=listed, category_ru='Prices')
            rows = [world(de, 'de-cpi'), world(us, 'us-cpi'), world(de, 'de-hidden-cpi', False), world(de, 'de-cpi-zero'), world(de, 'de-cpi-empty'), world(dead, 'xx-cpi')]
            ipca = world(br, 'br-cpi-ipca')
            # SQLite's built-in LOWER lacks Cyrillic case-folding; PostgreSQL
            # integration corpus separately exercises the real title casing.
            ipca.name_ru = 'индекс потребительских цен IPCA (к предыдущему месяцу)'
            ipca.name_en = 'IPCA consumer price index (month-on-month)'
            ipca_yoy = world(br, 'br-cpi-ipca-yoy')
            ipca_yoy.name_ru = 'Инфляция IPCA за 12 месяцев'
            ipca_yoy.name_en = 'IPCA 12-month accumulated change'
            rows += [ipca, ipca_yoy]
            unemployment = world(us, 'us-unemployment-rate')
            unemployment.name_ru = 'уровень безработицы'
            unemployment.name_en = 'Unemployment rate'
            unemployment.unit = 'PC_ACT'
            rows.append(unemployment)
            freq_monthly = world(de, 'de-frequency-month')
            freq_monthly.dataset_id = 'fixture_freq_m'
            freq_monthly.frequency = 'monthly'
            freq_monthly.points_count = 100
            freq_quarterly = world(de, 'de-frequency-quarter', False)
            freq_quarterly.dataset_id = 'fixture_freq_q'
            freq_quarterly.frequency = 'quarterly'
            freq_quarterly.points_count = 20
            hicp = world(de, 'de-hicp-index')
            hicp.dataset_id, hicp.unit, hicp.points_count = 'prc_hicp_midx', 'I25', 100
            hicp_yoy = world(de, 'de-hicp-annual-change', False)
            hicp_yoy.dataset_id, hicp_yoy.unit, hicp_yoy.points_count = 'prc_hicp_manr', 'RCH_A', 100
            rows += [freq_monthly, freq_quarterly, hicp, hicp_yoy]
            yen = world(jp, 'jp-fx-usd-jpy')
            yen.name_ru = 'курс доллара США к иене'
            yen.name_en = 'Japanese yen per US dollar'
            rows.append(yen)
            annual_change = world(de, 'de-cpi-annual-rate')
            annual_change.name_en = 'Annual rate of change in consumer prices'
            rows.append(annual_change)
            db.add_all(rows)
            ru = Indicator(code='cpi', name='Индекс потребительских цен', name_en='Consumer price index', unit='%')
            wages = Indicator(code='wages', name='Средняя зарплата', name_en='Average wages', unit='rubles')
            sibling = Indicator(code='fuel-ai95-yoy', name='АИ95 YoY', name_en='AI95 YoY', is_listed=False)
            extras = [
                Indicator(code='key-rate', name='Ключевая ставка ЦБ РФ', frequency='daily'),
                Indicator(code='key-rate-avg-quarter', name='Ключевая ставка ЦБ РФ — средняя за квартал', frequency='quarterly', is_listed=False),
                Indicator(code='exports', name='Экспорт товаров', frequency='quarterly'),
                Indicator(code='exports-sum-year', name='Экспорт товаров — за год', frequency='annual', is_listed=False),
                Indicator(code='usd-rub', name='Курс доллара США', frequency='daily'),
                Indicator(code='cny-rub', name='Курс китайского юаня', frequency='daily'),
                Indicator(code='usd-rub-yoy-year', name='Курс доллара США — к соответствующему году прошлого года', frequency='annual', is_listed=False),
                Indicator(code='usd-index', name='Индекс доллара США', frequency='daily'),
                Indicator(code='ust-10y', name='Доходность 10-летних гособлигаций США', frequency='daily'),
                Indicator(code='fuel-ai95', name='Цена бензина АИ-95', frequency='weekly'),
                Indicator(code='unemployment', name='Уровень безработицы', frequency='monthly'),
                Indicator(code='unemployment-avg-year', name='Уровень безработицы — средняя за год', frequency='annual', is_listed=False),
                Indicator(code='imports', name='Импорт товаров', frequency='quarterly'),
                Indicator(code='imports-sum-year', name='Импорт товаров — за год', frequency='annual', is_listed=False),
                Indicator(code='innovation-activity', name='Уровень инновационной активности', frequency='annual'),
                Indicator(code='brent', name='Нефть Brent', name_en='Brent crude oil', frequency='daily'),
                Indicator(code='btc-usd', name='Биткоин', name_en='Bitcoin', frequency='daily'),
            ]
            db.add_all((ru, wages, sibling, *extras))
            moscow = Region(slug='moskva', name='г. Москва', kind='region')
            primorye = Region(slug='primorskiy-kray', name='Приморский край', kind='region')
            ghost = Region(slug='ghost-region', name='Ghost region', kind='region')
            pop = RegionIndicator(code='population', name='Население', table_code='1.1', section_num=1, section_name='Population', unit='people')
            monthly = RegionIndicator(code='monthly-wages', name='Зарплата', table_code='1.2', section_num=1, section_name='Labor', unit='rubles')
            fuel = RegionIndicator(code='ceni-ai95', name='Цены на бензин АИ-95', table_code='1.3', section_num=1, section_name='Prices', unit='rubles')
            students = RegionIndicator(code='students', name='Численность студентов', table_code='1.4', section_num=1, section_name='Education', unit='people')
            primary_housing = RegionIndicator(code='srednie-tseny-na-pervichnom-rynke-zhilya', name='Средние цены на первичном рынке жилья', table_code='1.5', section_num=1, section_name='Housing', unit='рублей за квадратный метр общей площади')
            secondary_housing = RegionIndicator(code='srednie-tseny-na-vtorichnom-rynke-zhilya', name='Средние цены на вторичном рынке жилья', table_code='1.6', section_num=1, section_name='Housing', unit='рублей за квадратный метр общей площади')
            state = SubnationalRegion(country_code='US', slug='california', name_ru='Калифорния', name_en='California')
            sub = SubnationalIndicator(country_code='US', code='state-population', name_ru='Население', name_en='Population', series_template='fixture', frequency='annual', unit='people')
            db.add_all((moscow, primorye, ghost, pop, monthly, fuel, students, primary_housing, secondary_housing, state, sub))
            await db.flush()
            for row, value in zip(rows, (110, 120, 10, 0, None, 150, 4, 5, 3, 110, 120, 110, 5, 140, 5)):
                if value is not None:
                    db.add(WorldDataPoint(indicator_id=row.id, date=date(2024, 5, 1), value=value))
            for row in (ru, wages, sibling, *extras):
                db.add(IndicatorData(indicator_id=row.id, date=date(2024, 5, 1), value=100))
            db.add(RegionDataPoint(indicator_id=pop.id, region_id=moscow.id, year=2024, value=0))
            db.add(RegionMonthlyPoint(indicator_id=monthly.id, region_id=moscow.id, month=202405, value=100))
            db.add(RegionMonthlyPoint(indicator_id=fuel.id, region_id=moscow.id, month=202405, value=100))
            db.add(RegionDataPoint(indicator_id=students.id, region_id=moscow.id, year=2024, value=100))
            db.add(RegionDataPoint(indicator_id=primary_housing.id, region_id=primorye.id, year=2024, value=150000))
            db.add(RegionDataPoint(indicator_id=secondary_housing.id, region_id=moscow.id, year=2024, value=250000))
            db.add(SubnationalDataPoint(indicator_id=sub.id, region_id=state.id, period=date(2024, 1, 1), value=10))
            await db.commit()
    asyncio.run(seed())
    with TestClient(auth_env['app']) as client:
        yield client

def get(client, q, **kwargs):
    response = client.get('/api/v1/search', params=dict(q=q, **kwargs))
    assert response.status_code == 200, response.text
    return response.json()

@pytest.mark.parametrize('q', ['cpi US', 'CPI USA', 'инфляция США'])
def test_us_not_russian_cpi(search_client, q):
    body = get(search_client, q)
    assert body['results']
    assert all(row['country_slug'] == 'united-states' for row in body['results'])
    assert any(row.get('code') == 'us-cpi' for row in body['results'])

def test_country_entity(search_client):
    row = get(search_client, 'Германия')['results'][0]
    assert row['path'] == '/germany'
    assert row['kind'] == 'country'

def test_world_period_coverage(search_client):
    rows = get(search_client, 'CPI Germany 2024')['results']
    assert rows
    assert all(row['path'].endswith('/2024') and row['navigation'] == 'document' for row in rows)
    assert not get(search_client, 'CPI Germany 1999')['results']

def test_hidden_world(search_client):
    assert get(search_client, 'de-hidden-cpi')['results'][0]['code'] == 'de-hidden-cpi'
    assert not get(search_client, 'de-hidden-cpi 2024')['results']

def test_world_publication_gate(search_client):
    codes = {row.get('code') for row in get(search_client, 'CPI')['results']}
    assert not codes.intersection(('de-cpi-zero', 'de-cpi-empty', 'xx-cpi'))

def test_region_year_zero_and_no_phantom(search_client):
    row = get(search_client, 'population Moscow 2024')['results'][0]
    assert row['path'] == '/russia/region/moskva/population/2024'
    assert row['navigation'] == 'document'
    assert not get(search_client, 'population Moscow 1999')['results']

def test_monthly_region_without_annual(search_client):
    rows = get(search_client, 'wages Moscow')['results']
    assert any(row['path'] == '/russia/region/moskva/monthly-wages' and row['frequency'] == 'monthly' for row in rows)
    assert not get(search_client, 'wages Moscow 2024')['results']

def test_subnational(search_client):
    rows = get(search_client, 'population California')['results']
    assert any(row['path'] == '/united-states/region/california/state-population' for row in rows)
    assert all(row['country_slug'] == 'united-states' for row in rows)
    assert all(row['country_name'] == 'США' for row in rows)

@pytest.mark.parametrize('q,code,mode', [
    ('Ключевая ставка ЦБ РФ средняя по кварталам', 'key-rate-avg-quarter', 'avg-quarter'),
    ('Экспорт товаров уровень по годам', 'exports-sum-year', 'sum-year'),
    ('Курс доллара США год к году по годам', 'usd-rub-yoy-year', 'yoy-year'),
    ('Уровень безработицы средняя по годам', 'unemployment-avg-year', 'avg-year'),
    ('Импорт товаров уровень по годам', 'imports-sum-year', 'sum-year'),
])
def test_materialized_modes(search_client, q, code, mode):
    rows = get(search_client, q)['results']
    assert rows[0]['code'] == code
    assert rows[0]['path'].endswith('?mode=' + mode)
    assert rows[0]['navigation'] == 'spa'

@pytest.mark.parametrize('q,code', [('Индекс доллара США', 'usd-index'), ('Доходность 10-летних гособлигаций США', 'ust-10y')])
def test_market_issuer_exception(search_client, q, code):
    rows = get(search_client, q)['results']
    assert rows[0]['code'] == code
    assert rows[0]['country_slug'] == 'united-states'
    assert all(row.get('code') != 'cpi' for row in rows)

@pytest.mark.parametrize('q,code', [
    ('Индекс потребительских цен IPCA (к предыдущему месяцу) Бразилия', 'br-cpi-ipca'),
    ('IPCA 12-month accumulated change Brazil', 'br-cpi-ipca-yoy'),
])
def test_long_names_with_short_required_terms(search_client, q, code):
    assert get(search_client, q)['results'][0]['code'] == code

def test_localized_geography_labels(search_client):
    body = search_client.get('/api/v1/search', params=dict(q='population California'), headers={'X-FE-Locale': 'en'}).json()
    assert all(row['country_name'] == 'United States' for row in body['results'])
    rows = get(search_client, 'wages Moscow')['results']
    assert all(row['country_name'] == 'Россия' for row in rows)

@pytest.mark.parametrize('q,code', [('Уровень безработицы США', 'us-unemployment-rate'), ('количество студентов Moscow', 'students')])
def test_native_level_and_equivalent_counts(search_client, q, code):
    assert get(search_client, q)['results'][0]['code'] == code

@pytest.mark.parametrize('q,path,frequency', [
    ('population California annual', '/united-states/region/california/state-population', 'annual'),
    ('population Moscow yearly', '/russia/region/moskva/population', 'annual'),
    ('wages Moscow по месяцам', '/russia/region/moskva/monthly-wages', 'monthly'),
])
def test_regional_frequency_requires_matching_facts(search_client, q, path, frequency):
    rows = get(search_client, q)['results']
    assert rows[0]['path'] == path
    assert rows[0]['frequency'] == frequency
    assert not get(search_client, q.replace('annual', 'monthly').replace('yearly', 'monthly').replace('по месяцам', 'по годам'))['results']

def test_specific_national_fuel_before_regional_instances(search_client):
    assert get(search_client, 'аи95')['results'][0]['code'] == 'fuel-ai95'
    assert get(search_client, 'аи95 Moscow')['results'][0]['code'] == 'ceni-ai95'

def test_conflicting_geography_is_explicit(search_client):
    body = get(search_client, 'CPI Germany USA')
    assert body['results'] == []
    assert body['reason'] == 'ambiguous_geography'

def test_known_fx_pair_keeps_quoted_country(search_client):
    rows = get(search_client, 'Курс доллара США к иене Япония')['results']
    assert rows[0]['code'] == 'jp-fx-usd-jpy'
    assert all(row['country_slug'] == 'japan' for row in rows)

@pytest.mark.parametrize('q,code', [('Курс доллара США в России', 'usd-rub'), ('Курс юаня Китай Россия', 'cny-rub')])
def test_ruble_pairs_distinguish_issuer_from_quoted_country(search_client, q, code):
    rows = get(search_client, q)['results']
    assert rows[0]['code'] == code
    assert all(row['country_slug'] == 'russia' for row in rows)
    assert get(search_client, q + ' Germany')['reason'] == 'ambiguous_geography'

def test_exact_russian_headline_not_drowned_by_world_names(search_client):
    assert get(search_client, 'Уровень безработицы')['results'][0]['code'] == 'unemployment'

def test_world_batch_resolution_agrees_with_authoritative_resolver(search_client, auth_env):
    from sqlalchemy import select
    from app.models import WorldCountry, WorldIndicator
    from app.data.legacy_redirects import resolve_world_frequency_sibling
    from app.services.search_paths import world_search_paths
    async def check():
        async with auth_env['session_maker']() as db:
            country = (await db.execute(select(WorldCountry).where(WorldCountry.slug == 'germany'))).scalar_one()
            rows = list((await db.execute(select(WorldIndicator).where(WorldIndicator.country_id == country.id))).scalars())
            batch = await world_search_paths(db, [('germany', row) for row in rows])
            for row in rows:
                assert batch[('germany', row.code)] == await resolve_world_frequency_sibling(db, 'germany', row.code)
            assert batch[('germany', 'de-frequency-quarter')] == '/germany/indicator/de-frequency-month?mode=level-quarterly'
            assert batch[('germany', 'de-hicp-annual-change')] == '/germany/indicator/de-hicp-index?mode=yoy-monthly'
    asyncio.run(check())

def test_search_query_count_is_bounded(search_client, auth_env):
    from sqlalchemy import event
    engine = auth_env['session_maker'].kw['bind'].sync_engine
    statements = []
    def record(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', record)
    try:
        body = get(search_client, 'CPI Germany', limit=100)
        assert body['results']
        assert len(statements) <= 12
        statements.clear()
        body = get(search_client, 'Russia')
        assert not any(row['kind'] == 'region' for row in body['results'])
        assert len(statements) <= 12
    finally:
        event.remove(engine, 'before_cursor_execute', record)

def test_empty_literal_metachars(search_client):
    for q in (' ', '%', '_', '100%', 'cpi % magical'):
        assert not get(search_client, q)['results']

def test_limit_contract(search_client):
    body = get(search_client, 'cpi', limit=1)
    assert body['total'] == len(body['results']) == 1
    assert body['has_more'] is True
    assert body['version'] == 'federated-v2'
    for params in (dict(q='cpi', limit=101), dict(q='a'*257)):
        assert search_client.get('/api/v1/search', params=params).status_code == 422

def test_mrot_empty(search_client):
    assert not get(search_client, 'мрот')['results']

def test_annual_change_is_not_annual_frequency(search_client):
    intent = parse_intent('Annual rate of change in consumer prices Germany', GEOMETRY)
    assert ('search-mode-yoy',) in intent.terms
    assert ('search-freq-annual',) not in intent.terms
    rows = get(search_client, 'Annual rate of change in consumer prices Germany')['results']
    assert rows[0]['code'] == 'de-cpi-annual-rate'
    assert rows[0]['frequency'] == 'monthly'

def test_percent_unit_is_not_discarded(search_client):
    assert ('search-unit-percent',) in parse_intent('salary %', GEOMETRY).terms
    assert not get(search_client, 'salary %')['results']
    assert not get(search_client, 'population California %')['results']
    rows = get(search_client, 'CPI Germany %')['results']
    assert rows
    assert all(row.get('code') != 'de-hicp-index' for row in rows)
    assert not get(search_client, 'wages Moscow %')['results']
    assert not get(search_client, 'Средняя зарплата %')['results']

def test_native_level_titles_and_percentage_points(search_client):
    from app.services.search import _unit_metadata
    assert get(search_client, 'Уровень инновационной активности')['results'][0]['code'] == 'innovation-activity'
    assert get(search_client, 'population California level')['results'][0]['code'] == 'state-population'
    assert get(search_client, 'population Moscow level')['results'][0]['code'] == 'population'
    assert _unit_metadata('PC_PNT', 'процентных пунктов') == 'search-unit-percentage-point'
    assert _unit_metadata('Percentage points') == 'search-unit-percentage-point'
    assert _unit_metadata('PC_ACT') == 'search-unit-percent'

@pytest.mark.parametrize('locale', ['ru', 'en'])
def test_global_market_labels_do_not_claim_russian_statistics(search_client, locale):
    labels = {'usd-index': 'United States' if locale == 'en' else 'США',
        'ust-10y': 'United States' if locale == 'en' else 'США',
        'brent': 'Global markets' if locale == 'en' else 'Мировой рынок',
        'btc-usd': 'Global markets' if locale == 'en' else 'Мировой рынок'}
    for code, expected in labels.items():
        body = search_client.get('/api/v1/search', params={'q': code}, headers={'X-FE-Locale': locale}).json()
        row = next(row for row in body['results'] if row['code'] == code)
        assert row['country_name'] == expected
        assert row['key'] == 'ru:' + code
        assert '/indicator/' + code in row['path']

@pytest.mark.parametrize('query,slug,code', [
    ('Средние цены на первичном рынке жилья primorskiy-kray', 'primorskiy-kray', 'srednie-tseny-na-pervichnom-rynke-zhilya'),
    ('Средние цены на вторичном рынке жилья г. Москва moskva', 'moskva', 'srednie-tseny-na-vtorichnom-rynke-zhilya'),
])
def test_native_average_housing_prices_are_not_aggregation_modes(search_client, query, slug, code):
    intent = parse_intent(query, GEOMETRY)
    assert ('search-mode-avg',) not in intent.terms
    rows = get(search_client, query)['results']
    assert rows[0]['code'] == code
    assert rows[0]['path'] == f'/russia/region/{slug}/{code}'
    assert all(row['region_slug'] == slug for row in rows)
    assert not get(search_client, query + ' 1999')['results']
    # A separately requested temporal average still remains mandatory. The
    # native annual market mean does not invent an aggregation-mode destination.
    assert not get(search_client, query + ' средняя по годам')['results']


def test_search_endpoint_caches_by_normalized_query_and_locale(monkeypatch):
    """Repeated visitor queries are served from the cache, per locale and limit."""
    import asyncio
    from app.api import search as api

    store, calls = {}, []

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl=None):
        store[key] = value

    async def fake_search(db, q, *, limit):
        calls.append(q)
        return {"results": [], "total": 0, "has_more": False, "version": "x"}

    monkeypatch.setattr(api, "cache_get", fake_get)
    monkeypatch.setattr(api, "cache_set", fake_set)
    monkeypatch.setattr(api, "federated_search", fake_search)
    run = lambda q, limit=50: asyncio.run(api.search(q=q, limit=limit, db=None))
    run("Дизель"); run("  дизель "); run("дизель", limit=20)
    assert calls == ["Дизель", "дизель"]   # same normalized query/limit is one computation
    assert len(store) == 2
