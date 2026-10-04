"""Фирменная 404 через /seo/not-found (nginx catch-all) и 404 рендереров."""

import re


def test_seo_not_found_branded(client):
    r = client.get("/seo/not-found")
    assert r.status_code == 404
    html = r.text
    assert "<h1>Такой страницы нет</h1>" in html
    assert "Страна не найдена" not in html
    assert "Страница не найдена" not in html
    assert 'href="/#countries"' in html
    assert 'href="/compare"' in html
    assert 'href="/russia/today"' in html
    assert "seo-topbar" in html or "Forecast" in html
    assert "noindex" in html
    assert "links-exchange" not in html
    assert "seo-honeylink" not in html
    assert r.headers.get("x-robots-tag") == "noindex, follow"


def test_seo_not_found_has_search_and_popular_tiles(client):
    """Не тупик: поле поиска (GET на главную с q) и 4–6 плиток разделов."""
    html = client.get("/seo/not-found").text
    form = re.search(r'<form class="seo-search"[^>]*>(.*?)</form>', html, re.S)
    assert form, "нет формы поиска"
    assert 'action="/"' in html and 'method="get"' in html
    assert 'name="q"' in form.group(1)
    assert 'type="submit"' in form.group(1)
    grid = re.search(r'<ul class="seo-404-grid">(.*?)</ul>', html, re.S)
    assert grid
    tiles = re.findall(r"<li><a href=", grid.group(1))
    assert 4 <= len(tiles) <= 6
    # Дружелюбный текст без маркированного списка из 14 ссылок и без «откройте
    # главную и воспользуйтесь поиском в шапке».
    assert "воспользуйтесь поиском в шапке" not in html
    assert "Разделы каталога" not in html


def test_seo_not_found_uses_app_glass_chrome(client):
    """Та же стеклянная шапка, что у годовых страниц: меню сворачивается."""
    html = client.get("/seo/not-found").text
    assert '<header class="seo-topbar">' in html
    assert 'class="seo-menu-check"' in html
    assert 'class="seo-menu-btn"' in html
    assert "seo-foot-in" in html
    assert "Manrope" in html


def test_seo_not_found_opts_out_of_ads(client):
    """404 грузит тот же SSR-хром, что и быстрые ссылки, но без рекламы РСЯ."""
    html = client.get("/seo/not-found").text
    assert '<body class="seo-fast" data-no-ads>' in html
    assert "/assets/behavior-standalone.js" in html


def test_renderer_404_markers_share_one_branded_page():
    """«Страна не найдена»/«Not found» из рендереров → один заголовок (N46)."""
    from app.api.seo_pages import _html_response

    pages = [
        _html_response(404, "<h1>Страна не найдена</h1>"),
        _html_response(404, "Not found"),
        _html_response(404, "Страница не найдена"),
    ]
    bodies = [bytes(p.body).decode() for p in pages]
    for page, html in zip(pages, bodies):
        assert page.status_code == 404
        assert page.headers["x-robots-tag"] == "noindex, follow"
        assert "<h1>Такой страницы нет</h1>" in html
        assert "Страна не найдена" not in html
    assert bodies[0] == bodies[1] == bodies[2]


def test_not_found_english_has_no_russian_copy():
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_renderer import render_not_found_html

    token = set_locale("en")
    try:
        html = render_not_found_html()
    finally:
        reset_locale(token)
    assert "<h1>This page does not exist</h1>" in html
    assert 'placeholder="Inflation, GDP, interest rate…"' in html
    assert not re.search(r"<h1>[^<]*[А-Яа-я]", html)
    assert "Такой страницы нет" not in html


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
