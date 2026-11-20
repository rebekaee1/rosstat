"""Поиск, круг «Туризм» 20.11.2026, зона z6 (правки 8, 17, 24, 50).

«Ночёвки» не должны давать ставки овернайт; страна и регион из раздела «Туризм» приводят к туристским рядам;
туристический налог и курортный сбор различимы в названии выдачи; прежние типовые запросы не ухудшились.
"""
import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tour_client(auth_env, monkeypatch):
    from app.models import (Indicator, IndicatorData, Region, RegionDataPoint, RegionIndicator,
                            WorldCountry, WorldDataPoint, WorldIndicator)

    async def seed():
        async with auth_env['session_maker']() as db:
            ca = WorldCountry(code='CA', slug='canada', name_ru='Канада', name_en='Canada')
            cn = WorldCountry(code='CN', slug='china', name_ru='Китай', name_en='China')
            tr = WorldCountry(code='TR', slug='turkey', name_ru='Турция', name_en='Turkey')
            db.add_all((ca, cn, tr))
            await db.flush()

            def world(country, code, ru, en, unit='%', freq='monthly'):
                return WorldIndicator(country_id=country.id, code=code, name_ru=ru, name_en=en, dataset_id='national-' + code,
                                      slice_hash=code, unit=unit, frequency=freq, is_listed=True, category_ru='Прочее')
            rows = [
                world(ca, 'ca-overnight', 'Ставка овернайт', 'Overnight rate'),
                world(cn, 'cn-overnight', 'Ставка овернайт', 'Overnight rate'),
                world(tr, 'tr-gdp', 'ВВП', 'Gross domestic product', 'USD', 'annual'),
                world(tr, 'tr-population', 'Население', 'Population', 'people', 'annual'),
                world(tr, 'tr-tour-arrivals-russia', 'Туристы из России', 'Tourist arrivals from Russia', 'thousand', 'annual'),
                world(tr, 'tr-unemployment', 'Уровень безработицы', 'Unemployment rate'),
                world(tr, 'tr-cpi', 'Инфляция', 'Inflation rate'),
            ]
            db.add_all(rows)
            nights = Indicator(code='tour-hotel-nights', name='Ночёвки в гостиницах и других средствах размещения',
                               name_en='Nights spent in hotels and other accommodation', unit='млн ночёвок', frequency='annual')
            sanat = Indicator(code='tour-sanatorium-nights', name='Ночёвки в санаториях', name_en='Nights spent in health resorts',
                              unit='млн ночёвок', frequency='annual')
            tax = Indicator(code='tour-tax', name='Туристический налог в России', name_en='Tourist tax in Russia', unit='млн руб.', frequency='quarterly')
            fee = Indicator(code='tour-resort-fee', name='Курортный сбор в России', name_en='Resort fee in Russia', unit='млн руб.', frequency='annual')
            inflation = Indicator(code='cpi', name='Инфляция', name_en='Inflation', unit='%', frequency='monthly')
            key_rate = Indicator(code='key-rate', name='Ключевая ставка ЦБ РФ', name_en='Key rate', frequency='daily')
            gdp = Indicator(code='gdp-nominal', name='ВВП России', name_en='GDP of Russia', unit='млрд руб.', frequency='quarterly')
            unemployment = Indicator(code='unemployment', name='Уровень безработицы', name_en='Unemployment rate', unit='%', frequency='monthly')
            national = [nights, sanat, tax, fee, inflation, key_rate, gdp, unemployment]
            db.add_all(national)
            krasnodar = Region(slug='krasnodarskiy-kray', name='Краснодарский край', kind='region')
            db.add(krasnodar)
            petrol = RegionIndicator(code='ceni-ai95', name='Цены на бензин АИ-95', table_code='1.3', section_num=1, section_name='Цены', unit='руб.')
            medical = RegionIndicator(code='medical-staff', name='Численность врачей', table_code='1.4', section_num=1, section_name='Здравоохранение', unit='чел.')
            tour_region = RegionIndicator(code='tour-hotel-nights-region', name='Ночёвки в гостиницах региона', table_code='9.1',
                                          section_num=9, section_name='Туризм', unit='тыс. ночёвок')
            tour_tax_region = RegionIndicator(code='tour-tax-region', name='Туристический налог региона', table_code='9.2',
                                              section_num=9, section_name='Туризм', unit='млн руб.')
            db.add_all((petrol, medical, tour_region, tour_tax_region))
            await db.flush()
            for row in (petrol, medical, tour_region, tour_tax_region):
                db.add(RegionDataPoint(indicator_id=row.id, region_id=krasnodar.id, year=2024, value=100))
            for row in rows:
                db.add(WorldDataPoint(indicator_id=row.id, date=date(2024, 5, 1), value=5))
            for row in national:
                db.add(IndicatorData(indicator_id=row.id, date=date(2024, 5, 1), value=100))
            await db.commit()
    asyncio.run(seed())
    with TestClient(auth_env['app']) as client:
        yield client


