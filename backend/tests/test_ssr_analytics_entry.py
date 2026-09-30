"""SSR must escape the pre-September immutable cache of its fixed JS entry."""
import asyncio
from urllib.parse import parse_qs, urlsplit

import pytest
from bs4 import BeautifulSoup

from app.services import locale, seo_renderer as renderer


def collector_url(html):
    scripts = BeautifulSoup(html, "html.parser").find_all("script", src=True)
    return next(s["src"] for s in scripts if "behavior-standalone.js" in s["src"])


def annual_document(monkeypatch, build):
    async def assets():
        return renderer.AppAssets(
            '<link rel="stylesheet" href="/assets/main-test.css">',
            f'<script type="module" src="/assets/main-{build}.js"></script>',
        )

    monkeypatch.setattr(renderer, "get_app_assets", assets)
    return asyncio.run(renderer.build_document(
        title="АИ-95 в 2022", description="Тест",
        canonical_path="/russia/indicator/fuel-ai95/2022",
        body='<main><h1>АИ-95 в 2022</h1></main>', include_app=False,
    ))


@pytest.mark.parametrize("language", ["ru", "en"])
def test_annual_entry_escapes_legacy_immutable_cache(monkeypatch, language):
    token = locale.set_locale(language)
    try:
        html = annual_document(monkeypatch, "release-a")
    finally:
        locale.reset_locale(token)
    src = collector_url(html)
    # A browser with the bare URL cached immutable for a year must request a
    # different cache key. Changing origin response headers alone cannot do it.
    assert src != "/assets/behavior-standalone.js"
    assert urlsplit(src).path == "/assets/behavior-standalone.js"
    assert parse_qs(urlsplit(src).query)["v"]
    assert "/assets/main-release-a.js" not in html


def test_entry_version_is_stable_for_build_and_changes_with_release(monkeypatch):
    first = collector_url(annual_document(monkeypatch, "release-a"))
    same = collector_url(annual_document(monkeypatch, "release-a"))
    next_release = collector_url(annual_document(monkeypatch, "release-b"))
    assert first == same
    assert first != next_release


def test_not_found_and_asset_discovery_fallback_also_escape_bare_cache(monkeypatch):
    monkeypatch.setattr(renderer, "_APP_ASSETS", None)
    src = collector_url(renderer.render_not_found_html())
    assert src != "/assets/behavior-standalone.js"
    assert parse_qs(urlsplit(src).query)["v"]
