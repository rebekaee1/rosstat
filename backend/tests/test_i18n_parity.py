"""Locale resolver + i18n parity guards."""

from __future__ import annotations

from app.data.i18n.en_catalog import has_en_path
from app.data.i18n.glossary_en import GLOSSARY_EN
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
from app.data.i18n.seo_en import CATEGORY_META_EN, PAGE_META_EN
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
from app.services.seo_i18n import get_category_seo, get_page_seo

# Stub-regression guard: content agent restores ~167 codes; a wiped stub fails here.
_INDICATOR_COPY_EN_MIN = 160
_INDICATOR_COPY_EN_REQUIRED = ("cpi", "cpi-food", "wages-nominal", "key-rate")


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
        assert 'href="https://ru.forecasteconomy.com/russia/indicator/cpi"' in html
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
    from app.services.seo_i18n import public_indicator_seo, translate_source

    assert translate_source("Росстат", locale="en") == "Rosstat"
    assert translate_source("Банк России", locale="en") == "Bank of Russia"
    assert translate_source("Минфин", locale="en") == "Ministry of Finance"

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
        assert ">Indicators<" in header
        assert ">Today<" in header
        assert ">Regions<" in header
        assert ">Calendar<" in header
        assert ">About<" in header
        assert "Индикаторы" not in header
        assert "О проекте" not in header

        deep = _ssr_platform_deep_links()
        assert "Platform sections" in deep
        assert "Разделы платформы" not in deep

        nf = render_not_found_html()
        assert "Page not found" in nf
        assert ">Indicators<" in nf
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
        assert ">Indicators<" in pure
        assert "Open the platform" in pure
        assert "Открыть платформу" not in pure
    finally:
        reset_locale(token)

    token_ru = set_locale("ru")
    try:
        assert "Индикаторы" in _ssr_chrome_header()
        assert "Разделы платформы" in _ssr_platform_deep_links()
        assert "Страница не найдена" in render_not_found_html()
    finally:
        reset_locale(token_ru)


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
        assert "{name} in {year}" in tpl
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
        assert title.startswith("Consumer price index in 2024")
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

