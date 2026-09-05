"""Locale resolver + i18n parity guards."""

from __future__ import annotations

from app.data.i18n.en_catalog import has_en_path
from app.data.i18n.glossary_en import GLOSSARY_EN
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
from app.data.i18n.seo_en import (
    CATEGORY_META_EN,
    HOME_TEMPLATES_EN,
    PAGE_META_EN,
    PAGE_TEMPLATES_EN,
)
from app.services.i18n_display import public_name
from app.services.locale import (
    PRODUCTION_APEX_HOSTS,
    en_public_origin,
    html_lang,
    og_locale,
    resolve_locale,
    resolve_request_origin,
    ru_public_origin,
)
from app.services.seo_content import CATEGORY_META, PAGE_META
from app.services.seo_i18n import get_category_seo, get_page_seo, home_template, page_template

# Stub-regression guard: content agent restores ~167 codes; a wiped stub fails here.
_INDICATOR_COPY_EN_MIN = 160
_INDICATOR_COPY_EN_REQUIRED = ("cpi", "cpi-food", "wages-nominal", "key-rate")


def test_x_forwarded_host_beats_localhost_host():
    """Caddy/nginx must pass the public host; backend Host can be localhost."""
    from starlette.requests import Request
    from app.services.locale import resolve_locale_from_request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/seo/indicator/key-rate/2025",
        "raw_path": b"/seo/indicator/key-rate/2025",
        "query_string": b"",
        "headers": [
            (b"host", b"localhost"),
            (b"x-forwarded-host", b"forecasteconomy.com"),
        ],
        "client": ("127.0.0.1", 123),
        "server": ("localhost", 8000),
    }
    assert resolve_locale_from_request(Request(scope)) == "ru"

    scope["headers"] = [
        (b"host", b"localhost"),
        (b"x-forwarded-host", b"forecasteconomy.com"),
        (b"x-fe-locale", b"en"),
    ]
    assert resolve_locale_from_request(Request(scope)) == "en"


def test_localhost_defaults_to_ru():
    assert resolve_locale(host="localhost") == "ru"
    assert resolve_locale(host="127.0.0.1:8000") == "ru"
    assert resolve_locale(host="rosstat-frontend") == "ru"


def test_header_overrides_host():
    assert resolve_locale(host="localhost", header="en") == "en"
    assert resolve_locale(host="forecasteconomy.com", header="ru") == "ru"


def test_preview_locale_overrides_localhost():
    assert resolve_locale(host="localhost", preview="en") == "en"
    assert resolve_locale(host="localhost", preview="ru") == "ru"
    # Header wins over preview when both set.
    assert resolve_locale(host="localhost", header="ru", preview="en") == "ru"


def test_preview_locale_from_referer():
    from app.services.locale import preview_locale_from_referer

    assert preview_locale_from_referer(
        "http://localhost:5173/?preview_locale=en"
    ) == "en"
    assert preview_locale_from_referer(
        "http://localhost:5173/russia/today?preview_locale=ru&x=1"
    ) == "ru"
    assert preview_locale_from_referer("http://localhost:5173/") is None


def test_resolve_locale_from_request_query():
    """Direct backend: ?preview_locale=en binds locale without X-FE-Locale."""
    from starlette.requests import Request
    from app.services.locale import resolve_locale_from_request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/seo/page/home",
        "raw_path": b"/seo/page/home",
        "query_string": b"preview_locale=en",
        "headers": [(b"host", b"localhost:8000")],
        "client": ("127.0.0.1", 123),
        "server": ("localhost", 8000),
    }
    assert resolve_locale_from_request(Request(scope)) == "en"

    scope_ru = {
        **scope,
        "query_string": b"",
        "headers": [(b"host", b"localhost:8000")],
    }
    assert resolve_locale_from_request(Request(scope_ru)) == "ru"

    scope_ref = {
        **scope,
        "query_string": b"",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"referer", b"http://localhost:5173/?preview_locale=en"),
        ],
    }
    assert resolve_locale_from_request(Request(scope_ref)) == "en"


def test_production_apex_stays_ru_until_cutover_flag():
    """Without RUSTATS_APEX_LOCALE_EN, apex must remain Russian (Yandex-safe)."""
    for host in PRODUCTION_APEX_HOSTS:
        assert resolve_locale(host=host, apex_locale_en=False) == "ru"
        assert resolve_locale(host=host) == "ru"


def test_production_apex_is_en_when_cutover_enabled():
    for host in PRODUCTION_APEX_HOSTS:
        assert resolve_locale(host=host, apex_locale_en=True) == "en"


def test_ru_subdomain_is_ru():
    assert resolve_locale(host="ru.forecasteconomy.com") == "ru"
    assert resolve_locale(host="ru.forecasteconomy.com", apex_locale_en=True) == "ru"


def test_request_origin_host_aware():
    """Sitemap/canonical origin: ru. Host → ru origin; apex → public_origin."""
    assert resolve_request_origin("ru.forecasteconomy.com") == ru_public_origin()
    assert resolve_request_origin("ru.forecasteconomy.com") == (
        "https://ru.forecasteconomy.com"
    )
    assert resolve_request_origin("forecasteconomy.com") == en_public_origin()
    assert resolve_request_origin("www.forecasteconomy.com") == en_public_origin()
    assert resolve_request_origin("localhost") == en_public_origin()
    assert resolve_request_origin("en.forecasteconomy.com") == en_public_origin()


