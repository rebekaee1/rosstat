"""Поиск: вставленная ссылка на поиск другого сайта (Пульс 19.11.2026, правка 2 от 20.11.2026).

19.11.2026 человек на странице Ленинградской области вставил в поле поиска ссылку ЕМИСС
«https://www.fedstat.ru/indicators/search?searchText=%D0%9A%D…» и дважды получил ноль, затем набрал
«Коэффициент рождаемости» руками. Адрес читался как слова «https www fedstat ru indicators search».
Теперь из ссылки берётся текст поиска (searchText, text, q …), буквы раскодируются, ответ несёт
«Показаны результаты для: …».
"""
import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.services import search_rewrite
from app.services.search_rewrite import search_text_from_link

FEDSTAT = "https://www.fedstat.ru/indicators/search?searchText="
BIRTH_RATE = "%D0%9A%D0%BE%D1%8D%D1%84%D1%84%D0%B8%D1%86%D0%B8%D0%B5%D0%BD%D1%82+%D1%80%D0%BE%D0%B6%D0%B4%D0%B0%D0%B5%D0%BC%D0%BE%D1%81%D1%82%D0%B8"


@pytest.mark.parametrize("raw, expected", [
    (FEDSTAT + BIRTH_RATE, "Коэффициент рождаемости"),
    # Параметр в другом регистре и пробел как %20.
    ("https://www.fedstat.ru/indicators/search?searchtext=%D0%92%D0%A0%D0%9F%20%D0%BD%D0%B0", "ВРП на"),
    # Оборванный код буквы (так ссылка записана в журнале 19.11): целые буквы остаются, хвост отбрасывается.
    (FEDSTAT + "%D0%9A%D", "К"),
    ("https://rosstat.gov.ru/search?q=&text=%D0%B8%D0%BD%D1%84%D0%BB%D1%8F%D1%86%D0%B8%D1%8F", "инфляция"),
    ("www.google.com/search?q=gdp+russia&hl=ru", "gdp russia"),
    ("  https://yandex.ru/search/?text=ввп+россии  ", "ввп россии"),
])
def test_search_text_is_read_from_link(raw, expected):
    assert search_text_from_link(raw) == expected


@pytest.mark.parametrize("raw", [
    "коэффициент рождаемости",
    "https://www.fedstat.ru/indicator/31074",          # ссылка без текста поиска
    "https://www.fedstat.ru/indicators/search?searchText=",
    "https://example.com/?page=2",
    "ввп?",
    "что такое https://x.ru/?q=1",                       # не ссылка целиком
])
def test_other_queries_are_not_links(raw):
    assert search_text_from_link(raw) is None


@pytest.fixture
def link_client(auth_env, monkeypatch):
    from app.models import Region, RegionDataPoint, RegionIndicator

    monkeypatch.setattr(search_rewrite, "_vocabulary", None)

    async def seed():
        async with auth_env['session_maker']() as db:
            region = Region(slug='leningradskaya-oblast', name='Ленинградская область', kind='region')
            db.add(region)
            births = RegionIndicator(code='obschie-koeffitsienty-rozhdaemosti', name='Общие коэффициенты рождаемости',
                                     table_code='2.5', section_num=2, section_name='Население', unit='на 1000 человек')
            db.add(births)
            await db.flush()
            db.add(RegionDataPoint(indicator_id=births.id, region_id=region.id, year=2023, value=6.1))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env['app']) as client:
        yield client


def search(client, q):
    response = client.get('/api/v1/search', params={'q': q})
    assert response.status_code == 200, response.text
    return response.json()


def test_pasted_fedstat_link_finds_the_series(link_client):
    body = search(link_client, FEDSTAT + BIRTH_RATE)
    assert 'obschie-koeffitsienty-rozhdaemosti' in [row.get('code') for row in body['results']]
    assert body.get('corrected_query') == 'Коэффициент рождаемости'
    plain = search(link_client, 'коэффициент рождаемости')
    assert [row.get('key') for row in plain['results']] == [row.get('key') for row in body['results']]
