"""Пробелы поиска, подтверждённые живым поиском 13.11.2026 (гипотезы Пульса).

Каждый запрос ниже на боевом давал пустую или неверную выдачу при существующих рядах.
Названия, коды и ключевые слова рядов повторяют настоящий каталог. Там, где ряда в каталоге
нет (акцизы, цена стали, региональные данные раньше 1990 года), тест закрепляет честную
пустую выдачу, а не подстановку похожего ряда.

SQLite не сворачивает регистр кириллицы, поэтому названия, которые поиск находит запросом
к базе (точное название ряда, мировые ряды), записаны строчными буквами.
"""
import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.services.search_intent import parse_intent, region_reading

IMOEX_KEYWORDS = "индекс МосБиржи, IMOEX, индекс Московской биржи, фондовый индекс, индекс акций России, котировки IMOEX"
GOVERNMENT_KEYWORDS = "государственное потребление, госрасходы, потребление госсектора, расходы государства ВВП, компонент ВВП госсектор"
NATURAL_KEYWORDS = "естественный прирост населения, естественная убыль населения, рождаемость минус смертность, естественный прирост Росстат"

DIGITAL = "ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie"
INTERNET = "ispolzovanie-seti-internet-naseleniem-naselenie-ispolzovavshee-set"
FREIGHT = "indeksy-tarifov-na-gruzovye-perevozki"
SOWN = "posevnye-ploschadi-selskohozyaystvennyh-kultur"
WEAR = "stepen-iznosa-osnovnyh-fondov"
GRP = "valovoy-regionalnyy-produkt"
KETTLE = "ceni-chaynik-stalnoy-emalirovannyy"
PAN = "ceni-kastryulya-iz-emalirovannoy-ili-nerzhaveyuschey-stali"
PRICES = "Цены и тарифы"
REGIONAL_PPI = "indeksy-tsen-proizvoditeley-promyshlennyh-tovarov-po-vidam-20-11-4"


