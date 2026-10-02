"""Search may use both language labels while display copy stays host-localized."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.models import Region, RegionDataPoint, RegionIndicator


@pytest.fixture
def regional_search_client(auth_env):
    async def seed():
        async with auth_env["session_maker"]() as db:
            district = Region(slug="cfo", name="Центральный федеральный округ", kind="district")
            moscow = Region(slug="moskva", name="г. Москва", kind="region", district_slug="cfo")
            population = RegionIndicator(
                code="chislennost-naseleniya", name="Численность населения",
                unit="тысяч человек", section_num=1, section_name="Население",
                table_code="1.1", year_min=2023, year_max=2024, is_listed=True,
            )
            db.add_all([district, moscow, population])
            await db.flush()
            db.add_all([
                RegionDataPoint(region_id=moscow.id, indicator_id=population.id, year=2023, value=13000),
                RegionDataPoint(region_id=moscow.id, indicator_id=population.id, year=2024, value=13100),
            ])
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


@pytest.mark.parametrize("locale", ["ru", "en"])
def test_regional_catalog_profile_and_landing_keep_bilingual_search_fields(regional_search_client, locale):
    headers = {"X-FE-Locale": locale}
    catalog = regional_search_client.get("/api/v1/regions/catalog", headers=headers)
    assert catalog.status_code == 200
    section = catalog.json()["sections"][0]
    item = section["indicators"][0]
    assert item["name_ru"] == "Численность населения"
    assert item["name_en"] == "Population"
    assert item["unit_ru"] == "тысяч человек"
    assert item["unit_en"] == "thousand people"
    assert item["name"] == item[f"name_{locale}"]
    assert item["unit"] == item[f"unit_{locale}"]
    assert section["name"] == section[f"name_{locale}"]

    profile = regional_search_client.get("/api/v1/regions/moskva", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    result = body["sections"][0]["indicators"][0]
    assert result["name_ru"] == item["name_ru"]
    assert result["name_en"] == item["name_en"]
    assert result["value"] == 13100
    assert body["region"]["name_ru"] == "г. Москва"
    assert body["region"]["name_en"] == "Moscow"
    assert body["region"]["name"] == body["region"][f"name_{locale}"]

    landing = regional_search_client.get("/api/v1/regions", headers=headers)
    assert landing.status_code == 200
    region = landing.json()["districts"][0]["regions"][0]
    assert region["name_ru"] == "г. Москва"
    assert region["name_en"] == "Moscow"
