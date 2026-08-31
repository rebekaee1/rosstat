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


def test_og_page_methodology(client):
    r = client.get("/api/v1/og/page/methodology")
    assert r.status_code == 200
    body = r.text
    assert "Методология прогнозирования" in body
    assert '<link rel="canonical" href="https://forecasteconomy.com/methodology"' in body
    # Публичный язык: без кодовых идентификаторов стратегий/парсеров.
    for leak in ("monthly_auto", "generic_quarterly", "derived_from_source", "seed_data", "_parser"):
        assert leak not in body


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
            '<link rel="canonical" href="https://forecasteconomy.com/russia/category/prices">'
            '</head><body><h1>Цены</h1></body></html>'
        )

    monkeypatch.setattr(sitemap, "render_category_html", fake_category)
    r = client.get("/api/v1/og/category/prices")
    assert r.status_code == 200
    assert "Цены" in r.text
    assert '<link rel="canonical" href="https://forecasteconomy.com/russia/category/prices"' in r.text


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
            '<a href="/russia/category/prices">Цены</a><a href="/russia/indicator/cpi">ИПЦ</a>'
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

    async def fake_indicator(code, db, *, mode=None):
        assert code == "cpi"
        assert mode is None
        return 200, (
            '<html><head><title>ИПЦ — данные, график и прогноз</title>'
            '<meta name="description" content="ИПЦ России: данные Росстата">'
            '<link rel="canonical" href="https://forecasteconomy.com/russia/indicator/cpi">'
            '<script type="application/ld+json">{"@type":"Dataset"}</script>'
            '</head><body><div id="root"><h1>ИПЦ</h1>'
            '<a href="/russia/category/prices">Цены</a><a href="/russia/indicator/cpi-food">Продовольствие</a>'
            '</div></body></html>'
        )

    monkeypatch.setattr(seo_pages, "render_indicator_html", fake_indicator)
    r = client.get("/seo/indicator/cpi")
    assert r.status_code == 200
    assert "ИПЦ" in r.text
    assert "application/ld+json" in r.text


def test_universal_seo_indicator_forwards_mode_query(client, monkeypatch):
    from app.api import seo_pages

    async def fake_indicator(code, db, *, mode=None):
        assert code == "budget-revenue"
        assert mode == "sum-quarter"
        return 200, "<html><body><div id='root'>ok</div></body></html>"

    monkeypatch.setattr(seo_pages, "render_indicator_html", fake_indicator)
    r = client.get("/seo/indicator/budget-revenue", params={"mode": "sum-quarter"})
    assert r.status_code == 200
    assert "ok" in r.text


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
    assert "/calculator/mortgage" in paths
    assert "/calculator/compound" in paths
    assert "/russia/demographics" in paths
    assert "/russia/calendar" in paths
    assert "/methodology" in paths

    # Twelve categories × 1 indicator-grid page each (D5: split «Финансы и
    # валюты» → «Валюты» + «Деньги и бюджет»; +«Индексы» (MOEX); +«Товарные
    # рынки» (сырьё, нефть/золото перенесены из «Финансы»)).
    assert len(CATEGORIES) == 12
    for slug in (
        "prices", "rates", "labor", "gdp", "finance",
        "trade", "population", "business", "science", "currencies",
        "indices", "commodities",
    ):
        assert slug in CATEGORIES

    # Home page in PAGE_META — needed for nginx bot routing /og-proxy/page/home.
    assert "home" in PAGE_META


def test_meta_keywords_are_unique_per_page():
    """Pre-Wednesday-2026 issue: <meta name="keywords"> was hardcoded в
    seo_renderer и был одинаков для главной/категорий/индикаторов. После
    этого теста любые две произвольно выбранные страницы должны иметь
    различающиеся keywords (или хотя бы кастомные, отличные от дефолта).
    """
    from app.services.seo_content import PAGE_META, CATEGORY_META
    from app.services.seo_renderer import DEFAULT_KEYWORDS

    home_kw = PAGE_META["home"].keywords
    about_kw = PAGE_META["about"].keywords
    privacy_kw = PAGE_META["privacy"].keywords
    prices_kw = CATEGORY_META["prices"].keywords
    gdp_kw = CATEGORY_META["gdp"].keywords

    assert home_kw and home_kw != DEFAULT_KEYWORDS, "home must have its own keywords"
    assert about_kw and about_kw != home_kw
    assert privacy_kw and privacy_kw != home_kw
    assert prices_kw and prices_kw != home_kw
    assert gdp_kw and gdp_kw != prices_kw, "categories must differ from each other"


