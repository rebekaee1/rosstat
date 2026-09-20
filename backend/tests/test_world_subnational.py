"""Субнациональный bounded context (ADR-0014): паспорт, шаблоны, API, SSR."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.world_subnational_ingest import (
    expand_series_template,
    load_subnational_passport,
    period_key,
    period_label,
    period_start,
)


def test_us_passport_loads_51_territories_and_listed_indicators():
    passport = load_subnational_passport("us")
    assert passport.country_code == "US"
    assert passport.country_slug == "united-states"
    assert len(passport.regions) == 51
    slugs = {r.slug for r in passport.regions}
    assert "california" in slugs
    assert "new-york" in slugs
    assert "district-of-columbia" in slugs
    assert passport.default_indicator == "unemployment-rate"
    listed = [i for i in passport.indicators if i.is_listed]
    assert 8 <= len(listed) <= 12
    codes = {i.code for i in listed}
    assert "unemployment-rate" in codes
    assert "real-gdp" in codes


def test_series_template_geo_and_fips():
    assert expand_series_template("{geo}UR", geo="CA", fips="06") == "CAUR"
    assert expand_series_template("LBSSA{fips}", geo="CA", fips="06") == "LBSSA06"
    assert expand_series_template("MEHOINUS{geo}A672N", geo="NY", fips="36") == "MEHOINUSNYA672N"
    assert expand_series_template("STTMINWG{ST}", geo="DC", fips="11") == "STTMINWGDC"


def test_period_key_and_parse_roundtrip():
    assert period_key(date(2024, 5, 1), "monthly") == "2024-05"
    assert period_key(date(2024, 4, 1), "quarterly") == "2024-Q2"
    assert period_key(date(2023, 1, 1), "annual") == "2023"
    assert period_start("2024-05", "monthly") == date(2024, 5, 1)
    assert period_start("2024-Q3", "quarterly") == date(2024, 7, 1)
    assert period_start("2020", "annual") == date(2020, 1, 1)
    assert "2024" in period_label(date(2024, 1, 1), "annual", "en")


@pytest.fixture
def subnational_client(auth_env):
    import asyncio
    from fastapi.testclient import TestClient
    from app.models import (
        SubnationalDataPoint,
        SubnationalIndicator,
        SubnationalRegion,
        WorldCountry,
        WorldDataPoint,
        WorldIndicator,
    )

    async def _seed():
        async with auth_env["session_maker"]() as db:
            us = WorldCountry(
                code="US", slug="united-states", name_ru="США",
                name_en="United States", region_ru="Америка", sort_order=1,
            )
            db.add(us)
            await db.flush()
            ca = SubnationalRegion(
                country_code="US", slug="california", name_en="California",
                name_ru="Калифорния", kind="state", geo_code="CA", fips="06",
                sort_order=1,
            )
            ny = SubnationalRegion(
                country_code="US", slug="new-york", name_en="New York",
                name_ru="Нью-Йорк", kind="state", geo_code="NY", fips="36",
                sort_order=2,
            )
            ur = SubnationalIndicator(
                country_code="US", code="unemployment-rate",
                name_en="Unemployment rate", name_ru="Уровень безработицы",
                unit="PCT", unit_en="%", unit_ru="%", frequency="monthly",
                section_en="Labour", section_ru="Труд", provider="fred",
                series_template="{geo}UR", aggregation="last",
                source_en="BLS", source_ru="BLS", is_listed=True,
                national_code="us-unemployment-rate", better_is_low=True,
            )
            gdp = SubnationalIndicator(
                country_code="US", code="real-gdp",
                name_en="Real GDP", name_ru="Реальный ВРП",
                unit="USD_MLN", unit_en="mln 2017 USD", unit_ru="млн долл. 2017",
                frequency="annual", section_en="Accounts", section_ru="Счета",
                provider="fred", series_template="{geo}RGSP", aggregation="last",
                source_en="BEA", source_ru="BEA", is_listed=True,
            )
            db.add_all([ca, ny, ur, gdp])
            await db.flush()
            nat = WorldIndicator(
                country_id=us.id, code="us-unemployment-rate",
                dataset_id="laus", slice_json={}, slice_hash="nat-ur",
                name_ru="Уровень безработицы", name_en="Unemployment rate",
                name_quality="curated", unit="PCT", unit_ru="%",
                frequency="monthly", category_ru="Труд", source="BLS",
                is_listed=True, points_count=2,
                history_start=date(2024, 1, 1), history_end=date(2024, 2, 1),
            )
            db.add(nat)
            await db.flush()
            db.add_all([
                SubnationalDataPoint(
                    indicator_id=ur.id, region_id=ca.id,
                    period=date(2024, 1, 1), value=5.1,
                ),
                SubnationalDataPoint(
                    indicator_id=ur.id, region_id=ca.id,
                    period=date(2024, 2, 1), value=5.0,
                ),
                SubnationalDataPoint(
                    indicator_id=ur.id, region_id=ny.id,
                    period=date(2024, 1, 1), value=4.4,
                ),
                SubnationalDataPoint(
                    indicator_id=ur.id, region_id=ny.id,
                    period=date(2024, 2, 1), value=4.2,
                ),
                SubnationalDataPoint(
                    indicator_id=gdp.id, region_id=ca.id,
                    period=date(2023, 1, 1), value=3_000_000,
                ),
                SubnationalDataPoint(
                    indicator_id=gdp.id, region_id=ny.id,
                    period=date(2023, 1, 1), value=2_000_000,
                ),
                WorldDataPoint(
                    indicator_id=nat.id, date=date(2024, 1, 1), value=3.7,
                ),
                WorldDataPoint(
                    indicator_id=nat.id, date=date(2024, 2, 1), value=3.9,
                ),
            ])
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_subnational_hub_and_map(subnational_client):
    r = subnational_client.get("/api/v1/world/united-states/regions")
    assert r.status_code == 200
    body = r.json()
    assert body["default_indicator"] == "unemployment-rate"
    assert {x["slug"] for x in body["regions"]} == {"california", "new-york"}
    codes = {i["code"] for i in body["indicators"]}
    assert codes == {"unemployment-rate", "real-gdp"}

    m = subnational_client.get(
        "/api/v1/world/united-states/regions/map/unemployment-rate"
    )
    assert m.status_code == 200
    payload = m.json()
    assert payload["period"] == "2024-02"
    by_slug = {row["slug"]: row for row in payload["values"]}
    assert by_slug["new-york"]["rank"] == 1
    assert by_slug["california"]["rank"] == 2


def test_subnational_profile_and_series(subnational_client):
    p = subnational_client.get("/api/v1/world/united-states/regions/region/california")
    assert p.status_code == 200
    profile = p.json()
    ur = next(i for i in profile["indicators"] if i["code"] == "unemployment-rate")
    assert ur["value"] == 5.0
    assert ur["rank"] == 2
    assert ur["prev_value"] == 5.1
    assert {s["name"] for s in profile["sections"]} == {"Труд", "Счета"}

    s = subnational_client.get(
        "/api/v1/world/united-states/regions/region/california/unemployment-rate"
    )
    assert s.status_code == 200
    series = s.json()
    assert series["series"][0]["year"] == 2024
    assert series["national"]["code"] == "us-unemployment-rate"
    assert series["national"]["series"][-1]["value"] == 3.9
    assert series["rank"]["position"] == 2
    assert series["rank"]["total"] == 2
    assert series["rank"]["top"][0]["slug"] == "new-york"
    assert "BLS" in series["indicator"]["source"]
    assert "fred" not in (series["indicator"]["description"] or "").lower()


def test_subnational_ssr_hub_and_card(subnational_client):
    hub = subnational_client.get(
        "/seo/world/united-states/regions",
        headers={"X-FE-Locale": "en"},
    )
    assert hub.status_code == 200
    assert "<title>" in hub.text
    assert "BreadcrumbList" in hub.text
    assert "United States" in hub.text
    assert "/og/world/united-states/regions.png" in hub.text
    assert "ImageObject" in hub.text
    assert 'class="seo-chart"' in hub.text

    card = subnational_client.get(
        "/seo/world/united-states/region/california/unemployment-rate",
        headers={"X-FE-Locale": "en"},
    )
    assert card.status_code == 200
    assert "Unemployment" in card.text
    assert "California" in card.text
    assert "BreadcrumbList" in card.text
    assert 'property="og:image"' in card.text
    assert "/og/world/united-states/region/california/unemployment-rate.png" in card.text
    assert "ImageObject" in card.text
    assert 'class="seo-chart"' in card.text
    assert 'name="twitter:image"' in card.text

    ru = subnational_client.get("/seo/regions")
    assert ru.status_code in (200, 404)


def test_world_regions_in_static_sitemap_sections():
    from app.services.site_urls import section_names_static

    names = section_names_static()
    assert "world-regions" in names
    assert names.index("world-regions") > names.index("world")


def test_country_region_paths():
    from app.services import site_paths as paths
    from app.services.seo_world_subnational import (
        og_subnational_hub,
        og_subnational_indicator,
        og_subnational_region,
    )

    assert paths.country_regions("united-states") == "/united-states/regions"
    assert paths.country_region("united-states", "california") == "/united-states/region/california"
    assert paths.country_region_indicator(
        "united-states", "california", "unemployment-rate",
    ) == "/united-states/region/california/unemployment-rate"
    assert paths.region_hub() == "/russia/region"
    assert og_subnational_hub("united-states") == "/og/world/united-states/regions.png"
    assert og_subnational_region("united-states", "california") == (
        "/og/world/united-states/region/california.png"
    )
    assert og_subnational_indicator(
        "united-states", "california", "unemployment-rate",
    ) == "/og/world/united-states/region/california/unemployment-rate.png"


def test_en_catalog_subnational_paths():
    from app.data.i18n.en_catalog import has_en_path

    assert has_en_path("/united-states/regions")
    assert has_en_path("/united-states/region/california")
    assert has_en_path("/united-states/region/california/unemployment-rate")
    assert has_en_path("/russia/region/moskva")


def _assert_png(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(response.content) > 0


def test_subnational_og_png(subnational_client):
    card = subnational_client.get(
        "/api/v1/og-image/world-region/united-states/california/unemployment-rate.png",
        headers={"X-FE-Locale": "en"},
    )
    _assert_png(card)

    profile = subnational_client.get(
        "/api/v1/og-image/world-region/united-states/california.png",
        headers={"X-FE-Locale": "en"},
    )
    _assert_png(profile)

    hub = subnational_client.get(
        "/api/v1/og-image/world-regions/united-states.png",
        headers={"X-FE-Locale": "en"},
    )
    _assert_png(hub)

    missing = subnational_client.get(
        "/api/v1/og-image/world-region/united-states/atlantis/unemployment-rate.png",
        headers={"X-FE-Locale": "en"},
    )
    assert missing.status_code == 404
    assert subnational_client.get(
        "/api/v1/og-image/world-region/united-states/atlantis.png",
        headers={"X-FE-Locale": "en"},
    ).status_code == 404


def test_subnational_og_locale_labels(subnational_client):
    en = subnational_client.get(
        "/api/v1/og-image/world-region/united-states/california/unemployment-rate.png",
        headers={"X-FE-Locale": "en"},
    )
    ru = subnational_client.get(
        "/api/v1/og-image/world-region/united-states/california/unemployment-rate.png",
    )
    _assert_png(en)
    _assert_png(ru)
    assert en.content != ru.content

    ru_ssr = subnational_client.get(
        "/seo/world/united-states/region/california/unemployment-rate",
    )
    assert ru_ssr.status_code == 200
    assert "Калифорния" in ru_ssr.text
    assert "Уровень безработицы" in ru_ssr.text
    assert "/og/world/united-states/region/california/unemployment-rate.png" in ru_ssr.text


def test_subnational_og_nginx_rewrites():
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"
    ).read_text()
    block = text.split("location ^~ /og/", 1)[1].split("\n    }", 1)[0]
    indicator = "/og/world/([a-z0-9-]+)/region/([a-z0-9-]+)/([a-z0-9-]+)\\.png"
    profile = "/og/world/([a-z0-9-]+)/region/([a-z0-9-]+)\\.png"
    hub = "/og/world/([a-z0-9-]+)/regions\\.png"
    rating = "/og/world/rating/"
    generic = "/og/world/([a-z0-9-]+)/([a-z0-9_.-]+)\\.png"
    assert indicator in block
    assert profile in block
    assert hub in block
    assert "/api/v1/og-image/world-region/$1/$2/$3.png" in block
    assert "/api/v1/og-image/world-region/$1/$2.png" in block
    assert "/api/v1/og-image/world-regions/$1.png" in block
    assert block.index(rating) < block.index(indicator)
    assert block.index(indicator) < block.index(profile)
    assert block.index(profile) < block.index(hub)
    assert block.index(hub) < block.index(generic)