@pytest.fixture
def gaps_client(auth_env):
    from app.models import (Indicator, IndicatorData, Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint,
        WorldCountry, WorldDataPoint, WorldIndicator)

    async def seed():
        async with auth_env['session_maker']() as db:
            austria = WorldCountry(code='AT', slug='austria', name_ru='Австрия', name_en='Austria')
            db.add(austria)
            await db.flush()
            bonds = WorldIndicator(country_id=austria.id, code='at-sdg_13_70a-pc-tot',
                name_ru='выпуск зелёных облигаций корпорациями и государством, % от итога',
                name_en='Green bond issuance by corporations and governments, % of total', dataset_id='sdg_13_70a',
                slice_hash='at-sdg_13_70a-pc-tot', unit='PC', frequency='annual', is_listed=True, category_ru='Финансы')
            db.add(bonds)
            national = [
                Indicator(code='imoex', name='Индекс МосБиржи', name_en='MOEX Russia Index', frequency='daily', seo_keywords=IMOEX_KEYWORDS),
                Indicator(code='gdp-government', name='Государственное потребление', name_en='Government Consumption',
                    frequency='quarterly', seo_keywords=GOVERNMENT_KEYWORDS),
                Indicator(code='population-natural-growth', name='Естественный прирост населения', name_en='Natural Population Growth',
                    frequency='monthly', seo_keywords=NATURAL_KEYWORDS),
                Indicator(code='population', name='Численность населения', name_en='Population', frequency='annual'),
                Indicator(code='ppi', name='индекс цен производителей', name_en='Producer Price Index', frequency='monthly'),
                Indicator(code='ppi-yoy', name='ИЦП (изм. г/г)', name_en='Producer Price Index YoY', frequency='monthly', is_listed=False),
                Indicator(code='ipi', name='Индекс промышленного производства', name_en='Industrial Production Index', frequency='monthly'),
                Indicator(code='fuel-diesel', name='цена дизельного топлива', name_en='Diesel fuel price', frequency='weekly', unit='руб./л'),
                Indicator(code='depreciation-rate', name='Степень износа основных фондов', name_en='Depreciation rate of fixed assets', frequency='annual'),
            ]
            db.add_all(national)
            regions = {slug: Region(slug=slug, name=name, kind='region') for slug, name in (
                ('kaliningradskaya-oblast', 'Калининградская область'), ('udmurtskaya-respublika', 'Удмуртская Республика'),
                ('kaluzhskaya-oblast', 'Калужская область'), ('pskovskaya-oblast', 'Псковская область'),
                ('voronezhskaya-oblast', 'Воронежская область'), ('moskovskaya-oblast', 'Московская область'),
                ('hanty-mansiyskiy-ao', 'Ханты-Мансийский автономный округ — Югра'))}
            db.add_all(regions.values())

            def definition(code, name, table, unit, section='Раздел'):
                return RegionIndicator(code=code, name=name, table_code=table, section_num=1, section_name=section, unit=unit)

            annual = {
                WEAR: definition(WEAR, 'Степень износа основных фондов', '9.1', 'процент'),
                GRP: definition(GRP, 'Валовой региональный продукт', '8.1', 'млн рублей'),
                SOWN: definition(SOWN, 'Посевные площади сельскохозяйственных культур', '12.1', 'тыс. га'),
                DIGITAL: definition(DIGITAL, 'Использование цифровых технологий в организациях — организации, использовавшие персональные компьютеры', '17.1', 'процент'),
                INTERNET: definition(INTERNET, 'Использование сети Интернет населением — население, использовавшее сеть Интернет', '17.7', 'процент'),
                FREIGHT: definition(FREIGHT, 'Индексы тарифов на грузовые перевозки', '20.9', 'процент'),
                REGIONAL_PPI: definition(REGIONAL_PPI, 'Индексы цен производителей промышленных товаров по видам экономической '
                    'деятельности — добыча полезных ископаемых', '20.11', 'процент'),
                'koeffitsienty-estestvennogo-prirosta-naseleniya-na-1000-chelovek': definition(
                    'koeffitsienty-estestvennogo-prirosta-naseleniya-na-1000-chelovek',
                    'Коэффициенты естественного прироста населения на 1000 человек населения', '2.5', 'промилле'),
            }
            monthly = {
                'ceni-ai92': definition('ceni-ai92', 'Потребительские цены на бензин АИ-92, рублей за литр', '20.m1', 'рубль за литр', PRICES),
                'ceni-dt': definition('ceni-dt', 'Потребительские цены на дизельное топливо, рублей за литр', '20.m3', 'рубль за литр', PRICES),
                'ceni-internet': definition('ceni-internet', 'Средняя цена: абонентская плата за доступ в интернет, рублей в месяц', '20.m40', 'рублей в месяц', PRICES),
                KETTLE: definition(KETTLE, 'Средняя цена: чайник стальной эмалированный, рублей за шт.', '20.m50', 'рублей за шт.', PRICES),
                PAN: definition(PAN, 'Средняя цена: кастрюля из эмалированной или нержавеющей стали, рублей за шт.', '20.m51', 'рублей за шт.', PRICES),
            }
            db.add_all((*annual.values(), *monthly.values()))
            await db.flush()
            db.add(WorldDataPoint(indicator_id=bonds.id, date=date(2024, 1, 1), value=12))
            for row in national:
                db.add(IndicatorData(indicator_id=row.id, date=date(2024, 5, 1), value=100))
            for region in regions.values():
                for row in annual.values():
                    for year in (2020, 2024):
                        db.add(RegionDataPoint(indicator_id=row.id, region_id=region.id, year=year, value=50))
                for row in monthly.values():
                    db.add(RegionMonthlyPoint(indicator_id=row.id, region_id=region.id, month=202609, value=60))
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


# ── 1. Регион и показатель без точного названия ряда ──────────────────────────────────────────────

