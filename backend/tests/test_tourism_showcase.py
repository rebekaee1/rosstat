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
    assert hotels["rating_path"] == "/russia/region-rating/kollektivnye-sredstva"
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
    assert "Туризм по регионам России" in html and 'href="/russia/region-rating/kollektivnye-sredstva"' in html
    assert 'href="/russia/region/krasnodarskiy-kray/kollektivnye-sredstva"' in html
    assert "Туризм в странах мира" in html and 'href="/turkey/indicator/tr-tourist-arrivals"' in html
    assert f'href="/world/rating/{rating.slug}"' in html
    assert 'name="keywords"' in html and "турпоток" in html
    ld = [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    page = next(b for b in ld if b.get("@type") == "CollectionPage")
    urls = {e["url"] for e in page["mainEntity"]}
    assert any(u.endswith("/russia/region-rating/kollektivnye-sredstva") for u in urls)
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
