"""OG/SEO endpoint coverage.

These endpoints are served to bots via nginx user-agent routing
(Yandex/Google/etc. + Telegram/FB) so each route gets a unique
<title> and <meta name="description">. This kills the
«дубли title/description» warnings in Yandex Webmaster without
running a full SSR/prerender pipeline.
"""


def _has_meta(html: str, name: str, content_substr: str) -> bool:
    needle = f'<meta name="{name}" content="'
    idx = html.find(needle)
    if idx == -1:
        return False
    end = html.find('"', idx + len(needle))
    return end != -1 and content_substr in html[idx + len(needle) : end]


def test_og_page_home(client):
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


def test_og_page_privacy_unique_title(client):
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


def test_og_category_prices(client):
    r = client.get("/api/v1/og/category/prices")
    assert r.status_code == 200
    assert "Цены" in r.text
    assert '<link rel="canonical" href="https://forecasteconomy.com/category/prices"' in r.text


def test_og_category_unknown_404(client):
    r = client.get("/api/v1/og/category/no-such-slug")
    assert r.status_code == 404


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
