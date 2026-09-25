"""Sitemap includes live canonical content beyond editorial catalogue choices."""
import asyncio
from datetime import date

from app.models import (
    Indicator, IndicatorData,
    Region, RegionIndicator, RegionDataPoint, RegionMonthlyPoint,
    WorldCountry, WorldIndicator, WorldDataPoint,
)
from app.services import site_urls as urls


def test_national_source_history_is_not_cut_off_at_1990(auth_env, auth_client):
    async def seed_and_collect():
        async with auth_env["session_maker"]() as db:
            indicator = Indicator(code="population", name="Численность населения",
                                  unit="млн человек", frequency="annual",
                                  is_active=True, is_listed=True)
            db.add(indicator)
            await db.flush()
            db.add_all([
                IndicatorData(indicator_id=indicator.id, date=date(1897, 1, 1), value=67.5),
                IndicatorData(indicator_id=indicator.id, date=date(1989, 1, 1), value=147.4),
            ])
            await db.commit()
            return {u.path for u in await urls._year_urls(db, date(2026, 9, 24))}

    pages = asyncio.run(seed_and_collect())
    for year in (1897, 1989):
        path = f"/russia/indicator/population/{year}"
        assert path in pages
        response = auth_client.get(f"/seo/indicator-year/population/{year}")
        assert response.status_code == 200
        assert f'href="https://forecasteconomy.com{path}"' in response.text
        assert 'content="index, follow' in response.text
    assert auth_client.get("/seo/indicator-year/population/1898").status_code == 404
    assert auth_client.get("/seo/indicator-year/population/99999").status_code == 404


def test_regional_public_kinds_hidden_rows_and_monthly_pairs(auth_env):
    async def check():
        async with auth_env["session_maker"]() as db:
            regions = [Region(slug=s, name=s, kind=k) for s, k in (
                ("alpha", "region"), ("beta", "region"), ("gamma", "region"),
                ("district", "district"), ("russia", "country"), ("invalid", "other"),
            )]
            annual = RegionIndicator(code="wages", name="Wages", table_code="3.4",
                section_num=3, section_name="Work", is_listed=False)
            monthly = RegionIndicator(code="fuel", name="Fuel", table_code="16.20",
                section_num=16, section_name="Prices", is_listed=True)
            db.add_all(regions + [annual, monthly])
            await db.flush()
            for region in regions:
                db.add(RegionDataPoint(region_id=region.id, indicator_id=annual.id,
                    year=2018 if region.slug != "beta" else 2017, value=1))
            # A pair with both histories is one URL; monthly-only fuel must also exist.
            db.add_all([
                RegionMonthlyPoint(region_id=regions[0].id, indicator_id=annual.id, month=202501, value=2),
                RegionMonthlyPoint(region_id=regions[0].id, indicator_id=monthly.id, month=202502, value=2),
                RegionDataPoint(region_id=regions[0].id, indicator_id=annual.id, year=1899, value=1),
                RegionDataPoint(region_id=regions[0].id, indicator_id=annual.id, year=2100, value=1),
            ])
            await db.commit()
            today = date(2026, 9, 20)
            expected_pairs = {f"/russia/region/{r.slug}/wages" for r in regions[:-1]} | {
                "/russia/region/alpha/fuel"}
            full = await urls._regional_pair_urls(db, today)
            assert {u.path for u in full} == expected_pairs
            assert len(full) == len(expected_pairs)
            assert (await db.execute(urls._REG_PAIRS_COUNT)).scalar_one() == len(expected_pairs)
            source = urls._CHUNKED_SOURCES["regional-"]
            bounds = await urls._chunk_bounds(db, "regional-public-test", source.bounds, source.sort, 2)
            paged = []
            for after in bounds[:-1]:
                page, _ = await source.fetch(db, today, after, 2)
                paged.extend(page)
            assert {u.path for u in paged} == expected_pairs
            assert len(paged) == len(expected_pairs)
            years = {u.path for u in await urls._regional_year_urls(db, today)}
            assert len(years) == 7
            assert "/russia/region/district/wages/2018" in years
            assert "/russia/region/russia/wages/2018" in years
            assert "/russia/region/alpha/wages/1899" in years
            assert "/russia/region/alpha/wages/2100" in years
            assert (await db.execute(urls._REG_YEARS_COUNT)).scalar_one() == len(years)
            assert len((await db.execute(urls._regional_years_bounds_stmt())).all()) == len(years)
            source = urls._CHUNKED_SOURCES["regional-years-"]
            bounds = await urls._chunk_bounds(db, "regional-year-contract", source.bounds, source.sort, 2)
            paged_years = []
            for after in bounds[:-1]:
                page, _ = await source.fetch(db, today, after, 2)
                paged_years.extend(page)
            assert {u.path for u in paged_years} == years
            assert len(paged_years) == len(years)
            assert {u.path for u in await urls._region_vs_urls(db, today)} == {
                "/russia/region-vs/alpha-vs-gamma"}
            hubs = {u.path for u in await urls._region_hub_urls(db, today)}
            assert "/russia/region/district" in hubs
            assert "/russia/region/russia" in hubs
            assert "/russia/region/invalid" not in hubs
    asyncio.run(check())