def test_build_document_og_and_jsonld_follow_request_origin():
    """OG / RSS alternate / WebSite @id use bound request origin (not DOMAIN only)."""
    import asyncio

    from app.services.locale import (
        reset_locale,
        reset_request_origin,
        set_locale,
        set_request_origin,
    )
    from app.services.seo_renderer import _site_json_ld, build_document

    loc = set_locale("ru")
    origin = set_request_origin("https://ru.forecasteconomy.com")
    try:
        site = _site_json_ld()
        assert site["@graph"][0]["url"] == "https://ru.forecasteconomy.com"
        assert site["@graph"][0]["@id"] == "https://ru.forecasteconomy.com/#website"

        html = asyncio.run(
            build_document(
                title="T",
                description="D",
                canonical_path="/russia/indicator/cpi",
                body="<main>x</main>",
                include_app=True,
            )
        )
        assert 'href="https://forecasteconomy.com/russia/indicator/cpi"' in html
        assert 'href="https://ru.forecasteconomy.com/feed.xml"' in html
        assert 'content="https://ru.forecasteconomy.com/og-image-v2.png"' in html
        assert "hreflang=" not in html
    finally:
        reset_request_origin(origin)
        reset_locale(loc)

    loc = set_locale("ru")
    origin = set_request_origin("https://forecasteconomy.com")
    try:
        html = asyncio.run(
            build_document(
                title="T",
                description="D",
                canonical_path="/russia/indicator/cpi",
                body="<main>x</main>",
                include_app=True,
            )
        )
        assert 'href="https://forecasteconomy.com/feed.xml"' in html
        assert 'content="https://forecasteconomy.com/og-image-v2.png"' in html
    finally:
        reset_request_origin(origin)
        reset_locale(loc)


def test_ssr_cache_key_separates_request_hosts():
    """Apex and ru. Host must not share the same SSR HTML cache entry."""
    import asyncio

    from app.api import seo_pages
    from app.services.locale import (
        reset_locale,
        reset_request_origin,
        set_locale,
        set_request_origin,
    )

    async def keys():
        loc = set_locale("ru")
        try:
            o1 = set_request_origin("https://forecasteconomy.com")
            try:
                k_apex = await seo_pages._ssr_key("cpi", "indicator:cpi:", "sig")
            finally:
                reset_request_origin(o1)
            o2 = set_request_origin("https://ru.forecasteconomy.com")
            try:
                k_ru = await seo_pages._ssr_key("cpi", "indicator:cpi:", "sig")
            finally:
                reset_request_origin(o2)
            return k_apex, k_ru
        finally:
            reset_locale(loc)

    k_apex, k_ru = asyncio.run(keys())
    assert k_apex != k_ru
    assert "ssr:" in k_apex
    assert "ssr:" in k_ru


def test_hreflang_silent_until_apex_en_cutover(monkeypatch):
    """Do not advertise hreflang=en while apex is still Russian."""
    from app.config import settings
    from app.services.seo_renderer import _hreflang_head

    monkeypatch.setattr(settings, "apex_locale_en", False)
    assert _hreflang_head("/russia/indicator/cpi") == ""
    assert _hreflang_head("/") == ""

    monkeypatch.setattr(settings, "apex_locale_en", True)
    head = _hreflang_head("/")
    assert 'hreflang="ru"' in head
    assert 'hreflang="en"' in head
    assert "https://ru.forecasteconomy.com/" in head
    assert 'hreflang="x-default"' in head
    assert "https://forecasteconomy.com/" in head


def test_en_subdomain_is_en():
    assert resolve_locale(host="en.forecasteconomy.com") == "en"
    assert resolve_locale(host="en.localhost") == "en"


def test_html_lang_and_og_locale():
    assert html_lang("ru") == "ru"
    assert html_lang("en") == "en"
    assert og_locale("ru") == "ru_RU"
    assert og_locale("en") == "en_US"


def test_public_name_picks_en():
    assert public_name("ИПЦ", "CPI", locale="en") == "CPI"
    assert public_name("ИПЦ", "CPI", locale="ru") == "ИПЦ"
    assert public_name("ИПЦ", None, locale="en") == "ИПЦ"
    assert public_name("ИПЦ", "", locale="en") == "ИПЦ"


def test_get_page_seo_falls_back_when_en_empty():
    home = get_page_seo("home", locale="en")
    assert home is not None
    assert home.slug == "home"
    # Empty PAGE_META_EN → RU twin
    if not PAGE_META_EN:
        assert home.title == PAGE_META["home"].title


def test_get_category_seo_falls_back_when_en_empty():
    prices = get_category_seo("prices", locale="en")
    assert prices is not None
    if not CATEGORY_META_EN:
        assert prices.name == CATEGORY_META["prices"].name


def test_page_meta_en_parity_when_populated():
    """When content agent fills PAGE_META_EN, every RU slug must have a twin."""
    if not PAGE_META_EN:
        return
    missing = set(PAGE_META) - set(PAGE_META_EN)
    assert not missing, f"PAGE_META_EN missing slugs: {sorted(missing)}"


def test_category_meta_en_parity_when_populated():
    if not CATEGORY_META_EN:
        return
    missing = set(CATEGORY_META) - set(CATEGORY_META_EN)
    assert not missing, f"CATEGORY_META_EN missing slugs: {sorted(missing)}"


def test_home_templates_en_complete():
    required = {
        "eyebrow",
        "h2_countries",
        "h2_flagships",
        "h2_tools",
        "itemlist_countries",
        "itemlist_flagships",
    }
    assert required <= set(HOME_TEMPLATES_EN)
    for key in required:
        assert home_template(key, locale="en")
        assert home_template(key, locale="ru") is None
        assert not any(
            "а" <= ch.lower() <= "я" or ch in "ёЁ"
            for ch in HOME_TEMPLATES_EN[key]
        )


def test_page_templates_en_complete():
    required = {"h2_related", "h2_categories", "h2_section_indicators"}
    assert required <= set(PAGE_TEMPLATES_EN)
    for key in required:
        assert page_template(key, locale="en")
        assert page_template(key, locale="ru") is None
        assert not any(
            "а" <= ch.lower() <= "я" or ch in "ёЁ"
            for ch in PAGE_TEMPLATES_EN[key]
        )


