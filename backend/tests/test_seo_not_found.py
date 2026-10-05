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


def test_seo_not_found_has_search_and_popular_chips(client):
    """Не тупик: поле поиска (GET на главную с q), чипы популярных разделов и «Вернуться назад»."""
    html = client.get("/seo/not-found").text
    form = re.search(r'<form class="seo-search"[^>]*>(.*?)</form>', html, re.S)
    assert form, "нет формы поиска"
    assert 'action="/"' in html and 'method="get"' in html
    assert 'name="q"' in form.group(1)
    assert 'type="submit"' in form.group(1)
    chips = re.search(r'<ul class="seo-404-chips">(.*?)</ul>', html, re.S)
    assert chips
    links = re.findall(r"<li><a href=", chips.group(1))
    assert 6 <= len(links) <= 10
    # Валюты и калькуляторы раньше пропадали: теперь они в чипах, как и в основном меню.
    assert 'href="/currencies"' in chips.group(1)
    assert 'href="/calculator"' in chips.group(1)
    assert 'id="seo-404-back"' in html and "Вернуться назад" in html
    # Вместо огромной цифры 404 — маленькая планета; цифра остаётся только словами в подписи.
    assert "seo-404-code" not in html
    assert 'class="seo-404-planet"' in html
    # Дружелюбный текст без маркированного списка из 14 ссылок и без «откройте
    # главную и воспользуйтесь поиском в шапке».
    assert "воспользуйтесь поиском в шапке" not in html
    assert "Разделы каталога" not in html


def test_seo_not_found_shares_header_ticker_and_footer_with_the_app(client):
    """Одна шапка на всех страницах: язык RU/EN, бегущая строка, «Валюты», вход и регистрация, общий подвал."""
    html = client.get("/seo/not-found").text
    assert 'id="seo-ticker"' in html and "/seo-ticker.js" in html
    assert 'class="seo-lang-seg"' in html
    # Язык как в приложении: кружок с кодом и стрелка, список по нажатию (без флага).
    assert 'class="seo-lang-code"' in html and "Русский" in html and "English" in html
    assert ">Валюты<" in html and ">Калькуляторы<" in html
    assert 'href="/login"' in html and 'href="/register"' in html
    # Подзаголовок бренда тёмный, как в приложении (раньше был золотым).
    assert "small{display:block;font-size:7px;font-weight:600;letter-spacing:.16em;color:inherit" in html
    # Подвал со столбцами, как в приложении.
    assert 'class="seo-foot-col"' in html
    assert ">Инструменты<" in html and ">Информация<" in html


def test_seo_not_found_suggests_a_section_from_the_address():
    """«Возможно, вы искали»: по словам из адреса предлагается раздел сайта (рейтинг, калькуляторы)."""
    from app.services.seo_renderer import _not_found_guesses, render_not_found_html

    ru = _not_found_guesses("/ranking/gdp", False)
    assert ru and ru[0][0] == "/world/rating/gdp-usd"
    assert ru[0][1] == "Рейтинг стран по ВВП"
    assert _not_found_guesses("/calculators", False)[0][0] == "/calculator"
    assert _not_found_guesses("/zzz", False) == []
    html = render_not_found_html(path="/ranking/gdp")
    assert "Возможно, вы искали" in html
    assert 'href="/world/rating/gdp-usd"' in html
    assert "Возможно, вы искали" not in render_not_found_html(path="/zzz")


def test_seo_not_found_uses_app_glass_chrome(client):
    """Та же стеклянная шапка, что у годовых страниц: меню сворачивается."""
    html = client.get("/seo/not-found").text
    assert '<header class="seo-topbar">' in html
    assert 'class="seo-menu-check"' in html
    assert 'class="seo-menu-btn"' in html
    assert "seo-foot-in" in html
    assert "Manrope" in html
    # Поиск доступен и из шапки (якорь к полю), поле имеет якорь и короткую подсказку, которая не режется.
    assert 'class="seo-search-btn" href="#seo-404-q"' in html
    assert 'id="seo-404-q"' in html
    assert 'placeholder="Инфляция, ВВП, ставка…"' in html


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
    assert 'placeholder="Inflation, GDP, rates…"' in html
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


