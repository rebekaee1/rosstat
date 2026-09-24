"""Public years are data-backed, four-digit dates, shared by HTML, PNG and sitemap."""
import asyncio
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from app.models import (
    EconomicEvent, Indicator, IndicatorData, Region, RegionDataPoint, RegionIndicator,
    WorldCountry, WorldDataPoint, WorldIndicator,
)
from app.services import site_paths as paths, site_urls as urls


@pytest.mark.parametrize("year", [1000, 1897, 2100, 9998])
def test_path_builders_share_date_contract(year):
    assert paths.is_public_year(year) and paths.is_public_year(str(year))
    assert paths.indicator_year("russia", "x", year).endswith(f"/{year}")
    assert paths.indicator_month("russia", "x", year, 12).endswith(f"/{year}-12")
    assert paths.og_indicator("russia", "x", f"{year}-12").endswith(f"/{year}-12.png")
    assert paths.region_indicator_year("alpha", "x", year).endswith(f"/{year}")
    assert paths.og_region_year("alpha", "x", year).endswith(f"/{year}.png")
    assert paths.world_rating_year("x", year).endswith(f"/{year}")
    assert paths.og_world_rating_year("x", year).endswith(f"/{year}.png")
    assert paths.calendar(year, 12).endswith(f"/{year}/12")


@pytest.mark.parametrize("year", [999, 9999, 10000, "0000", "01000", "٢٠٢٥", "2025.0", " 2025", True])
def test_noncanonical_dates_cannot_be_constructed(year):
    assert not paths.is_public_year(year)
    with pytest.raises(ValueError):
        paths.indicator_year("russia", "x", year)
    with pytest.raises(ValueError):
        paths.og_indicator("russia", "x", year)


@pytest.mark.parametrize("period", ["1897-00", "2100-13", "9999-01", "0999-01", "10000-01"])
def test_invalid_month_periods(period):
    assert not paths.is_public_month_period(period)
    with pytest.raises(ValueError):
        paths.og_indicator("russia", "x", period)


def test_nginx_routes_and_rewrite_captures_share_contract():
    config = (Path(__file__).parents[2] / "frontend/nginx.conf").read_text()
    locations = [(re.compile(re.sub(r"\(\?<([a-z_]+)>", r"(?P<\1>", p)), body)
                 for p, body in re.findall(r'location ~ "([^"]+)" \{(.*?)\n    \}', config, re.S)]
    rewrites = [(re.compile(p), target) for p, target in re.findall(r'rewrite "([^"]+)" (\S+) break;', config)]
    templates = ["/russia/indicator/cpi/{y}", "/russia/indicator/cpi/{y}-12",
                 "/germany/indicator/population/{y}", "/russia/region/moskva/wages/{y}",
                 "/world/rating/gdp-usd/{y}", "/russia/calendar/{y}/12"]
    og_templates = [
        ("/og/russia/cpi/{y}.png", "/api/v1/og-image/indicator/cpi/{y}.png"),
        ("/og/russia/cpi/{y}-12.png", "/api/v1/og-image/indicator/cpi/{y}-12.png"),
        ("/og/germany/population/{y}.png", "/api/v1/og-image/world/germany/population/{y}.png"),
        ("/og/russia/region/moskva/wages/{y}.png", "/api/v1/og-image/region/moskva/wages/{y}.png"),
        ("/og/world/rating/gdp-usd/{y}.png", "/api/v1/og-image/world-rating/gdp-usd/{y}.png"),
    ]
    for year in [1000, 1897, 2100, 9998, 999, 9999, 10000]:
        valid = paths.is_public_year(year)
        for template in templates:
            matches = [body for p, body in locations if p.fullmatch(template.format(y=year))]
            assert matches, (template, year)
            assert ("proxy_pass" in matches[0]) == valid, (template, year)
            if not valid:
                assert "return 404;" in matches[0]
        for template, expected in og_templates:
            matches = [(p.fullmatch(template.format(y=year)), target) for p, target in rewrites]
            matches = [(m, target) for m, target in matches if m]
            assert bool(matches) == valid, (template, year)
            if valid:
                match, target = matches[0]
                resolved = re.sub(r"\$(\d+)", lambda m: match.group(int(m[1])), target)
                assert resolved == expected.format(y=year)