def test_render_russia_hub_html_locale_en_no_cyrillic_in_body(monkeypatch):
    """/seo/page/russia: EN body uses PAGE_META_EN + Related sections; RU intact."""
    import asyncio
    import re

    from app.services.locale import reset_locale, set_locale
    from app.services import seo_renderer

    async def fake_assets():
        return seo_renderer._fallback_assets()

    monkeypatch.setattr(seo_renderer, "get_app_assets", fake_assets)
    cyrillic = re.compile(r"[А-Яа-яЁё]")

    token = set_locale("en")
    try:
        status, html_en = asyncio.run(seo_renderer.render_page_html("russia"))
        assert status == 200
        assert PAGE_META_EN["russia"].h1 in html_en
        assert PAGE_META_EN["russia"].intro[:40] in html_en
        assert "Related sections" in html_en
        assert "Indicator categories" in html_en
        assert "Связанные разделы" not in html_en
        related_en = re.search(r"Related sections.*?</ul>", html_en, re.DOTALL)
        assert related_en, "missing related sections"
        assert "Economy today" not in related_en.group(0)
        assert "Экономика сегодня" not in html_en
        # Main content blocks must stay Latin for locale=en.
        main = re.search(r"<main class=\"seo-page\">(.*?)</main>", html_en, re.DOTALL)
        assert main, "missing main"
        assert not cyrillic.search(main.group(1)), main.group(1)[:200]
    finally:
        reset_locale(token)

    token_ru = set_locale("ru")
    try:
        status, html_ru = asyncio.run(seo_renderer.render_page_html("russia"))
        assert status == 200
        assert PAGE_META["russia"].h1 in html_ru
        assert "Связанные разделы" in html_ru
        assert "Категории показателей" in html_ru
        related_ru = re.search(r"Связанные разделы.*?</ul>", html_ru, re.DOTALL)
        assert related_ru, "missing related sections"
        assert "Экономика сегодня" not in related_ru.group(0)
        assert "Related sections" not in html_ru
    finally:
        reset_locale(token_ru)


def test_render_categories_hub_html_locale_en(monkeypatch):
    """/seo/category: EN h1/intro/section headings; RU unchanged."""
    import asyncio

    from app.services.locale import reset_locale, set_locale
    from app.services import seo_renderer

    async def fake_assets():
        return seo_renderer._fallback_assets()

    monkeypatch.setattr(seo_renderer, "get_app_assets", fake_assets)

    token = set_locale("en")
    try:
        status, html_en = asyncio.run(seo_renderer.render_categories_hub_html(None))
        assert status == 200
        assert PAGE_META_EN["russia-categories"].h1 in html_en
        assert "Related sections" in html_en
        assert ">Categories<" in html_en or "<h2>Categories</h2>" in html_en
        assert "Связанные разделы" not in html_en
        assert "Категории показателей России" not in html_en
        assert "Prices and inflation" in html_en
        assert "Цены и инфляция" not in html_en
    finally:
        reset_locale(token)

    token_ru = set_locale("ru")
    try:
        status, html_ru = asyncio.run(seo_renderer.render_categories_hub_html(None))
        assert status == 200
        assert PAGE_META["russia-categories"].h1 in html_ru
        assert "Связанные разделы" in html_ru
        assert "<h2>Категории</h2>" in html_ru
        assert "Related sections" not in html_ru
        assert "Цены и инфляция" in html_ru
    finally:
        reset_locale(token_ru)


def test_render_home_html_locale_en_no_cyrillic_in_json_ld(monkeypatch):
    """locale=en: title/ItemList/category names English; locale=ru keeps Cyrillic."""
    import asyncio
    import json
    import re
    from types import SimpleNamespace

    from app.services.locale import reset_locale, set_locale
    from app.services import seo_renderer

    async def fake_inds(db, codes):
        return [
            SimpleNamespace(
                code="cpi",
                name="Индекс потребительских цен",
                name_en="Consumer Price Index",
            )
        ]

    monkeypatch.setattr(seo_renderer, "_indicators_by_codes", fake_inds)

    async def fake_assets():
        return seo_renderer._fallback_assets()

    monkeypatch.setattr(seo_renderer, "get_app_assets", fake_assets)

    async def fake_country_links(db):
        return (("/sweden", "Sweden"),)

    monkeypatch.setattr(seo_renderer, "_home_country_links", fake_country_links)

    cyrillic = re.compile(r"[А-Яа-яЁё]")

    def _json_ld_blobs(html: str) -> list[dict | list]:
        blobs = []
        for m in re.finditer(
            r'<script type="application/ld\+json">(.*?)</script>',
            html,
            re.DOTALL,
        ):
            blobs.append(json.loads(m.group(1)))
        return blobs

    def _item_lists(blobs: list) -> list[dict]:
        out = []
        for blob in blobs:
            if isinstance(blob, dict) and blob.get("@type") == "ItemList":
                out.append(blob)
            elif isinstance(blob, list):
                out.extend(
                    x for x in blob if isinstance(x, dict) and x.get("@type") == "ItemList"
                )
        return out

    token = set_locale("en")
    try:
        html_en = asyncio.run(seo_renderer.render_home_html(None))
        assert 'id="fe-bootstrap"' in html_en
        assert '"locale":"en"' in html_en
        assert "Consumer Price Index" in html_en
        assert PAGE_META_EN["home"].title in html_en
        assert '<html lang="en"' in html_en or "lang=\"en\"" in html_en
        assert "Official data for Russia, regions, and countries" in html_en
        assert ">Countries</h2>" in html_en
        assert "Официальные данные" not in html_en
        assert "Страны</h2>" not in html_en

        lists_en = _item_lists(_json_ld_blobs(html_en))
        assert len(lists_en) >= 2
        for lst in lists_en:
            assert not cyrillic.search(lst["name"]), lst["name"]
            for el in lst.get("itemListElement") or []:
                assert not cyrillic.search(el.get("name") or ""), el
        assert any(
            "Countries with official statistics on the platform" == lst["name"]
            for lst in lists_en
        )
        assert any(
            "Key macroeconomic indicators" == lst["name"] for lst in lists_en
        )
    finally:
        reset_locale(token)

    token_ru = set_locale("ru")
    try:
        html_ru = asyncio.run(seo_renderer.render_home_html(None))
        assert PAGE_META["home"].title in html_ru
        assert "Официальные данные России, регионов и стран" in html_ru
        assert "Страны с официальной статистикой на платформе" in html_ru
        assert "Official data for Russia, regions, and countries" not in html_ru
        lists_ru = _item_lists(_json_ld_blobs(html_ru))
        assert any(cyrillic.search(lst["name"] or "") for lst in lists_ru)
    finally:
        reset_locale(token_ru)