def test_breadcrumbs_have_separator_and_current_markers():
    """Крошки чистых SSR-страниц: разделитель и текущая страница в своих тегах (CSS рисует «›» и обрезает)."""
    from app.services.seo_renderer import _breadcrumbs_nav

    html = _breadcrumbs_nav([("/", "Главная"), ("/russia", "Россия"), ("/russia/x", "Показатель 2024")])
    assert html.count('class="seo-crumb-sep"') == 2
    assert '<span class="seo-crumb-cur" aria-current="page">Показатель 2024</span>' in html


def test_not_found_english_matches_the_app_header_and_suggests_in_english():
    """404 на английском с первого кадра: США в меню, «Sign in», переключатель, подсказка и «Go back»."""
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_renderer import render_not_found_html

    token = set_locale("en")
    try:
        html = render_not_found_html(path="/rankings")
    finally:
        reset_locale(token)
    assert ">United States<" in html and ">Currencies<" in html
    assert ">Sign in<" in html and ">Sign up<" in html
    assert 'class="seo-lang-seg"' in html and "Maybe you were looking for" in html
    assert 'href="/world/rating/gdp-usd">Country ranking by GDP<' in html
    assert ">Go back<" in html
    assert not re.search(r"<h1>[^<]*[А-Яа-я]", html)
    assert ">Войти<" not in html and "Вернуться" not in html


def _with_app_shell(monkeypatch):
    from app.services import seo_renderer

    monkeypatch.setattr(
        seo_renderer,
        "_APP_ASSETS",
        seo_renderer.AppAssets(
            head_links='<link rel="stylesheet" href="/assets/main-x.css">',
            body_scripts='<script type="module" src="/assets/main-x.js"></script>',
        ),
    )


def test_not_found_is_the_app_document_when_the_shell_is_available(monkeypatch):
    """БД3: 404 в общей оболочке: тот же документ приложения, флаг для NotFound.jsx, без канона и языковых пар."""
    from app.services.seo_renderer import render_not_found_html

    _with_app_shell(monkeypatch)
    html = render_not_found_html(path="/zzz-nothing")
    assert "<script>window.__feNotFound=true</script>" in html
    assert '<meta name="robots" content="noindex, follow">' in html
    assert 'rel="canonical"' not in html and 'hreflang' not in html
    assert "/assets/main-x.js" in html and "/assets/main-x.css" in html
    # Текст для роботов и посетителей без JavaScript лежит в #root, а шапку и подвал рисует приложение.
    root = html.split('<div id="root">', 1)[1]
    assert "<h1>Такой страницы нет</h1>" in root
    assert 'class="seo-topbar"' not in html and 'class="seo-foot-in"' not in html
    # Бумажная заставка на первом кадре: человек не видит белого экрана.
    assert 'class="fe-boot-splash"' in html


def test_not_found_route_keeps_status_and_noindex_in_the_app_shell(client, monkeypatch):
    from app.services import seo_renderer

    async def warm():
        _with_app_shell(monkeypatch)
        return seo_renderer._APP_ASSETS

    monkeypatch.setattr(seo_renderer, "get_app_assets", warm)
    r = client.get("/seo/not-found", headers={"x-original-uri": "/nothing/here"})
    assert r.status_code == 404
    assert r.headers.get("x-robots-tag") == "noindex, follow"
    assert "window.__feNotFound=true" in r.text


def test_not_found_without_the_shell_stays_a_self_contained_page(monkeypatch):
    """Минуты выкладки: приложения нет, страница всё равно целая (шапка, лента, подвал, поиск)."""
    from app.services import seo_renderer

    monkeypatch.setattr(seo_renderer, "_APP_ASSETS", None)
    html = seo_renderer.render_not_found_html(path="/zzz")
    assert "__feNotFound" not in html
    assert 'class="seo-topbar"' in html and 'class="seo-foot-in"' in html
    assert 'id="seo-404-q"' in html
