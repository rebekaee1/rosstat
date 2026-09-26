"""Субнациональный bounded context (ADR-0014): паспорт, шаблоны, API, SSR."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.services.world_subnational_ingest import (
    FredStLouisError,
    expand_series_template,
    fetch_bls_recent_sync,
    fetch_fred_csv_sync,
    load_subnational_passport,
    _with_real_income_vintage,
    fetch_real_income_vintage_sync,
    merge_and_scale_points,
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
    assert len(listed) == 16
    codes = {i.code for i in listed}
    assert "unemployment-rate" in codes
    assert "real-gdp" in codes
    assert {"civilian-labor-force", "civilian-employment", "unemployed-persons", "government-employment"} <= codes
    scaled = {i.code: i for i in passport.indicators}
    assert scaled["civilian-employment"].value_scale == 0.001
    assert scaled["government-employment"].value_scale == 1.0
    assert scaled["unemployed-persons"].national_code == "us-unemployed"
    assert scaled["civilian-labor-force"].bls_series_template == "LASST{fips}0000000000006"


def test_real_income_vintage_updates_all_public_labels():
    passport = _with_real_income_vintage(load_subnational_passport("us"), 2026)
    spec = next(s for s in passport.indicators if s.code == "median-household-income")
    assert spec.unit == "USD_2026"
    assert "2026" in spec.unit_en and "2026" in spec.unit_ru
    assert all("2025" not in value for value in (
        spec.description_en, spec.description_ru, spec.methodology_en, spec.methodology_ru,
    ))


def test_real_income_vintage_requires_official_units(monkeypatch):
    from app.services import world_subnational_ingest as ingest

    class Response:
        text = '<th scope="row">Units</th><td>2025 C-CPI-U Dollars</td>'
        def raise_for_status(self):
            pass

    monkeypatch.setattr(ingest.requests, "get", lambda *a, **kw: Response())
    assert fetch_real_income_vintage_sync("MEHOINUSCAA672N") == 2025
    Response.text = '<th>Units</th><td>Dollars</td>'
    with pytest.raises(ValueError, match="Units metadata"):
        fetch_real_income_vintage_sync("MEHOINUSCAA672N")


def test_series_template_geo_and_fips():
    assert expand_series_template("{geo}UR", geo="CA", fips="06") == "CAUR"
    assert expand_series_template("LBSSA{fips}", geo="CA", fips="06") == "LBSSA06"
    assert expand_series_template("MEHOINUS{geo}A672N", geo="NY", fips="36") == "MEHOINUSNYA672N"
    assert expand_series_template("STTMINWG{ST}", geo="DC", fips="11") == "STTMINWGDC"
    assert expand_series_template("LASST{fips}0000000000005", geo="CA", fips="06") == "LASST060000000000005"


def test_fred_transient_failure_is_not_reported_as_missing(monkeypatch):
    import requests
    from app.services import world_subnational_ingest as ingest

    def fail(*args, **kwargs):
        raise requests.Timeout("temporary outage")

    monkeypatch.setattr(ingest.requests, "get", fail)
    monkeypatch.setattr(ingest.time, "sleep", lambda _: None)
    with pytest.raises(FredStLouisError, match="fetch failed"):
        fetch_fred_csv_sync("CALF")


def test_bls_recent_points_replace_fred_lag_and_preserve_1976_history(monkeypatch):
    from app.services import world_subnational_ingest as ingest

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"status": "REQUEST_SUCCEEDED", "Results": {"series": [{
                "seriesID": "LASST060000000000005",
                "data": [
                    {"year": "2026", "period": "M08", "value": "18506343"},
                    {"year": "2026", "period": "M07", "value": "18542859"},
                ],
            }]}}

    monkeypatch.setattr(ingest.requests, "post", lambda *args, **kwargs: Response())
    recent = fetch_bls_recent_sync(["LASST060000000000005"])
    merged = merge_and_scale_points(
        [(date(1976, 1, 1), 8873133), (date(2026, 7, 1), 18540000)],
        recent["LASST060000000000005"],
        0.001,
    )
    assert merged == [
        (date(1976, 1, 1), 8873.133),
        (date(2026, 7, 1), 18542.859),
        (date(2026, 8, 1), 18506.343),
    ]


def test_subnational_scheduled_job_invalidates_world_caches(monkeypatch):
    from app.services import world_subnational_ingest as ingest
    from app.core import cache

    monkeypatch.setattr(ingest, "list_subnational_countries", lambda: ["US"])
    monkeypatch.setattr(ingest, "ingest_country", AsyncMock(return_value=[
        ingest.SeriesReport("civilian-employment", "california", "LASST060000000000005", "loaded", points=1),
    ]))
    bump = AsyncMock()
    monkeypatch.setattr(cache, "bump_namespaces", bump)

    asyncio.run(ingest.world_subnational_ingest_job())
    bump.assert_awaited_once_with("world", "ssr-world", "world-catalog")


def test_subnational_scheduled_job_reports_series_failures(monkeypatch):
    from app.services import world_subnational_ingest as ingest
    from app.core import cache

    monkeypatch.setattr(ingest, "list_subnational_countries", lambda: ["US"])
    monkeypatch.setattr(ingest, "ingest_country", AsyncMock(return_value=[
        ingest.SeriesReport("civilian-employment", "california", "LASST060000000000005", "error", detail="BLS unavailable"),
    ]))
    monkeypatch.setattr(cache, "bump_namespaces", AsyncMock())
    with pytest.raises(RuntimeError, match="world_subnational ingest failures: US:1"):
        asyncio.run(ingest.world_subnational_ingest_job())


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


def test_every_observed_year_of_nonfeatured_state_series_has_a_quicklink(
    subnational_client, auth_env,
):
    from sqlalchemy import select
    from app.models import SubnationalDataPoint, SubnationalIndicator, SubnationalRegion
    from app.services.site_urls import _world_region_years_page
    from app.services.sitemap_images import image_path_for_page

    async def seed_and_collect():
        async with auth_env["session_maker"]() as db:
            ca = (await db.execute(select(SubnationalRegion).where(
                SubnationalRegion.slug == "california",
            ))).scalar_one()
            custom = SubnationalIndicator(
                country_code="US", code="custom-ratio",
                name_en="Custom ratio", name_ru="Дополнительный показатель",
                unit="PCT", unit_en="%", unit_ru="%", frequency="annual",
                section_en="Other", section_ru="Прочее", provider="fred",
                series_template="TEST", aggregation="last",
                source_en="Official", source_ru="Официальный источник", is_listed=True,
            )
            db.add(custom)
            await db.flush()
            db.add_all([
                SubnationalDataPoint(indicator_id=custom.id, region_id=ca.id,
                                     period=date(1900, 1, 1), value=1.0),
                SubnationalDataPoint(indicator_id=custom.id, region_id=ca.id,
                                     period=date(2025, 1, 1), value=2.0),
            ])
            await db.commit()
            urls = []
            cursor = None
            while True:
                page, next_cursor = await _world_region_years_page(db, date(2026, 9, 24), cursor, 2)
                urls.extend(page)
                if not page:
                    break
                cursor = next_cursor
            return urls

    urls = asyncio.run(seed_and_collect())
    paths = [url.path for url in urls]
    assert len(paths) == len(set(paths))
    for year in (1900, 2025):
        path = f"/united-states/region/california/custom-ratio/{year}"
        assert path in paths
        assert image_path_for_page(path) == (
            f"/og/world/united-states/region/california/custom-ratio/{year}.png"
        )
        response = subnational_client.get(
            f"/seo/world/united-states/region/california/custom-ratio/{year}"
        )
        assert response.status_code == 200
        assert path in response.text
    assert subnational_client.get(
        "/seo/world/united-states/region/california/custom-ratio/2024"
    ).status_code == 404
    card = subnational_client.get(
        "/seo/world/united-states/region/california/custom-ratio"
    )
    assert card.status_code == 200
    assert "/custom-ratio/1900" in card.text
    assert "/custom-ratio/2025" in card.text


def test_partial_state_year_compares_the_same_month(subnational_client, auth_env):
    from sqlalchemy import select
    from app.models import SubnationalDataPoint, SubnationalIndicator, SubnationalRegion

    async def seed():
        async with auth_env["session_maker"]() as db:
            ca = (await db.execute(select(SubnationalRegion).where(
                SubnationalRegion.slug == "california",
            ))).scalar_one()
            unemployment = (await db.execute(select(SubnationalIndicator).where(
                SubnationalIndicator.code == "unemployment-rate",
            ))).scalar_one()
            db.add_all([
                SubnationalDataPoint(indicator_id=unemployment.id, region_id=ca.id,
                                     period=date(2025, 8, 1), value=5.0),
                SubnationalDataPoint(indicator_id=unemployment.id, region_id=ca.id,
                                     period=date(2025, 12, 1), value=6.0),
                SubnationalDataPoint(indicator_id=unemployment.id, region_id=ca.id,
                                     period=date(2026, 8, 1), value=5.5),
            ])
            await db.commit()

    asyncio.run(seed())
    response = subnational_client.get(
        "/seo/world/united-states/region/california/unemployment-rate/2026"
    )
    assert response.status_code == 200
    assert "Изменение к 2025: +0,5 %" in response.text
    assert "-0,5 %" not in response.text


def test_district_of_columbia_is_in_region_comparisons(subnational_client, auth_env):
    from sqlalchemy import select
    from app.models import SubnationalDataPoint, SubnationalIndicator, SubnationalRegion
    from app.services.site_urls import _world_region_vs_urls

    async def seed_and_collect():
        async with auth_env["session_maker"]() as db:
            unemployment = (await db.execute(select(SubnationalIndicator).where(
                SubnationalIndicator.code == "unemployment-rate",
            ))).scalar_one()
            dc = SubnationalRegion(
                country_code="US", slug="district-of-columbia", name_en="District of Columbia",
                name_ru="Округ Колумбия", kind="district", geo_code="DC", fips="11",
                sort_order=3,
            )
            db.add(dc)
            await db.flush()
            db.add(SubnationalDataPoint(
                indicator_id=unemployment.id, region_id=dc.id,
                period=date(2024, 2, 1), value=5.4,
            ))
            await db.commit()
            return await _world_region_vs_urls(db, date(2026, 9, 24))

    urls = asyncio.run(seed_and_collect())
    paths = {url.path for url in urls}
    assert len(paths) == 3  # 2 states + DC → all three unordered pairs
    path = "/united-states/region-vs/california-vs-district-of-columbia"
    assert path in paths
    response = subnational_client.get(
        "/seo/world/united-states/region-vs/california-vs-district-of-columbia"
    )
    assert response.status_code == 200
    assert "Штаты и округ Колумбия" in response.text
    assert path in response.text


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
    assert has_en_path("/united-states/region-vs/california-vs-texas")
    assert has_en_path("/not-a-country/region-vs/a-vs-b") is False
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


@pytest.mark.parametrize("locale", ["ru", "en"])
@pytest.mark.parametrize("portrait", [False, True])
def test_subnational_indicator_og_uses_localized_source(
    auth_env, subnational_client, monkeypatch, locale, portrait
):
    import asyncio
    from sqlalchemy import select
    from app.models import SubnationalIndicator
    from app.services import og_image

    sources = {"ru": "Бюро статистики труда США", "en": "U.S. Bureau of Labor Statistics"}

    async def update_sources():
        async with auth_env["session_maker"]() as db:
            series = await db.scalar(
                select(SubnationalIndicator).where(
                    SubnationalIndicator.code == "unemployment-rate"
                )
            )
            series.source_ru = sources["ru"]
            series.source_en = sources["en"]
            await db.commit()

    asyncio.run(update_sources())
    captured = []
    cache_keys = []
    monkeypatch.setattr(og_image, "cached_og", lambda key, **_kw: cache_keys.append(key))
    monkeypatch.setattr(og_image, "store_og", lambda *args, **_kw: None)
    monkeypatch.setattr(
        og_image, "render_indicator_og", lambda **kwargs: captured.append(kwargs) or b"png"
    )
    response = subnational_client.get(
        "/api/v1/og-image/world-region/united-states/california/unemployment-rate.png",
        params={"portrait": "1" if portrait else "0"},
        headers={"X-FE-Locale": locale},
    )
    assert response.status_code == 200
    assert captured[0]["source_label"] == sources[locale]
    assert captured[0]["portrait"] is portrait
    variant = "portrait" if portrait else "landscape"
    assert cache_keys == [
        f"fe1:wr:source-v2:{locale}:united-states:california:unemployment-rate:{variant}"
    ]


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


def test_subnational_portrait_uses_real_month_and_visible_picture(subnational_client, monkeypatch):
    from bs4 import BeautifulSoup
    from app.services import og_image

    captured=[]
    monkeypatch.setattr(og_image, "cached_og", lambda key, **_kw: None)
    monkeypatch.setattr(og_image, "store_og", lambda *args, **_kw: None)
    monkeypatch.setattr(og_image, "render_rating_og", lambda **kw: captured.append(kw) or b"png")
    response=subnational_client.get("/api/v1/og-image/world-regions/united-states.png?portrait=1",headers={"X-FE-Locale":"en"})
    assert response.status_code==200
    assert captured[0]["portrait"] is True
    assert captured[0]["period_text"]=="February 2024"
    assert captured[0]["source_label"]=="BLS"
    page=subnational_client.get("/seo/world/united-states/regions")
    soup=BeautifulSoup(page.text,"html.parser")
    source=soup.select_one(".seo-chart picture source")
    assert source is not None
    assert source["srcset"].endswith("/og/world/united-states/regions.png?portrait=1")



def test_missing_region_series_has_no_indexable_page_or_profile_link(auth_env, subnational_client):
    import asyncio
    from bs4 import BeautifulSoup
    from datetime import date
    from sqlalchemy import select
    from app.models import SubnationalRegion, SubnationalIndicator, SubnationalDataPoint
    async def seed():
        async with auth_env['session_maker']() as db:
            region = SubnationalRegion(country_code='US', slug='alabama', name_en='Alabama',
                                       name_ru='Алабама', kind='state', geo_code='AL', fips='01')
            db.add(region)
            await db.flush()
            gdp = await db.scalar(select(SubnationalIndicator).where(SubnationalIndicator.code == 'real-gdp'))
            db.add(SubnationalDataPoint(region_id=region.id, indicator_id=gdp.id, period=date(2023, 1, 1), value=200000))
            await db.commit()
    asyncio.run(seed())
    for locale in ('ru', 'en'):
        headers = {'X-FE-Locale': locale}
        assert subnational_client.get('/api/v1/world/united-states/regions/region/alabama/unemployment-rate', headers=headers).status_code == 404
        assert subnational_client.get('/seo/world/united-states/region/alabama/unemployment-rate', headers=headers).status_code == 404
        profile = subnational_client.get('/seo/world/united-states/region/alabama', headers=headers)
        assert profile.status_code == 200
        soup = BeautifulSoup(profile.text, 'html.parser')
        assert not soup.select('a[href="/united-states/region/alabama/unemployment-rate"]')