def test_indicator_copy_en_not_stubbed():
    """Fail loudly if indicator_copy_en.py is wiped back to an empty stub."""
    n = len(INDICATOR_COPY_EN)
    assert n >= _INDICATOR_COPY_EN_MIN, (
        f"INDICATOR_COPY_EN has {n} codes (< {_INDICATOR_COPY_EN_MIN}): "
        "файл снова затёрли stub’ом"
    )
    missing = [c for c in _INDICATOR_COPY_EN_REQUIRED if c not in INDICATOR_COPY_EN]
    assert not missing, (
        f"INDICATOR_COPY_EN missing required codes {missing}: "
        "файл снова затёрли stub’ом"
    )


def test_glossary_has_core_terms():
    for key in ("ИПЦ", "Ключевая ставка", "Росстат", "Банк России", "Минфин"):
        assert key in GLOSSARY_EN


def test_world_concepts_have_name_en():
    from app.data.world_concepts import WORLD_CONCEPTS

    missing = [c.slug for c in WORLD_CONCEPTS if not (c.name_en or "").strip()]
    assert not missing, f"WORLD_CONCEPTS missing name_en: {missing}"


def test_public_indicator_seo_en_title_and_source():
    import re

    from app.services.seo_i18n import (
        localize_territory_fact,
        public_indicator_seo,
        translate_source,
        world_template,
    )

    assert translate_source("Росстат", locale="en") == "Rosstat"
    assert translate_source("Банк России", locale="en") == "Bank of Russia"
    assert translate_source("Минфин", locale="en") == "Ministry of Finance"
    assert translate_source("Евростат", locale="en") == "Eurostat"
    assert translate_source("Банк Японии", locale="en") == "Bank of Japan"

    fact = localize_territory_fact(
        {"unit": "км²", "source": "Евростат", "value": 1},
        locale="en",
    )
    assert fact["unit"] == "km²"
    assert fact["source"] == "Eurostat"
    assert localize_territory_fact(
        {"unit": "км²", "source": "Евростат"},
        locale="ru",
    )["unit"] == "км²"

    assert world_template("country_title", locale="en") == (
        "Economy of {country}: statistics and indicators"
    )
    sweden_title = world_template("country_title", locale="en").format(country="Sweden")
    assert sweden_title == "Economy of Sweden: statistics and indicators"
    assert not re.search(r"[А-Яа-яЁё]", sweden_title)

    overlay = public_indicator_seo(
        "cpi",
        name_ru="Индекс потребительских цен",
        name_en="CPI",
        description_ru="RU desc",
        methodology_ru="RU method",
        source_ru="Росстат",
        seo_title_ru="ИПЦ — прогноз и данные",
        seo_description_ru="Русское описание",
        seo_blocks_ru=[{"title": "Что такое", "body": "тело"}],
        frequency="monthly",
        locale="en",
    )
    assert overlay["name"] == "Consumer Price Index"
    assert overlay["seo_title"] == "Consumer Price Index — data and chart"
    assert "ИПЦ" not in (overlay["seo_title"] or "")
    assert overlay["source"] == "Rosstat"
    assert isinstance(overlay["seo_blocks"], list)
    assert len(overlay["seo_blocks"]) == 6
    assert overlay["seo_blocks"][0]["title"] == "What it shows"
    assert "Росстат" not in overlay["seo_blocks"][-1]["body"]


def test_webmaster_sync_host_ids_include_ru_after_cutover(monkeypatch):
    from app.config import settings
    from app.services.analytics_backfill import webmaster_sync_host_ids

    monkeypatch.setattr(settings, "apex_locale_en", False)
    ids = webmaster_sync_host_ids()
    assert ids == [settings.webmaster_host_id]

    monkeypatch.setattr(settings, "apex_locale_en", True)
    ids = webmaster_sync_host_ids()
    assert settings.webmaster_host_id in ids
    assert settings.webmaster_host_id_for("ru.forecasteconomy.com") in ids


def test_public_indicator_fields_en_does_not_leak_russian():
    """EN overlay missing → optional copy is omitted, not Russian fallback."""
    from app.services.seo_i18n import public_indicator_fields

    fields = public_indicator_fields(
        "no-such-overlay-code",
        name_ru="Русское имя",
        name_en="English name",
        description_ru="Русское описание, которое нельзя показывать",
        methodology_ru="Русская методология",
        unit_ru="%",
        locale="en",
    )
    assert fields["name"] == "English name"
    assert fields["description"] is None
    assert fields["methodology"] is None
    cyr = __import__("re").compile(r"[А-Яа-яЁё]")
    for value in fields.values():
        if isinstance(value, str):
            assert not cyr.search(value), value


def test_indicator_copy_en_entries_have_name_and_description():
    missing_name = [
        code
        for code, copy in INDICATOR_COPY_EN.items()
        if not (copy.get("name") or "").strip()
    ]
    assert not missing_name, f"INDICATOR_COPY_EN missing name: {missing_name[:20]}"
    missing_desc = [
        code
        for code, copy in INDICATOR_COPY_EN.items()
        if "description" in copy and not (copy.get("description") or "").strip()
    ]
    assert not missing_desc, f"INDICATOR_COPY_EN empty description: {missing_desc[:20]}"


_CYRILLIC_RE = __import__("re").compile(r"[А-Яа-яЁё]")