def test_bare_region_adjective_names_the_region(gaps_client):
    """«калининградская степень износа»: прилагательное без слова «область» — тот же регион."""
    body = get(gaps_client, 'калининградская степень износа')
    assert body['results'], body
    first = body['results'][0]
    assert first['code'] == WEAR and first['region_slug'] == 'kaliningradskaya-oblast'
    assert first['path'] == f'/russia/region/kaliningradskaya-oblast/{WEAR}'
    assert all(row.get('region_slug') == 'kaliningradskaya-oblast' for row in body['results'])
    assert body['intent']['regions'] == ['region:russia:kaliningradskaya-oblast']


def test_bare_region_adjective_does_not_override_a_working_reading(gaps_client):
    """Прилагательное становится регионом только когда иначе выдача пуста: «московская биржа» остаётся биржей."""
    body = get(gaps_client, 'московской биржи')
    assert codes(body) == ['imoex']
    assert body['intent']['regions'] == []


def test_colloquial_republic_name_with_fuel_price(gaps_client):
    """«цена бензина удмуртия»: разговорное название республики."""
    body = get(gaps_client, 'цена бензина удмуртия')
    assert 'ceni-ai92' in codes(body), body
    assert all(row.get('region_slug') == 'udmurtskaya-respublika' for row in body['results'])
    assert not body.get('corrected_query')
    assert 'ceni-ai92' in codes(get(gaps_client, 'бензин в удмуртии'))


def test_gasoline_price_in_region_puts_gasoline_before_diesel(gaps_client):
    """«цена бензина удмуртия»: бензин первой строкой, дизель остаётся в выдаче ниже."""
    found = codes(get(gaps_client, 'цена бензина удмуртия'))
    assert found[0] == 'ceni-ai92', found
    assert 'ceni-dt' in found and found.index('ceni-dt') > found.index('ceni-ai92')
    # Запрос о дизеле по-прежнему ставит первым дизель.
    assert codes(get(gaps_client, 'цена дизеля удмуртия'))[0] == 'ceni-dt'


def test_fuel_cost_means_fuel_price(gaps_client):
    """«стоимость дизельного топлива калужская область» — цена дизеля в регионе, а не продажи в рублях."""
    body = get(gaps_client, 'стоимость дизельного топлива калужская область')
    assert body['results'] and body['results'][0]['code'] == 'ceni-dt', body
    assert body['results'][0]['region_slug'] == 'kaluzhskaya-oblast'
    assert codes(get(gaps_client, 'стоимость дизельного топлива'))[0] == 'fuel-diesel'


def test_national_title_does_not_hide_the_regional_series(gaps_client):
    """«цена дизельного топлива калужская область»: точное название национального ряда не заслоняет региональный."""
    body = get(gaps_client, 'цена дизельного топлива калужская область')
    assert body['results'], body
    assert body['results'][0]['code'] == 'ceni-dt'
    assert body['results'][0]['region_slug'] == 'kaluzhskaya-oblast'
    # Без региона точное название по-прежнему ведёт к национальному ряду.
    assert codes(get(gaps_client, 'цена дизельного топлива'))[0] == 'fuel-diesel'


def test_name_inside_official_title_with_indicator(gaps_client):
    """«врп югра»: слово из официального названия округа вместе с показателем; одиночный запрос «югра» не меняется."""
    body = get(gaps_client, 'врп югра')
    assert body['results'] and body['results'][0]['code'] == GRP
    assert body['results'][0]['region_slug'] == 'hanty-mansiyskiy-ao'
    alone = get(gaps_client, 'югра')
    assert [row['key'] for row in alone['results']] == ['region:russia:hanty-mansiyskiy-ao']


def test_region_with_grp_abbreviation(gaps_client):
    body = get(gaps_client, 'псковская область врп')
    assert body['results'][0]['code'] == GRP
    assert body['results'][0]['region_slug'] == 'pskovskaya-oblast'


def test_region_indicator_year_follows_available_facts(gaps_client):
    """«воронежская область посевные площади в … году»: год с данными находится, 1980-го в каталоге нет."""
    assert get(gaps_client, 'воронежская область посевные площади')['results'][0]['code'] == SOWN
    row = get(gaps_client, 'воронежская область посевные площади в 2020 году')['results'][0]
    assert row['path'] == f'/russia/region/voronezhskaya-oblast/{SOWN}/2020' and row['navigation'] == 'document'
    # Региональные ряды начинаются с 1990 года: 1980 — пробел каталога, выдачу не выдумываем.
    empty = get(gaps_client, 'воронежская область посевные площади в 1980 году')
    assert empty['results'] == [] and empty['reason'] == 'no_coverage'


