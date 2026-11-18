"""Пустые поиски Пульса за 17.11.2026: запрос своими словами → словами каталога (18.11.2026).

Каждый запрос ниже на боевом ничего не находил при существующем ряде. Новые чтения работают только после пустой
выдачи: словарь замен, опечатка в слове каталога, числа из таблицы, «X и Y», общие слова о территории, слово без
исправления в понятие словаря. Пробелы каталога остаются честно пустыми. Названия и коды повторяют настоящий каталог.
"""
import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.services import search_rewrite
from app.services.search_rewrite import _correction, conjunction_parts, profile_only, rewrite_words

REGISTERED = "uroven-bezrabotitsy-uroven-zaregistrirovannoy-bezrabotitsy"
SOWN_GRAIN = "posevnye-ploschadi-zernovyh-i-zernobobovyh-kultur"
SOWN = "posevnye-ploschadi-selskohozyaystvennyh-kultur"
BIRTHS = "obschie-koeffitsienty-rozhdaemosti"
DEATHS = "obschie-koeffitsienty-smertnosti"
TENSION = "nagruzka-nezanyatogo-naseleniya-sostoyaschego-na-registratsionnom-uchete"
FREIGHT = "perevozki-gruzov-avtomobilnym-transportom-organizatsiy-vseh-vidov"


# ── Чистые правила ────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("регистрируемая безработица", "уровень зарегистрированной безработицы"),
    ("Безработица Регистрируемая россия", "уровень зарегистрированной безработицы россия"),
    ("Тамбовская область площади посева зерновых", "тамбовская область посевные площади зерновых"),
    ("коэффициент напряженности", "нагрузка незанятого населения на одну заявленную вакансию"),
    ("кредитная задолженность физ", "кредиты физическим лицам"),
    ("задолженность домохозяйств", "кредиты физическим лицам"),
    ("структура потребительских расходов по КОФП", "структура потребительских расходов"),
    ("коэфицент рождаемости", "коэффициент рождаемости"),
    # Числа из ячейки таблицы — не уточнение; год остаётся.
    ("Перевозки грузов Самарская область 2014 43,6", "перевозки грузов самарская область 2014"),
    ("Дефицит бюджета, в том 17 числе", "дефицит бюджета в том числе"),
    ('"Ввод в действие основных фондов" дагеста6', 'ввод в действие основных фондов дагеста'),
    ("Сведения о задолженности по кредитам, предоставленным кредитными организациями физическим лицам-резидентам»",
     "кредиты физическим лицам"),
    ("17 383 024", ""),
])
def test_rewrite_words(raw, expected):
    assert rewrite_words(raw) == expected


@pytest.mark.parametrize("raw", ["цена аи-92", "ипц 2015=100", "врачей на 1000 человек", "инфляция 2024", "ввп"])
def test_rewrite_keeps_identities_and_years(raw):
    assert rewrite_words(raw) == raw


def test_conjunctions_and_profile_words():
    assert conjunction_parts("Рождаемость и смертность Псковская область") == ["рождаемость", "смертность псковская область"]
    assert conjunction_parts("наблюдаемая инфляция vs ожидаемая инфляция") == ["наблюдаемая инфляция", "ожидаемая инфляция"]
    # Запятая в скопированном названии таблицы — не союз.
    assert conjunction_parts("Дефицит федерального бюджета, в том числе ненефтегазовый") == []
    assert profile_only((("место",), ("экономике",)))
    assert not profile_only((("экономике",), ("безработица",)))
    assert not profile_only(())


def test_typo_correction_needs_one_word_or_forms_of_one_word():
    assert _correction("пложади", {"площади"}) == "площади"
    # Пропущенная буква — самая частая опечатка: «хозяйста» → «хозяйства», а не «хозяйств».
    assert _correction("хозяйста", {"хозяйства", "хозяйств"}) == "хозяйства"
    # Разные слова — не исправляем.
    assert _correction("кошка", {"ложка", "кошки"}) is None
    assert _correction("слово", set()) is None


