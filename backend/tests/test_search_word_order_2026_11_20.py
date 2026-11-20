"""Поиск: часть фразы и другой порядок слов (Пульс 19.11.2026, правка 1 от 20.11.2026).

19.11.2026 три человека на страницах регионов искали ВРП словами «Валовый вн…», «Внутренний валовой пр»,
«Внутренний региональный продукт» и получали ноль. На общем поиске то же: «валовый вн», «внутренний валовой пр»,
«внутренний региональный продукт» — пусто, «внутренний валовой продукт» — только мировые ряды «… % ВВП».

1. Фраза понятия из трёх и более слов в другом порядке — то же понятие (первое чтение, ``search_intent``).
2. Конец запроса — недописанная фраза понятия или её слова в другом порядке: после пустой выдачи дописывается
   до фразы целиком (``search_rewrite.complete_concept_phrase``), ответ несёт «Показаны результаты для».
3. «Внутренний региональный продукт» — понятие ВРП.
"""
import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.services import search_rewrite
from app.services.search_intent import parse_intent
from app.services.search_rewrite import complete_concept_phrase, rewrite_words

GRP = "valovoy-regionalnyy-produkt"


# ── Чистые правила ────────────────────────────────────────────────────────────────────────────────

def _codes(raw):
    return [term[0] for term in parse_intent(raw, []).terms]


@pytest.mark.parametrize("raw", ["внутренний валовой продукт", "продукт внутренний валовой", "внутренний валовый продукт"])
def test_reordered_phrase_is_the_same_concept(raw):
    assert _codes(raw) == _codes("валовой внутренний продукт") == ["gdp"]


def test_mixed_up_regional_product_is_grp():
    assert _codes("внутренний региональный продукт") == [GRP]


def test_short_phrases_keep_their_order():
    # В двух словах порядок несёт смысл («евро доллар» — курс евро в долларах): правило другого порядка их не трогает.
    assert _codes("доллар евро") != ["eur-usd"]


@pytest.mark.parametrize("raw,expected", [
    ("валовый вн", "валовой внутренний продукт"),
    ("Валовый внутренний про", "валовой внутренний продукт"),
    ("внутренний валовой пр", "валовой внутренний продукт"),
    ("Внутренний ре", "валовой региональный продукт"),
    ("Внутренний регион", "валовой региональный продукт"),
    ("валовой ре", "валовой региональный продукт"),
    ("псковская область валовый вн", "псковская область валовой внутренний продукт"),
    ("уровень бе", "уровень безработицы"),
])
def test_unfinished_phrase_is_completed(raw, expected):
    assert rewrite_words(raw) == expected


@pytest.mark.parametrize("raw", [
    "валовой внутренний продукт",  # уже целиком
    "ввп на",                      # одно значимое слово
    "валовый р",                   # одна буква — окно поиска дописывает само по строкам выдачи
    "цена аи-92",
    "валовый вн псковская",         # фраза не в конце запроса
    "внутренние затраты",
])
def test_other_queries_are_untouched(raw):
    plain = " ".join(raw.lower().split())
    assert complete_concept_phrase(plain) == plain


# ── Поиск целиком ─────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def order_client(auth_env, monkeypatch):
    from app.models import Indicator, IndicatorData, Region, RegionDataPoint, RegionIndicator

    monkeypatch.setattr(search_rewrite, "_vocabulary", None)

    async def seed():
        async with auth_env['session_maker']() as db:
            gdp = Indicator(code='gdp-nominal', name='ВВП номинальный', name_en='Nominal GDP', frequency='quarterly')
            db.add(gdp)
            region = Region(slug='pskovskaya-oblast', name='Псковская область', kind='region')
            db.add(region)
            grp = RegionIndicator(code=GRP, name='Валовой региональный продукт', table_code='10.1', section_num=10,
                                  section_name='Национальные счета', unit='млн руб.')
            db.add(grp)
            await db.flush()
            db.add(IndicatorData(indicator_id=gdp.id, date=date(2024, 1, 1), value=100))
            db.add(RegionDataPoint(indicator_id=grp.id, region_id=region.id, year=2023, value=50))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env['app']) as client:
        yield client


def search(client, q):
    response = client.get('/api/v1/search', params={'q': q})
    assert response.status_code == 200, response.text
    return response.json()


def codes(body):
    return [row.get('code') for row in body['results']]


@pytest.mark.parametrize("q", ["внутренний валовой продукт", "валовый вн", "внутренний валовой пр"])
def test_gdp_found_by_part_and_other_order(order_client, q):
    assert 'gdp-nominal' in codes(search(order_client, q))


@pytest.mark.parametrize("q", ["внутренний региональный продукт", "внутренний ре", "псковская область валовый вн"])
def test_grp_found_by_mixed_up_words(order_client, q):
    assert GRP in codes(search(order_client, q))


def test_completion_is_shown(order_client):
    body = search(order_client, 'валовый вн')
    assert body.get('corrected_query') == 'валовой внутренний продукт'
    # Полный запрос находит своё первым чтением: строки «Показаны результаты для» нет.
    assert 'corrected_query' not in search(order_client, 'валовой внутренний продукт')
