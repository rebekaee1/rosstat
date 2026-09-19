"""INDEX_POLICY: пороги, robots-meta, канон без ?mode=."""
from datetime import date

from app.services.index_policy import (
    RUSSIA_YEAR_MIN_POINTS,
    is_noindex_path,
    robots_for_path,
    strip_mode_query,
)


def test_russia_year_min_points_is_six():
    assert RUSSIA_YEAR_MIN_POINTS == 6


def test_old_regional_year_is_indexable():
    today = date(2026, 9, 3)
    path = "/russia/region/moskva/chislennost-naseleniya/2018"
    assert not is_noindex_path(path, today=today)
    assert robots_for_path(path, today=today).startswith("index, follow")
    assert not is_noindex_path("/russia/region/moskva/chislennost-naseleniya/2024", today=today)


def test_old_month_landing_is_indexable():
    today = date(2026, 9, 3)
    assert not is_noindex_path("/russia/indicator/cpi/2023-04", today=today)
    assert not is_noindex_path("/russia/indicator/cpi/2026-01", today=today)


def test_old_world_year_is_indexable():
    today = date(2026, 9, 3)
    assert not is_noindex_path("/germany/indicator/de-foo/2010", today=today)
    assert not is_noindex_path("/germany/indicator/de-cpi/2022", today=today)


def test_hubs_stay_indexable():
    assert not is_noindex_path("/russia/indicator/cpi")
    assert not is_noindex_path("/russia/region/moskva/chislennost-naseleniya")
    assert "index, follow" in robots_for_path("/")


def test_strip_mode_query():
    assert strip_mode_query("/russia/indicator/cpi?mode=weekly") == "/russia/indicator/cpi"
    assert strip_mode_query("/russia/indicator/cpi") == "/russia/indicator/cpi"
    assert strip_mode_query("/x?mode=a&utm_source=y") == "/x?utm_source=y"


def test_honeypot_noindex():
    assert is_noindex_path("/__honeypot__/trap")


def test_historical_sitemap_preserves_data_and_listing_gates(auth_env):
    import asyncio
    from app.models import Indicator, IndicatorData, Region, RegionIndicator, RegionDataPoint
    from app.services import site_urls as urls

    async def check():
        async with auth_env["session_maker"]() as db:
            for code, frequency, months, listed, active in (
                ("quarter-full", "quarterly", (1, 4, 7, 10), True, True),
                ("quarter-short", "quarterly", (1, 4, 7), True, True),
                ("annual-history", "annual", (1,), True, True),
                ("month-full", "monthly", (1, 2, 3, 4, 5, 6), True, True),
                ("month-short", "monthly", (1,), True, True),
                ("month-hidden", "monthly", (1, 2, 3, 4, 5, 6), False, True),
                ("month-inactive", "monthly", (1, 2, 3, 4, 5, 6), True, False),
                ("inflation", "monthly", (1, 2, 3, 4, 5, 6), True, True),
                ("week-full", "weekly", (1, 2, 3, 4, 5, 6), True, True),
                ("day-short", "daily", (1, 2, 3, 4, 5), True, True),
                ("empty", "annual", (), True, True),
            ):
                ind = Indicator(code=code, name=code, frequency=frequency,
                                is_listed=listed, is_active=active)
                db.add(ind)
                await db.flush()
                db.add_all([IndicatorData(indicator_id=ind.id, date=date(2018, m, 1), value=1)
                            for m in months])
            region = Region(slug="moskva", name="Москва", kind="region")
            db.add(region)
            await db.flush()
            for code, listed, years in (
                ("chislennost-naseleniya", True, (2018, 2024)),
                ("hidden", False, (2018,)),
                ("empty", True, ()),
            ):
                ind = RegionIndicator(code=code, name=code, table_code="1.1",
                                      section_num=1, section_name="Население", is_listed=listed)
                db.add(ind)
                await db.flush()
                db.add_all([RegionDataPoint(region_id=region.id, indicator_id=ind.id,
                                            year=y, value=1) for y in years])
            await db.commit()
            today = date(2026, 9, 20)
            years = {u.path for u in await urls._year_urls(db, today)}
            assert years == {f"/russia/indicator/{c}/2018" for c in
                             ("quarter-full", "annual-history", "month-full", "week-full")}
            months = {u.path for u in await urls._month_urls(db, today)}
            assert months == {f"/russia/indicator/month-full/2018-{m:02d}" for m in range(1, 7)} | {
                "/russia/indicator/month-short/2018-01"}
            month_pages = []
            cursor = None
            while True:
                page, cursor = await urls._months_page(db, today, cursor, 2)
                month_pages.extend(page)
                if cursor is None:
                    break
            assert {u.path for u in month_pages} == months
            source = urls._CHUNKED_SOURCES["months-"]
            bounds = await urls._chunk_bounds(db, "test-months-", source.bounds, source.sort, 2)
            bounded = []
            for after in bounds[:-1]:
                page, _ = await source.fetch(db, today, after, 2)
                bounded.extend(page)
            assert {u.path for u in bounded} == months
            assert len(bounded) == len(months)
            assert "months-1" in await urls.section_names(db)
            assert "months" not in await urls.section_names(db)
            assert {u.path for u in await urls.resolve_section(db, "months-1")} == months
            assert {u.path for u in await urls.resolve_section(db, "months")} == months
            regional = {u.path for u in await urls._regional_year_urls(db, today)}
            assert regional == {f"/russia/region/moskva/chislennost-naseleniya/{y}" for y in (2018, 2024)}
            assert (await db.execute(urls._REG_YEARS_COUNT)).scalar_one() == 2
            bounds = (await db.execute(urls._regional_years_bounds_stmt())).all()
            assert {row[2] for row in bounds} == {2018, 2024}
            page, cursor = await urls._regional_years_page(db, today, None, 1)
            next_page, _ = await urls._regional_years_page(db, today, cursor, 1)
            assert {u.path for u in page + next_page} == regional
            assert page[0].path.endswith("/2018")

    asyncio.run(check())


