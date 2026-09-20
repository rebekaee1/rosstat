"""Sitemap includes live canonical content beyond editorial catalogue choices."""
import asyncio
from datetime import date

from app.models import (
    Region, RegionIndicator, RegionDataPoint, RegionMonthlyPoint,
    WorldCountry, WorldIndicator, WorldDataPoint,
)
from app.services import site_urls as urls


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
            assert len(years) == 5
            assert "/russia/region/district/wages/2018" in years
            assert "/russia/region/russia/wages/2018" in years
            assert not any(p.endswith(("/1899", "/2100")) for p in years)
            assert (await db.execute(urls._REG_YEARS_COUNT)).scalar_one() == len(years)
            assert len((await db.execute(urls._regional_years_bounds_stmt())).all()) == len(years)
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
