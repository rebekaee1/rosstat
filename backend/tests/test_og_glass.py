"""Truthful chart geometry and readable phone companions for the shared OG renderer."""
from datetime import date
import io

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
import pytest

from app.services.og_image import _chart_coordinates, _glass_panel, render_indicator_og
from app.services.seo_renderer import _prepare_quicklink_body, _preview_body_urls, _seo_chart_figure


def test_chart_preserves_whole_observed_span_without_tail_truncation():
    points, _ = _chart_coordinates(list(range(100)), (0, 0, 990, 100))
    assert len(points) == 100
    assert points[0][1] == 0
    assert points[-1][1] == 990


def test_missing_observations_are_not_zero_and_single_point_is_not_duplicated():
    points, _ = _chart_coordinates([None, 12.0, None], (0, 0, 100, 100))
    assert len(points) == 1 and points[0][0] == 1
    assert _chart_coordinates([], (0, 0, 100, 100))[0] == []


def test_time_axis_preserves_a_missing_year():
    points, _ = _chart_coordinates([1, 2, 4], (0, 0, 300, 100),
                                   [date(2021, 1, 1), date(2022, 1, 1), date(2024, 1, 1)])
    assert points[1][1] == pytest.approx(100)


def test_glass_panel_has_readable_pearl_surface_and_soft_shadow():
    image = Image.new("RGBA", (220, 170), (38, 43, 56, 255))
    _glass_panel(ImageDraw.Draw(image), (40, 35, 180, 120), radius=18)
    assert image.getpixel((100, 75)) == (255, 255, 255, 249)
    shadow_pixel = image.getpixel((100, 126))
    assert 17 < shadow_pixel[0] < 38 and shadow_pixel[3] == 255


@pytest.mark.parametrize("portrait,dimensions", [(False, (1200, 630)), (True, (1080, 1350))])
def test_image_companion_dimensions_and_real_single_observation(portrait, dimensions):
    png = render_indicator_og(code="population", name="Численность населения",
        value_text="146,12 млн чел.", date_text="Годовое значение", values=[146.12],
        point_dates=[date(2025, 1, 1)], frequency="annual", period_text="2025",
        x_labels=("2025", "2025"), source_label="Росстат", portrait=portrait)
    with Image.open(io.BytesIO(png)) as image:
        assert image.size == dimensions


@pytest.mark.parametrize("path", [
    "/og/russia/cpi/2025.png", "/og/russia/cpi/2025-07.png",
    "/og/russia/region/tulskaya-oblast/wages/2024.png",
    "/og/germany/gdp/2024.png", "/og/world/united-states/region/california/gdp.png",
])
def test_series_figure_exposes_portrait_with_crawlable_fallback(path):
    html = _prepare_quicklink_body(_seo_chart_figure(path,"Actual data","Rosstat",href="/russia/indicator/cpi"),"/russia/indicator/cpi/2025")
    soup = BeautifulSoup(html,"html.parser")
    assert soup.source["srcset"] == path + "?portrait=1"
    assert soup.img["src"] == path
    assert soup.img["width"] == "1200" and soup.img["height"] == "630"
    assert soup.img["loading"] == "eager" and soup.img["fetchpriority"] == "high"


@pytest.mark.parametrize("path", ["/og/world/germany.png", "/og/russia/today.png", "/og/world-rating/gdp/2025.png"])
def test_hub_figure_exposes_native_portrait(path):
    assert "<picture>" in _seo_chart_figure(path,"Hub data","Official data")


@pytest.mark.parametrize("year", ["2025", "1897"])
def test_visible_source_anchor_is_internal_and_table_scrolls(year):
    html = _prepare_quicklink_body('<a href="https://rosstat.gov.ru/data" target="_blank">Росстат</a><table><tr><td>1</td></tr></table>', f"/russia/indicator/cpi/{year}")
    soup = BeautifulSoup(html,"html.parser")
    assert soup.a["href"] == "/russia/indicator/cpi"
    assert "target" not in soup.a.attrs
    assert "seo-table-scroll" in soup.table.parent["class"]


@pytest.mark.parametrize("label", ["Россия", "Russia"])
def test_quicklink_country_name_keeps_country_destination_without_rewriting_indicator_links(label):
    body = (
        f'<a href="/russia">{label}</a>'
        '<a href="/russia/indicator/gdp-nominal-annual">GDP</a>'
    )
    soup = BeautifulSoup(_prepare_quicklink_body(body, "/world/vs/gdp-usd/russia-vs-germany"), "html.parser")
    assert soup.find("a", string=label)["href"] == "/russia"
    assert soup.find("a", string="GDP")["href"] == "/russia/indicator/gdp-nominal-annual"


