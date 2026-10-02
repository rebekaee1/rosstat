"""Exact native titles are identities while outside facets remain mandatory."""
import asyncio
from datetime import date

import pytest

from test_search_federated import get, search_client  # noqa: F401 (shared hermetic fixture)


@pytest.mark.parametrize(('query', 'title', 'expected'), [
    ('Gross domestic product (GDP) current prices', 'Gross domestic product, % GDP', False),
    ('Gross domestic product, % GDP Russia', 'Gross domestic product (% GDP)', True),
    ('Population per area 2015 100', 'Population per area, 2015=100', False),
    ('Population per area (2015=100) Russia', 'Population per area, 2015=100', True),
    ('Price of grain USD t Russia', 'Price of grain USD/t', False),
    ('Price of grain (USD / t) Russia', 'Price of grain USD/t', True),
    ('Average wages (annual) Russia %', 'Average wages — annual', True),
])
def test_native_title_proof_keeps_economic_symbols(query, title, expected):
    from app.services.search import _native_title_span
    assert _native_title_span(query, title) is expected


def test_native_percent_title_cannot_mask_nominal_gdp_question(auth_env, search_client):
    from app.models import Indicator, IndicatorData

    async def seed():
        async with auth_env['session_maker']() as db:
            nominal = Indicator(code='gdp-nominal', name='ВВП номинальный', name_en='Nominal GDP',
                unit='млрд руб.', frequency='quarterly', category='Economy')
            share = Indicator(code='native-share-fixture', name='валовой внутренний продукт, % ВВП',
                name_en='Gross domestic product, % GDP', unit='%', frequency='annual', category='Economy')
            db.add_all((nominal, share))
            await db.flush()
            for row in (nominal, share):
                db.add(IndicatorData(indicator_id=row.id, date=date(2024, 1, 1), value=100))
            await db.commit()

    asyncio.run(seed())
    body = get(search_client, 'валовой внутренний продукт (ВВП) текущих ценах.')
    assert body['results'][0]['code'] == 'gdp-nominal'
    assert all(hit['code'] != 'native-share-fixture' for hit in body['results'])
    exact = get(search_client, 'валовой внутренний продукт, % ВВП Russia 2024')
    assert exact['results'][0]['code'] == 'native-share-fixture'
    assert not get(search_client, 'валовой внутренний продукт (ВВП) текущих ценах. magical')['results']


@pytest.mark.parametrize('title', ['Population at 1 January', 'Average nominal monthly wages', 'Quarterly count per 1000 residents'])
def test_native_title_is_preserved_before_period_and_mode_parsing(auth_env, search_client, title):
    from app.models import Indicator, IndicatorData
    async def seed():
        async with auth_env['session_maker']() as db:
            row = Indicator(code='native-fixture', name=title, name_en=title, unit='people', frequency='annual', category='Test', source='fixture', source_url='https://example.test')
            db.add(row)
            await db.flush()
            db.add(IndicatorData(indicator_id=row.id, date=date(2024, 1, 1), value=100))
            await db.commit()
    asyncio.run(seed())
    body = get(search_client, title + ' Russia')
    assert body['intent']['year'] is None
    assert body['intent']['month'] is None
    assert body['results'][0]['code'] == 'native-fixture'
    assert get(search_client, title + ' Russia 2024')['results'][0]['path'].endswith('/2024')
    assert not get(search_client, title + ' Russia 1999')['results']
    assert not get(search_client, title + ' Russia %')['results']
    assert not get(search_client, title + ' magical Russia')['results']
    if len(title) >= 24 and len(title.split()) >= 4:
        assert get(search_client, title[:-2] + ' Russia')['results'][0]['code'] == 'native-fixture'
        assert not get(search_client, title[:-2] + ' Russia %')['results']


def test_remainder_geography_cannot_silently_become_inclusive_region(auth_env, search_client):
    from app.models import Region
    async def seed():
        async with auth_env['session_maker']() as db:
            db.add(Region(slug='moscow-remainder', name='Moscow (excluding territory)', kind='remainder'))
            await db.commit()
    asyncio.run(seed())
    body = get(search_client, 'population Moscow (excluding territory)')
    assert body['intent']['regions'] == ['region:russia:moscow-remainder']
    assert body['results'] == []
