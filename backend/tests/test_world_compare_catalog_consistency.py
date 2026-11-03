"""Каталог сравнения описывает тот же ряд, который отдаёт `/compare/series`: индикатор, частота, единица.

Раньше каталог брал первый listed ряд страны по коду, а `/compare/series` — лучший по `choose_compare_indicator`;
отсюда «индекс 2015=100» у годового процентного ряда МВФ (Япония и ещё десять стран), годовая частота у месячной
безработицы Японии и годовая частота у России при месячном ряде.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.models import (
    Indicator,
    IndicatorData,
    WorldCountry,
    WorldDataPoint,
    WorldIndicator,
)


def _world_indicator(country, code, dataset, provider, slice_json, unit, unit_ru, frequency, history_end, *,
                     listed=True, name="Ряд", points=24):
    return WorldIndicator(
        country_id=country.id,
        code=code,
        dataset_id=dataset,
        provider=provider,
        slice_json=slice_json,
        slice_hash=code,
        name_ru=name,
        name_quality="curated",
        unit=unit,
        unit_ru=unit_ru,
        frequency=frequency,
        category_ru="Цены",
        source="Тест",
        history_start=date(2020, 1, 1),
        history_end=history_end,
        points_count=points,
        is_listed=listed,
    )


@pytest.fixture
def compare_client(auth_env):
    async def seed():
        async with auth_env["session_maker"]() as db:
            jp = WorldCountry(code="JP", slug="japan", name_ru="Япония", name_en="Japan", region_ru="Азия", sort_order=1)
            de = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany", region_ru="Европа", sort_order=2)
            db.add_all([jp, de])
            await db.flush()
            eurostat_hicp = {"unit": "I15", "coicop": "CP00", "freq": "M"}
            rows = [
                # Япония: годовой ряд МВФ «инфляция за год, %» понятия hicp-index и годовая безработица МВФ (listed),
                # а рядом непубличная месячная безработица Евростата, которую отдаёт `/compare/series`.
                _world_indicator(jp, "jp-weo-pcpipch", "weo", "imf", {"weo_code": "PCPIPCH"}, "PC",
                                 "изменение за год, %", "annual", date(2025, 1, 1), points=12),
                _world_indicator(jp, "jp-weo-lur", "weo", "imf", {"weo_code": "LUR"}, "PC",
                                 "% экономически активного населения", "annual", date(2025, 1, 1), points=12),
                _world_indicator(jp, "jp-une_rt_m-total-sa-t-pc-act", "une_rt_m", "eurostat",
                                 {"age": "TOTAL", "sex": "T", "s_adj": "SA", "unit": "PC_ACT", "freq": "M"},
                                 "PC_ACT", "% экономически активного населения", "monthly", date(2026, 9, 1),
                                 listed=False, points=60),
                # Германия: замороженный prc_hicp_midx и живой prc_hicp_minr с тем же срезом корзины.
                _world_indicator(de, "de-prc_hicp_midx-cp00-i15", "prc_hicp_midx", "eurostat", eurostat_hicp,
                                 "I15", "индекс 2015=100", "monthly", date(2024, 12, 1), points=60),
                _world_indicator(de, "de-prc_hicp_minr-cp00-i15", "prc_hicp_minr", "eurostat", eurostat_hicp,
                                 "I15", "индекс 2015=100", "monthly", date(2026, 9, 1), points=60),
            ]
            db.add_all(rows)
            db.add_all([
                Indicator(code="cpi-yoy", name="ИПЦ за год", unit="%", frequency="monthly", source="Росстат",
                          parser_type="derived", is_active=True, is_listed=False),
                Indicator(code="unemployment", name="Безработица", unit="%", frequency="monthly", source="Росстат",
                          parser_type="rosstat_xlsx", is_active=True, is_listed=True),
                Indicator(code="population", name="Население", unit="млн чел.", frequency="annual", source="Росстат",
                          parser_type="rosstat_xlsx", is_active=True, is_listed=True),
            ])
            await db.flush()
            for ind in rows:
                for month in range(1, 4):
                    db.add(WorldDataPoint(indicator_id=ind.id, date=date(2024, month, 1), value=2.0 + month))
            by_code = {
                row.code: row.id
                for row in (await db.execute(Indicator.__table__.select())).all()
            }
            for month in range(1, 10):
                db.add(IndicatorData(indicator_id=by_code["cpi-yoy"], date=date(2026, month, 1), value=7.0 - month / 10))
                db.add(IndicatorData(indicator_id=by_code["unemployment"], date=date(2026, month, 1), value=2.4))
            for year in (2023, 2024, 2025):
                db.add(IndicatorData(indicator_id=by_code["population"], date=date(year, 1, 1), value=146.0))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def _catalog_item(client, code):
    items = client.get("/api/v1/world/compare/catalog").json()["items"]
    return next(row for row in items if row["code"] == code)


def test_imf_percent_series_is_not_called_an_index(compare_client):
    japan = _catalog_item(compare_client, "w:japan:hicp-index")
    assert japan["indicator_code"] == "jp-weo-pcpipch"
    assert japan["unit"] == "изменение за год, %"
    assert japan["peer_mode"] == "level-annual"


def test_catalog_picks_the_deeper_unlisted_eurostat_series_like_compare_series(compare_client):
    unemployment = _catalog_item(compare_client, "w:japan:unemployment-rate")
    assert unemployment["indicator_code"] == "jp-une_rt_m-total-sa-t-pc-act"
    assert unemployment["frequency"] == "monthly"
    germany = _catalog_item(compare_client, "w:germany:hicp-index")
    assert germany["indicator_code"] == "de-prc_hicp_minr-cp00-i15"


def test_russia_monthly_series_are_monthly_in_catalog_and_series(compare_client):
    hicp = _catalog_item(compare_client, "w:russia:hicp-index")
    unemployment = _catalog_item(compare_client, "w:russia:unemployment-rate")
    population = _catalog_item(compare_client, "w:russia:population")
    assert hicp["frequency"] == "monthly"
    assert unemployment["frequency"] == "monthly"
    assert population["frequency"] == "annual"

    series = compare_client.get("/api/v1/world/compare/series/russia/hicp-index").json()
    assert series["meta"]["frequency"] == "monthly"
    assert series["meta"]["unit"] == "изменение за год, %"
    assert len(series["data"]) == 9
    assert series["data"][-1] == {"date": "2026-09-01", "value": 6.1}
    yearly = compare_client.get("/api/v1/world/compare/series/russia/population").json()
    assert yearly["meta"]["frequency"] == "annual"


def test_every_catalog_item_matches_its_series_meta(compare_client):
    items = compare_client.get("/api/v1/world/compare/catalog").json()["items"]
    assert items
    for item in items:
        response = compare_client.get(
            f"/api/v1/world/compare/series/{item['country_slug']}/{item['concept_slug']}",
        )
        if response.status_code != 200:
            continue
        meta = response.json()["meta"]
        for key in ("indicator_code", "frequency", "unit"):
            assert meta[key] == item[key], (item["code"], key, meta[key], item[key])
