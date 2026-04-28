"""OG/SEO endpoint coverage.

The same renderer is used by universal SEO pages and by legacy OG endpoints,
so humans, Yandex/Google, and social preview bots can receive the same
route-specific HTML contract.
"""


def _has_meta(html: str, name: str, content_substr: str) -> bool:
    needle = f'<meta name="{name}" content="'
    idx = html.find(needle)
    if idx == -1:
        return False
    end = html.find('"', idx + len(needle))
    return end != -1 and content_substr in html[idx + len(needle) : end]


def test_og_page_home(client, monkeypatch):
    from app.api import sitemap

    async def fake_home(db):
        return (
            '<html><head><title>Forecast Economy — экономические данные</title>'
            '<meta name="description" content="Бесплатная аналитическая платформа">'
            '<link rel="canonical" href="https://forecasteconomy.com">'
            '</head><body><h1>Forecast Economy</h1></body></html>'
        )

    monkeypatch.setattr(sitemap, "render_home_html", fake_home)
    r = client.get("/api/v1/og/page/home")
    assert r.status_code == 200
    body = r.text
    assert "Forecast Economy" in body
    assert "<title>" in body
    assert _has_meta(body, "description", "Бесплатная")
    assert '<link rel="canonical" href="https://forecasteconomy.com"' in body


def test_og_page_about(client):
    r = client.get("/api/v1/og/page/about")
    assert r.status_code == 200
    assert "О проекте" in r.text
    assert '<link rel="canonical" href="https://forecasteconomy.com/about"' in r.text


def test_og_page_privacy_unique_title(client, monkeypatch):
    from app.api import sitemap

    async def fake_home(db):
        return (
            "<html><head><title>Forecast Economy — экономические данные</title>"
            '<meta name="description" content="Бесплатная">'
            '<link rel="canonical" href="https://forecasteconomy.com">'
            "</head><body><h1>Home</h1></body></html>"
        )

    monkeypatch.setattr(sitemap, "render_home_html", fake_home)
    r_home = client.get("/api/v1/og/page/home").text
    r_priv = client.get("/api/v1/og/page/privacy").text
    # Different titles are the whole point of this endpoint.
    assert _extract_title(r_home) != _extract_title(r_priv)


def test_og_page_compare(client):
    r = client.get("/api/v1/og/page/compare")
    assert r.status_code == 200
    assert "Сравн" in r.text


def test_og_page_unknown_404(client):
    r = client.get("/api/v1/og/page/does-not-exist")
    assert r.status_code == 404


def test_og_category_prices(client, monkeypatch):
    from app.api import sitemap

    async def fake_category(slug, db):
        assert slug == "prices"
        return 200, (
            '<html><head><title>Цены и инфляция в России — Forecast Economy</title>'
            '<meta name="description" content="ИПЦ, инфляция, цены">'
            '<link rel="canonical" href="https://forecasteconomy.com/category/prices">'
            '</head><body><h1>Цены</h1></body></html>'
        )

    monkeypatch.setattr(sitemap, "render_category_html", fake_category)
    r = client.get("/api/v1/og/category/prices")
    assert r.status_code == 200
    assert "Цены" in r.text
    assert '<link rel="canonical" href="https://forecasteconomy.com/category/prices"' in r.text


def test_og_category_unknown_404(client, monkeypatch):
    from app.api import sitemap

    async def fake_category(slug, db):
        assert slug == "no-such-slug"
        return 404, "Not found"

    monkeypatch.setattr(sitemap, "render_category_html", fake_category)
    r = client.get("/api/v1/og/category/no-such-slug")
    assert r.status_code == 404


def test_universal_seo_page_home(client, monkeypatch):
    from app.api import seo_pages

    async def fake_home(db):
        return (
            '<html><head><title>Forecast Economy — экономические данные</title>'
            '<meta name="description" content="Бесплатная аналитическая платформа">'
            '<link rel="canonical" href="https://forecasteconomy.com">'
            '<script type="application/ld+json">{"@type":"WebSite"}</script>'
            '</head><body><div id="root"><h1>Forecast Economy</h1>'
            '<a href="/category/prices">Цены</a><a href="/indicator/cpi">ИПЦ</a>'
            '</div></body></html>'
        )

    monkeypatch.setattr(seo_pages, "render_home_html", fake_home)
    r = client.get("/seo/page/home")
    assert r.status_code == 200
    assert "Forecast Economy" in r.text
    assert '<div id="root">' in r.text
    assert "application/ld+json" in r.text


def test_universal_seo_indicator_contract(client, monkeypatch):
    from app.api import seo_pages

    async def fake_indicator(code, db):
        assert code == "cpi"
        return 200, (
            '<html><head><title>ИПЦ — данные, график и прогноз</title>'
            '<meta name="description" content="ИПЦ России: данные Росстата">'
            '<link rel="canonical" href="https://forecasteconomy.com/indicator/cpi">'
            '<script type="application/ld+json">{"@type":"Dataset"}</script>'
            '</head><body><div id="root"><h1>ИПЦ</h1>'
            '<a href="/category/prices">Цены</a><a href="/indicator/cpi-food">Продовольствие</a>'
            '</div></body></html>'
        )

    monkeypatch.setattr(seo_pages, "render_indicator_html", fake_indicator)
    r = client.get("/seo/indicator/cpi")
    assert r.status_code == 200
    assert "ИПЦ" in r.text
    assert "application/ld+json" in r.text


def test_sitemap_static_pages_constant():
    """Static-pages part of the sitemap is a Python constant — covers
    /, /about, /privacy, /calculator, /compare, /demographics — without DB.
    Compare being listed here is the fix for «Сравнение» disappearing
    from sitemap-driven SEO crawls (it has its own page, was never indexed).
    """
    from app.api.sitemap import STATIC_PAGES, CATEGORIES, PAGE_META

    paths = {p for p, _, _ in STATIC_PAGES}
    assert "/" in paths
    assert "/about" in paths
    assert "/privacy" in paths
    assert "/compare" in paths
    assert "/calculator" in paths
    assert "/demographics" in paths

    # Nine categories × 1 indicator-grid page each.
    assert len(CATEGORIES) == 9
    for slug in ("prices", "rates", "labor", "gdp", "finance", "trade", "population", "business", "science"):
        assert slug in CATEGORIES

    # Home page in PAGE_META — needed for nginx bot routing /og-proxy/page/home.
    assert "home" in PAGE_META


def _extract_title(html: str) -> str:
    start = html.find("<title>")
    end = html.find("</title>")
    if start == -1 or end == -1:
        return ""
    return html[start + len("<title>") : end]