def test_indicator_keywords_default_generator_works():
    """Если у индикатора нет ручного override в INDICATOR_SEO_KEYWORDS, он
    должен получать keywords-строку через default_keywords(name, category, source).
    Никакой индикатор не должен ехать в прод с пустыми keywords.
    """
    from app.data.indicator_seo import default_keywords, INDICATOR_SEO_KEYWORDS

    kw = default_keywords("Индекс промышленного производства", "Бизнес", "Росстат")
    assert "Индекс промышленного производства" in kw
    assert "Россия" in kw
    assert "прогноз" in kw
    assert "Росстат" in kw

    cbr_kw = default_keywords("Курс доллара", "Финансы", "Банк России")
    assert "Банк России" in cbr_kw
    assert "Росстат" not in cbr_kw

    assert "cpi" in INDICATOR_SEO_KEYWORDS
    assert "key-rate" in INDICATOR_SEO_KEYWORDS
    assert len(INDICATOR_SEO_KEYWORDS) >= 30


def test_faq_json_ld_from_seo_blocks():
    """seo_blocks индикатора превращаются в FAQPage structured data: каждый
    блок — Question + acceptedAnswer. Это делает Q&A-секцию «О показателе»
    индексируемой как rich result, а не просто текстом."""
    from app.services.seo_renderer import _faq_json_ld, SeoBlock

    blocks = (
        SeoBlock(title="Что такое показатель", body="Развёрнутое описание показателя."),
        SeoBlock(title="Как читать график", body="Развёрнутое описание режимов."),
    )
    faq = _faq_json_ld(blocks)
    assert faq is not None
    assert faq["@type"] == "FAQPage"
    assert len(faq["mainEntity"]) == 2
    first = faq["mainEntity"][0]
    assert first["@type"] == "Question"
    assert first["name"] == "Что такое показатель"
    assert first["acceptedAnswer"]["@type"] == "Answer"
    assert first["acceptedAnswer"]["text"] == "Развёрнутое описание показателя."

    # Меньше двух валидных блоков — FAQPage не строим (single Q бессмысленен).
    assert _faq_json_ld((SeoBlock(title="X", body="Y"),)) is None
    assert _faq_json_ld(()) is None


def test_seo_critical_css_in_build_document():
    import asyncio

    from app.services.seo_renderer import SEO_CRITICAL_CSS, build_document

    html = asyncio.run(
        build_document(
            title="Test",
            description="Desc",
            canonical_path="/",
            body='<main class="seo-page"><h1>Test</h1></main>',
        )
    )
    assert SEO_CRITICAL_CSS in html
    assert 'id="seo-critical"' in html
    assert ".seo-page" in html
    assert 'name="yandex-verification" content="02b4966d46881470"' in html
    assert 'name="yandex-verification" content="5e35c47bf83e75a9"' in html


def test_sort_head_links_stylesheets_first():
    from app.services.seo_renderer import _sort_head_links

    links = [
        '<link href="/assets/index.css" rel="stylesheet"/>',
        '<link href="/assets/app.js" rel="modulepreload"/>',
        '<link href="/favicon.ico" rel="icon"/>',
    ]
    sorted_links = _sort_head_links(links)
    assert "stylesheet" in sorted_links[0]
    assert "modulepreload" in sorted_links[-1]


def test_category_rich_list_includes_descriptions():
    from app.services.seo_content import CATEGORY_META
    from app.services.seo_renderer import _category_rich_list

    html = _category_rich_list(CATEGORY_META)
    assert 'href="/russia/category/prices"' in html
    assert "seo-cat-desc" in html
    assert "ИПЦ" in html


