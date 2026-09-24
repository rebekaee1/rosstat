"""Discovery uses real OG route families, the same host, and the selected year."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from app.api.sitemap import _render_urlset
from app.services.sitemap_images import image_path_for_page
from app.services.site_urls import SiteUrl, REGIONAL_CHUNK

SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
IMAGE = "{http://www.google.com/schemas/sitemap-image/1.1}"


@pytest.mark.parametrize("page,image", [
    ("/russia/indicator/cpi", "/og/russia/cpi.png"),
    ("/russia/indicator/cpi/2025", "/og/russia/cpi/2025.png"),
    ("/russia/indicator/cpi/2025-07", "/og/russia/cpi/2025-07.png"),
    ("/russia/indicator/population/1897", "/og/russia/population/1897.png"),
    ("/russia/region/tulskaya-oblast/wages", "/og/russia/region/tulskaya-oblast/wages.png"),
    ("/russia/region/tulskaya-oblast/wages/2024", "/og/russia/region/tulskaya-oblast/wages/2024.png"),
    ("/russia/region-rating/wages", "/og/russia/region-rating/wages.png"),
    ("/russia/region/map/wages", "/og/russia/region-rating/wages.png"),
    ("/russia/region/map/wages?year=2020", "/og/russia/region-rating/wages.png?year=2020"),
    ("/russia/region-vs/moskva-vs-tulskaya-oblast", "/og/russia/region-vs/moskva-vs-tulskaya-oblast.png"),
    ("/germany", "/og/world/germany.png"),
    ("/germany/indicator/gdp-usd", "/og/germany/gdp-usd.png"),
    ("/germany/indicator/namq_10_gdp.ab-c/2024", "/og/germany/namq_10_gdp.ab-c/2024.png"),
    ("/world/rating/gdp-usd", "/og/world/rating/gdp-usd.png"),
    ("/world/rating/gdp-usd/2024", "/og/world/rating/gdp-usd/2024.png"),
    ("/france-vs-germany/gdp-usd", "/og/world-vs/france-vs-germany/gdp-usd.png"),
    ("/united-states/regions", "/og/world/united-states/regions.png"),
    ("/united-states/region/california", "/og/world/united-states/region/california.png"),
    ("/united-states/region/california/unemployment-rate", "/og/world/united-states/region/california/unemployment-rate.png"),
    ("/russia/demographics", "/og/russia/demographics.png"),
    ("/russia/today", "/og/russia/today.png"),
    ("/russia/today/cpi", "/og/russia/cpi.png"),
])
def test_known_data_family_image_paths(page, image):
    assert image_path_for_page(page) == image


@pytest.mark.parametrize("page", [
    "/", "/russia", "/about", "/unknown", "/calendar", "/russia/calendar/2025/12",
    "/russia/region/map/overview", "/russia/region/moskva", "/russia/category/prices",
    "/germany/category/prices", "/germany/region/map/gdp", "/world/rating/unknown",
    "/world/rating/gdp-usd/2024?year=2020", "/fake-vs-germany/gdp-usd",
    "/germany-vs-germany/gdp-usd", "/germany/indicator/cpi/2025-07",
    "/russia/indicator/cpi/0000", "/russia/indicator/cpi/9999", "/russia/indicator/cpi/2025-13",
    "/russia/region/map/wages?year=2020&year=2024", "/russia/indicator/cpi?mode=yoy",
    "https://foreign.example/russia/indicator/cpi", "//foreign.example/russia/indicator/cpi",
    "/russia/indicator/<cpi>", "/russia/indicator/cpi#chart", "/russia/indicator/cpi/2025/extra",
])
def test_unknown_static_and_unsupported_modes_have_no_image(page):
    assert image_path_for_page(page) is None


@pytest.mark.parametrize("origin", ["https://forecasteconomy.com", "https://ru.forecasteconomy.com"])
def test_dynamic_xml_image_namespace_and_host_are_exact(origin):
    pages = [SiteUrl("/russia/indicator/cpi/2025", "2025-12-01", "monthly", "0.8"),
             SiteUrl("/about", "2026-01-01", "yearly", "0.5")]
    root = ET.fromstring(_render_urlset(pages, origin=origin))
    assert len(root.findall(f"{SM}url")) == len(pages)
    first, second = root.findall(f"{SM}url")
    assert first.findtext(f"{SM}loc") == origin + pages[0].path
    assert first.findtext(f"{IMAGE}image/{IMAGE}loc") == origin + "/og/russia/cpi/2025.png"
    assert second.find(f"{IMAGE}image") is None
    assert first.findtext(f"{SM}lastmod") == "2025-12-01"


def test_xml_escaping_remains_well_formed_for_query_strings():
    path = "/about?reference=1&label=<data>"
    xml = _render_urlset([SiteUrl(path,"2026-01-01","monthly","0.5")])
    assert "&amp;label=&lt;data&gt;" in xml
    assert ET.fromstring(xml).findtext(f"{SM}url/{SM}loc").endswith(path)


def test_image_extension_preserves_chunk_url_count_and_protocol_size():
    rows = [SiteUrl(f"/russia/region/test-region-{i}/chislennost-naseleniya/2024", "2024-12-31", "yearly", "0.4") for i in range(REGIONAL_CHUNK)]
    xml = _render_urlset(rows, origin="https://ru.forecasteconomy.com")
    root = ET.fromstring(xml)
    assert len(root.findall(f"{SM}url")) == REGIONAL_CHUNK
    assert len(root.findall(f"{SM}url/{IMAGE}image")) == REGIONAL_CHUNK
    assert len(xml.encode()) < 50 * 1024 * 1024
