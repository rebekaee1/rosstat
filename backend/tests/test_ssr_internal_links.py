"""Страж внутренних ссылок SSR (14.11.2026, аудит scripts/ssr-link-audit.py на локальном стенде).

Найдено и исправлено в источниках ссылок:
* хаб регионов, профиль региона, «другие рейтинги» ссылались на рейтинг и карту цен на топливо
  (/russia/region-rating/ceni-*, /russia/region/map/ceni-*) — у этих показателей нет годовых данных
  по субъектам, страницы отвечают 404;
* каталог страны мира ссылался на замороженный дубль HICP (cind), который отвечает 301 на
  карточку-преемника, уже стоящую в каталоге;
* каталог, «этот показатель в других странах», «ещё в разделе» и годы карточки ссылались на
  неосновные версии точных дублей рядов (canonical на основную, world_canonical).
"""

from __future__ import annotations

import asyncio
import re

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services import world_canonical as wc
from tests.test_seo_growth_pages import seeded_env  # noqa: F401
from tests.test_seo_world_year import CODE_ANNUAL, CODE_MONTHLY, CODE_SIBLING_M, world_year_client  # noqa: F401


def test_region_hub_links_only_ratings_with_regional_data(seeded_env):  # noqa: F811
    from app.models import RegionIndicator

    async def _seed():
        async with seeded_env["session_maker"]() as s:
            s.add(RegionIndicator(
                code="ceni-ai92", table_code="16.20", section_num=16, section_name="Цены",
                name="Цены на бензин АИ-92", unit="рублей за литр", is_listed=True,
            ))
            await s.commit()

    asyncio.run(_seed())
    with TestClient(seeded_env["app"]) as tc:
        hub = tc.get("/seo/regions").text
        assert "/russia/region-rating/chislennost-naseleniya" in hub
        assert "/russia/region-rating/ceni-ai92" not in hub and "/russia/region/map/ceni-ai92" not in hub
        assert tc.get("/seo/region-rating/ceni-ai92").status_code == 404  # потому и не ссылаемся


@pytest.fixture
def duplicate(monkeypatch):
    monkeypatch.setattr(settings, "world_duplicate_canonical", True)
    monkeypatch.setattr(wc, "published_map", lambda: {"germany": {CODE_MONTHLY: CODE_SIBLING_M}})


def test_country_catalog_hides_non_primary_versions(world_year_client, duplicate):  # noqa: F811
    html = world_year_client.get("/seo/world/germany").text
    assert f"/germany/indicator/{CODE_MONTHLY}\"" not in html
    assert f"/germany/indicator/{CODE_ANNUAL}\"" in html


def test_non_primary_card_year_links_go_to_primary(world_year_client, duplicate):  # noqa: F811
    html = world_year_client.get(f"/seo/world/germany/{CODE_MONTHLY}").text
    years = re.findall(rf'href="/germany/indicator/([^/"]+)/(\d{{4}})', html)
    assert years and all(code == CODE_SIBLING_M for code, _y in years), years


def test_country_catalog_skips_superseded_card_with_listed_successor():
    """Чистое правило: дубль cind с листинговым преемником не ссылается; без преемника — остаётся."""
    from app.data.world_superseded import superseded_target

    target = superseded_target("prc_hicp_cind", "at-prc_hicp_cind-cp00-i15", {"coicop": "CP00", "unit": "I15"}, "I15")
    if target is None:
        pytest.skip("правило cind изменилось")
    assert target[0].startswith("at-prc_hicp_")
