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


def test_warm_builds_missing_key_and_skips_cached(movers_client, auth_env, monkeypatch):
    """Прогрев собирает сводку, если ключа нет, и ничего не делает, если ключ на месте."""
    import app.api.regions as regions
    import app.database as database

    store: dict = {}
    calls: list[str] = []

    async def fake_get(key):
        return store.get(key)

    async def fake_build(db, key):
        calls.append(key)
        payload = {"items": [{"code": "ceni-yaytsa"}]}
        store[key] = payload
        return payload

    monkeypatch.setattr(database, "async_session", auth_env["session_maker"])
    monkeypatch.setattr(regions, "cache_get", fake_get)
    monkeypatch.setattr(regions, "_build_russia_prices_summary", fake_build)
    assert asyncio.run(regions.warm_russia_prices_summary(force=False)) == {"ru": 1, "en": 1}
    assert asyncio.run(regions.warm_russia_prices_summary(force=False)) == {}
    assert len(calls) == 2
    assert asyncio.run(regions.warm_russia_prices_summary(force=True)) == {"ru": 1, "en": 1}
    assert len(calls) == 4


def test_movers_skip_discontinued(movers_client, monkeypatch):
    """Ряды, которые Росстат больше не публикует, в расчёт топа не попадают."""
    import app.api.regions as regions

    real = regions.price_meta

    def fake(code):
        meta = real(code)
        if meta and code == "ceni-moloko":
            return {**meta, "is_discontinued": True}
        return meta

    monkeypatch.setattr(regions, "price_meta", fake)
    monkeypatch.setattr(regions, "versioned_key", _fresh_key)
    data = movers_client.get("/api/v1/regions/russia/prices-summary").json()
    mv = data.get("movers") or {}
    assert all(m["code"] != "ceni-moloko" for m in mv.get("down", []) + mv.get("up", []))


async def _fresh_key(namespace, key):
    return f"test-fresh:{namespace}:{key}"
