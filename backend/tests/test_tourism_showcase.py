"""Раздел «Туризм» (20.11.2026): этажи Россия / регионы / мир, серверная страница и поиск по бытовым словам."""
import asyncio
import json
import re
from datetime import date

import pytest

from app.services.search_intent import parse_intent
from app.services.tourism_showcase import is_tourism_region_indicator


@pytest.mark.parametrize(("code", "section", "name", "expected"), [
    ("tour-hotels-nights", "Прочее", "Ночёвки", True),
    ("x", "Туризм", "Что угодно", True),
    ("x", "Культура, отдых и туризм", "Коллективные средства размещения — число коллективных средств размещения", True),
    ("x", "Культура, отдых и туризм", "Туристские фирмы — число туристских фирм", True),
    ("x", "Цены и тарифы", "Средняя цена: проживание в гостинице, рублей за сутки с человека", True),
    ("x", "Цены и тарифы", "Средняя цена: санаторий, рублей за день", True),
    ("x", "Культура, отдых и туризм", "Численность зрителей театров", False),
    ("x", "Уровень жизни населения", "Средняя зарплата по месяцам: гостиницы и общепит", False),
    ("x", "ЖКХ", "Число котельных", False),
    ("x", "Финансы", "Средства, размещенные на депозитах", False),
])
def test_regional_selection_is_a_rule_not_a_list(code, section, name, expected):
    assert is_tourism_region_indicator(code, section, name) is expected


@pytest.mark.parametrize(("query", "key"), [
    ("туризм", "tour-"),
    ("туризм в россии", "tour-"),
    ("турпоток", "tour-"),
    ("tourism", "tour-"),
    ("выездной туризм", "tour-outbound"),
    ("поездки за границу", "tour-outbound"),
    ("въездной туризм", "tour-inbound"),
    ("иностранные туристы", "tour-inbound"),
    ("гостиницы", "tour-hotel"),
    ("отели", "tour-hotel"),
    ("ночевки", "tour-hotel"),
    ("санатории", "tour-sanator"),
    ("турфирмы", "tour-firm"),
    ("туристический налог", "tour-tax"),
    ("курортный сбор", "tour-tax"),
])
def test_tourism_words_reach_the_section(query, key):
    keys = [group[0] for group in parse_intent(query, []).terms]
    assert key in keys, keys


def test_old_arrivals_concept_is_kept():
    # «Туристы» по-прежнему ведут к прибытиям (search_language), новый словарь его не перехватывает.
    assert parse_intent("туристы", []).terms[0][0] == "tourism"


@pytest.fixture
def tourism_client(auth_env):
    from fastapi.testclient import TestClient

    from app.data.world_concepts import WORLD_CONCEPTS
    from app.models import (
        Indicator,
        Region,
        RegionDataPoint,
        RegionIndicator,
        WorldCountry,
        WorldIndicator,
    )

    rating = next(c for c in WORLD_CONCEPTS if "rating" in c.enabled_surfaces)

    async def seed():
        async with auth_env["session_maker"]() as db:
            db.add(Indicator(code="tour-outbound-trips", name="Выездные туристские поездки россиян",
                             name_en="Outbound tourist trips by Russians", unit="тыс.", frequency="quarterly",
                             category="Туризм", source="Росстат", is_active=True, is_listed=True))
            regions = [Region(slug=s, name=n, kind="region") for s, n in (
                ("moskva", "г. Москва"), ("krasnodarskiy-kray", "Краснодарский край"),
                ("respublika-krym", "Республика Крым"), ("tverskaya-oblast", "Тверская область"))]
            hotels = RegionIndicator(code="kollektivnye-sredstva", table_code="6.5.1", section_num=6,
                                     section_name="Культура, отдых и туризм",
                                     name="Коллективные средства размещения — число коллективных средств размещения",
                                     unit="единица", year_max=2024, is_listed=True)
            theatre = RegionIndicator(code="teatry", table_code="6.1.1", section_num=6,
                                      section_name="Культура, отдых и туризм",
                                      name="Численность зрителей театров", unit="человек", year_max=2024,
                                      is_listed=True)
            db.add_all([*regions, hotels, theatre])
            await db.flush()
            for region, value in zip(regions, (1500, 2600, 1100, 300)):
                db.add(RegionDataPoint(indicator_id=hotels.id, region_id=region.id, year=2024, value=value))
                db.add(RegionDataPoint(indicator_id=theatre.id, region_id=region.id, year=2024, value=1))
            turkey = WorldCountry(code="TR", slug="turkey", name_ru="Турция", name_en="Turkey")
            db.add(turkey)
            await db.flush()
            db.add(WorldIndicator(country_id=turkey.id, code="tr-tourist-arrivals",
                                  dataset_id=sorted(rating.dataset_ids)[0], slice_hash="t1",
                                  name_ru="Прибытия иностранных туристов", name_en="International tourist arrivals",
                                  unit="THS", unit_ru="тыс.", frequency="monthly", category_ru="Туризм",
                                  points_count=120, is_listed=True, history_end=date(2026, 9, 1)))
            db.add(WorldIndicator(country_id=turkey.id, code="tr-gdp", dataset_id="gdp-x", slice_hash="t2",
                                  name_ru="ВВП", name_en="GDP", unit="USD", unit_ru="долл.", frequency="annual",
                                  category_ru="ВВП", is_listed=True))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client, rating