@pytest.mark.parametrize("locale", ["ru", "en"])
def test_preview_body_preserves_period_and_fragment_and_separates_image_urls(locale):
    from urllib.parse import parse_qs, urlsplit

    body = '''<a id="cta" href="/world/rating/gdp-usd?view=interactive&amp;year=2024#chart">Chart</a>
      <a id="site" href="https://forecasteconomy.com/russia/region?year=2020#chart">Regions</a>
      <a id="fragment" href="#chart">Jump</a><a id="external" href="https://rosstat.gov.ru/data?year=2024">Source</a>
      <a id="mail" href="mailto:test@example.com">Mail</a>
      <picture><source srcset="/og/world/rating/gdp-usd/2024.png?portrait=1 1x, /og/world/rating/gdp-usd/2024.png?portrait=1&amp;size=2 2x">
      <img src="/og/world/rating/gdp-usd/2024.png?preview_locale=xx" width="1200" height="630"></picture>
      <img id="external-image" src="https://example.com/image.png"><img id="embedded" src="data:image/png;base64,abcd">
      <script type="application/ld+json">{"url":"https://rosstat.gov.ru/data"}</script>'''
    result = _preview_body_urls(body, locale)
    soup = BeautifulSoup(result, "html.parser")
    cta = urlsplit(soup.select_one("#cta")["href"])
    assert cta.path == "/world/rating/gdp-usd" and cta.fragment == "chart"
    assert parse_qs(cta.query) == {"view": ["interactive"], "year": ["2024"], "preview_locale": [locale]}
    assert soup.select_one("#site")["href"] == f"/russia/region?year=2020&preview_locale={locale}#chart"
    assert soup.select_one("#fragment")["href"] == "#chart"
    assert soup.select_one("#external")["href"] == "https://rosstat.gov.ru/data?year=2024"
    assert soup.select_one("#mail")["href"] == "mailto:test@example.com"
    assert soup.select_one("picture img")["src"].endswith(f"?preview_locale={locale}")
    assert soup.source["srcset"] == (
        f"/og/world/rating/gdp-usd/2024.png?portrait=1&preview_locale={locale} 1x, "
        f"/og/world/rating/gdp-usd/2024.png?portrait=1&size=2&preview_locale={locale} 2x"
    )
    assert soup.select_one("#external-image")["src"] == "https://example.com/image.png"
    assert soup.select_one("#embedded")["src"] == "data:image/png;base64,abcd"
    assert soup.script.string == '{"url":"https://rosstat.gov.ru/data"}'
    assert _preview_body_urls(result, locale) == result


@pytest.mark.parametrize("locale", ["ru", "en"])
@pytest.mark.parametrize("preview", [False, True])
@pytest.mark.parametrize("include_app", [False, True])
def test_document_preview_urls_are_body_only(locale, preview, include_app, monkeypatch):
    import asyncio
    import json
    from app.config import settings
    from app.services.locale import (
        reset_locale, reset_preview_locale, set_locale, set_preview_locale,
    )
    from app.services.seo_renderer import build_document

    monkeypatch.setattr(settings, "apex_locale_en", True)
    body = '''<a id="cta" href="/world/rating/gdp-usd?view=interactive&amp;year=2024#chart">Chart</a>
        <figure class="seo-chart"><img src="/og/russia/cpi/2025.png" alt="CPI 2025" width="1200" height="630"></figure>'''
    provenance = {"@context": "https://schema.org", "@type": "Dataset", "url": "https://rosstat.gov.ru/data"}
    lt, pt = set_locale(locale), set_preview_locale(preview)
    try:
        html = asyncio.run(build_document(
            title="CPI 2025", description="Actual data", canonical_path="/russia/indicator/cpi/2025",
            body=body, include_app=include_app, json_ld=[provenance],
            og_image="https://forecasteconomy.com/og/russia/cpi/2025.png",
        ))
    finally:
        reset_preview_locale(pt)
        reset_locale(lt)
    soup = BeautifulSoup(html, "html.parser")
    suffix = f"&preview_locale={locale}" if preview else ""
    assert soup.select_one("#cta")["href"] == f"/world/rating/gdp-usd?view=interactive&year=2024{suffix}#chart"
    assert soup.select_one(".seo-chart img")["src"] == "/og/russia/cpi/2025.png" + (f"?preview_locale={locale}" if preview else "")
    assert soup.select_one(".seo-chart source")["srcset"] == f"/og/russia/cpi/2025.png?portrait=1{suffix}"
    assert "preview_locale" not in str(soup.head)
    assert json.loads(soup.select_one('script[type="application/ld+json"]').string) == provenance
    assert soup.select_one('link[rel="canonical"]')["href"].endswith("/russia/indicator/cpi/2025")
    # Preview is noindex and must not advertise an alternate cluster.
    if preview:
        assert not soup.select('link[hreflang]')
    else:
        assert soup.select('link[hreflang]')
    assert soup.select_one('meta[property="og:image"]')["content"] == "https://forecasteconomy.com/og/russia/cpi/2025.png"
    if not preview:
        assert "preview_locale" not in html
    else:
        # Chrome/platform links also keep the preview without introducing hosts.
        internal_links = [a["href"] for a in soup.select("body a[href]") if a["href"].startswith("/")]
        assert internal_links and all(f"preview_locale={locale}" in href for href in internal_links)