# ── Поиск целиком ─────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def rewrite_client(auth_env, monkeypatch):
    from app.models import Indicator, IndicatorData, Region, RegionDataPoint, RegionIndicator

    monkeypatch.setattr(search_rewrite, "_vocabulary", None)

    async def seed():
        async with auth_env['session_maker']() as db:
            national = [
                Indicator(code='gdp-investment', name='Валовое накопление капитала', name_en='Gross capital formation',
                    frequency='quarterly'),
                Indicator(code='deposits', name='Вклады физических лиц', name_en='Household deposits', frequency='monthly'),
                Indicator(code='birth-rate', name='Коэффициент рождаемости', name_en='Birth rate', frequency='annual'),
            ]
            db.add_all(national)
            regions = {slug: Region(slug=slug, name=name, kind='region') for slug, name in (
                ('pskovskaya-oblast', 'Псковская область'), ('tambovskaya-oblast', 'Тамбовская область'),
                ('samarskaya-oblast', 'Самарская область'))}
            db.add_all(regions.values())

            def definition(code, name, table, unit):
                return RegionIndicator(code=code, name=name, table_code=table, section_num=1, section_name='Раздел', unit=unit)

            annual = [
                definition(REGISTERED, 'Уровень безработицы — уровень зарегистрированной безработицы', '4.6', 'процент'),
                definition(SOWN_GRAIN, 'Посевные площади зерновых и зернобобовых культур', '12.2', 'тыс. га'),
                definition(SOWN, 'Посевные площади сельскохозяйственных культур', '12.1', 'тыс. га'),
                definition(BIRTHS, 'Общие коэффициенты рождаемости', '2.3', 'промилле'),
                definition(DEATHS, 'Общие коэффициенты смертности', '2.4', 'промилле'),
                definition(TENSION, 'Нагрузка незанятого населения, состоящего на регистрационном учете в органах службы '
                    'занятости населения, в расчете на одну заявленную вакансию', '4.9', 'человек'),
                definition(FREIGHT, 'Перевозки грузов автомобильным транспортом организаций всех видов деятельности',
                    '16.3', 'млн т'),
            ]
            db.add_all(annual)
            await db.flush()
            for row in national:
                db.add(IndicatorData(indicator_id=row.id, date=date(2024, 1, 1), value=100))
            for region in regions.values():
                for row in annual:
                    for year in (2014, 2024):
                        db.add(RegionDataPoint(indicator_id=row.id, region_id=region.id, year=year, value=50))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env['app']) as client:
        yield client


def get(client, q):
    response = client.get('/api/v1/search', params={'q': q})
    assert response.status_code == 200, response.text
    return response.json()


def codes(body):
    return [row.get('code') for row in body['results']]


def test_registered_unemployment_in_own_words(rewrite_client):
    body = get(rewrite_client, 'регистрируемая безработица')
    assert REGISTERED in codes(body), body
    assert body['corrected_query'] == 'уровень зарегистрированной безработицы'


def test_sown_area_word_order(rewrite_client):
    body = get(rewrite_client, 'Тамбовская область площади посева зерновых и зернобобовых культур')
    assert codes(body)[0] == SOWN_GRAIN, body
    assert all(row.get('region_slug') == 'tambovskaya-oblast' for row in body['results'])


def test_labour_market_tension_is_load_per_vacancy(rewrite_client):
    assert codes(get(rewrite_client, 'коэффициент напряженности')) == [TENSION]


def test_catalogue_typo_and_region_typo(rewrite_client):
    body = get(rewrite_client, 'посевные пложади сельскохозяйственных культур псковсая область')
    assert codes(body)[:1] == [SOWN], body
    assert body['results'][0]['region_slug'] == 'pskovskaya-oblast'


def test_table_row_with_numbers(rewrite_client):
    body = get(rewrite_client, 'Перевозки грузов автомобильным транспортом организаций всех видов деятельности '
        'Самарская область 2014 43,6')
    assert codes(body) == [FREIGHT], body
    assert body['results'][0]['region_slug'] == 'samarskaya-oblast'


def test_two_indicators_with_one_region(rewrite_client):
    body = get(rewrite_client, 'рождаемость и смертность псковская область')
    found = codes(body)
    assert BIRTHS in found and DEATHS in found, body
    assert all(row.get('region_slug') == 'pskovskaya-oblast' for row in body['results'])


def test_region_economy_is_the_region_page(rewrite_client):
    for query in ('псковская область в экономике', 'место псковской области в экономике России'):
        body = get(rewrite_client, query)
        assert body['results'] and body['results'][0]['kind'] == 'region', (query, body)
        assert body['results'][0]['region_slug'] == 'pskovskaya-oblast'


def test_real_catalogue_word_is_not_corrected_into_a_concept(rewrite_client):
    """«накопление» — слово ряда «Валовое накопление капитала», а не описка в «накопления» (= вклады)."""
    assert codes(get(rewrite_client, 'валовое накопление'))[:1] == ['gdp-investment']


def test_gaps_stay_empty(rewrite_client):
    for query in ('закредитованность', 'посевные площади сои', 'наблюдаемая инфляция vs ожидаемая инфляция'):
        body = get(rewrite_client, query)
        assert body['results'] == [], (query, body)


def test_working_query_is_untouched(rewrite_client):
    body = get(rewrite_client, 'коэффициент рождаемости')
    assert codes(body)[0] == 'birth-rate'
    assert not body.get('corrected_query')