def test_sitemap_priority_listed_vs_unlisted():
    from app.api.sitemap import _sitemap_priority

    assert _sitemap_priority(listed=True, is_indicator=True) == "0.8"
    assert _sitemap_priority(listed=False, is_indicator=True) == "0.5"


def test_sort_indicators_for_seo_puts_flagship_first():
    from app.services.seo_content import CATEGORY_META
    from app.services.seo_renderer import _sort_indicators_for_seo

    class _Fake:
        def __init__(self, code: str, name: str):
            self.code = code
            self.name = name

    indicators = [
        _Fake("auto-loan-rate", "Автокредиты"),
        _Fake("key-rate", "Ключевая ставка"),
        _Fake("ruonia", "RUONIA"),
    ]
    ordered = _sort_indicators_for_seo(indicators, CATEGORY_META["rates"])
    assert ordered[0].code == "key-rate"


def test_enrich_description_adds_latest_value():
    from datetime import date
    from types import SimpleNamespace

    from app.services.seo_renderer import _enrich_description

    current = SimpleNamespace(value=13.96, date=date(2026, 6, 10))
    out = _enrich_description("RUONIA: ставка овернайт.", current, "%", code="ruonia")
    # Русская типографика: запятая в дроби, дата словами (В-22)
    assert "13,96" in out
    assert "10 июня 2026" in out
    assert out.startswith("Актуальное значение")


def test_enrich_description_en_latest_value_quarter():
    from datetime import date
    from types import SimpleNamespace

    from app.services.locale import reset_locale, set_locale
    from app.services.seo_renderer import _enrich_description

    current = SimpleNamespace(value=5.32, date=date(2025, 6, 1))
    token = set_locale("en")
    try:
        out = _enrich_description(
            "GDP growth.",
            current,
            "%",
            code="gdp-yoy",
            frequency="quarterly",
        )
    finally:
        reset_locale(token)
    assert out.startswith("Latest value")
    assert "in Q2 2025" in out
    assert "Актуальное" not in out
    assert "квартал" not in out
    assert "5.32" in out
    assert ",5" not in out and "5,32" not in out


def test_enrich_description_en_gdp_nominal_no_ru_decimal():
    from datetime import date
    from types import SimpleNamespace

    from app.services.locale import reset_locale, set_locale
    from app.services.seo_renderer import _enrich_description

    current = SimpleNamespace(value=49869.5, date=date(2026, 3, 1))
    token = set_locale("en")
    try:
        out = _enrich_description(
            "Nominal GDP.",
            current,
            "млрд руб.",
            code="gdp-nominal",
            frequency="quarterly",
        )
    finally:
        reset_locale(token)
    assert "49,869.5 bln RUB" in out
    assert "in Q1 2026" in out
    assert ",5" not in out
    assert "\u202f" not in out
    assert "млрд" not in out


def test_value_period_phrase_en_quarter():
    from datetime import date

    from app.services.display import value_period_phrase

    assert value_period_phrase(date(2025, 3, 1), "quarterly", locale="en") == "in Q1 2025"
    assert value_period_phrase(date(2025, 3, 1), "quarterly", locale="ru") == "за 1 квартал 2025"


def test_enrich_description_cpi_shows_change_not_raw_index():
    """Инцидент «инфляция 100,2%»: CPI-индекс в meta — изменение цен, не сырой индекс."""
    from datetime import date
    from types import SimpleNamespace

    from app.services.seo_renderer import _enrich_description

    current = SimpleNamespace(value=100.17, date=date(2026, 5, 1))
    out = _enrich_description("ИПЦ России.", current, "%", code="cpi", frequency="monthly")
    assert "+0,17 % за месяц" in out
    assert "100,17" not in out and "100.17" not in out


def test_forecast_ssr_desc_tail_no_duplicate():
    """V2: хвост не дублируется, если «прогноз» уже в description."""
    from app.data.indicator_seo import (
        FORECAST_SSR_DESC_TAIL,
        append_forecast_ssr_desc_tail,
    )

    with_forecast = "ИПЦ России: прогноз на 12 месяцев."
    assert append_forecast_ssr_desc_tail(with_forecast) == with_forecast
    bare = "Уровень безработицы: помесячный ряд Росстата."
    out = append_forecast_ssr_desc_tail(bare)
    assert FORECAST_SSR_DESC_TAIL in out
    assert out.count("прогноз") == 1


