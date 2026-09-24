"""INDEX_POLICY: пороги, robots-meta, канон без ?mode=."""
from datetime import date

from app.services.index_policy import (
    RUSSIA_YEAR_MIN_POINTS,
    is_noindex_path,
    robots_for_path,
    strip_mode_query,
)


def test_russia_year_min_points_matches_live_ssr():
    assert RUSSIA_YEAR_MIN_POINTS == 1


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


def test_historical_sitemap_matches_public_ssr_gates(auth_env):
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
                             ("quarter-full", "quarter-short", "annual-history", "month-full", "month-short",
                              "month-hidden", "week-full", "day-short")}
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
            assert regional == {f"/russia/region/moskva/chislennost-naseleniya/{y}" for y in (2018, 2024)} | {
                "/russia/region/moskva/hidden/2018"}
            assert (await db.execute(urls._REG_YEARS_COUNT)).scalar_one() == 3
            bounds = (await db.execute(urls._regional_years_bounds_stmt())).all()
            assert {row[2] for row in bounds} == {2018, 2024}
            page, cursor = await urls._regional_years_page(db, today, None, 1)
            next_page, cursor = await urls._regional_years_page(db, today, cursor, 1)
            final_page, _ = await urls._regional_years_page(db, today, cursor, 1)
            assert {u.path for u in page + next_page + final_page} == regional
            assert page[0].path.endswith("/2018")

    asyncio.run(check())


def test_world_sitemap_includes_all_public_datasets_and_preserves_validity(auth_env):
    import asyncio
    from app.models import WorldCountry, WorldIndicator, WorldDataPoint
    from app.services import site_urls as urls

    async def check():
        async with auth_env["session_maker"]() as db:
            country = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany")
            us = WorldCountry(code="US", slug="united-states", name_ru="США", name_en="United States")
            db.add_all([country, us])
            await db.flush()
            for code, dataset, frequency, listed, years in (
                ("de-une-primary", "une_rt_m", "monthly", True, (2010, 2024)),
                ("de-une-secondary", "une_rt_m", "quarterly", True, (2010,)),
                ("de-uncurated", "unknown_dataset", "annual", True, (999, 1880, 2010, 2100, 9999)),
                ("us-gdp-real", "FRED_GDPC1", "quarterly", True, (1947, 2025)),
                ("de-hidden", "demo_pjan", "annual", False, (2010,)),
                ("de-empty", "prc_hicp_midx", "monthly", True, ()),
            ):
                ind = WorldIndicator(country_id=us.id if code.startswith("us-") else country.id, code=code, dataset_id=dataset,
                                     slice_hash=code, slice_json={"unit": "PC_ACT", "sex": "T", "age": "TOTAL"},
                                     name_ru=code, name_quality="curated", frequency=frequency,
                                     unit="PC_ACT", unit_ru="%", points_count=len(years), is_listed=listed)
                db.add(ind)
                await db.flush()
                db.add_all([WorldDataPoint(indicator_id=ind.id, date=date(y, 1, 1), value=1) for y in years])
            inactive = WorldCountry(code="XX", slug="inactive", name_ru="Inactive", name_en="Inactive", is_active=False)
            db.add(inactive)
            await db.flush()
            excluded = WorldIndicator(country_id=inactive.id, code="inactive-test", dataset_id="unknown_dataset",
                slice_hash="inactive", name_ru="Inactive", frequency="annual", is_listed=True)
            db.add(excluded)
            await db.flush()
            db.add(WorldDataPoint(indicator_id=excluded.id, date=date(2025, 1, 1), value=1))
            await db.commit()
            today = date(2026, 9, 20)
            expected = {f"/germany/indicator/de-une-primary/{y}" for y in (2010, 2024)} | {
                "/germany/indicator/de-uncurated/1880",
                "/germany/indicator/de-uncurated/2010",
                "/germany/indicator/de-uncurated/2100",
                "/united-states/indicator/us-gdp-real/1947", "/united-states/indicator/us-gdp-real/2025",
            }
            assert {u.path for u in await urls._world_year_urls(db, today)} == expected
            cards = {path.rsplit("/", 1)[0] for path in expected}
            assert {u.path for u in await urls._world_cards_urls(db, today)} == cards
            assert (await db.execute(urls._WORLD_CARDS_COUNT)).scalar_one() == 4
            source_cards = urls._CHUNKED_SOURCES["world-indicators-"]
            card_bounds = await urls._chunk_bounds(db, "world-cards-test", source_cards.bounds, source_cards.sort, 2)
            bounded_cards = []
            for after in card_bounds[:-1]:
                page, _ = await source_cards.fetch(db, today, after, 2)
                bounded_cards.extend(page)
            assert {u.path for u in bounded_cards} == cards
            assert len(bounded_cards) == len(cards)
            # Bounds/count retain the secondary frequency; page filtering still excludes its 301.
            # Historical/future source years are valid; unsafe 999/9999 are not.
            assert (await db.execute(urls._WORLD_YEARS_COUNT)).scalar_one() == 8
            assert {int(r[1]) for r in (await db.execute(urls._world_years_bounds_stmt())).all()} == {1880, 1947, 2010, 2024, 2025, 2100}
            paths = set()
            cursor = None
            for _ in range(10):
                page, cursor = await urls._world_years_page(db, today, cursor, 1)
                paths.update(u.path for u in page)
                if cursor is None:
                    break
            assert paths == expected
            assert cursor is None
            source = urls._CHUNKED_SOURCES["world-years-"]
            bounds = await urls._chunk_bounds(db, "world-years-test", source.bounds, source.sort, 2)
            bounded = []
            for after in bounds[:-1]:
                page, _ = await source.fetch(db, today, after, 2)
                bounded.extend(page)
            assert {u.path for u in bounded} == expected
            assert len(bounded) == len(expected)

    asyncio.run(check())
