"""Круг 12, BACK2 П1: «страна + понятие» поднимает главный ряд понятия страны (ВВП США, ВВП Китая, ...).

Раньше запрос «ввп сша» отдавал сотню составляющих BEA («Состав ВВП: Оплата труда»), а главный
ряд (ВВП в текущих долларах МВФ, `us-weo-ngdpd`) обрезался лимитом кандидатов раньше, чем получал счёт.
"""
import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

CLUTTER = 140  # больше бюджета кандидатов (100): главный ряд по алфавиту кода идёт после мусора


@pytest.fixture
def headline_client(auth_env):
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def seed():
        async with auth_env['session_maker']() as db:
            us = WorldCountry(code='US', slug='united-states', name_ru='США', name_en='United States')
            de = WorldCountry(code='DE', slug='germany', name_ru='Германия', name_en='Germany')
            cn = WorldCountry(code='CN', slug='china', name_ru='Китай', name_en='China')
            fr = WorldCountry(code='FR', slug='france', name_ru='Франция', name_en='France')
            db.add_all((us, de, cn, fr))
            await db.flush()
            rows = []

            def world(country, code, name_en, *, name_ru=None, unit='%', frequency='annual', dataset='national'):
                row = WorldIndicator(country_id=country.id, code=code, name_ru=name_ru or name_en, name_en=name_en,
                    dataset_id=dataset, slice_hash=code, unit=unit, frequency=frequency, is_listed=True, category_ru='Test')
                rows.append(row)
                return row

            for i in range(CLUTTER):  # составляющие BEA: то же слово «GDP» в названии, код раньше по алфавиту
                world(us, f'us-bea-sagdp1-{i:03d}', f'State GDP overview: Compensation {i} (GDP component)')
                world(de, f'de-bea-sagdp1-{i:03d}', f'GDP and main components: item {i}', frequency='quarterly')
            world(us, 'us-weo-ngdpd', 'Gross domestic product at current prices', unit='billion $')
            world(us, 'us-weo-ngdpdpc', 'Gross domestic product per capita at current prices', unit='$ per person')
            world(us, 'us-gdp-per-capita-real', 'Real Gross Domestic Product Per Capita', frequency='quarterly')
            world(de, 'de-weo-ngdpd', 'Gross domestic product at current prices', unit='billion $')
            world(de, 'de-namq_10_gdp-b1gq-sca-clv15-meur', 'Gross domestic product (GDP) and main components', frequency='quarterly', dataset='namq_10_gdp')
            world(cn, 'cn-weo-ngdpd', 'Gross domestic product at current prices', unit='billion $')
            world(cn, 'cn-weo-ngdpdpc', 'Gross domestic product per capita at current prices', unit='$ per person')
            world(cn, 'cn-gdp-real', 'Gross domestic product at constant prices (quarterly)', frequency='quarterly')
            world(cn, 'cn-weo-ggxwdg', 'General government gross debt, % of GDP')
            for i in range(CLUTTER):
                world(de, f'de-lfsi_jhh_a-sc{i:03d}-pc', f'Population in jobless private households {i}')
                world(fr, f'fr-lfsi_jhh_a-sc{i:03d}-pc', f'Population in jobless private households {i}')
            world(de, 'de-une_rt_m-total-sa-t-pc-act', 'Unemployment by sex and age - monthly data', unit='PC_ACT', frequency='monthly')
            world(de, 'de-weo-lur', 'Unemployment rate')
            world(fr, 'fr-une_rt_m-total-sa-t-pc-act', 'Unemployment by sex and age - monthly data', unit='PC_ACT', frequency='monthly')
            db.add_all(rows)
            await db.flush()
            for row in rows:
                db.add(WorldDataPoint(indicator_id=row.id, date=date(2024, 1, 1), value=100))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env['app']) as client:
        yield client


def _codes(client, q, limit=50, locale=None):
    headers = {'X-FE-Locale': locale} if locale else {}
    response = client.get('/api/v1/search', params=dict(q=q, limit=limit), headers=headers)
    assert response.status_code == 200, response.text
    return [row.get('code') for row in response.json()['results']]


@pytest.mark.parametrize('q,first', [
    ('ввп сша', 'us-weo-ngdpd'),
    ('ВВП США', 'us-weo-ngdpd'),
    ('gdp usa', 'us-weo-ngdpd'),
    ('gdp united states', 'us-weo-ngdpd'),
    ('ввп германии', 'de-weo-ngdpd'),
    ('gdp germany', 'de-weo-ngdpd'),
    ('ввп китая', 'cn-weo-ngdpd'),
    ('gdp china', 'cn-weo-ngdpd'),
])
def test_country_gdp_headline_is_first(headline_client, q, first):
    codes = _codes(headline_client, q)
    assert codes[0] == first, codes[:5]


@pytest.mark.parametrize('limit', [5, 10, 50, 100])
def test_headline_survives_any_limit(headline_client, limit):
    assert _codes(headline_client, 'ввп сша', limit=limit)[0] == 'us-weo-ngdpd'


def test_per_capita_headline_is_not_overall_gdp(headline_client):
    assert _codes(headline_client, 'ввп на душу населения сша')[0] == 'us-weo-ngdpdpc'
    # «ВВП страны» не подменяется ВВП на душу
    assert _codes(headline_client, 'ввп китая').index('cn-weo-ngdpd') < _codes(headline_client, 'ввп китая').index('cn-weo-ngdpdpc')


def test_unemployment_headline_not_clipped_by_neighbours(headline_client):
    codes = _codes(headline_client, 'безработица германии', limit=10)
    assert 'de-une_rt_m-total-sa-t-pc-act' in codes[:2]
    assert 'de-weo-lur' in codes[:3]
    assert _codes(headline_client, 'unemployment france', limit=10)[0] == 'fr-une_rt_m-total-sa-t-pc-act'


def test_other_countries_gdp_not_leaking(headline_client):
    codes = _codes(headline_client, 'ввп сша')
    assert not any(code.startswith(('de-', 'cn-')) for code in codes)
