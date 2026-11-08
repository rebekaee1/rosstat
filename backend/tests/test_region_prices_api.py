"""API цен региона: поля подачи и сравнение с Россией и Москвой (Z1)."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.models import Region, RegionIndicator, RegionMonthlyPoint


@pytest.fixture
def prices_client(auth_env):
    async def seed():
        async with auth_env["session_maker"]() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            msk = Region(slug="moskva", name="г. Москва", kind="region")
            alt = Region(slug="altayskiy-kray", name="Алтайский край", kind="region")
            eggs = RegionIndicator(
                code="ceni-yaytsa", name="Средняя цена: яйца куриные, рублей за 10 штук",
                unit="рублей за 10 штук", section_num=20, section_name="Цены и тарифы",
                table_code="20.m1", is_listed=True,
            )
            db.add_all([rf, msk, alt, eggs])
            await db.flush()
            for reg, base in ((rf, 100.0), (msk, 120.0), (alt, 90.0)):
                for month, bump in ((202608, 0), (202609, 2)):
                    db.add(RegionMonthlyPoint(region_id=reg.id, indicator_id=eggs.id, month=month, value=base + bump))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def test_profile_and_monthly_expose_price_fields_and_compare(prices_client):
    prof = prices_client.get("/api/v1/regions/altayskiy-kray").json()
    item = prof["sections"][0]["indicators"][0]
    assert item["short_name"] == "Яйца куриные, 10 шт."
    assert item["price_group"] == "Продукты"
    assert item["is_discontinued"] is False and item["last_month"] >= 202609
    assert item["period_label"] == "сентябрь 2026"
    assert "ceni-yaytsa" in prof["price_headline_codes"]

    mon = prices_client.get("/api/v1/regions/altayskiy-kray/i/ceni-yaytsa/monthly").json()
    assert mon["indicator"]["short_name"] == "Яйца куриные, 10 шт."
    assert mon["compare"]["russia"] == {"value": 102.0, "month": 202609}
    assert mon["compare"]["moskva"] == {"value": 122.0, "month": 202609}

    own = prices_client.get("/api/v1/regions/moskva/i/ceni-yaytsa/monthly").json()
    assert own["compare"]["moskva"] is None and own["compare"]["russia"]["value"] == 102.0
