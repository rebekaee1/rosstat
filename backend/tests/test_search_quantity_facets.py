"""Quantity facets use native metadata and preserve typed subject boundaries."""
import asyncio
from datetime import date
import pytest

from app.services.search_intent import parse_intent, match_score
from app.services.search_units import unit_metadata
from test_search_federated import get, search_client  # noqa: F401


@pytest.mark.parametrize('query,expected', [
    ('construction work quarterly billion rubles', {'search-freq-quarterly', 'search-unit-billion', 'search-unit-rub'}),
    ('рабочая сила месячный млн человек', {'search-freq-monthly', 'search-unit-million'}),
    ('population monthly million persons', {'search-freq-monthly', 'search-unit-million', 'search-unit-persons'}),
    ('индекс потребительских цен ежемесячно', {'cpi', 'search-freq-monthly'}),
    ('Валовой внутренний продукт (ВВП) текущих ценах', {'gdp-nominal'}),
    ('gross domestic product constant prices quarterly', {'gdp-real', 'search-freq-quarterly'}),
    ('численность пенсионеров ежегодно', {'pensioners', 'search-freq-annual'}),
    ('How many people have jobs', {'employment-count'}),
])
def test_composition_retains_native_quantity_and_frequency(query, expected):
    terms = {group[0] for group in parse_intent(query, []).terms}
    assert expected <= terms
    if 'gdp-nominal' in expected or 'gdp-real' in expected:
        assert 'cpi-food' not in terms
    if 'pensioners' in expected:
        assert 'pension' not in terms


def test_short_autocomplete_is_anchored_and_never_a_qualifier():
    assert match_score(parse_intent('ин', []), names=('Индекс доходов',)) is not None
    assert match_score(parse_intent('ин', []), names=('Биткоин',)) is None
    assert match_score(parse_intent('cpi ин', []), names=('Consumer price index inflation',)) is None


def test_scale_and_currency_markers_are_metadata_only():
    million = unit_metadata('USD_MN_CHAINED')
    assert 'search-unit-million' in million and 'search-unit-usd' in million
    assert 'search-unit-billion' not in million
    assert 'search-unit-persons' not in unit_metadata('percent')
    assert 'search-unit-index' not in unit_metadata('млрд руб. в ценах 2015 года')


def test_world_quantity_is_filtered_before_candidate_budget(auth_env, search_client):
    from app.models import WorldCountry, WorldIndicator, WorldDataPoint
    from sqlalchemy import select
    async def seed():
        async with auth_env['session_maker']() as db:
            country = (await db.execute(select(WorldCountry).where(WorldCountry.slug == 'germany'))).scalar_one()
            rows = [WorldIndicator(country_id=country.id, code=f'aaa-population-{i}', slice_hash=f'wrong-{i}', name_ru='Население', name_en='Population', dataset_id='fixture-population', is_listed=True, unit='THS_PER', unit_ru='тыс. человек', frequency='annual', points_count=1) for i in range(105)]
            rows.append(WorldIndicator(country_id=country.id, code='zzz-population', slice_hash='correct', name_ru='Население', name_en='Population', dataset_id='fixture-population', is_listed=True, unit='MIO_PER', unit_ru='млн человек', frequency='annual', points_count=1))
            db.add_all(rows)
            await db.flush()
            db.add_all([WorldDataPoint(indicator_id=row.id, date=date(2024, 1, 1), value=10) for row in rows])
            await db.commit()
    asyncio.run(seed())
    rows = get(search_client, 'Population Germany annual million persons')['results']
    assert [row['code'] for row in rows] == ['zzz-population']
    assert not get(search_client, 'Population Germany annual billion persons')['results']
    assert not get(search_client, 'Population Germany annual million persons rubles')['results']
    assert not get(search_client, 'Population Germany monthly million persons')['results']
    assert not get(search_client, 'Population Germany annual million persons magical')['results']


@pytest.mark.parametrize("query", ["usd r", "курс доллара к ру", "доллар ру"])
def test_registered_currency_pair_autocomplete_retains_other_qualifiers(query):
    intent = parse_intent(query, [])
    assert len(intent.terms) == 1 and intent.terms[0][0] == "usd-rub"
    assert match_score(intent, code="usd-rub") is not None
    assert match_score(parse_intent(query + " magical", []), code="usd-rub") is None


def test_share_and_monetary_value_are_not_neutral_grammar():
    intent = parse_intent("стоимость экспорта", [])
    assert ("search-unit-money",) in intent.terms
    assert match_score(intent, names=("Индекс физического объема экспорта",), metadata=unit_metadata("Index2020=100")) is None
    assert match_score(parse_intent("доля рождаемости", []), names=("Число родившихся",)) is None
