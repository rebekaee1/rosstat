"""Native title spans and producer units preserve all external constraints."""
import asyncio
from datetime import date

import pytest

from app.services.search import _unit_metadata
from app.services.search_units import unit_metadata
from test_search_federated import get, search_client  # noqa: F401


@pytest.mark.parametrize("unit", ["Percentage points", "PC_PNT", "п.п.", "процентные пункты"])
def test_percentage_points_never_become_percent(unit):
    metadata = _unit_metadata(unit)
    assert "search-unit-percentage-point" in metadata
    assert "search-unit-percent " not in metadata + " "
    assert "search-unit-percentage-point" not in _unit_metadata("Percent")


def test_generic_dollar_requires_declared_producer_currency():
    assert "search-unit-usd" not in unit_metadata("Thousands of dollars")
    assert "search-unit-usd" in unit_metadata("Thousands of dollars", native_currency="USD")
    assert "search-unit-usd" not in unit_metadata("Canadian dollars", native_currency="USD")
    assert "search-unit-usd" not in unit_metadata("people", native_currency="USD")


@pytest.mark.parametrize("unit,key", [("RUB/л", "litre"), ("USD/t", "tonne"), ("USD / t", "tonne"), ("USD/t/year", "tonne"), ("тыс. тонн", "tonne"), ("килограммов", "kilogram")])
def test_native_physical_unit_has_exact_dimension(unit, key):
    assert "search-unit-" + key in unit_metadata(unit)
    assert "search-unit-tonne" not in unit_metadata("RUB/тыс. человек")
    assert "search-unit-litre" not in unit_metadata("points/level")


def test_percentage_point_constraint_precedes_world_budget(auth_env, search_client):
    from app.models import WorldCountry, WorldIndicator, WorldDataPoint
    from sqlalchemy import select
    async def seed():
        async with auth_env["session_maker"]() as db:
            country = (await db.execute(select(WorldCountry).where(WorldCountry.slug == "germany"))).scalar_one()
            rows = [WorldIndicator(country_id=country.id, code=f"aaa-pressure-{i}", name_ru="Pressure change", name_en="Pressure change", unit="Percent", frequency="annual", is_listed=True, points_count=1, dataset_id="fixture-pressure", slice_hash=str(i)) for i in range(105)]
            rows.append(WorldIndicator(country_id=country.id, code="zzz-pressure", name_ru="Pressure change", name_en="Pressure change", unit="Percentage points", frequency="annual", is_listed=True, points_count=1, dataset_id="fixture-pressure", slice_hash="pp"))
            db.add_all(rows)
            await db.flush()
            db.add_all(WorldDataPoint(indicator_id=row.id, date=date(2024, 1, 1), value=7) for row in rows)
            await db.commit()
    asyncio.run(seed())
    result = get(search_client, "pressure change Germany percentage points 2024")
    assert [row["code"] for row in result["results"]] == ["zzz-pressure"], result
    assert not get(search_client, "pressure change Germany percentage points percent 2024")["results"]
    assert not get(search_client, "pressure change Germany percentage points magical 2024")["results"]


def test_native_symbol_spacing_and_suffix_have_sql_scorer_parity(auth_env, search_client):
    from app.models import WorldCountry, WorldIndicator, WorldDataPoint
    from sqlalchemy import select
    async def seed():
        async with auth_env["session_maker"]() as db:
            country = (await db.execute(select(WorldCountry).where(WorldCountry.slug == "germany"))).scalar_one()
            units = ("USD/t", "USD / t", "USD/t/year", "USD /\tl", "USD/level", "USD/thousand persons")
            rows = [WorldIndicator(country_id=country.id, code=f"physical-{i}", name_ru="Physical fixture", name_en="Physical fixture", unit=unit, frequency="annual", dataset_id="fixture-physical", slice_hash=str(i), is_listed=True, points_count=1) for i, unit in enumerate(units)]
            db.add_all(rows)
            await db.flush()
            db.add_all(WorldDataPoint(indicator_id=row.id, date=date(2024, 1, 1), value=5) for row in rows)
            await db.commit()
    asyncio.run(seed())
    assert {row["code"] for row in get(search_client, "Physical fixture Germany USD per tonne 2024")["results"]} == {"physical-0", "physical-1", "physical-2"}
    assert {row["code"] for row in get(search_client, "Physical fixture Germany USD per litre 2024")["results"]} == {"physical-3"}


@pytest.mark.parametrize("title", ["Wheat (US winter) price", "Объём выполненных строительных работ", "Native rate (change in %)"])
def test_embedded_native_title_protects_internal_facets(auth_env, search_client, title):
    from app.models import Indicator, IndicatorData
    async def seed():
        async with auth_env["session_maker"]() as db:
            row = Indicator(code="embedded-native", name=title, name_en=title, unit="people", frequency="annual", category="Test", source="fixture", source_url="https://example.test")
            db.add(row)
            await db.flush()
            db.add(IndicatorData(indicator_id=row.id, date=date(2024, 1, 1), value=9))
            await db.commit()
    asyncio.run(seed())
    query = title + " Russia annual persons 2024"
    assert get(search_client, query)["results"][0]["code"] == "embedded-native"
    assert not get(search_client, query + " magical")["results"]
    assert not get(search_client, query + " percent")["results"]


def test_us_state_generic_native_dollars_match_only_usd(auth_env, search_client):
    from app.models import SubnationalRegion, SubnationalIndicator, SubnationalDataPoint
    from sqlalchemy import select
    async def seed():
        async with auth_env["session_maker"]() as db:
            region = (await db.execute(select(SubnationalRegion).where(SubnationalRegion.slug == "california"))).scalar_one()
            row = SubnationalIndicator(country_code="US", code="state-fixture-receipts", name_ru="Special receipts", name_en="Special receipts", series_template="fixture", frequency="annual", unit="Thousands of dollars", unit_ru="тыс. долл.", unit_en="Thousands of dollars")
            db.add(row)
            await db.flush()
            db.add(SubnationalDataPoint(indicator_id=row.id, region_id=region.id, period=date(2024, 1, 1), value=11))
            await db.commit()
    asyncio.run(seed())
    query = "special receipts California annual thousand USD 2024"
    assert [row["code"] for row in get(search_client, query)["results"]] == ["state-fixture-receipts"]
    assert not get(search_client, query.replace("USD", "CAD"))["results"]
    assert not get(search_client, query + " magical")["results"]