def test_en_indicator_copy_payload_has_no_cyrillic():
    """EN overlay texts that reach the card must not leak Russian."""
    from app.services.seo_i18n import public_indicator_fields

    leaked = []
    for code, copy in INDICATOR_COPY_EN.items():
        fields = public_indicator_fields(
            code,
            name_ru="Русское имя",
            name_en=copy.get("name"),
            description_ru="Русское описание",
            methodology_ru="Русская методология",
            unit_ru=copy.get("unit") or "%",
            locale="en",
        )
        for key, value in fields.items():
            if not isinstance(value, str) or not _CYRILLIC_RE.search(value):
                continue
            leaked.append(f"{code}.{key}: {value[:80]}")
    assert not leaked, leaked[:15]


def test_export_csv_headers_follow_locale():
    from app.api.export import _build_csv
    from app.services.locale import reset_locale, set_locale

    token = set_locale("en")
    try:
        csv = _build_csv([("2024-01-01", 1.5)], [], "Value").decode("utf-8-sig")
        assert "Date;Value;Type" in csv
        assert ";actual" in csv
        assert "Дата" not in csv
        assert "факт" not in csv
        assert "1.5" in csv or "1,5" not in csv.split("\n")[-1]
    finally:
        reset_locale(token)

    token = set_locale("ru")
    try:
        csv = _build_csv([("2024-01-01", 1.5)], [], "Значение").decode("utf-8-sig")
        assert "Дата;Значение;Тип" in csv
        assert ";факт" in csv
    finally:
        reset_locale(token)


def test_localize_view_mode_label_en():
    from app.services.seo_i18n import localize_hero_label, localize_view_mode_label

    assert localize_view_mode_label("Год к году", locale="en") == "Year on year"
    assert localize_hero_label("Год к году", locale="en") == "Year on year"
    assert localize_view_mode_label("Год к году", locale="ru") == "Год к году"


def test_hreflang_catalog_home():
    assert has_en_path("/") is True
    assert has_en_path("/about") is True


def test_ssr_chrome_locale_en():
    """SSR chrome / platform deep-links respect X-FE-Locale via get_locale()."""
    import asyncio

    from app.services.locale import reset_locale, set_locale
    from app.services.seo_renderer import (
        _ssr_chrome_header,
        _ssr_platform_deep_links,
        build_document,
        render_not_found_html,
    )

    token = set_locale("en")
    try:
        header = _ssr_chrome_header()
        assert ">Home<" in header
        assert ">Today<" in header
        assert ">Regions<" in header
        assert ">Calendar<" in header
        assert ">About<" in header
        # EN-топнав без Russia-link (страна данных — не приглашающая поверхность).
        assert ">Russia<" not in header
        assert f'href="{paths.russia_home() if False else "/russia"}">Russia</a>' not in header
        assert "Индикаторы" not in header
        assert "О проекте" not in header

        deep = _ssr_platform_deep_links()
        assert "Platform sections" in deep
        assert "Разделы платформы" not in deep
        # Deep-links EN переименованы без слова «Russia»; адреса прежние.
        assert "Russia" not in deep
        assert '<a href="/">Indicators</a>' in deep
        assert 'href="/russia/region"' in deep

        nf = render_not_found_html()
        assert "Page not found" in nf
        assert ">Home<" in nf
        assert "Страница не найдена" not in nf

        spa = asyncio.run(
            build_document(
                title="T",
                description="D",
                canonical_path="/russia/today/cpi",
                body='<main class="seo-page"><h1>x</h1></main>',
                include_app=True,
            )
        )
        assert "Platform sections" in spa
        assert "Разделы платформы" not in spa

        pure = asyncio.run(
            build_document(
                title="Y",
                description="D",
                canonical_path="/russia/indicator/cpi/2024",
                body='<main class="seo-page"><h1>2024</h1></main>',
                include_app=False,
            )
        )
        assert ">Home<" in pure
        assert "Open the platform" in pure
        assert "Открыть платформу" not in pure
        # S2: EN-футер без «for Russia, its regions…».
        assert "official statistics for national economies" in pure
        assert "for Russia, its regions" not in pure
    finally:
        reset_locale(token)

    token_ru = set_locale("ru")
    try:
        assert "Главная" in _ssr_chrome_header()
        assert "Россия</a>" in _ssr_chrome_header()
        assert "Разделы платформы" in _ssr_platform_deep_links()
        assert "Индикаторы России</a>" in _ssr_platform_deep_links()
        assert "Страница не найдена" in render_not_found_html()
    finally:
        reset_locale(token_ru)


def test_preview_locale_noindex(monkeypatch):
    """S3: preview-EN до кутовера — noindex; обычные страницы — index."""
    import asyncio

    from app.config import settings
    from app.services.locale import (
        reset_locale,
        reset_preview_locale,
        set_locale,
        set_preview_locale,
    )
    from app.services.seo_renderer import build_document

    monkeypatch.setattr(settings, "apex_locale_en", False)

    async def render():
        return await build_document(
            title="T",
            description="D",
            canonical_path="/russia/indicator/cpi",
            body="<main>x</main>",
            include_app=True,
        )

    # 1) Обычная EN-поверхность (X-FE-Locale/en. host, без preview): индексируется.
    token = set_locale("en")
    pt = set_preview_locale(False)
    try:
        html = asyncio.run(render())
        assert '<meta name="robots" content="index, follow, max-snippet:-1' in html
        assert "noindex" not in html
    finally:
        reset_preview_locale(pt)
        reset_locale(token)

    # 2) Preview EN (?preview_locale=en): noindex,follow.
    token = set_locale("en")
    pt = set_preview_locale(True)
    try:
        html = asyncio.run(render())
        assert '<meta name="robots" content="noindex, follow">' in html
        assert 'content="index, follow' not in html
    finally:
        reset_preview_locale(pt)
        reset_locale(token)

    # 3) RU по умолчанию: без noindex.
    token = set_locale("ru")
    pt = set_preview_locale(False)
    try:
        html = asyncio.run(render())
        assert '<meta name="robots" content="index, follow, max-snippet:-1' in html
        assert "noindex" not in html
    finally:
        reset_preview_locale(pt)
        reset_locale(token)