def test_data_backed_years_across_public_families(auth_env, auth_client, monkeypatch):
    years = (1000, 1897, 2100, 9998)

    async def seed_and_collect():
        async with auth_env["session_maker"]() as db:
            annual = Indicator(code="historical-population", name="Население", name_en="Population",
                               unit="человек", frequency="annual", is_active=True, is_listed=True)
            monthly = Indicator(code="historical-monthly", name="Месячный ряд", name_en="Monthly series",
                                unit="%", frequency="monthly", is_active=True, is_listed=True)
            region = Region(slug="alpha", name="Alpha", kind="region")
            regional = RegionIndicator(code="historical-population", name="Население", table_code="1.1",
                                       section_num=1, section_name="Population", is_listed=False)
            country = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany", is_active=True)
            db.add_all([annual, monthly, region, regional, country])
            await db.flush()
            world = WorldIndicator(country_id=country.id, code="historical-population", dataset_id="demo_pjan",
                                   slice_json={"unit": "NR", "age": "TOTAL", "sex": "T"}, slice_hash="year-contract",
                                   name_ru="Население", name_en="Population", frequency="annual", unit="NR", unit_ru="человек",
                                   is_listed=True, points_count=len(years))
            db.add(world)
            await db.flush()
            for year in years:
                db.add_all([
                    IndicatorData(indicator_id=annual.id, date=date(year, 1, 1), value=100),
                    IndicatorData(indicator_id=monthly.id, date=date(year, 12, 1), value=10),
                    RegionDataPoint(region_id=region.id, indicator_id=regional.id, year=year, value=100),
                    WorldDataPoint(indicator_id=world.id, date=date(year, 1, 1), value=100),
                ])
                for day in (4, 11, 18):
                    db.add(EconomicEvent(title="Публикация", event_type="release", source="rosstat",
                        scheduled_date=date(year, 12, day), event_key=f"year-contract:{year}:{day}",
                        is_estimated=False, date_confidence="official_explicit", source_url="https://rosstat.gov.ru/calendar",
                        source_hash=f"hash-{year}-{day}", last_seen_at=datetime(2026, 9, 24)))
            await db.commit()
            today = date(2026, 9, 24)
            collected = []
            for fetch in [urls._year_urls, urls._world_year_urls, urls._regional_year_urls, urls._calendar_month_urls]:
                collected.extend(await fetch(db, today))
            months = (await db.execute(urls._months_stmt())).all()
            assert {int(row[1]) for row in months} == set(years)
            world_paths = {u.path for u in collected if u.path.startswith("/germany/")}
            assert len(world_paths) == len(years)
            assert (await db.execute(urls._WORLD_YEARS_COUNT)).scalar_one() == len(years)
            source = urls._CHUNKED_SOURCES["world-years-"]
            bounds = await urls._chunk_bounds(db, "year-contract-world", source.bounds, source.sort, 2)
            paged = []
            for after in bounds[:-1]:
                page, _ = await source.fetch(db, today, after, 2)
                paged.extend(page)
            assert {u.path for u in paged} == world_paths
            return {u.path for u in collected}

    sitemap = asyncio.run(seed_and_collect())
    # Exercise real data selection; rendering itself has dedicated image tests.
    from app.api import sitemap as og
    monkeypatch.setattr("app.services.og_image.cached_og", lambda key: None)
    monkeypatch.setattr("app.services.og_image.store_og", lambda key, png: None)
    async def capture_render(renderer, **kwargs):
        assert kwargs["values"]
        return b"\x89PNG\r\n\x1a\n"
    monkeypatch.setattr(og, "render_og_async", capture_render)
    endpoints = [
        ("/seo/indicator-year/historical-population/{y}", "/russia/indicator/historical-population/{y}", "/api/v1/og-image/indicator/historical-population/{y}.png"),
        ("/seo/world-indicator-year/germany/historical-population/{y}", "/germany/indicator/historical-population/{y}", "/api/v1/og-image/world/germany/historical-population/{y}.png"),
        ("/seo/region-indicator-year/alpha/historical-population/{y}", "/russia/region/alpha/historical-population/{y}", "/api/v1/og-image/region/alpha/historical-population/{y}.png"),
        ("/seo/indicator-month/historical-monthly/{y}-12", None, "/api/v1/og-image/indicator/historical-monthly/{y}-12.png"),
        ("/seo/calendar-month/{y}/12", "/russia/calendar/{y}/12", None),
    ]
    for locale in ("ru", "en"):
        headers = {"X-FE-Locale": locale}
        for year in years:
            for html_path, public_path, image_path in endpoints:
                if public_path:
                    assert public_path.format(y=year) in sitemap
                response = auth_client.get(html_path.format(y=year), headers=headers)
                assert response.status_code == 200, (html_path, year, response.text[:100])
                assert f"{year}" in response.text
                if year == 9998 and "calendar" in html_path:
                    assert '/russia/calendar/9999/' not in response.text
                if image_path:
                    assert auth_client.get(image_path.format(y=year), headers=headers).status_code == 200
        for year in (1800, 999, 9999, 10000):
            for html_path, _, image_path in endpoints:
                assert auth_client.get(html_path.format(y=year), headers=headers).status_code == 404
                if image_path:
                    assert auth_client.get(image_path.format(y=year), headers=headers).status_code == 404