def test_region_map_og_uses_requested_year_not_latest(auth_env, monkeypatch):
    import asyncio
    from fastapi.testclient import TestClient
    from app.models import Region, RegionIndicator, RegionDataPoint
    from app.services import og_image

    async def seed():
        async with auth_env["session_maker"]() as db:
            indicator = RegionIndicator(code="chislennost-naseleniya", table_code="1.1",
                section_num=1, section_name="Население", name="Численность населения",
                unit="человек", year_min=2020, year_max=2024, is_listed=True)
            db.add(indicator)
            regions = [Region(slug=f"test-region-{i}",name=f"Регион {i}",kind="region",sort_order=i) for i in range(10)]
            db.add_all(regions)
            await db.flush()
            for i, region in enumerate(regions):
                for year, value in ((2020, 100+i), (2024, 1000+i)):
                    db.add(RegionDataPoint(indicator_id=indicator.id,region_id=region.id,year=year,value=value))
            await db.commit()
    asyncio.run(seed())
    captured, keys = [], []
    monkeypatch.setattr(og_image,"cached_og", lambda key, **_kw:None)
    monkeypatch.setattr(og_image,"store_og", lambda key, png, **_kw:keys.append(key))
    monkeypatch.setattr(og_image,"render_rating_og",lambda **kw:captured.append(kw) or b"png")
    with TestClient(auth_env["app"]) as client:
        page = client.get("/seo/regions/map/chislennost-naseleniya?year=2020")
        assert page.status_code == 200
        assert '/og/russia/region-rating/chislennost-naseleniya.png?year=2020' in page.text
        assert '?year=2020#chart' in page.text
        image = client.get("/api/v1/og-image/region-rating/chislennost-naseleniya.png?year=2020")
        assert image.status_code == 200
        assert captured[0]["year"] == 2020 and captured[0]["rows"][0][1] == 109
        latest = client.get("/api/v1/og-image/region-rating/chislennost-naseleniya.png")
        assert latest.status_code == 200
        assert captured[1]["year"] == 2024 and captured[1]["rows"][0][1] == 1009
        assert keys[0] != keys[1]
        assert client.get("/api/v1/og-image/region-rating/chislennost-naseleniya.png?year=2019").status_code == 404


@pytest.mark.parametrize("groups", [[], [("A",1),("B",2)], [("A",1),("B",2),("C",None)], [("A",1),("B",2),("C",float("nan"))], [("A",-1),("B",2),("C",3)], [("A",0),("B",0),("C",0)]])
def test_composition_rejects_missing_or_invalid_age_groups(groups):
    from app.services.og_image import render_demographics_og
    with pytest.raises(ValueError):
        render_demographics_og(year=2024,groups=groups,unit="people",source_label="Official source")


@pytest.mark.parametrize("portrait,dimensions", [(False,(1200,630)),(True,(1080,1350))])
def test_composition_has_a_phone_companion(portrait,dimensions):
    from app.services.og_image import render_demographics_og
    png=render_demographics_og(year=2024,groups=[("Younger than working age",20),("Working age",60),("Older than working age",20)],unit="people",source_label="Fixture: rendering test",locale="en",portrait=portrait)
    with Image.open(io.BytesIO(png)) as image:
        assert image.size==dimensions