def get(client, q, **kwargs):
    response = client.get('/api/v1/search', params=dict(q=q, **kwargs))
    assert response.status_code == 200, response.text
    return response.json()


def codes(body):
    return [row.get('code') for row in body['results']]


def test_nights_exact_word_before_overnight_rates(tour_client):
    body = get(tour_client, 'ночёвки')
    found = codes(body)
    assert found[0] == 'tour-hotel-nights'
    assert 'tour-sanatorium-nights' in found
    # Слово «овернайт» не синоним ночёвок в гостинице: ставки Канады и Китая в этой выдаче не нужны.
    assert 'ca-overnight' not in found and 'cn-overnight' not in found


def test_overnight_rate_query_still_finds_the_rates(tour_client):
    found = codes(get(tour_client, 'овернайт'))
    assert 'ca-overnight' in found and 'cn-overnight' in found


def test_place_without_section_keeps_old_behaviour(tour_client):
    plain = get(tour_client, 'Турция')
    assert codes(plain) == codes(get(tour_client, 'Турция', section='unknown'))
    assert plain['results'][0]['kind'] == 'country'


def test_turkey_from_tourism_section_leads_with_tourism_rows(tour_client):
    body = get(tour_client, 'Турция', section='tourism')
    rows = body['results']
    assert rows[0]['kind'] == 'country'
    assert rows[1]['code'] == 'tr-tour-arrivals-russia'
    assert {'tr-gdp', 'tr-population'} <= set(codes(body))


def test_region_from_tourism_section_leads_with_tourism_rows(tour_client):
    body = get(tour_client, 'Краснодарский край', section='tourism')
    found = codes(body)
    assert body['results'][0]['kind'] == 'region'
    assert set(found[1:3]) == {'tour-hotel-nights-region', 'tour-tax-region'}
    assert {'ceni-ai95', 'medical-staff'} <= set(found)
    # Без раздела порядок прежний: у всех строк равный счёт, туризм не поднимается.
    assert set(codes(get(tour_client, 'Краснодарский край'))) == set(found)


def test_section_does_not_change_non_place_queries(tour_client):
    assert codes(get(tour_client, 'налог', section='tourism')) == codes(get(tour_client, 'налог'))


@pytest.mark.parametrize('q, first', [
    ('инфляция', 'cpi'),
    ('ключевая ставка', 'key-rate'),
    ('ВВП России', 'gdp-nominal'),
    ('безработица', 'unemployment'),
])
def test_typical_queries_keep_their_headline_first(tour_client, q, first):
    found = [row['code'] for row in get(tour_client, q)['results'] if row.get('code')]
    assert found and found[0] == first, found


def test_cache_key_separates_the_section():
    from app.api.search import _cache_key
    from app.services.search_section import known_section

    assert _cache_key('Турция', 50) != _cache_key('Турция', 50, 'tourism')
    assert _cache_key('Турция', 50) == _cache_key('Турция', 50, None)
    assert known_section('Tourism ') == 'tourism' and known_section('weather') is None and known_section(None) is None
