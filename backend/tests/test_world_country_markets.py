"""Рыночные ряды общего каталога на странице страны."""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture
def markets_client(auth_env):
    import asyncio
    from fastapi.testclient import TestClient
    from app.models import Indicator, IndicatorData, WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            us = WorldCountry(
                code="US", slug="united-states", name_ru="США",
                name_en="United States", region_ru="Америка", sort_order=1,
            )
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия",
                name_en="Germany", region_ru="Европа", sort_order=2,
            )
            db.add_all([us, de])
            await db.flush()

            une = WorldIndicator(
                country_id=us.id,
                code="us-unemployment",
                dataset_id="us_unrate",
                slice_json={"freq": "M"},
                slice_hash="us-une",
                name_ru="Уровень безработицы",
                name_en="Unemployment rate",
                name_quality="curated",
                unit="PC",
                unit_ru="%",
                frequency="monthly",
                category_ru="Рынок труда",
                source="BLS",
                history_start=date(2024, 1, 1),
                history_end=date(2026, 6, 1),
                points_count=2,
                is_listed=True,
            )
            db.add(une)
            await db.flush()
            db.add_all([
                WorldDataPoint(indicator_id=une.id, date=date(2024, 1, 1), value=3.7),
                WorldDataPoint(indicator_id=une.id, date=date(2026, 6, 1), value=4.1),
            ])

            ust = Indicator(
                code="ust-10y",
                name="Доходность 10-летних гособлигаций США",
                name_en="U.S. 10-Year Treasury Yield",
                unit="%",
                frequency="daily",
                source="Министерство финансов США",
                parser_type="fred_csv",
                is_active=True,
                is_listed=True,
            )
            usd = Indicator(
                code="usd-index",
                name="Индекс доллара США",
                name_en="Broad U.S. Dollar Index",
                unit="пунктов",
                frequency="daily",
                source="ФРС США",
                parser_type="fred_csv",
                is_active=True,
                is_listed=True,
            )
            db.add_all([ust, usd])
            await db.flush()
            db.add_all([
                IndicatorData(indicator_id=ust.id, date=date(2026, 8, 20), value=4.21),
                IndicatorData(indicator_id=ust.id, date=date(2026, 8, 21), value=4.25),
                IndicatorData(indicator_id=usd.id, date=date(2026, 8, 21), value=120.10),
            ])
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_united_states_exposes_market_indicators(markets_client):
    body = markets_client.get("/api/v1/world/countries/united-states").json()
    markets = body["market_indicators"]
    codes = [item["code"] for item in markets]
    assert codes == ["ust-10y", "usd-index"]

    ust = markets[0]
    assert ust["name"] == "Доходность 10-летних гособлигаций США"
    assert ust["name_en"]
    assert ust["unit"] == "%"
    assert ust["last_value"] == 4.25
    assert ust["last_date"] == "2026-08-21"

    world_codes = [
        item["code"]
        for cat in body["categories"]
        for item in cat["indicators"]
    ]
    assert "us-unemployment" in world_codes
    assert "ust-10y" not in world_codes


def test_germany_market_indicators_empty(markets_client):
    body = markets_client.get("/api/v1/world/countries/germany").json()
    assert body["market_indicators"] == []


def test_united_states_market_names_follow_locale(markets_client):
    en = markets_client.get(
        "/api/v1/world/countries/united-states",
        headers={"X-FE-Locale": "en"},
    ).json()
    by_code = {item["code"]: item for item in en["market_indicators"]}
    assert by_code["ust-10y"]["name"] == "U.S. 10-year Treasury yield"
    assert by_code["usd-index"]["name"] == "Broad U.S. Dollar Index"
