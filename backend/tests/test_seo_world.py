"""SSR/SEO мирового блока: три типа страниц, sitemap listed-only, BreadcrumbList."""

from __future__ import annotations

import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def world_seo_client(auth_env):
    """Мини-датасет мирового блока (как test_world.world_client) + TestClient."""
    import asyncio

    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия",
                name_en="Germany", region_ru="Европа", sort_order=1,
            )
            fr = WorldCountry(
                code="FR", slug="france", name_ru="Франция",
                name_en="France", region_ru="Европа", sort_order=2,
            )
            db.add_all([de, fr])
            await db.flush()
            listed = WorldIndicator(
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
                source_url="https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx",
                description=(
                    "Гармонизированный индекс потребительских цен в Германии — "
                    "официальный ряд Евростата."
                ),
                methodology="Источник данных — Евростат. Частота публикации — месячная.",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=18,
                is_listed=True,
            )
            listed_q = WorldIndicator(
                country_id=de.id,
                code="de-prc_hicp_qidx-cp00-i15",
                dataset_id="prc_hicp_qidx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "Q"},
                slice_hash="abcq",
                name_ru="Гармонизированный индекс потребительских цен, поквартально",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="quarterly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 4, 1),
                points_count=6,
                is_listed=True,
            )
            # Тот же card_key, что у monthly (stem prc_hicp_* → разный stem!)
            # Для теста 301 используем une_rt_m / une_rt_q с одинаковым срезом.
            une_m = WorldIndicator(
                country_id=de.id,
                code="de-une_rt_m-total-sa-t-pc-act",
                dataset_id="une_rt_m",
                slice_json={"unit": "PC_ACT", "age": "TOTAL", "sex": "T", "s_adj": "SA"},
                slice_hash="une1",
                name_ru="Безработица, % экономически активного населения, помесячно",
                name_quality="curated",
                unit="PC_ACT",
                unit_ru="% экономически активного населения",
                frequency="monthly",
                category_ru="Рынок труда",
                source="Евростат",
                history_start=date(2020, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=66,
                is_listed=True,
            )
            une_q = WorldIndicator(
                country_id=de.id,
                code="de-une_rt_q-y15-74-sa-t-pc-act",
                dataset_id="une_rt_q",
                slice_json={"unit": "PC_ACT", "age": "Y15-74", "sex": "T", "s_adj": "SA"},
                slice_hash="une1q",
                name_ru="Безработица, % экономически активного населения, поквартально",
                name_quality="curated",
                unit="PC_ACT",
                unit_ru="% экономически активного населения",
                frequency="quarterly",
                category_ru="Рынок труда",
                source="Евростат",
                history_start=date(2020, 1, 1),
                history_end=date(2025, 4, 1),
                points_count=22,
                is_listed=True,
            )
            peer = WorldIndicator(
                country_id=fr.id,
                code="fr-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="abc",
                name_ru="Гармонизированный индекс потребительских цен, помесячно",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="monthly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=18,
                is_listed=True,
            )
            raw = WorldIndicator(
                country_id=de.id,
                code="de-zz_raw_stub",
                dataset_id="zz_raw",
                slice_json={},
                slice_hash="raw",
                name_ru="Экономический показатель",
                name_quality="raw",
                unit="",
                unit_ru="",
                frequency="monthly",
                category_ru="Прочее",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2024, 8, 1),
                points_count=8,
                is_listed=False,
            )
            db.add_all([listed, listed_q, une_m, une_q, peer, raw])
            await db.flush()
            for ind in (listed, peer):
                for i in range(18):
                    y = 2024 + (i // 12)
                    m = (i % 12) + 1
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(y, m, 1),
                        value=100.0 + i,
                    ))
            for ind in (listed_q, une_q):
                for i in range(6):
                    y = 2024 + (i // 4)
                    q = (i % 4) + 1
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(y, (q - 1) * 3 + 1, 1),
                        value=100.0 + i,
                    ))
            for i in range(18):
                y = 2024 + (i // 12)
                m = (i % 12) + 1
                db.add(WorldDataPoint(
                    indicator_id=une_m.id,
                    date=date(y, m, 1),
                    value=3.0 + i * 0.1,
                ))
            for i in range(8):
                db.add(WorldDataPoint(
                    indicator_id=raw.id,
                    date=date(2024, i + 1, 1),
                    value=1.0 + i,
                ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def _jsonld(html: str) -> list[dict]:
    return [
        json.loads(m.group(1))
        for m in re.finditer(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S
        )
    ]


def _breadcrumb_names(html: str) -> list[str]:
    for block in _jsonld(html):
        if block.get("@type") == "BreadcrumbList":
            items = sorted(
                block["itemListElement"], key=lambda x: x["position"]
            )
            return [it["name"] for it in items]
    return []


def _visible_root(html: str) -> str:
    # Vite-shell в тестах может отсутствовать — ищем .seo-page напрямую.
    body = re.search(r'<div class="seo-page">(.*)</div>\s*(?:<script|</div>)', html, re.S)
    if not body:
        body = re.search(r'<div id="root">(.*)</div>', html, re.S)
    assert body
    visible = re.sub(r"<script[^>]*>.*?</script>", "", body.group(1), flags=re.S)
    return visible


def test_seo_world_home(world_seo_client):
    r = world_seo_client.get("/seo/world")
    assert r.status_code == 200
    html = r.text
    assert "Мировая экономика" in html
    assert "Германия" in html
    assert "Евростат" in html
    assert 'canonical" href="https://forecasteconomy.com/world"' in html
    assert _breadcrumb_names(html) == ["Главная", "Мировая экономика"]
    visible = _visible_root(html)
    for leak in ("Eurostat", "SDMX", "dataflow"):
        assert leak not in visible


def test_seo_world_country(world_seo_client):
    r = world_seo_client.get("/seo/world/germany")
    assert r.status_code == 200
    html = r.text
    assert "Экономика Германии" in html
    title = re.search(r"<title>([^<]+)</title>", html).group(1)
    assert "Германии" in title
    for leak in ("Eurostat", "SDMX", "dataflow", "prc_hicp"):
        assert leak not in title
    assert 'src="/og/world/germany.png"' in html
    assert any("ImageObject" in json.dumps(b) for b in _jsonld(html))
    crumbs = _breadcrumb_names(html)
    assert crumbs == ["Главная", "Мировая экономика", "Германия"]
    assert crumbs[0] == "Главная"


def test_seo_world_indicator(world_seo_client):
    code = "de-prc_hicp_midx-cp00-i15"
    r = world_seo_client.get(f"/seo/world/germany/{code}")
    assert r.status_code == 200
    html = r.text
    assert "Гармонизированный индекс потребительских цен" in html
    # H1: показатель в предложном падеже страны, без суффикса частоты
    assert "<h1>Гармонизированный индекс потребительских цен в Германии</h1>" in html
    assert "помесячно" not in re.search(r"<h1>[^<]+</h1>", html).group(0)
    assert "Германии" in html
    assert "Евростат" in html
    assert "по стране" not in html
    assert "в стране" not in html
    assert f'src="/og/world/germany/{code}.png"' in html
    assert "seo-chart" in html
    assert "117" in html  # последнее значение 100+17
    blocks = _jsonld(html)
    assert any(b.get("@type") == "Dataset" for b in blocks)
    assert any(b.get("@type") == "ImageObject" for b in blocks)
    ds = next(b for b in blocks if b.get("@type") == "Dataset")
    assert "temporalCoverage" in ds
    crumbs = _breadcrumb_names(html)
    assert crumbs[0] == "Главная"
    assert crumbs[1] == "Мировая экономика"
    assert crumbs[2] == "Германия"
    assert "потребительских цен" in crumbs[3]
    assert "/world/france/" in html
    visible = _visible_root(html)
    for leak in ("Eurostat", "SDMX", "dataflow"):
        assert leak not in visible


def test_seo_world_unemployment_freq_links_and_301(world_seo_client):
    primary = "de-une_rt_m-total-sa-t-pc-act"
    quarterly = "de-une_rt_q-y15-74-sa-t-pc-act"

    r = world_seo_client.get(f"/seo/world/germany/{primary}")
    assert r.status_code == 200
    html = r.text
    assert "<h1>Безработица, % экономически активного населения в Германии</h1>" in html
    assert "mode=level-monthly" in html
    assert "mode=level-quarterly" in html
    assert "Частота наблюдений" in html
    assert "по стране" not in html
    assert "в стране" not in html

    redir = world_seo_client.get(
        f"/seo/world/germany/{quarterly}", follow_redirects=False
    )
    assert redir.status_code == 301
    loc = redir.headers["location"]
    assert f"/world/germany/{primary}" in loc
    assert "mode=level-quarterly" in loc


def test_seo_world_unlisted_404(world_seo_client):
    assert world_seo_client.get("/seo/world/germany/de-zz_raw_stub").status_code == 404
    assert world_seo_client.get("/seo/world/no-such-country").status_code == 404


def test_world_sitemap_listed_only(world_seo_client):
    idx = world_seo_client.get("/sitemap.xml")
    assert idx.status_code == 200
    assert "sitemap-world.xml" in idx.text
    assert "sitemap-world-indicators-1.xml" in idx.text

    world = world_seo_client.get("/sitemap-world.xml")
    assert world.status_code == 200
    assert "https://forecasteconomy.com/world</loc>" in world.text
    assert "https://forecasteconomy.com/world/germany" in world.text
    assert "https://forecasteconomy.com/world/france" in world.text

    inds = world_seo_client.get("/sitemap-world-indicators-1.xml")
    assert inds.status_code == 200
    assert "/world/germany/de-prc_hicp_midx-cp00-i15" in inds.text
    assert "/world/germany/de-une_rt_m-total-sa-t-pc-act" in inds.text
    # вторичная частота не в индексе
    assert "de-une_rt_q-y15-74-sa-t-pc-act" not in inds.text
    assert "de-zz_raw_stub" not in inds.text
    assert "<lastmod>2025-" in inds.text

def test_world_og_png(world_seo_client):
    code = "de-prc_hicp_midx-cp00-i15"
    country = world_seo_client.get("/api/v1/og-image/world/germany.png")
    assert country.status_code == 200
    assert country.headers["content-type"].startswith("image/png")
    assert country.content[:8] == b"\x89PNG\r\n\x1a\n"

    card = world_seo_client.get(f"/api/v1/og-image/world/germany/{code}.png")
    assert card.status_code == 200
    assert card.headers["content-type"].startswith("image/png")
    assert card.content[:8] == b"\x89PNG\r\n\x1a\n"

    assert world_seo_client.get(
        "/api/v1/og-image/world/germany/de-zz_raw_stub.png"
    ).status_code == 404
