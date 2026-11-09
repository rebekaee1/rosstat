"""R4-A: сравнение цен двух регионов, корзина, зарплата в корзинах."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint
from app.services.r4a_price_compare import BASKET


@pytest.fixture
def cmp_client(auth_env):
    async def seed():
        async with auth_env["session_maker"]() as db:
            a = Region(slug="voronezhskaya-oblast", name="Воронежская область", kind="region")
            b = Region(slug="krasnodarskiy-kray", name="Краснодарский край", kind="region")
            msk = Region(slug="moskva", name="г. Москва", kind="city")
            wage = RegionIndicator(code="w34", name="Зарплата", unit="рублей", section_num=3,
                                   section_name="Оплата труда", table_code="3.4", is_listed=True)
            db.add_all([a, b, msk, wage])
            await db.flush()
            db.add_all([RegionDataPoint(region_id=a.id, indicator_id=wage.id, year=2025, value=60000),
                        RegionDataPoint(region_id=b.id, indicator_id=wage.id, year=2025, value=75000)])
            for n, (code, _q) in enumerate(BASKET):
                ind = RegionIndicator(code=code, name=f"Цена {code}", unit="рублей", section_num=20,
                                      section_name="Цены", table_code=f"20.m{n}", is_listed=True)
                db.add(ind)
                await db.flush()
                db.add(RegionMonthlyPoint(region_id=a.id, indicator_id=ind.id, month=202609, value=100))
                db.add(RegionMonthlyPoint(region_id=b.id, indicator_id=ind.id, month=202608, value=90))
                db.add(RegionMonthlyPoint(region_id=b.id, indicator_id=ind.id, month=202609, value=110))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def test_price_compare_basket_and_wage(cmp_client):
    r = cmp_client.get("/api/v1/regions/vs/voronezhskaya-oblast/krasnodarskiy-kray/prices")
    assert r.status_code == 200
    d = r.json()
    assert d["month"] == 202609 and d["period_label"] == "сентябрь 2026"
    b = d["basket"]
    assert b["cheaper_slug"] == "voronezhskaya-oblast"
    assert b["diff_pct"] == 10.0
    assert d["wage"]["baskets_a"] == round(60000 / b["total_a"], 1)
    assert d["cheaper_count"]["a"] == d["cheaper_count"]["total"]


def test_price_compare_rejects_same_and_cities(cmp_client):
    assert cmp_client.get("/api/v1/regions/vs/moskva/krasnodarskiy-kray/prices").status_code == 404
    assert cmp_client.get("/api/v1/regions/vs/krasnodarskiy-kray/krasnodarskiy-kray/prices").status_code == 404



def test_latest_monthly_points_takes_only_last_n_per_pair(auth_env):
    """09.11.2026: последние точки пары без чтения всей истории (на SQLite — переносимый путь, тот же результат)."""
    from app.services.regional_monthly_latest import latest_monthly_points

    async def scenario():
        async with auth_env["session_maker"]() as db:
            reg = Region(slug="test-lmp", name="Тест", kind="region")
            ind = RegionIndicator(code="ceni-test-lmp", table_code="20.m1", section_num=20, section_name="Цены",
                                  name="Тест", unit="руб.", is_listed=True)
            db.add_all([reg, ind])
            await db.flush()
            db.add_all([RegionMonthlyPoint(indicator_id=ind.id, region_id=reg.id, month=m, value=float(m % 100))
                        for m in (202401, 202402, 202609, 202608)])
            await db.commit()
            one = await latest_monthly_points(db, [ind.id], [reg.id], n=1)
            two = await latest_monthly_points(db, [ind.id], [reg.id], n=2)
            none = await latest_monthly_points(db, [], [reg.id])
            return one[(ind.id, reg.id)], two[(ind.id, reg.id)], none

    one, two, none = asyncio.run(scenario())
    assert one == [(202609, 9.0)]
    assert two == [(202609, 9.0), (202608, 8.0)]
    assert none == {}