def test_world_comparisons_include_nonadjacent_pairs_but_not_404s(auth_env):
    async def check():
        async with auth_env["session_maker"]() as db:
            for i, (slug, values, active) in enumerate((
                ("alpha", [100, 110], True), ("beta", [200, 210], True),
                ("gamma", [300, 310], True), ("single", [100], True),
                ("zero", [100, 0], True), ("empty", [], True),
                ("inactive", [100, 110], False),
            )):
                country = WorldCountry(code=f"X{i}", slug=slug, name_ru=slug, name_en=slug, is_active=active)
                db.add(country)
                await db.flush()
                indicator = WorldIndicator(country_id=country.id, code=f"{slug}-population",
                    dataset_id="demo_pjan", slice_hash=slug,
                    slice_json={"unit": "NR", "age": "TOTAL", "sex": "T"},
                    name_ru="Population", name_en="Population", unit="NR", unit_ru="человек",
                    frequency="annual", is_listed=True, points_count=len(values))
                db.add(indicator)
                await db.flush()
                db.add_all([WorldDataPoint(indicator_id=indicator.id, date=date(2018 + j, 1, 1), value=value)
                            for j, value in enumerate(values)])
            await db.commit()
            pages = await urls._world_vs_urls(db, date(2026, 9, 20))
            expected = {"/alpha-vs-beta/population", "/alpha-vs-gamma/population", "/beta-vs-gamma/population"}
            assert {u.path for u in pages} == expected
            assert len(pages) == len(expected)
            # Use the real SSR seam as the acceptance oracle, not a duplicated rule.
            from app.services.seo_world_compare import render_world_vs_html
            for page in pages:
                pair, concept = page.path.strip("/").split("/")
                a, b = pair.split("-vs-")
                status, html = await render_world_vs_html(a, b, concept, db)
                assert status == 200
                assert 'content="index, follow' in html
            for b in ("single", "zero", "empty", "inactive"):
                status, _ = await render_world_vs_html("alpha", b, "population", db)
                assert status == 404
    asyncio.run(check())


def test_world_regions_sitemap_stays_under_protocol_limit(auth_env, monkeypatch):
    from app.models import SubnationalDataPoint, SubnationalIndicator, SubnationalRegion

    async def check():
        async with auth_env["session_maker"]() as db:
            db.add(WorldCountry(
                code="US", slug="united-states", name_ru="США",
                name_en="United States", sort_order=1,
            ))
            await db.flush()
            regions = [
                SubnationalRegion(
                    country_code="US", slug=slug, name_en=name, name_ru=name,
                    sort_order=order,
                )
                for order, slug, name in (
                    (1, "new-york", "New York"),
                    (2, "california", "California"),
                    (3, "wyoming", "Wyoming"),
                )
            ]
            indicators = [
                SubnationalIndicator(
                    country_code="US", code=code, name_en=code, name_ru=code,
                    series_template=code, is_listed=listed,
                )
                for code, listed in (("a", True), ("b", True), ("hidden", False))
            ]
            db.add_all(regions + indicators)
            await db.flush()
            by_slug = {region.slug: region for region in regions}
            by_code = {indicator.code: indicator for indicator in indicators}
            db.add_all([
                SubnationalDataPoint(
                    indicator_id=by_code["a"].id, region_id=by_slug["new-york"].id,
                    period=date(2024, 1, 1), value=1,
                ),
                SubnationalDataPoint(
                    indicator_id=by_code["a"].id, region_id=by_slug["california"].id,
                    period=date(2025, 1, 1), value=1,
                ),
                SubnationalDataPoint(
                    indicator_id=by_code["b"].id, region_id=by_slug["california"].id,
                    period=date(2023, 1, 1), value=1,
                ),
                SubnationalDataPoint(
                    indicator_id=by_code["hidden"].id, region_id=by_slug["new-york"].id,
                    period=date(2026, 1, 1), value=1,
                ),
            ])
            await db.commit()
            built = await urls._world_regions_urls(db, date(2026, 9, 25))
            paths = [item.path for item in built]
            assert await urls._world_regions_url_count(db) == len(built)
            assert paths == [
                "/united-states/regions",
                "/united-states/region/new-york",
                "/united-states/region/new-york/a",
                "/united-states/region/california",
                "/united-states/region/california/a",
                "/united-states/region/california/b",
                "/united-states/region/wyoming",
            ]
            assert built[0].lastmod == "2025-01-01"
            paged = await urls._world_regions_page(db, 0, len(built))
            assert [(item.path, item.lastmod, item.priority) for item in paged] == [
                (item.path, item.lastmod, item.priority) for item in built
            ]
            monkeypatch.setattr(urls, "SITEMAP_MAX_URLS", 3)
            monkeypatch.setattr(urls, "WORLD_CHUNK", 3)
            names = [name for name, _chunk in urls.bounded_section_items("world-regions", built)]
            assert names == ["world-regions-1", "world-regions-2", "world-regions-3"]
            assert urls.section_names_for_count("world-regions", len(built)) == names

            async def must_not_materialise(*args, **kwargs):
                raise AssertionError("shard resolve must not load every world-region URL")

            monkeypatch.setattr(urls, "_world_regions_urls", must_not_materialise)
            second = await urls.resolve_section(db, "world-regions-2")
            assert [item.path for item in second] == paths[3:6]
            assert await urls.resolve_section(db, "world-regions") is None
            streamed = [item async for item in urls._iter_world_region_sections(db)]
            assert [name for name, _chunk in streamed] == names
            assert [item.path for item in streamed[1][1]] == paths[3:6]

    asyncio.run(check())