def test_overview_has_regions_with_leaders_and_world(tourism_client):
    client, rating = tourism_client
    body = client.get("/api/v1/tourism/overview").json()
    assert body["russia"] == {"count": 1, "path": "/russia/category/tourism"}

    codes = [row["code"] for row in body["regions"]["items"]]
    assert codes == ["kollektivnye-sredstva"]  # театры не туризм
    hotels = body["regions"]["items"][0]
    assert hotels["group"] == "stay"
    # Четыре субъекта — у ряда нет страницы рейтинга и карты (нужно ≥ 10): ссылка на ряд по России.
    assert hotels["rating_path"] is None and hotels["map_path"] is None
    assert hotels["path"] == "/russia/region/russia/kollektivnye-sredstva"
    assert [leader["slug"] for leader in hotels["leaders"]] == ["krasnodarskiy-kray", "moskva", "respublika-krym"]
    assert hotels["leaders"][0]["path"] == "/russia/region/krasnodarskiy-kray/kollektivnye-sredstva"

    world = body["world"]
    assert world["count"] == 1
    assert world["countries"][0]["slug"] == "turkey"
    assert world["countries"][0]["series"][0]["path"] == "/turkey/indicator/tr-tourist-arrivals"
    assert [c["slug"] for c in world["concepts"]] == [rating.slug]
    # Публичный ответ без диапазонов и служебных полей.
    assert "lower" not in json.dumps(body) and "upper" not in json.dumps(body)


