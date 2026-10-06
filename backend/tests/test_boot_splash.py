"""Волна 6 (1.1): фирменная заставка вместо «голого» серверного текста для человека.

Контракт: SSR-тело остаётся в HTML для роботов (скрывает его только класс html.fe-boot, который
ставит скрипт в <head> и не ставит ботам), поверх стоит заставка, а снимает её приложение или
запасной таймер.
"""
import asyncio
import re
from pathlib import Path


def _spa_doc(**kwargs):
    from app.services.seo_renderer import build_document

    return asyncio.run(
        build_document(
            title="Test",
            description="Desc",
            canonical_path="/russia/today/cpi",
            body='<main class="seo-page"><h1>Ключевая ставка</h1><p>Видимый роботу текст</p></main>',
            include_app=True,
            **kwargs,
        )
    )


def test_spa_ssr_has_splash_style_script_and_markup_before_root():
    html = _spa_doc()
    assert 'id="fe-boot-css"' in html
    assert 'class="fe-boot-splash"' in html
    # заставка стоит до #root и скрыта без html.fe-boot
    assert html.index('class="fe-boot-splash"') < html.index('<div id="root">')
    assert ".fe-boot-splash{display:none}" in html
    assert "html.fe-boot #root{visibility:hidden}" in html
    assert "html.fe-js .fe-boot-splash{display:none!important}" in html
    assert "Загружаем…" in html


def test_boot_class_is_set_by_head_script_and_not_by_markup():
    html = _spa_doc()
    head = html.split("</head>", 1)[0]
    assert 'classList.add("fe-boot")' in head
    # класс не вшит в разметку: без JS и у роботов серверный текст виден
    assert re.search(r'<html[^>]*class="[^"]*fe-boot', html) is None
    # роботы, предпросмотры и /embed/ заставку не получают
    assert "/bot|crawl|spider|slurp|facebookexternalhit|lighthouse|headless/i" in head
    assert 'location.pathname.indexOf("/embed/")===0' in head
    assert "navigator.webdriver" in head
    # запасной таймер: если приложение не загрузилось, человек видит обычный текст, а не вечную заставку
    from app.services.seo_renderer import BOOT_FALLBACK_MS

    assert f"setTimeout(function(){{h.classList.remove(\"fe-boot\")}},{BOOT_FALLBACK_MS})" in head
    assert 8000 <= BOOT_FALLBACK_MS <= 20000


def test_reveal_script_lifts_the_splash():
    html = _spa_doc()
    assert 'classList.remove("fe-boot")' in html
    assert 'classList.add("fe-js")' in html


def test_server_text_stays_in_html_for_robots():
    html = _spa_doc()
    root = html.split('<div id="root">', 1)[1]
    assert "Видимый роботу текст" in root
    assert "Ключевая ставка" in root


def test_splash_english_caption():
    from app.services.locale import reset_locale, set_locale

    token = set_locale("en")
    try:
        html = _spa_doc()
    finally:
        reset_locale(token)
    assert "Loading…" in html
    assert "Загружаем…" not in html.split('class="fe-boot-splash"', 1)[1].split("</div>", 1)[0]


def test_pure_ssr_pages_have_no_splash():
    from app.services.seo_renderer import build_document

    pure = asyncio.run(
        build_document(
            title="Год",
            description="Тест",
            canonical_path="/russia/indicator/cpi/2024",
            body='<main class="seo-page"><h1>2024</h1></main>',
            include_app=False,
        )
    )
    assert "fe-boot" not in pure


def test_html_background_and_light_scheme_prevent_black_flash():
    from app.services.seo_renderer import SEO_CRITICAL_CSS, render_not_found_html

    assert "html{background:#EEF0F4;color-scheme:light}" in SEO_CRITICAL_CSS
    assert '<meta name="color-scheme" content="light">' in render_not_found_html()


def test_first_frame_is_paper_with_the_logo_not_a_white_or_grey_screen():
    """БД8: фон бумаги на самом html и в заставке, крупный логотип; чистые SSR-страницы не затронуты."""
    html = _spa_doc()
    css = html.split('<style id="fe-boot-css">', 1)[1].split("</style>", 1)[0]
    assert "html{background:#F4F5F7}" in css
    assert "html.fe-boot{overflow:hidden;background:#F4F5F7}" in css
    splash_rule = [line for line in css.splitlines() if line.startswith("html.fe-boot .fe-boot-splash{")][0]
    assert splash_rule.rstrip("}").endswith("#F4F5F7;color:#202A3C;font-family:Manrope,system-ui,sans-serif")
    assert "#EEF0F4" not in splash_rule
    # Логотип с золотым квадратом внутри заставки и крупнее прежнего.
    splash = html.split('<div class="fe-boot-splash"', 1)[1].split("</div>", 1)[0]
    assert 'fill="#AD8A48"' in splash and "forecast<i>economy</i>" in splash
    assert ".fe-boot-brand svg{width:46px;height:52px}" in css


def test_shell_index_html_mirrors_the_splash_contract():
    """frontend/index.html (оболочка /login, /register, /account) держит тот же блок заставки."""
    from app.services.seo_renderer import BOOT_FALLBACK_MS

    shell = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    html = shell.read_text(encoding="utf-8")
    assert 'id="fe-boot-css"' in html
    assert 'class="fe-boot-splash"' in html
    assert html.index('class="fe-boot-splash"') < html.index('<div id="root">')
    assert 'html.fe-boot #root{visibility:hidden}' in html
    assert 'html.fe-js .fe-boot-splash{display:none!important}' in html
    assert f"setTimeout(function(){{h.classList.remove(\"fe-boot\")}},{BOOT_FALLBACK_MS})" in html
    assert "/bot|crawl|spider|slurp|facebookexternalhit|lighthouse|headless/i" in html


def test_prenonblocking_shell_css_is_not_duplicated_and_gets_a_noscript_fallback():
    from app.services.seo_renderer import _nonblocking_stylesheets

    ready = (
        '<link rel="stylesheet" crossorigin href="/assets/main-x.css" '
        'media="print" data-fe-css="1" onload="this.media=\'all\'">'
    )
    out = _nonblocking_stylesheets(ready)
    assert out.count('media="print"') == 1
    assert out.count("onload=") == 1
    assert '<noscript><link rel="stylesheet" href="/assets/main-x.css"></noscript>' in out

    plain = _nonblocking_stylesheets('<link rel="stylesheet" href="/assets/main-y.css">')
    assert 'media="print" data-fe-css="1"' in plain
    assert '<noscript><link rel="stylesheet" href="/assets/main-y.css"></noscript>' in plain