# ── 2. Синонимы и сокращения ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('q', ['икт', 'ИКТ', 'цифровизация', 'цифровизации'])
def test_ict_and_digitalisation_find_digital_technology_series(gaps_client, q):
    found = codes(get(gaps_client, q))
    assert DIGITAL in found and INTERNET in found, found
    # Цена доступа в интернет — другой показатель.
    assert 'ceni-internet' not in found


def test_digital_adjective_still_finds_digital_technologies(gaps_client):
    assert codes(get(gaps_client, 'цифровые'))[0] == DIGITAL


@pytest.mark.parametrize('q', ['естественная убыль населения', 'убыль населения'])
def test_natural_decrease_is_natural_population_change(gaps_client, q):
    found = codes(get(gaps_client, q))
    assert found and found[0] == 'population-natural-growth', found
    assert 'population' not in found


def test_full_ppi_name_with_industry(gaps_client):
    """«индекс цен производителей промышленность» — полное название ИЦП, а не индекс промышленного производства."""
    found = codes(get(gaps_client, 'индекс цен производителей промышленность'))
    assert found and found[0] == 'ppi', found
    assert 'ipi' not in found
    # Региональные ряды с тем же названием остаются в выдаче, национальный ИЦП — первой строкой.
    full = codes(get(gaps_client, 'индекс цен производителей промышленных товаров'))
    assert full[0] == 'ppi' and REGIONAL_PPI in full
    # Прежние запросы не тронуты: точное название и сама промышленность.
    assert codes(get(gaps_client, 'индекс цен производителей'))[0] == 'ppi'
    assert codes(get(gaps_client, 'промышленность'))[0] == 'ipi'


@pytest.mark.parametrize('q', ['стоимость грузоперевозок', 'цены на грузоперевозки'])
def test_freight_cost_is_the_freight_tariff_index(gaps_client, q):
    found = codes(get(gaps_client, q))
    assert found and found[0] == FREIGHT, found


# ── 3. Неверная выдача ────────────────────────────────────────────────────────────────────────────

def test_excise_is_not_a_typo_of_shares(gaps_client):
    """«акциз» — настоящее слово, а не описка в «акции»: индекса МосБиржи в выдаче нет, рядов по акцизам в каталоге нет."""
    body = get(gaps_client, 'акциз')
    assert 'imoex' not in codes(body)
    assert body['results'] == [] and body['reason'] == 'no_coverage'
    # Допуск одной опечатки для остальных слов сохранён.
    assert 'imoex' in codes(get(gaps_client, 'акции'))


@pytest.mark.parametrize('q', ['цены на сталь', 'сталь', 'steel'])
def test_steel_is_not_steel_kitchenware(gaps_client, q):
    """Товар из стали (чайник, кастрюля) — не цена стали; активного ряда цены стали в каталоге нет."""
    body = get(gaps_client, q)
    assert not {KETTLE, PAN}.intersection(codes(body)), body
    assert body['results'] == [] and body['reason'] == 'no_coverage'


def test_steel_kitchenware_is_still_found_by_its_own_name(gaps_client):
    assert KETTLE in codes(get(gaps_client, 'чайник'))
    assert PAN in codes(get(gaps_client, 'кастрюля'))


def test_state_puts_government_consumption_first(gaps_client):
    """«государство»: государственное потребление выше зелёных облигаций Австрии; состав выдачи прежний."""
    found = codes(get(gaps_client, 'государство'))
    assert found[0] == 'gdp-government', found
    assert 'at-sdg_13_70a-pc-tot' in found