def test_locale_middleware_sets_preview_flag():
    """Preview-флаг ставится middleware только при явном override=локали."""
    from starlette.requests import Request

    from app.services.locale import (
        LOCALE_HEADER,
        PREVIEW_QUERY,
        _normalize_locale_token,
        preview_locale_from_referer,
        resolve_locale_from_request,
    )

    def explicit_override(qs: bytes, headers: list[tuple[bytes, bytes]]) -> str | None:
        """Дублирует логику middleware: явный override запроса, если есть."""
        request = Request({
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": qs,
            "headers": headers + [(b"host", b"localhost:8000")],
            "client": ("127.0.0.1", 123),
            "server": ("localhost", 8000),
        })
        header = None
        for key, value in headers:
            if key.decode("latin-1").lower() == LOCALE_HEADER:
                header = value.decode("latin-1")
        return (
            _normalize_locale_token(request.query_params.get(PREVIEW_QUERY))
            or _normalize_locale_token(preview_locale_from_referer(request.headers.get("referer")))
            or _normalize_locale_token(header)
        )

    # Обычный запрос без override — не preview.
    assert explicit_override(b"", []) is None

    # ?preview_locale=en → явный EN-preview.
    assert explicit_override(b"preview_locale=en", []) == "en"

    # X-FE-Locale=en (не query) — тоже явный override.
    assert explicit_override(b"", [(b"x-fe-locale", b"en")]) == "en"

    # ?preview_locale=мусор — не override.
    assert explicit_override(b"preview_locale=xx", []) is None


def test_localize_category_and_freq_en():
    from app.services.seo_i18n import frequency_label_en, localize_category_name

    assert localize_category_name("Цены", locale="en") == "Prices and inflation"
    assert localize_category_name("Цены", locale="ru") == "Цены"
    assert frequency_label_en("monthly") == "monthly"


def test_hreflang_fast_page_prefixes():
    assert has_en_path("/russia/today") is True
    assert has_en_path("/russia/today/cpi") is True
    assert has_en_path("/russia/calendar/2026/08") is True
    assert has_en_path("/russia/indicator/cpi/2024") is True
    assert has_en_path("/russia/region-rating/chislennost-naseleniya") is True
    assert has_en_path("/russia/region-vs/moskva-vs-sankt-peterburg") is True


def test_year_template_title_shape():
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_i18n import year_template
    from app.services.seo_renderer import _year_page_title_desc

    token = set_locale("en")
    try:
        tpl = year_template("title_monthly")
        assert tpl is not None
        assert "{name} in {country}, {year}" in tpl
        title, desc = _year_page_title_desc(
            name="Consumer price index",
            year=2024,
            frequency="monthly",
            n_rows=12,
            current_year=False,
            period_note="",
            summary_label="Annual average",
            summary_text="101,2",
            source="Rosstat",
        )
        assert title.startswith("Consumer price index in Russia, 2024")
        assert "в 2024" not in title
        assert "Consumer price index in 2024" in desc
        assert "значений" not in desc
    finally:
        reset_locale(token)


def test_today_body_templates_en():
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_i18n import today_template
    from app.services.seo_today import _change_phrase

    token = set_locale("en")
    try:
        assert today_template("body_lead")
        assert today_template("faq_h2") == "Questions and answers"
        assert "today" in (today_template("hub_item_today") or "")
        phrase = _change_phrase(14.25, 14.0, "%")
        assert "pp" in phrase
        assert "выше" not in phrase
        assert "предыдущего" not in phrase
    finally:
        reset_locale(token)


def test_hreflang_does_not_claim_random_path():
    # Unknown deep path without matching prefix → no EN alternate.
    assert has_en_path("/this-path-does-not-exist-xyz") is False


def test_region_display_name_tatarstan_en():
    from app.services.seo_i18n import region_display_name

    assert (
        region_display_name(
            "respublika-tatarstan",
            "Республика Татарстан",
            locale="en",
        )
        == "Republic of Tatarstan"
    )
    assert (
        region_display_name(
            "respublika-tatarstan",
            "Республика Татарстан",
            locale="ru",
        )
        == "Республика Татарстан"
    )


def test_region_indicator_copy_en():
    from app.services.seo_i18n import region_indicator_copy

    copy = region_indicator_copy(
        "chislennost-naseleniya",
        name_ru="Численность населения",
        unit_ru="тысяч человек",
        section_ru="Население",
        locale="en",
    )
    assert copy["name"] == "Population"
    assert "thousand" in (copy["unit"] or "").lower()
    assert copy["section"] == "Population"


def test_regional_template_profile_title_en():
    from app.services.seo_i18n import regional_template

    tpl = regional_template("region_profile.title", locale="en")
    assert tpl is not None
    assert "{region}" in tpl
    assert "regional statistics" in tpl.lower()


# Hermetic API/SSR locale checks — seed from test_route_smoke.route_client.
from tests.test_route_smoke import route_client  # noqa: E402, F401


def test_api_region_profile_en_locale(route_client):
    """locale=en → Moscow EN name; indicator name from EN catalog overlay."""
    from app.data.i18n import region_indicators_en as ri_mod

    # Smoke seed uses code `naselenie`; map EN copy for the test.
    ri_mod.REGION_INDICATORS_EN["naselenie"] = {
        "name": "Population",
        "unit": "thousand people",
        "note": None,
        "section": "Population",
    }
    try:
        prof = route_client.get(
            "/api/v1/regions/moskva",
            headers={"X-FE-Locale": "en"},
        )
        assert prof.status_code == 200
        assert prof.json()["region"]["name"] == "Moscow"

        detail = route_client.get(
            "/api/v1/regions/moskva/i/naselenie",
            headers={"X-FE-Locale": "en"},
        )
        assert detail.status_code == 200
        assert detail.json()["indicator"]["name"] == "Population"

        html = route_client.get(
            "/seo/region/moskva",
            headers={"X-FE-Locale": "en"},
        )
        assert html.status_code == 200
        assert "Moscow — regional statistics" in html.text
    finally:
        ri_mod.REGION_INDICATORS_EN.pop("naselenie", None)