def test_ssr_tourism_page_has_three_floors_and_markup(tourism_client):
    client, rating = tourism_client
    response = client.get("/seo/category/tourism")
    assert response.status_code == 200
    html = response.text
    assert '<link rel="canonical" href="https://forecasteconomy.com/russia/category/tourism"' in html
    assert re.search(r"<h1>Туризм в России, регионах и мире", html)
    assert 'href="/russia/indicator/tour-outbound-trips"' in html
    assert "Туризм по регионам России" in html and 'href="/russia/region/russia/kollektivnye-sredstva"' in html
    assert "<h3>Гостиницы и санатории</h3>" in html
    assert 'href="/russia/region/krasnodarskiy-kray/kollektivnye-sredstva"' in html
    assert "Туризм в странах мира" in html and 'href="/turkey/indicator/tr-tourist-arrivals"' in html
    assert f'href="/world/rating/{rating.slug}"' in html
    assert 'name="keywords"' in html and "турпоток" in html
    ld = [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    page = next(b for b in ld if b.get("@type") == "CollectionPage")
    urls = {e["url"] for e in page["mainEntity"]}
    assert any(u.endswith("/russia/region/russia/kollektivnye-sredstva") for u in urls)
    assert any(u.endswith("/turkey/indicator/tr-tourist-arrivals") for u in urls)


def test_ssr_tourism_page_in_english(tourism_client, auth_env):
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_renderer import render_category_html

    async def render():
        token = set_locale("en")
        try:
            async with auth_env["session_maker"]() as db:
                return await render_category_html("tourism", db)
        finally:
            reset_locale(token)

    status, html = asyncio.run(render())
    assert status == 200
    assert "<h1>Tourism in Russia, its regions and the world" in html
    assert "Tourism across Russia&#x27;s regions" in html or "Tourism across Russia's regions" in html
    assert "Tourism in countries worldwide" in html and ">Turkey<" in html
    assert "Туризм по регионам" not in html


def test_tourism_is_in_sitemap_categories():
    from app.services.seo_content import CATEGORY_META
    from app.data.i18n.seo_en import CATEGORY_META_EN

    assert CATEGORY_META["tourism"].api_category == CATEGORY_META_EN["tourism"].api_category == "Туризм"
    from app.services.seo_i18n import localize_category_name

    assert localize_category_name("Туризм", locale="en") == "Tourism"


@pytest.mark.parametrize(("name", "group"), [
    ("Гости гостиниц и прочих средств размещения за месяц", "flows"),
    ("Туристы, отправленные турфирмами: Турция", "flows"),
    ("Траты жителей региона в зарубежных поездках", "money"),
    ("Туристический налог за год", "money"),
    ("Средняя цена: санаторий, рублей за день", "prices"),
    ("Средняя цена: проезд в купейном вагоне нефирменного скорого поезда, 100 км", "transport"),
    ("Число туроператоров", "business"),
    ("Туристские фирмы — число туристских фирм", "business"),
    ("Число мест в санаториях", "stay"),
])
def test_region_groups_by_meaning(name, group):
    from app.services.tourism_showcase import region_group

    assert region_group(name) == group


def test_world_series_russia_then_total_first():
    from app.services.tourism_showcase import _world_series_key

    rows = [("tr-arr-az", "Прибытия иностранных туристов: Азербайджан", 200),
            ("tr-arr", "Прибытия иностранных туристов", 150),
            ("tr-emp", "Занятые в туризме, тысяч человек", 300),
            ("tr-arr-russia", "Прибытия туристов из России", 100)]
    ordered = [code for code, name, pts in sorted(rows, key=lambda r: _world_series_key(*r))]
    assert ordered[:2] == ["tr-arr-russia", "tr-arr"]
    assert ordered[-1] == "tr-emp"


def test_rating_links_only_when_page_exists(auth_env):
    from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint
    from app.services.tourism_showcase import build_overview

    async def run():
        async with auth_env["session_maker"]() as db:
            regions = [Region(slug=f"r{i}", name=f"Регион {i}", kind="region") for i in range(11)]
            year = RegionIndicator(code="tour-nalog-za-god", table_code="t", section_num=90, section_name="Туризм",
                                   name="Туристический налог за год", unit="млн руб.", year_max=2025, is_listed=True)
            month = RegionIndicator(code="tour-ksr-razmeshcheno-mes", table_code="t", section_num=90,
                                    section_name="Туризм", name="Гости гостиниц за месяц", unit="тыс.",
                                    year_max=2026, is_listed=True)
            db.add_all([*regions, year, month])
            await db.flush()
            for i, r in enumerate(regions):
                db.add(RegionDataPoint(indicator_id=year.id, region_id=r.id, year=2025, value=i + 1))
                db.add(RegionMonthlyPoint(indicator_id=month.id, region_id=r.id, month=202609, value=i + 1))
            await db.commit()
            return await build_overview(db)

    body = asyncio.run(run())
    rows = {r["code"]: r for r in body["regions"]["items"]}
    assert rows["tour-nalog-za-god"]["rating_path"] == "/russia/region-rating/tour-nalog-za-god"
    assert rows["tour-nalog-za-god"]["map_path"] == "/russia/region/map/tour-nalog-za-god"
    assert rows["tour-ksr-razmeshcheno-mes"]["rating_path"] is None
    assert rows["tour-ksr-razmeshcheno-mes"]["map_path"] is None
    assert rows["tour-ksr-razmeshcheno-mes"]["path"] == "/russia/region/russia/tour-ksr-razmeshcheno-mes"
    # По карточке с лидерами на группу: поток (месячный) и деньги (годовой).
    assert rows["tour-ksr-razmeshcheno-mes"]["leaders"][0]["slug"] == "r10"
    assert rows["tour-nalog-za-god"]["leaders"][0]["slug"] == "r10"


def test_tourism_query_puts_russia_flagships_first_and_districts_last():
    from app.services.search_tourism import tourism_first

    rows = [
        {"key": "rg:cfo", "kind": "region_indicator", "code": "tour-turpotok-nochevki", "region_slug": "cfo"},
        {"key": "ru:tour-cpi-hotels", "kind": "russia", "code": "tour-cpi-hotels"},
        {"key": "w:al", "kind": "world", "code": "al-tourism-gdp-share"},
        {"key": "ru:tour-inbound-trips", "kind": "russia", "code": "tour-inbound-trips"},
        {"key": "rg:ru", "kind": "region_indicator", "code": "tour-ksr", "region_slug": "russia", "regional_group": {}},
        {"key": "ru:tour-outbound-trips", "kind": "russia", "code": "tour-outbound-trips"},
    ]
    keys = [r["key"] for r in tourism_first(rows, parse_intent("туризм", []))]
    assert keys == ["ru:tour-outbound-trips", "ru:tour-inbound-trips", "ru:tour-cpi-hotels", "w:al", "rg:ru", "rg:cfo"]
    assert [r["key"] for r in tourism_first(rows, parse_intent("инфляция", []))] == [r["key"] for r in rows]
    assert tourism_first(rows, parse_intent("tourism", []))[0]["code"] == "tour-outbound-trips"
