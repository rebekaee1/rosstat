"""Брендовая 404 через /seo/not-found (nginx catch-all)."""


def test_seo_not_found_branded(client):
    r = client.get("/seo/not-found")
    assert r.status_code == 404
    html = r.text
    assert "Страница не найдена" in html
    assert 'href="/#countries"' in html
    assert 'href="/compare"' in html
    assert 'href="/russia/today"' in html
    assert "seo-topbar" in html or "Forecast" in html
    assert "noindex" in html
    assert "links-exchange" not in html
    assert "seo-honeylink" not in html
    assert r.headers.get("x-robots-tag") == "noindex, follow"


def test_seo_not_found_opts_out_of_ads(client):
    """404 грузит тот же SSR-хром, что и быстрые ссылки, но без рекламы РСЯ."""
    html = client.get("/seo/not-found").text
    assert '<body class="seo-fast" data-no-ads>' in html
    assert "/assets/behavior-standalone.js" in html


def test_quicklink_page_keeps_ads(client):
    """Быстрая ссылка (include_app=False) не помечена data-no-ads."""
    import asyncio

    from app.services.seo_renderer import build_document

    html = asyncio.run(build_document(
        title="ИПЦ в 2024 году", description="Тест",
        canonical_path="/russia/indicator/cpi/2024",
        body='<main class="seo-page"><h1>ИПЦ в 2024 году</h1></main>',
        include_app=False,
    ))
    assert "/assets/behavior-standalone.js" in html
    assert "data-no-ads" not in html
