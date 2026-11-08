"""R2-Z4 (08.11.2026): города вместо областей, квартплата."""
import pytest

from app.services.search_intent import match_score, parse_intent

GEOMETRY = [
    dict(key='country:russia', kind='country', slug='russia', name_ru='Россия', name_en='Russia', country_slug='russia', country_code='RU'),
    dict(key='region:russia:respublika-tatarstan', kind='region', slug='respublika-tatarstan', name_ru='Республика Татарстан', name_en='Tatarstan Republic', country_slug='russia'),
    dict(key='region:russia:sverdlovskaya-oblast', kind='region', slug='sverdlovskaya-oblast', name_ru='Свердловская область', name_en='Sverdlovsk Oblast', country_slug='russia'),
    dict(key='region:russia:sankt-peterburg', kind='region', slug='sankt-peterburg', name_ru='Санкт-Петербург', name_en='Saint Petersburg', country_slug='russia'),
    dict(key='region:russia:nizhegorodskaya-oblast', kind='region', slug='nizhegorodskaya-oblast', name_ru='Нижегородская область', name_en='Nizhny Novgorod Oblast', country_slug='russia'),
]


@pytest.mark.parametrize('query, region', [
    ('квартплата казань', 'respublika-tatarstan'),
    ('цена яиц в казани', 'respublika-tatarstan'),
    ('хлеб екб', 'sverdlovskaya-oblast'),
    ('молоко екатеринбург', 'sverdlovskaya-oblast'),
    ('молоко питер', 'sankt-peterburg'),
    ('молоко нижний новгород', 'nizhegorodskaya-oblast'),
])
def test_city_names_point_to_their_region(query, region):
    intent = parse_intent(query, GEOMETRY)
    assert intent.regions == frozenset((f'region:russia:{region}',))


def test_kvartplata_is_utilities():
    intent = parse_intent('квартплата', GEOMETRY)
    assert intent.error is None
    assert match_score(intent, code='ceni-gaz-setevoy', names=('Средняя цена: газ сетевой, рублей за м³',)) is not None


@pytest.mark.asyncio
async def test_explicit_region_rows_get_latest_value(monkeypatch):
    from app.services import search_regional_groups as g

    async def fake(db, code, *, monthly, slugs=None):
        assert slugs == ('moskva',) and monthly
        return {'moskva': (31219.7123456, '2026-09-01')}

    monkeypatch.setattr(g, '_latest_by_region', fake)
    rows = [{'kind': 'region_indicator', 'region_slug': 'moskva', 'code': 'ceni-arenda-1k', 'frequency': 'monthly'},
            {'kind': 'russia', 'code': 'cpi'}]
    await g.attach_region_row_values(None, rows)
    assert rows[0]['latest'] == {'value': 31219.7123, 'date': '2026-09-01'}
    assert 'latest' not in rows[1]
