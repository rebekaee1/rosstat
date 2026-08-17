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
            it = WorldCountry(
                code="IT", slug="italy", name_ru="Италия",
                name_en="Italy", region_ru="Европа", sort_order=3,
            )
            db.add_all([de, fr, it])
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
            no_year_value = WorldIndicator(
                country_id=it.id,
                code="it-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="it-abc",
                name_ru="Гармонизированный индекс потребительских цен, помесячно",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="monthly",
                category_ru="Цены",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=0,
                is_listed=True,
            )
            population = WorldIndicator(
                country_id=de.id,
                code="de-demo_pjan-total-t-nr",
                dataset_id="demo_pjan",
                slice_json={"unit": "NR", "age": "TOTAL", "sex": "T"},
                slice_hash="pop1",
                name_ru="Численность населения",
                name_quality="curated",
                unit="NR",
                unit_ru="человек",
                frequency="annual",
                category_ru="Население",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
                is_listed=True,
            )
            budget = WorldIndicator(
                country_id=de.id,
                code="de-gov_10dd_edpt1-b9-s13-pc-gdp",
                dataset_id="gov_10dd_edpt1",
                slice_json={"unit": "PC_GDP", "na_item": "B9", "sector": "S13"},
                slice_hash="bud1",
                name_ru="Сальдо бюджета сектора государственного управления",
                name_quality="curated",
                unit="PC_GDP",
                unit_ru="% ВВП",
                frequency="annual",
                category_ru="Финансы",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
                is_listed=True,
            )
            gdp_annual = WorldIndicator(
                country_id=de.id,
                code="de-nama_10_gdp-b1gq-clv15-meur",
                dataset_id="nama_10_gdp",
                slice_json={"unit": "CLV15_MEUR", "na_item": "B1GQ"},
                slice_hash="gdp1",
                name_ru="Валовой внутренний продукт в постоянных ценах, год",
                name_quality="curated",
                unit="CLV15_MEUR",
                unit_ru="в постоянных ценах 2015 года, млн евро",
                frequency="annual",
                category_ru="Национальные счета",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
                is_listed=True,
            )
            long_rate = WorldIndicator(
                country_id=de.id,
                code="de-irt_lt_mcby_m-mcby",
                dataset_id="irt_lt_mcby_m",
                slice_json={"freq": "M", "int_rt": "MCBY"},
                slice_hash="irt1",
                name_ru="Доходность долгосрочных государственных облигаций",
                name_quality="curated",
                unit="",
                unit_ru="%",
                frequency="monthly",
                category_ru="Ставки",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=18,
                is_listed=True,
            )
            activity = WorldIndicator(
                country_id=de.id,
                code="de-lfsi_emp_a-y15-64-act-t-pc-pop",
                dataset_id="lfsi_emp_a",
                slice_json={
                    "age": "Y15-64", "sex": "T", "freq": "A",
                    "unit": "PC_POP", "indic_em": "ACT",
                },
                slice_hash="act1",
                name_ru="Уровень экономической активности",
                name_quality="curated",
                unit="PC_POP",
                unit_ru="% населения",
                frequency="annual",
                category_ru="Рынок труда",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
                is_listed=True,
            )
            gdp_pc_eu = WorldIndicator(
                country_id=de.id,
                code="de-nama_10_pc-b1gq-pc-eu27-2020-hab-meur-cp",
                dataset_id="nama_10_pc",
                slice_json={
                    "freq": "A",
                    "unit": "PC_EU27_2020_HAB_MEUR_CP",
                    "na_item": "B1GQ",
                },
                slice_hash="gdppc1",
                name_ru="ВВП на душу населения относительно среднего по ЕС",
                name_quality="curated",
                unit="PC_EU27_2020_HAB_MEUR_CP",
                unit_ru="% от среднего по ЕС на душу населения",
                frequency="annual",
                category_ru="Национальные счета",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=2,
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
            db.add_all([
                listed, listed_q, une_m, une_q, peer, no_year_value,
                population, budget, gdp_annual, long_rate, activity, gdp_pc_eu, raw,
            ])
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
            for i in range(18):
                y = 2024 + (i // 12)
                m = (i % 12) + 1
                db.add(WorldDataPoint(
                    indicator_id=long_rate.id,
                    date=date(y, m, 1),
                    value=2.0 + i * 0.05,
                ))
            for ind, values in (
                (population, (83_000_000.0, 83_200_000.0)),
                (budget, (-2.1, -1.8)),
                (gdp_annual, (3_200_000.0, 3_250_000.0)),
                (activity, (78.1, 78.4)),
                (gdp_pc_eu, (122.0, 123.5)),
            ):
                for i, value in enumerate(values):
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(2024 + i, 1, 1),
                        value=value,
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
    assert _breadcrumb_names(html) == ["Главная", "Страны"]
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
    assert crumbs == ["Главная", "Страны", "Германия"]
    assert crumbs[0] == "Главная"


def test_seo_world_country_locale_en(world_seo_client):
    r = world_seo_client.get("/seo/world/germany?preview_locale=en")
    assert r.status_code == 200
    html = r.text
    title = re.search(r"<title>([^<]+)</title>", html).group(1)
    assert title == "Economy of Germany: statistics and indicators"
    assert not re.search(r"[А-Яа-яЁё]", title)
    assert "<h1>Economy of Germany: statistics and indicators</h1>" in html
    assert "Eurostat" in html
    assert "Евростат" not in re.search(r"<h1>[^<]+</h1>", html).group(0)
    # RU regression intact without preview
    r_ru = world_seo_client.get("/seo/world/germany")
    assert "Экономика Германии" in r_ru.text


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
    assert f'src="/og/germany/{code}.png"' in html
    assert "seo-chart" in html
    assert "117" in html  # последнее значение 100+17
    blocks = _jsonld(html)
    assert any(b.get("@type") == "Dataset" for b in blocks)
    assert any(b.get("@type") == "ImageObject" for b in blocks)
    ds = next(b for b in blocks if b.get("@type") == "Dataset")
    assert "temporalCoverage" in ds
    crumbs = _breadcrumb_names(html)
    assert crumbs[0] == "Главная"
    assert crumbs[1] == "Страны"
    assert crumbs[2] == "Германия"
    assert "потребительских цен" in crumbs[3]
    assert 'href="/france"' in html or "/france/" in html
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
    assert f"/germany/indicator/{primary}" in loc
    assert "mode=level-quarterly" in loc


def test_seo_world_rating(world_seo_client):
    r = world_seo_client.get("/seo/world/rating/hicp-index")
    assert r.status_code == 200
    html = r.text
    assert "Рейтинг стран по изменению потребительских цен за год" in html
    assert "базовые периоды национальных индексов" in html
    assert 'canonical" href="https://forecasteconomy.com/world/rating/hicp-index"' in html
    assert 'src="/og/world/rating/hicp-index.png"' in html
    assert "seo-chart" in html
    assert "Германия" in html
    assert "Франция" in html
    assert "Италия" in html
    assert "Страны без данных" in html

    blocks = _jsonld(html)
    assert any(b.get("@type") == "ImageObject" for b in blocks)
    item_list = next(b for b in blocks if b.get("@type") == "ItemList")
    assert item_list["numberOfItems"] == 2
    assert item_list["itemListElement"][0]["position"] == 1
    assert "Германия" in item_list["itemListElement"][0]["name"]
    assert _breadcrumb_names(html) == [
        "Главная",
        "Страны",
        "Рейтинг",
        "Изменение потребительских цен за год",
    ]

    visible = _visible_root(html)
    for leak in ("Eurostat", "SDMX", "dataflow", "concept", "provider", "dataset"):
        assert leak not in visible


def test_seo_world_rating_default_redirect(world_seo_client):
    r = world_seo_client.get("/seo/world/rating", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"].endswith("/world/rating/unemployment-rate")


def test_world_rating_surface_nonempty_and_gated(world_seo_client):
    """Рейтинг by construction: только surface=rating, и у каждого снапшот непустой."""
    from app.data.world_concepts import WORLD_CONCEPTS

    rating_slugs = {
        concept.slug
        for concept in WORLD_CONCEPTS
        if "rating" in concept.enabled_surfaces
    }
    assert rating_slugs == {
        "hicp-index",
        "unemployment-rate",
        "budget-balance-gdp",
        "population",
        "long-term-interest-rate",
        "activity-rate",
        "gdp-per-capita-eu",
    }
    assert "gdp-volume-annual" not in rating_slugs
    assert "gdp-volume-quarterly" not in rating_slugs

    catalog = world_seo_client.get("/api/v1/world/rating/concepts")
    assert catalog.status_code == 200
    catalog_slugs = {item["slug"] for item in catalog.json()["concepts"]}
    assert catalog_slugs == rating_slugs

    for slug in sorted(rating_slugs):
        snapshot = world_seo_client.get(f"/api/v1/world/compare/snapshot/{slug}")
        assert snapshot.status_code == 200, slug
        assert snapshot.json()["items"], f"пустой снапшот рейтинга: {slug}"
        ssr = world_seo_client.get(f"/seo/world/rating/{slug}")
        assert ssr.status_code == 200, slug
        assert "<table>" in ssr.text

    for slug in ("gdp-volume-annual", "gdp-volume-quarterly"):
        assert world_seo_client.get(f"/seo/world/rating/{slug}").status_code == 404
        assert slug not in catalog_slugs


def test_seo_world_unlisted_404(world_seo_client):
    assert world_seo_client.get("/seo/world/germany/de-zz_raw_stub").status_code == 404
    assert world_seo_client.get("/seo/world/no-such-country").status_code == 404


def test_world_sitemap_listed_only(world_seo_client):
    idx = world_seo_client.get("/sitemap.xml")
    assert idx.status_code == 200
    assert "sitemap-world.xml" in idx.text
    assert "sitemap-world-ratings.xml" in idx.text
    assert "sitemap-world-indicators-1.xml" in idx.text

    world = world_seo_client.get("/sitemap-world.xml")
    assert world.status_code == 200
    assert "https://forecasteconomy.com/world</loc>" in world.text
    assert "https://forecasteconomy.com/germany" in world.text
    assert "https://forecasteconomy.com/france" in world.text

    ratings = world_seo_client.get("/sitemap-world-ratings.xml")
    assert ratings.status_code == 200
    assert "https://forecasteconomy.com/world/rating/hicp-index" in ratings.text
    assert "https://forecasteconomy.com/world/rating/unemployment-rate" in ratings.text
    assert "https://forecasteconomy.com/world/rating/population" in ratings.text
    assert "https://forecasteconomy.com/world/rating/budget-balance-gdp" in ratings.text
    assert "https://forecasteconomy.com/world/rating/long-term-interest-rate" in ratings.text
    assert "https://forecasteconomy.com/world/rating/activity-rate" in ratings.text
    assert "https://forecasteconomy.com/world/rating/gdp-per-capita-eu" in ratings.text
    assert "gdp-volume-annual" not in ratings.text
    assert "gdp-volume-quarterly" not in ratings.text

    inds = world_seo_client.get("/sitemap-world-indicators-1.xml")
    assert inds.status_code == 200
    assert "/germany/indicator/de-prc_hicp_midx-cp00-i15" in inds.text
    assert "/germany/indicator/de-une_rt_m-total-sa-t-pc-act" in inds.text
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

    rating = world_seo_client.get("/api/v1/og-image/world-rating/hicp-index.png")
    assert rating.status_code == 200
    assert rating.headers["content-type"].startswith("image/png")
    assert rating.content[:8] == b"\x89PNG\r\n\x1a\n"

    assert world_seo_client.get(
        "/api/v1/og-image/world/germany/de-zz_raw_stub.png"
    ).status_code == 404
