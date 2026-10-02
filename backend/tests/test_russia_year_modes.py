"""A period destination must display the exact stored series selected by its mode."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest
from bs4 import BeautifulSoup

from app.data.legacy_redirects import resolve_unlisted_indicator
from app.data.view_model_families import FAMILIES
from app.models import Indicator, IndicatorData
from app.services.search_intent import SearchIntent
from app.services.search_paths import russia_period_data_code, russia_year_mode_paths, russia_year_search_path


def test_every_registered_mode_resolves_exactly_without_code_guessing():
    for family in FAMILIES:
        assert russia_period_data_code(family.base, None) == family.base
        assert russia_period_data_code(family.base, "not-a-real-mode") is None
        for mode in family.modes:
            assert russia_period_data_code(family.base, mode.mode) == mode.code
    # Registered code overrides are deliberately unlike a concatenated token.
    assert russia_period_data_code("gdp-nominal", "yoy") == "gdp-yoy"
    assert russia_period_data_code("wages-nominal", "avg-year") == "wages-nominal-annual"
    assert russia_period_data_code("unemployment", "annual") == "unemployment-annual"
    assert russia_period_data_code("unknown-indicator", "yoy") is None


@pytest.mark.parametrize("group,token", [("yoy", "yoy-year"), ("pop", "pop-gg")])
def test_search_year_path_keeps_requested_group_for_shared_series(group, token):
    intent = SearchIntent("", "", ((f"search-mode-{group}",),), year=2024)
    path = russia_year_search_path("budget-deficit-yoy-year", intent, 2024)
    assert path == f"/russia/indicator/budget-deficit/2024?mode={token}"
    parsed = urlsplit(path)
    assert russia_period_data_code("budget-deficit", parse_qs(parsed.query)["mode"][0]) == "budget-deficit-yoy-year"


def test_year_path_rejects_retired_different_series_and_invalid_year():
    intent = SearchIntent("", "", (), year=2024)
    assert russia_year_search_path("wages-nominal-annual", intent, 2024) == "/russia/indicator/wages-nominal/2024?mode=avg-year"
    assert russia_year_search_path("steel-avg-year", intent, 2024) is None
    assert russia_year_search_path("copper-avg-week", intent, 2024) is None
    assert russia_year_search_path("wages-nominal", intent, 9999) is None


def test_year_mode_paths_enumerate_all_registered_aliases_and_exact_bespoke_only():
    pairs = russia_year_mode_paths("budget-deficit-yoy-year", 2024)
    assert set(pairs) == {("budget-deficit", f"/russia/indicator/budget-deficit/2024?mode={mode}")
        for mode in ("yoy-year", "pop-gg")}
    assert russia_year_mode_paths("unemployment-annual", 2024) == (("unemployment", "/russia/indicator/unemployment/2024?mode=annual"),)
    assert russia_year_mode_paths("copper-avg-week", 2024) == ()


@pytest.fixture
def mode_year_client(auth_env, auth_client):
    async def seed():
        async with auth_env["session_maker"]() as db:
            definitions = [
                ("gdp-nominal", "ВВП в текущих ценах", "GDP at current prices", "млрд руб.", "quarterly", True),
                ("gdp-yoy", "ВВП — к соответствующему кварталу прошлого года", "GDP — year over year", "%", "quarterly", False),
                ("wages-nominal", "Номинальная заработная плата", "Nominal wages", "руб.", "monthly", True),
                ("wages-nominal-annual", "Номинальная заработная плата — средняя за год", "Nominal wages — annual average", "руб.", "annual", False),
                ("eur-usd", "Курс евро к доллару", "EUR/USD exchange rate", "$", "daily", True),
                ("eur-usd-avg-year", "Курс евро к доллару — средняя за год", "EUR/USD exchange rate — annual average", "$", "annual", False),
            ]
            by_code = {}
            for code, name, name_en, unit, frequency, listed in definitions:
                indicator = Indicator(code=code, name=name, name_en=name_en, unit=unit,
                    frequency=frequency, category="ВВП", source="Росстат",
                    is_active=True, is_listed=listed)
                db.add(indicator)
                by_code[code] = indicator
            await db.flush()
            points = {
                "gdp-nominal": [(2022, 1, 90000), (2024, 1, 95000), (2024, 4, 96000)],
                "gdp-yoy": [(2022, 1, float("inf")), (2023, 1, 3.25), (2024, 1, 4.5), (2024, 4, 5.5), (2024, 12, float("inf")), (2025, 1, 6.25)],
                "wages-nominal": [(2024, 1, 80000), (2024, 2, 81000)],
                "wages-nominal-annual": [(2023, 1, 76000), (2024, 1, 87000), (2025, 1, 97000)],
                "eur-usd": [(2024, 1, 1.1)],
                "eur-usd-avg-year": [(2024, 1, 1.08)],
            }
            for code, values in points.items():
                for year, month, value in values:
                    db.add(IndicatorData(indicator_id=by_code[code].id, date=date(year, month, 1), value=value))
            await db.commit()
    asyncio.run(seed())
    return auth_client


@pytest.mark.parametrize("locale", ["ru", "en"])
def test_year_mode_renders_actual_values_native_title_unit_and_navigation(mode_year_client, locale, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "apex_locale_en", True)
    host = "ru.forecasteconomy.com" if locale == "ru" else "forecasteconomy.com"
    response = mode_year_client.get("/seo/indicator-year/gdp-nominal/2024?mode=yoy", headers={"Host": host})
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    suffix = "к соответствующему кварталу прошлого года" if locale == "ru" else "Nominal GDP growth YoY"
    assert suffix in soup.title.text
    assert suffix in soup.h1.text
    assert "4,5" in soup.text if locale == "ru" else "4.5" in soup.text
    assert "5,5" in soup.text if locale == "ru" else "5.5" in soup.text
    assert "%" in soup.select_one("table").text
    assert "95\u202f000" not in soup.text and "96\u202f000" not in soup.text
    canonical = soup.select_one('link[rel="canonical"]')["href"]
    assert canonical.endswith("/russia/indicator/gdp-nominal/2024?mode=yoy")
    for year in (2023, 2025):
        assert soup.select_one(f'a[href="/russia/indicator/gdp-nominal/{year}?mode=yoy"]')
    assert not soup.select_one('a[href="/russia/indicator/gdp-nominal/2022?mode=yoy"]')
    assert soup.select_one('.seo-chart a')["href"] == "/russia/indicator/gdp-nominal?mode=yoy#chart"
    assert soup.select_one('.seo-chart img')["src"] == "/og/russia/gdp-yoy/2024.png"
    assert soup.select_one('meta[property="og:image"]')["content"].endswith("/og/russia/gdp-yoy/2024.png")
    datasets = [json.loads(tag.text) for tag in soup.select('script[type="application/ld+json"]')]
    dataset = next(item for item in datasets if item.get("@type") == "Dataset")
    assert dataset["url"] == canonical
    assert suffix in dataset["variableMeasured"]


def test_annual_mode_reads_registered_override_and_base_year_still_reads_source(mode_year_client):
    selected = mode_year_client.get("/seo/indicator-year/wages-nominal/2024?mode=avg-year")
    assert selected.status_code == 200
    soup = BeautifulSoup(selected.text, "html.parser")
    assert "средняя за год" in soup.title.text and "средняя за год" in soup.h1.text
    assert "87\u202f000" in soup.text and "руб." in soup.text
    assert soup.select_one('.seo-chart img')["src"] == "/og/russia/wages-nominal-annual/2024.png"
    base = mode_year_client.get("/seo/indicator-year/wages-nominal/2024")
    assert base.status_code == 200 and "80\u202f000" in base.text
    assert BeautifulSoup(base.text, "html.parser").select_one('link[rel="canonical"]')["href"].endswith("/wages-nominal/2024")


@pytest.mark.parametrize("path", [
    "/seo/indicator-year/gdp-nominal/2024?mode=not-a-real-mode",
    "/seo/indicator-year/gdp-nominal/2024?mode=qoq",  # Registered, absent sibling.
    "/seo/indicator-year/gdp-nominal/2022?mode=yoy",  # Only nonfinite observations.
    "/seo/indicator-year/gdp-nominal/2021?mode=yoy",  # Source coverage never substitutes.
])
def test_unknown_missing_or_nonfinite_mode_year_is_truthful_404(mode_year_client, path):
    response = mode_year_client.get(path)
    assert response.status_code == 404
    assert response.headers["x-robots-tag"] == "noindex, follow"


def test_sibling_year_redirect_preserves_registered_mode_and_attribution(mode_year_client):
    response = mode_year_client.get("/seo/indicator-year/gdp-yoy/2024?mode=ignored&ysclid=abc", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "/russia/indicator/gdp-nominal/2024?mode=yoy&ysclid=abc"
    assert resolve_unlisted_indicator("gdp-yoy") == "/russia/indicator/gdp-nominal?mode=yoy"
    landed = mode_year_client.get("/seo/indicator-year/gdp-nominal/2024?mode=yoy")
    assert landed.status_code == 200 and "4,5" in landed.text


def test_currency_and_legacy_path_cut_redirects_keep_mode(mode_year_client):
    for code, public_prefix in [("eur-usd", "currencies"), ("wages-nominal", "russia")]:
        response = mode_year_client.get(f"/seo/indicator-year/{code}/2024?mode=avg-year", follow_redirects=False,
            headers={"X-Path-Cut-Legacy": "1", "X-Original-URI": f"/indicator/{code}/2024?mode=avg-year"})
        assert response.status_code == 301
        assert response.headers["location"] == f"/{public_prefix}/indicator/{code}/2024?mode=avg-year"
    response = mode_year_client.get("/seo/indicator-year/eur-usd/2024?mode=avg-year", follow_redirects=False,
        headers={"X-Original-URI": "/russia/indicator/eur-usd/2024?mode=avg-year"})
    assert response.headers["location"] == "/currencies/indicator/eur-usd/2024?mode=avg-year"


def test_mode_year_hreflang_and_locale_switch_match_mode_canonical(mode_year_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "apex_locale_en", True)
    response = mode_year_client.get("/seo/indicator-year/wages-nominal/2024?mode=avg-year", headers={"Host": "ru.forecasteconomy.com"})
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    for locale in ("ru", "en", "x-default"):
        assert soup.select_one(f'link[hreflang="{locale}"]')["href"].endswith("/wages-nominal/2024?mode=avg-year")
    assert soup.select_one("a.seo-lang")["href"].endswith("/wages-nominal/2024?mode=avg-year")


def test_mode_year_cache_follows_materialized_series_and_separates_modes(mode_year_client, monkeypatch):
    from app.api import seo_pages
    calls = []
    async def capture(namespace, variant, ttl, render, **kwargs):
        calls.append((namespace, variant))
        return await render()
    monkeypatch.setattr(seo_pages, "_cached_html", capture)
    for mode in ("avg-year", "level"):
        assert mode_year_client.get(f"/seo/indicator-year/wages-nominal/2024?mode={mode}").status_code == 200
    assert calls[0][0] == "wages-nominal-annual"
    assert calls[1][0] == "wages-nominal"
    assert calls[0][1] != calls[1][1]


def test_linked_year_image_reads_native_selected_series(mode_year_client, monkeypatch):
    from app.api import sitemap
    captured = {}
    monkeypatch.setattr("app.services.og_image.cached_og", lambda *_args, **_kwargs: None)
    async def capture_render(_renderer, **kwargs):
        captured.update(kwargs)
        return b"\x89PNG\r\n\x1a\n"
    async def skip_store(*_args, **_kwargs):
        return None
    monkeypatch.setattr(sitemap, "render_og_async", capture_render)
    monkeypatch.setattr("app.services.og_image.store_og_async", skip_store)
    response = mode_year_client.get("/api/v1/og-image/indicator/wages-nominal-annual/2024.png")
    assert response.status_code == 200
    assert float(captured["value_text"].replace(",", ".")) == 87000
    assert captured["unit_suffix"] == "руб."
    assert "средняя за год" in captured["name"]
    assert captured["values"] == [76000.0, 87000.0, 97000.0]


def test_sitemap_year_modes_match_actual_finite_series_canonical_and_lastmod(mode_year_client, auth_env):
    from app.services.site_urls import _year_urls, is_recrawl_eligible
    async def collect():
        async with auth_env["session_maker"]() as db:
            return await _year_urls(db, date(2026, 10, 1))
    urls = asyncio.run(collect())
    by_path = {item.path: item for item in urls}
    assert len(by_path) == len(urls)
    wanted = {
        "/russia/indicator/gdp-nominal/2024?mode=yoy": "2024-04-01",
        "/russia/indicator/wages-nominal/2024?mode=avg-year": "2024-01-01",
        "/russia/indicator/wages-nominal/2024?mode=level": "2024-02-01",
        "/currencies/indicator/eur-usd/2024?mode=avg-year": "2024-01-01",
    }
    for path, lastmod in wanted.items():
        assert by_path[path].lastmod == lastmod
        assert is_recrawl_eligible(path)
    assert "/russia/indicator/gdp-nominal/2022?mode=yoy" not in by_path
    assert "/russia/indicator/gdp-nominal/2024?mode=qoq" not in by_path
    assert not any("/gdp-yoy/" in path or "/wages-nominal-annual/" in path for path in by_path)
    # Every emitted mode period uses the public parent URL, renders 200 and
    # declares that exact query-preserving canonical rather than a base year.
    for path in (path for path in by_path if "?mode=" in path):
        parsed = urlsplit(path)
        parent, year = parsed.path.rsplit("/", 2)[-2:]
        response = mode_year_client.get(f"/seo/indicator-year/{parent}/{year}?{parsed.query}")
        assert response.status_code == 200, path
        canonical = BeautifulSoup(response.text, "html.parser").select_one('link[rel="canonical"]')["href"]
        assert canonical.endswith(path)
    assert not is_recrawl_eligible("/russia/indicator/gdp-nominal/2024?mode=made-up")
    assert not is_recrawl_eligible("/russia/indicator/gdp-nominal/2024?mode=yoy&extra=1")


def test_sitemap_modes_require_active_parent_and_use_batched_year_metadata(mode_year_client, auth_env):
    from sqlalchemy import event, update
    from app.services.site_urls import _year_urls
    async def collect():
        async with auth_env["session_maker"]() as db:
            # A materialized mode cannot publish an inactive parent card.
            await db.execute(update(Indicator).where(Indicator.code == "eur-usd").values(is_active=False))
            await db.commit()
            engine = db.get_bind()
            calls = []
            def record(_conn, _cursor, statement, *_args):
                if statement.lstrip().upper().startswith("SELECT"):
                    calls.append(statement)
            event.listen(engine, "before_cursor_execute", record)
            try:
                urls = await _year_urls(db, date(2026, 10, 1))
            finally:
                event.remove(engine, "before_cursor_execute", record)
            assert len(calls) == 2  # One code/year aggregate + active parent metadata.
            return urls
    paths = {item.path for item in asyncio.run(collect())}
    assert not any(path.startswith("/currencies/indicator/eur-usd/") for path in paths)
