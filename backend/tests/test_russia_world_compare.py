"""Российская карточка с world-концептом отдаёт блок сравнения стран."""

from __future__ import annotations

from datetime import date

import pytest

from app.data.world_concept_russia import concept_slug_for_russia_code
from app.services.world_compare import (
    choose_compare_indicator,
    peer_fetch_mode,
    russia_world_compare_ssr_links,
)


def test_reverse_index_maps_card_and_link_codes():
    assert concept_slug_for_russia_code("cpi") == "hicp-index"
    assert concept_slug_for_russia_code("cpi-yoy") == "hicp-index"
    assert concept_slug_for_russia_code("unemployment") == "unemployment-rate"
    assert concept_slug_for_russia_code("population") == "population"
    assert concept_slug_for_russia_code("weo-gdp-usd") == "gdp-usd"
    assert concept_slug_for_russia_code("weo-government-debt-gdp") == "government-debt-gdp"
    assert concept_slug_for_russia_code("weo-budget-balance-gdp") == "budget-balance-gdp"
    assert concept_slug_for_russia_code("weo-gdp-per-capita-usd") == "gdp-per-capita-usd"


def test_reverse_index_fail_closed_for_incompatible_cards():
    assert concept_slug_for_russia_code("key-rate") is None
    assert concept_slug_for_russia_code("gdp-real") is None
    assert concept_slug_for_russia_code("gdp-nominal") is None
    assert concept_slug_for_russia_code("cpi-food") is None
    assert concept_slug_for_russia_code("long-term-interest-rate") is None


def test_ssr_links_include_rating_and_vs_pair():
    links = russia_world_compare_ssr_links("cpi")
    assert links
    hrefs = [href for href, _kind in links]
    assert "/world/rating/hicp-index" in hrefs
    assert any("-vs-" in href and "hicp-index" in href for href in hrefs)
    assert russia_world_compare_ssr_links("key-rate") is None


def test_choose_compare_indicator_prefers_live_minr_over_frozen_midx():
    from types import SimpleNamespace
    from app.data.world_concepts import CONCEPT_BY_SLUG

    concept = CONCEPT_BY_SLUG["hicp-index"]
    midx = SimpleNamespace(
        code="de-prc_hicp_midx-cp00-i15",
        dataset_id="prc_hicp_midx",
        unit="I15",
        unit_ru="индекс 2015=100",
        provider="eurostat",
        is_listed=False,
        history_end=date(2025, 12, 1),
        slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
    )
    minr = SimpleNamespace(
        code="de-prc_hicp_minr-total-i15",
        dataset_id="prc_hicp_minr",
        unit="I15",
        unit_ru="индекс 2015=100",
        provider="eurostat",
        is_listed=True,
        history_end=date(2026, 8, 1),
        slice_json={"unit": "I15", "coicop18": "TOTAL", "freq": "M"},
    )
    picked = choose_compare_indicator([midx, minr], concept, frozenset())
    assert picked is not None
    assert picked.code == "de-prc_hicp_minr-total-i15"


def test_hicp_peer_mode_is_yoy_for_index_series():
    from types import SimpleNamespace
    from app.data.world_concepts import CONCEPT_BY_SLUG

    concept = CONCEPT_BY_SLUG["hicp-index"]
    indicator = SimpleNamespace(
        code="de-prc_hicp_midx-cp00-i15",
        frequency="monthly",
        slice_json={"unit": "I15", "coicop": "CP00"},
        provider="eurostat",
    )
    mode, adjust = peer_fetch_mode(concept, indicator)
    assert mode == "yoy-monthly"
    assert adjust is None


@pytest.fixture
def russia_compare_client(auth_env):
    import asyncio
    from fastapi.testclient import TestClient
    from app.models import Indicator, WorldCountry, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия",
                name_en="Germany", region_ru="Европа", sort_order=1,
                is_active=True,
            )
            db.add(de)
            await db.flush()
            db.add(WorldIndicator(
                country_id=de.id,
                code="de-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="abc",
                name_ru="Гармонизированный индекс потребительских цен, помесячно",
                name_en="HICP",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="monthly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2026, 6, 1),
                points_count=18,
                is_listed=True,
                provider="eurostat",
            ))
            db.add_all([
                Indicator(
                    code="cpi", name="Индекс потребительских цен", unit="%",
                    frequency="monthly", category="Цены", is_active=True, is_listed=True,
                ),
                Indicator(
                    code="key-rate", name="Ключевая ставка ЦБ", unit="%",
                    frequency="daily", category="Ставки", is_active=True, is_listed=True,
                ),
            ])
            await db.commit()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_seed())
    finally:
        loop.close()

    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_cpi_meta_includes_world_compare_peers(russia_compare_client):
    body = russia_compare_client.get("/api/v1/indicators/cpi").json()
    block = body["world_compare"]
    assert block["concept"]["slug"] == "hicp-index"
    assert "inflation" in block["concept"]["compatible_modes"]
    slugs = {row["country_slug"] for row in block["peers"]}
    assert "germany" in slugs
    germany = next(row for row in block["peers"] if row["country_slug"] == "germany")
    assert germany["peer_mode"] == "yoy-monthly"


def test_key_rate_meta_has_no_world_compare(russia_compare_client):
    body = russia_compare_client.get("/api/v1/indicators/key-rate").json()
    assert body["world_compare"] is None