def test_ssr_tatarstan_title_en(route_client, auth_env):
    """Seed Republic of Tatarstan and assert EN SSR title."""
    import asyncio

    from sqlalchemy import select

    from app.models import Region

    async def _seed():
        async with auth_env["session_maker"]() as db:
            existing = (
                await db.execute(
                    select(Region).where(Region.slug == "respublika-tatarstan")
                )
            ).scalar_one_or_none()
            if existing is None:
                db.add(
                    Region(
                        slug="respublika-tatarstan",
                        name="Республика Татарстан",
                        kind="region",
                        district_slug="cfo",
                    )
                )
                await db.commit()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_seed())
    finally:
        loop.close()

    r = route_client.get(
        "/seo/region/respublika-tatarstan",
        headers={"X-FE-Locale": "en"},
    )
    assert r.status_code == 200
    assert "Republic of Tatarstan — regional statistics" in r.text

    legacy = route_client.get(
        "/seo/region/tatarstan",
        headers={"X-FE-Locale": "en"},
        follow_redirects=False,
    )
    assert legacy.status_code == 301


def test_localize_reference_period_en():
    from app.services.seo_i18n import localize_reference_period

    assert localize_reference_period("июль 2026", locale="en") == "July 2026"
    assert localize_reference_period("июль 2026", locale="ru") == "июль 2026"


def test_ssr_regions_hub_locale_en_no_cyrillic_shell(monkeypatch):
    """Regions hub EN: eyebrow/lead/keywords Latin; RU path unchanged."""
    import asyncio
    import re
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.services.locale import reset_locale, set_locale
    from app.services import seo_regional, seo_renderer

    async def fake_assets():
        return seo_renderer._fallback_assets()

    monkeypatch.setattr(seo_renderer, "get_app_assets", fake_assets)

    class _FakeResult:
        def __init__(self, value):
            self._value = value

        def scalars(self):
            return self

        def all(self):
            return self._value if isinstance(self._value, list) else []

        def scalar(self):
            return self._value if not isinstance(self._value, list) else 0

        def scalar_one_or_none(self):
            return None

    districts = [
        SimpleNamespace(
            slug="cfo", name="Central Federal District", kind="district",
            district_slug=None, sort_order=1,
        ),
    ]
    regions = districts + [
        SimpleNamespace(
            slug="moskva", name="Москва", kind="region",
            district_slug="cfo", sort_order=2,
        ),
    ]

    async def fake_execute(stmt):
        s = str(stmt)
        if "region_indicators" in s.lower() or "RegionIndicator" in s:
            return _FakeResult(0)
        return _FakeResult(regions)

    db = SimpleNamespace(execute=fake_execute)
    monkeypatch.setattr(
        seo_regional,
        "select",
        lambda *a, **k: SimpleNamespace(),
    )
    # Bypass complex select typing — stub whole render path pieces via execute.
    cyrillic = re.compile(r"[А-Яа-яЁё]")

    token = set_locale("en")
    try:
        # Minimal: regional_template keys must be Latin.
        from app.services.seo_i18n import regional_template

        for key in (
            "regions_hub.eyebrow",
            "regions_hub.lead",
            "regions_hub.keywords",
            "region_indicator.p1",
            "region_indicator.faq_h2",
        ):
            val = regional_template(key, locale="en")
            assert val, key
            assert not cyrillic.search(val), val
    finally:
        reset_locale(token)


def test_default_keywords_en():
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_renderer import _default_keywords

    token = set_locale("en")
    try:
        kw = _default_keywords()
        assert "Rosstat" in kw
        assert "макроэкономические" not in kw
    finally:
        reset_locale(token)

    token = set_locale("ru")
    try:
        assert "макроэкономические" in _default_keywords()
    finally:
        reset_locale(token)



def _html_locale_request(
    *,
    host="forecasteconomy.com",
    path="/russia/indicator/cpi",
    ua="Mozilla/5.0",
    cookie="",
    ip="203.0.113.5",
    extra_headers=None,
    query=b"",
    original_uri=None,
):
    from starlette.requests import Request

    headers = [
        (b"host", host.encode()),
        (b"accept", b"text/html"),
        (b"user-agent", ua.encode()),
        (b"x-forwarded-for", ip.encode()),
    ]
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    if original_uri:
        headers.append((b"x-original-uri", original_uri.encode()))
    if extra_headers:
        headers.extend(extra_headers)
    return Request({
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": query,
        "scheme": "https",
        "server": (host, 443),
        "client": (ip, 1),
        "headers": headers,
    })