def test_forecast_ssr_pilot_gate_requires_forecast_steps():
    """V2/V4/V5 только для whitelist ∩ forecast_steps>0 (key-rate без прогноза — off)."""
    from types import SimpleNamespace

    from app.data.indicator_seo import FORECAST_SSR_PILOT_CODES
    from app.services.seo_renderer import _forecast_ssr_enabled

    assert FORECAST_SSR_PILOT_CODES == frozenset({
        "cpi", "key-rate", "gdp-real", "unemployment", "wages-nominal",
    })
    cpi = SimpleNamespace(code="cpi", model_config_json={"forecast_steps": 12})
    key = SimpleNamespace(code="key-rate", model_config_json={"forecast_steps": 0})
    other = SimpleNamespace(code="m2", model_config_json={"forecast_steps": 12})
    assert _forecast_ssr_enabled(cpi) is True
    assert _forecast_ssr_enabled(key) is False
    assert _forecast_ssr_enabled(other) is False


def test_forecast_ssr_indicator_body_v4_v5():
    """V4 абзац под графиком + V5 alt с «прогноз» на пилоте."""
    from types import SimpleNamespace

    from app.data.indicator_seo import FORECAST_SSR_CHART_NOTE, forecast_ssr_image_name
    from app.services.seo_renderer import _indicator_body

    ind = SimpleNamespace(
        code="cpi",
        name="Индекс потребительских цен на товары и услуги",
        unit="%",
        frequency="monthly",
        source="Росстат",
        source_url="https://rosstat.gov.ru/statistics/price",
        description="ИПЦ России.",
        methodology="Фиксированная корзина.",
        seo_blocks=None,
        model_config_json={"forecast_steps": 12},
    )
    html = _indicator_body(
        ind, None, [], [], 0, None, None, forecast_ssr=True,
    )
    assert 'class="seo-forecast-note"' in html
    assert FORECAST_SSR_CHART_NOTE in html
    assert 'href="/methodology"' in html
    expected_alt = forecast_ssr_image_name(ind.name)
    assert f'alt="{expected_alt}"' in html
    # Без флага — нет V4/V5.
    html_off = _indicator_body(ind, None, [], [], 0, None, None, forecast_ssr=False)
    assert "seo-forecast-note" not in html_off
    assert "график динамики и прогноз" not in html_off


def test_autolink_terms_in_seo_blocks():
    """Перелинковка: первое вхождение термина → ссылка, self-ссылки пропущены."""
    from html import escape

    from app.services.seo_renderer import _autolink

    text = escape("Обычно RUONIA торгуется в коридоре вокруг ключевой ставки. RUONIA — рыночная.")
    out = _autolink(text, current_code="ruonia")
    # self-ссылка на ruonia не ставится
    assert 'href="/russia/indicator/ruonia"' not in out
    assert '<a href="/russia/indicator/key-rate">ключевой ставки</a>' in out
    # второе вхождение RUONIA тоже не линкуется (без current_code линкуется только первое)
    out2 = _autolink(text, current_code=None)
    assert out2.count('href="/russia/indicator/ruonia"') == 1


def test_autolink_does_not_double_link():
    from html import escape

    from app.services.seo_renderer import _autolink

    text = escape("ИПЦ растёт, индекс потребительских цен — основной измеритель.")
    out = _autolink(text)
    # оба паттерна ведут на cpi — линкуется только один
    assert out.count('href="/russia/indicator/cpi"') == 1


def test_og_image_renders_png():
    from app.services.og_image import render_indicator_og

    png = render_indicator_og(
        code="cpi",
        name="Индекс потребительских цен на товары и услуги",
        value_text="+0,21",
        date_text="на 1 мая 2026",
        values=[0.5, 0.3, 0.4, 0.2, 0.25, 0.21],
        subtitle="индекс потребительских цен, изменение за месяц",
        context_pill="Годовая инфляция — 6,0%",
        unit_suffix="%",
        x_labels=("май 2024", "май 2026"),
    )
    assert png[:4] == b"\x89PNG"
    assert len(png) > 5000


