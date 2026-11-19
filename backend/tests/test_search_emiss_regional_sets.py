"""Поиск по помесячным региональным рядам ЕМИСС зоны E (19.11.2026).

Запросы — пустые поиски людей из отчёта каталога ЕМИСС 19.11.2026 («цена подсолнечник», «цена семена»,
«стоимость грузоперевозок», посевные и ввод жилья по регионам) и запросы Яндекса («цена пшеницы»).
Названия и единицы рядов — из реестра ``app.data.emiss_regional_sets``; потребительская цена подсолнечного
масла и годовые ряды стоят рядом, чтобы проверить порядок выдачи.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.data.emiss_regional_sets import artifact_rows

ANNUAL_FREIGHT = "indeksy-tarifov-na-gruzovye-perevozki"
ANNUAL_HOUSING = "vvod-v-deystvie-zhilyh-domov"
OIL = "ceni-maslo-podsolnechnoe"


@pytest.fixture
def client(auth_env):
    from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint

    async def seed():
        async with auth_env["session_maker"]() as db:
            regions = [Region(slug=slug, name=name, kind="region") for slug, name in (
                ("voronezhskaya-oblast", "Воронежская область"), ("krasnodarskiy-kray", "Краснодарский край"),
                ("pskovskaya-oblast", "Псковская область"))]
            db.add_all(regions)
            monthly = [RegionIndicator(code=r["code"], name=r["name"], table_code=r["table_code"],
                                       section_num=r["section_num"], section_name=r["section_name"], unit=r["unit"])
                       for r in artifact_rows()]
            monthly.append(RegionIndicator(code=OIL, name="Средняя цена: масло подсолнечное, рублей за литр",
                                           table_code="20.m10", section_num=20, section_name="Цены и тарифы",
                                           unit="рублей за литр"))
            annual = [
                RegionIndicator(code=ANNUAL_FREIGHT, name="Индексы тарифов на грузовые перевозки", table_code="20.9",
                                section_num=20, section_name="Цены и тарифы", unit="процент"),
                RegionIndicator(code=ANNUAL_HOUSING, name="Ввод в действие жилых домов", table_code="14.3",
                                section_num=14, section_name="Строительство", unit="тысяч м² общей площади"),
            ]
            db.add_all((*monthly, *annual))
            await db.flush()
            for region in regions:
                for row in monthly:
                    db.add(RegionMonthlyPoint(indicator_id=row.id, region_id=region.id, month=202609, value=60))
                for row in annual:
                    db.add(RegionDataPoint(indicator_id=row.id, region_id=region.id, year=2024, value=50))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as c:
        yield c


def codes(client, q):
    response = client.get("/api/v1/search", params={"q": q})
    assert response.status_code == 200, response.text
    return [row.get("code") for row in response.json()["results"]]


@pytest.mark.parametrize("q", ["цена подсолнечник", "цена подсолнечника", "подсолнечник цена воронежская область"])
def test_sunflower_price_finds_the_farm_price(client, q):
    found = codes(client, q)
    assert "selhoz-cena-podsolnechnik" in found[:3], found


@pytest.mark.parametrize("q", ["цена пшеницы", "пшеница цена краснодарский край"])
def test_wheat_price_finds_the_farm_price(client, q):
    assert "selhoz-cena-pshenica" in codes(client, q)[:3]


def test_seed_price_finds_oilseeds(client):
    found = codes(client, "цена семена")
    assert {"selhoz-cena-podsolnechnik", "selhoz-cena-raps"} & set(found[:5]), found


@pytest.mark.parametrize("q", ["стоимость грузоперевозок", "цены на грузоперевозки"])
def test_freight_cost_keeps_the_tariff_index_first_and_adds_monthly(client, q):
    found = codes(client, q)
    assert found and found[0] in (ANNUAL_FREIGHT, "tarif-gruz-vse-mes"), found
    assert "tarif-gruz-vse-mes" in found, found


def test_housing_by_region_finds_the_monthly_series(client):
    found = codes(client, "ввод жилья воронежская область")
    assert "vvod-zhilya-mes" in found[:3], found


def test_sunflower_oil_is_still_found(client):
    assert OIL in codes(client, "подсолнечное масло")[:2]