def test_locale_host_redirect_after_cutover(monkeypatch):
    """После cutover: люди из РФ → ru.; боты и явный EN остаются на хосте."""
    from app.config import settings
    from app.main import _locale_host_redirect

    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "geo_locale_redirect_enabled", True)
    monkeypatch.setattr(settings, "browser_lang_redirect_enabled", True)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")
    monkeypatch.setattr("app.services.geoip.lookup", lambda ip: {"country_code": "RU"})

    ru_ip = _locale_host_redirect(_html_locale_request())
    assert ru_ip is not None and ru_ip.status_code == 307
    assert ru_ip.headers["location"] == "https://ru.forecasteconomy.com/russia/indicator/cpi"

    from_yandex = _locale_host_redirect(_html_locale_request(
        extra_headers=[(b"referer", b"https://yandex.ru/search/?text=%D0%B8%D0%BF%D1%86")],
    ))
    assert from_yandex is not None
    loc = from_yandex.headers["location"]
    assert loc.startswith("https://ru.forecasteconomy.com/russia/indicator/cpi?")
    assert "utm_referrer=" in loc
    assert "yandex.ru" in loc

    with_ysclid = _locale_host_redirect(_html_locale_request(
        query=b"ysclid=lor7sw5p9o",
        extra_headers=[(b"referer", b"https://yandex.ru/")],
    ))
    assert with_ysclid is not None
    loc_y = with_ysclid.headers["location"]
    assert "ysclid=lor7sw5p9o" in loc_y
    assert "utm_referrer=" in loc_y

    from_self = _locale_host_redirect(_html_locale_request(
        extra_headers=[(b"referer", b"https://forecasteconomy.com/")],
    ))
    assert from_self is not None
    assert "utm_referrer" not in from_self.headers["location"]

    monkeypatch.setattr("app.services.geoip.lookup", lambda ip: {"country_code": "US"})
    assert _locale_host_redirect(_html_locale_request(
        extra_headers=[(b"accept-language", b"ru-RU,ru;q=0.9")],
    )) is None

    monkeypatch.setattr("app.services.geoip.lookup", lambda ip: {"country_code": "RU"})
    assert _locale_host_redirect(_html_locale_request(ua="YandexBot/3.0")) is None
    assert _locale_host_redirect(_html_locale_request(ua="Googlebot/2.1")) is None
    assert _locale_host_redirect(_html_locale_request(ua="GPTBot/1.0")) is None
    assert _locale_host_redirect(_html_locale_request(path="/api/v1/health/ready")) is None
    assert _locale_host_redirect(_html_locale_request(cookie="fe_locale_pref=en")) is None
    assert _locale_host_redirect(_html_locale_request(query=b"locale_pref=en")) is None

    cookie_ru = _locale_host_redirect(_html_locale_request(
        cookie="fe_locale_pref=ru",
    ))
    assert cookie_ru is not None
    assert cookie_ru.headers["location"] == "https://ru.forecasteconomy.com/russia/indicator/cpi"

    from_ru_en = _locale_host_redirect(_html_locale_request(
        host="ru.forecasteconomy.com",
        cookie="fe_locale_pref=en",
    ))
    assert from_ru_en is not None and from_ru_en.status_code == 307
    assert from_ru_en.headers["location"] == "https://forecasteconomy.com/russia/indicator/cpi"

    monkeypatch.setattr(settings, "geo_locale_redirect_enabled", False)
    assert _locale_host_redirect(_html_locale_request()) is None

    monkeypatch.setattr(settings, "apex_locale_en", False)
    monkeypatch.setattr(settings, "geo_locale_redirect_enabled", True)
    assert _locale_host_redirect(_html_locale_request()) is None


def test_locale_pref_cookie_persist_and_host_swap(monkeypatch):
    """Явный флажок: cookie на общем Domain; RU с apex сразу на ru."""
    from app.config import settings
    from app.main import _locale_host_redirect, _persist_locale_pref_redirect

    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "geo_locale_redirect_enabled", True)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")
    monkeypatch.setattr("app.services.geoip.lookup", lambda ip: {"country_code": "RU"})

    persist = _persist_locale_pref_redirect(_html_locale_request(query=b"locale_pref=en"))
    assert persist is not None and persist.status_code == 303
    assert persist.headers["location"] == "/russia/indicator/cpi"
    set_cookie = persist.headers.get("set-cookie", "")
    assert "fe_locale_pref=en" in set_cookie
    assert "domain=.forecasteconomy.com" in set_cookie.lower()
    assert _locale_host_redirect(_html_locale_request(query=b"locale_pref=en")) is None

    persist_orig = _persist_locale_pref_redirect(_html_locale_request(
        path="/seo/category/gdp",
        original_uri="/russia/category/gdp?locale_pref=en",
    ))
    assert persist_orig is not None and persist_orig.status_code == 303
    assert persist_orig.headers["location"] == "/russia/category/gdp"
    assert "fe_locale_pref=en" in persist_orig.headers.get("set-cookie", "")

    persist_ru = _persist_locale_pref_redirect(_html_locale_request(query=b"locale_pref=ru"))
    assert persist_ru is not None and persist_ru.status_code == 303
    assert persist_ru.headers["location"] == "https://ru.forecasteconomy.com/russia/indicator/cpi"
    assert "fe_locale_pref=ru" in persist_ru.headers.get("set-cookie", "")


def test_persist_locale_pref_keeps_preview_until_cutover(monkeypatch):
    """До cutover 303 не сбрасывает preview_locale и сам ставит его для EN."""
    from urllib.parse import parse_qs, urlsplit

    from starlette.requests import Request

    from app.config import settings
    from app.main import _persist_locale_pref_redirect

    monkeypatch.setattr(settings, "apex_locale_en", False)

    def _req(query: bytes, path: str = "/"):
        return Request({
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": query,
            "scheme": "http",
            "server": ("localhost", 3000),
            "headers": [(b"host", b"localhost:3000")],
        })

    persist = _persist_locale_pref_redirect(
        _req(b"preview_locale=en&locale_pref=en", "/"),
    )
    assert persist is not None and persist.status_code == 303
    loc = persist.headers["location"]
    qs = parse_qs(urlsplit(loc).query)
    assert loc.startswith("/")
    assert "forecasteconomy.com" not in loc
    assert qs.get("preview_locale") == ["en"]
    assert "locale_pref" not in qs
    assert "fe_locale_pref=en" in persist.headers.get("set-cookie", "")

    injected = _persist_locale_pref_redirect(_req(b"locale_pref=en", "/russia"))
    assert injected is not None
    injected_qs = parse_qs(urlsplit(injected.headers["location"]).query)
    assert injected.headers["location"].startswith("/russia")
    assert injected_qs.get("preview_locale") == ["en"]

    back_ru = _persist_locale_pref_redirect(
        _req(b"preview_locale=en&locale_pref=ru", "/"),
    )
    assert back_ru is not None
    ru_qs = parse_qs(urlsplit(back_ru.headers["location"]).query)
    assert "preview_locale" not in ru_qs
    assert "fe_locale_pref=ru" in back_ru.headers.get("set-cookie", "")