def test_og_image_cache_roundtrip():
    from app.services import og_image

    og_image.store_og("test-code", b"fakepng")
    assert og_image.cached_og("test-code") == b"fakepng"
    assert og_image.cached_og("missing") is None


def test_indexnow_payload(monkeypatch):
    import asyncio

    from app.services import indexnow

    captured = {}

    class _FakeResponse:
        status_code = 200
        text = "ok"

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            captured["url"] = url
            captured["payload"] = json
            return _FakeResponse()

    monkeypatch.setattr(indexnow.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(indexnow.settings, "indexnow_enabled", True)
    ok = asyncio.run(indexnow.ping_updated_indicators(["cpi", "key-rate", "cpi"]))
    assert ok
    urls = captured["payload"]["urlList"]
    assert "https://forecasteconomy.com/" in urls
    assert "https://forecasteconomy.com/russia/indicator/cpi" in urls
    # дубликаты схлопнуты
    assert len(urls) == len(set(urls))
    assert captured["payload"]["key"] == indexnow.settings.indexnow_key


def test_universal_seo_indicator_year_route(client, monkeypatch):
    from app.api import seo_pages

    async def fake_year(code, year, db):
        assert code == "cpi"
        assert year == 2024
        return 200, "<html><body><div id='root'><h1>ИПЦ в 2024 году</h1></div></body></html>"

    monkeypatch.setattr(seo_pages, "render_indicator_year_html", fake_year)
    r = client.get("/seo/indicator-year/cpi/2024")
    assert r.status_code == 200
    assert "2024" in r.text
    # ETag присутствует
    assert r.headers.get("etag")
    # повторный запрос с If-None-Match → 304
    r2 = client.get("/seo/indicator-year/cpi/2024", headers={"If-None-Match": r.headers["etag"]})
    assert r2.status_code == 304


def test_seo_etag_304(client, monkeypatch):
    from app.api import seo_pages

    async def fake_home(db):
        return "<html><body><div id='root'>home</div></body></html>"

    monkeypatch.setattr(seo_pages, "render_home_html", fake_home)
    r1 = client.get("/seo/page/home")
    etag = r1.headers.get("etag")
    assert etag
    r2 = client.get("/seo/page/home", headers={"If-None-Match": etag})
    assert r2.status_code == 304


def test_build_document_year_page_excludes_app(client):
    """include_app=False: без React-bundle и без modulepreload (404 после гидратации).

    Единственный разрешённый скрипт в теле — standalone-сборщик аналитики
    behavior-standalone.js (ADR-0010: чистые SSR-страницы не слепая зона)."""
    import asyncio

    from app.services.seo_renderer import build_document

    html = asyncio.run(
        build_document(
            title="ИПЦ в 2024 году",
            description="Тест",
            canonical_path="/russia/indicator/cpi/2024",
            body='<main class="seo-page"><h1>ИПЦ в 2024 году</h1></main>',
            include_app=False,
        )
    )
    body = html.split("<body>")[1]
    assert "modulepreload" not in html
    assert "/assets/behavior-standalone.js" in body
    # React-бандл (хэшированный index-*.js) в чистый SSR не попадает.
    body_without_collector = body.replace(
        '<script type="module" src="/assets/behavior-standalone.js" defer></script>', "")
    assert "module" not in body_without_collector


def test_ssr_chrome_topnav_keeps_hub_deep_links():
    """seo-topnav на pure-SSR (годовые landing'и + 404) обязан держать хабы.

    Срезать /russia/region|/russia/today|/world|/russia/calendar нельзя: это единственная
    серверная шапка для страниц без React. SPA-SSR (~77k URL) chrome не
    получает — там отдельный блок seo-platform-nav (см. соседний тест)."""
    import re

    from app.services.locale import reset_locale, set_locale
    from app.services.seo_renderer import (
        _SSR_CHROME_HEADER,
        _ssr_chrome_header,
        _ssr_platform_deep_links,
    )

    m = re.search(r'<nav class="seo-topnav">(.*?)</nav>', _SSR_CHROME_HEADER, re.S)
    assert m, "seo-topnav отсутствует в _SSR_CHROME_HEADER"
    topnav = m.group(1)
    for href in ("/russia", "/russia/region", "/russia/today", "/#countries", "/russia/calendar"):
        assert f'href="{href}"' in topnav, f"в seo-topnav нет ссылки на {href}"
    assert "Демограф" not in topnav

    token = set_locale("en")
    try:
        en_header = _ssr_chrome_header()
        assert "Home" in en_header
        assert "Today" in en_header
        assert "Regions" in en_header
        assert "Countries" in en_header
        assert "Calendar" in en_header
        assert "Главная" not in en_header
        en_nav = _ssr_platform_deep_links()
        assert "Platform sections" in en_nav
        assert "Разделы платформы" not in en_nav
    finally:
        reset_locale(token)

    assert "Главная" in _ssr_chrome_header()
    assert "Разделы платформы" in _ssr_platform_deep_links()


def test_spa_ssr_gets_platform_deep_links():
    """SPA-SSR (include_app=True) без chrome обязан получить блок выхода в хабы.

    Иначе тонкие семейства (/russia/today/*, /russia/calendar/*) оставляют боту одни крошки.
    Pure-SSR с chrome этот блок не дублирует."""
    import asyncio

    from app.services.locale import reset_locale, set_locale
    from app.services.seo_renderer import build_document

    spa = asyncio.run(
        build_document(
            title="Тест",
            description="Тест",
            canonical_path="/russia/today/cpi",
            body='<main class="seo-page"><nav><a href="/">Главная</a></nav><h1>x</h1></main>',
            include_app=True,
        )
    )
    assert 'class="seo-section seo-platform-nav"' in spa
    for href in ("/russia/region", "/russia/today", "/#countries", "/russia/calendar", "/compare", "/"):
        assert f'href="{href}"' in spa
    assert "Разделы платформы" in spa
    # Браузер с JS не должен видеть SEO-тело как «сломанный сайт» до гидратации.
    assert 'classList.add("fe-js")' in spa
    assert "html.fe-js #root > .seo-page" in spa
    assert 'type="module"' in spa

    token = set_locale("en")
    try:
        spa_en = asyncio.run(
            build_document(
                title="Test",
                description="Test",
                canonical_path="/russia/today/cpi",
                body='<main class="seo-page"><h1>x</h1></main>',
                include_app=True,
            )
        )
    finally:
        reset_locale(token)
    assert "Platform sections" in spa_en
    assert "Разделы платформы" not in spa_en

    pure = asyncio.run(
        build_document(
            title="Год",
            description="Тест",
            canonical_path="/russia/indicator/cpi/2024",
            body='<main class="seo-page"><h1>2024</h1></main>',
            include_app=False,
        )
    )
    assert 'class="seo-topnav"' in pure
    # chrome уже даёт хабы — platform-nav не дублируем в body
    assert 'class="seo-section seo-platform-nav"' not in pure
    # Pure-SSR без React-app: SEO видим, нет fe-js hide, нет SPA-скриптов и
    # modulepreload'ов. Стилевой main-*.css остаётся (chrome стилизован им).
    assert 'classList.add("fe-js")' not in pure
    assert 'type="module" src="/assets/main-' not in pure
    assert "modulepreload" not in pure


def test_build_document_og_image_override():
    import asyncio

    from app.services.seo_renderer import build_document

    html = asyncio.run(
        build_document(
            title="Тест",
            description="Тест",
            canonical_path="/russia/indicator/cpi",
            body="<main><h1>x</h1></main>",
            og_image="https://forecasteconomy.com/og/russia/cpi.png",
        )
    )
    assert 'og:image" content="https://forecasteconomy.com/og/russia/cpi.png"' in html
    assert "og-image-v2.png" not in html


def _extract_title(html: str) -> str:
    start = html.find("<title>")
    end = html.find("</title>")
    if start == -1 or end == -1:
        return ""
    return html[start + len("<title>") : end]
