"""Сводка средних цен по России для национального каталога (R7-D)."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.models import Region, RegionIndicator, RegionMonthlyPoint


@pytest.fixture
def summary_client(auth_env):
    async def seed():
        async with auth_env["session_maker"]() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            eggs = RegionIndicator(
                code="ceni-yaytsa", name="Средняя цена: яйца куриные, рублей за 10 штук",
                unit="рублей за 10 штук", section_num=20, section_name="Цены и тарифы",
                table_code="20.m1", is_listed=True,
            )
            db.add_all([rf, eggs])
            await db.flush()
            for month, val in ((202509, 100.0), (202608, 108.0), (202609, 110.0)):
                db.add(RegionMonthlyPoint(region_id=rf.id, indicator_id=eggs.id, month=month, value=val))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def test_summary_has_price_year_change_and_spark(summary_client):
    data = summary_client.get("/api/v1/regions/russia/prices-summary").json()
    assert len(data["items"]) == 1
    it = data["items"][0]
    assert it["code"] == "ceni-yaytsa"
    assert it["value"] == 110.0 and it["prev_value"] == 108.0
    assert it["year_ago_value"] == 100.0 and it["yoy_pct"] == 10.0
    assert it["period_label"] == "сентябрь 2026"
    assert it["spark"] == [100.0, 108.0, 110.0]
    assert it["short_name"] == "Яйца куриные, 10 шт."
    assert data["groups"][0]["group"] == "Продукты" and data["total"] >= 1


def test_summary_404_without_russia(auth_env):
    with TestClient(auth_env["app"]) as client:
        assert client.get("/api/v1/regions/russia/prices-summary").status_code == 404