def test_historical_world_sitemap_preserves_curated_primary_and_data_gates(auth_env, monkeypatch):
    import asyncio
    from app.models import WorldCountry, WorldIndicator, WorldDataPoint
    from app.services import site_urls as urls

    async def check():
        async with auth_env["session_maker"]() as db:
            country = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany")
            db.add(country)
            await db.flush()
            for code, dataset, frequency, listed, years in (
                ("de-une-primary", "une_rt_m", "monthly", True, (2010, 2024)),
                ("de-une-secondary", "une_rt_m", "quarterly", True, (2010,)),
                ("de-uncurated", "unknown_dataset", "annual", True, (2010,)),
                ("de-hidden", "demo_pjan", "annual", False, (2010,)),
                ("de-empty", "prc_hicp_midx", "monthly", True, ()),
            ):
                ind = WorldIndicator(country_id=country.id, code=code, dataset_id=dataset,
                                     slice_hash=code, slice_json={"unit": "PC_ACT", "sex": "T", "age": "TOTAL"},
                                     name_ru=code, name_quality="curated", frequency=frequency,
                                     unit="PC_ACT", unit_ru="%", points_count=len(years), is_listed=listed)
                db.add(ind)
                await db.flush()
                db.add_all([WorldDataPoint(indicator_id=ind.id, date=date(y, 1, 1), value=1) for y in years])
            await db.commit()
            today = date(2026, 9, 20)
            expected = {f"/germany/indicator/de-une-primary/{y}" for y in (2010, 2024)}
            assert {u.path for u in await urls._world_year_urls(db, today)} == expected
            # Bounds/count retain the secondary frequency; page filtering still excludes its 301.
            assert (await db.execute(urls._WORLD_YEARS_COUNT)).scalar_one() == 3
            assert {int(r[1]) for r in (await db.execute(urls._world_years_bounds_stmt())).all()} == {2010, 2024}
            paths = set()
            cursor = None
            for _ in range(4):
                page, cursor = await urls._world_years_page(db, today, cursor, 1)
                paths.update(u.path for u in page)
                if cursor is None:
                    break
            assert paths == expected
            monkeypatch.setattr(urls, "curated_world_dataset_ids", lambda: frozenset())
            assert await urls._world_year_urls(db, today) == []
            assert await urls._world_years_page(db, today, None, 10) == ([], None)

    asyncio.run(check())
