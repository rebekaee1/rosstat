"""R9-B: топ подорожавших и подешевевших в сводке цен России."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.models import Region, RegionIndicator, RegionMonthlyPoint


@pytest.fixture
def movers_client(auth_env):
    async def seed():
        async with auth_env["session_maker"]() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            a = RegionIndicator(code="ceni-yaytsa", name="Средняя цена: яйца, рублей за 10 штук", unit="рублей за 10 штук",
                                section_num=20, section_name="Цены и тарифы", table_code="20.m1", is_listed=True)
            b = RegionIndicator(code="ceni-moloko", name="Средняя цена: молоко, рублей за литр", unit="рублей за литр",
                                section_num=20, section_name="Цены и тарифы", table_code="20.m1", is_listed=True)
            db.add_all([rf, a, b])
            await db.flush()
            for ind, old, new in ((a, 100.0, 120.0), (b, 80.0, 72.0)):
                db.add(RegionMonthlyPoint(region_id=rf.id, indicator_id=ind.id, month=202509, value=old))
                db.add(RegionMonthlyPoint(region_id=rf.id, indicator_id=ind.id, month=202609, value=new))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def test_movers_split_up_and_down(movers_client):
    data = movers_client.get("/api/v1/regions/russia/prices-summary").json()
    mv = data["movers"]
    assert [m["code"] for m in mv["up"]] == ["ceni-yaytsa"]
    assert mv["up"][0]["yoy_pct"] == 20.0
    assert [m["code"] for m in mv["down"]] == ["ceni-moloko"]
    assert mv["down"][0]["yoy_pct"] == -10.0
    assert mv["period_label"] == "сентябрь 2026"