def test_second_readings_need_a_trigger_and_are_bounded(gaps_client, auth_env):
    """Второе чтение есть только у запроса с точным названием ряда или словом-началом названия региона."""
    from app.services.search import _MAX_SECOND_READINGS, _geometry, _literal_title, _second_readings

    async def readings(q):
        async with auth_env['session_maker']() as db:
            geometry, _countries = await _geometry(db)
            title = await _literal_title(db, q, geometry)
            intent = parse_intent(q, geometry, literal_content=title)
            return await _second_readings(db, q, geometry, intent, title)

    assert asyncio.run(readings('квазар')) == []
    assert asyncio.run(readings('воронежская область посевные площади в 1980 году')) == []
    assert 1 <= len(asyncio.run(readings('цена дизельного топлива калужская область'))) <= _MAX_SECOND_READINGS
    assert len(asyncio.run(readings('калининградская степень износа'))) == 1


# ── Разбор запроса ────────────────────────────────────────────────────────────────────────────────

GEOMETRY = [
    dict(key='region:russia:udmurtskaya-respublika', kind='region', slug='udmurtskaya-respublika', name_ru='Удмуртская Республика',
        name_en='Udmurt Republic', country_slug='russia'),
    dict(key='region:russia:kemerovskaya-oblast', kind='region', slug='kemerovskaya-oblast', name_ru='Кемеровская область — Кузбасс',
        name_en='Kemerovo Oblast — Kuzbass', country_slug='russia'),
    dict(key='region:russia:hanty-mansiyskiy-ao', kind='region', slug='hanty-mansiyskiy-ao',
        name_ru='Ханты-Мансийский автономный округ — Югра', name_en='Khanty-Mansi Autonomous Okrug — Yugra', country_slug='russia'),
    dict(key='region:russia:respublika-saha', kind='region', slug='respublika-saha', name_ru='Республика Саха (Якутия)',
        name_en='Sakha Republic (Yakutia)', country_slug='russia'),
    dict(key='region:russia:chechenskaya-respublika', kind='region', slug='chechenskaya-respublika', name_ru='Чеченская Республика',
        name_en='Chechen Republic', country_slug='russia'),
]


@pytest.mark.parametrize('q,slug', [
    ('зарплата удмуртия', 'udmurtskaya-respublika'), ('зарплата в удмуртии', 'udmurtskaya-respublika'),
    ('зарплата кузбасс', 'kemerovskaya-oblast'),
    ('зарплата хмао', 'hanty-mansiyskiy-ao'), ('зарплата якутия', 'respublika-saha'),
    ('зарплата чечня', 'chechenskaya-respublika'), ('зарплата в чечне', 'chechenskaya-respublika'),
])
def test_colloquial_region_names_are_geography(q, slug):
    intent = parse_intent(q, GEOMETRY)
    assert intent.regions == frozenset((f'region:russia:{slug}',))
    assert intent.corrected is None
    assert len(intent.terms) == 1


@pytest.mark.parametrize('q,slug', [
    ('зарплата югра', 'hanty-mansiyskiy-ao'), ('зарплата в югре', 'hanty-mansiyskiy-ao'),
    ('зарплата кемеровская область', 'kemerovskaya-oblast'), ('зарплата в кемеровской области', 'kemerovskaya-oblast'),
    ('зарплата в якутии', 'respublika-saha'),
])
def test_names_inside_official_titles_are_geography_in_the_second_reading(q, slug):
    """«Югра», «Кемеровская область» стоят в официальном названии: одиночный запрос уже находит субъект и не меняется."""
    first = parse_intent(q, GEOMETRY)
    second = region_reading(q, first, GEOMETRY)
    assert second is not None and second.regions == frozenset((f'region:russia:{slug}',))
    assert len(second.terms) == 1 and second.terms[0][0] == 'wage'
    # Одиночное название в первом чтении остаётся словом запроса, как раньше.
    name = q.replace('зарплата в ', '').replace('зарплата ', '')
    assert parse_intent(name, GEOMETRY).regions == frozenset()


def test_second_reading_is_absent_for_ordinary_queries():
    intent = parse_intent('зарплата', GEOMETRY)
    assert region_reading('зарплата', intent, GEOMETRY) is None
