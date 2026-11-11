"""Возврат русской аудитории в Google (решение владельца 11.11.2026).

1. Старые адреса до языкового сплита (``X-Path-Cut-Legacy: 1``) с английского apex
   ведут 301 на ту же страницу ``ru.``; на ``ru.``, localhost и без сплита — относительно.
2. На ``ru.`` годовые страницы стран мира и их регионов получают
   ``<meta name="googlebot" content="noindex, follow">``; Россия, валюты, рейтинги,
   карточки и apex (EN) — без метки.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services import site_paths as paths
from app.services.index_policy import (
    GOOGLEBOT_NOINDEX_META,
    googlebot_meta_for_path,
    is_ru_google_noindex_path,
)


def _legacy(path: str, host: str):
    from app.main import app

    return TestClient(app).get(
        path, follow_redirects=False,
        headers={"X-Path-Cut-Legacy": "1", "Host": host, "User-Agent": "Googlebot/2.1"},
    )


class TestLegacyRedirectToRu:
    def test_apex_legacy_indicator_goes_to_ru_host(self, monkeypatch):
        monkeypatch.setattr(settings, "apex_locale_en", True)
        r = _legacy("/seo/indicator/cpi", "forecasteconomy.com")
        assert r.status_code == 301
        assert r.headers["location"] == "https://ru.forecasteconomy.com" + paths.russia_indicator("cpi")

    def test_apex_legacy_year_goes_to_ru_host(self, monkeypatch):
        monkeypatch.setattr(settings, "apex_locale_en", True)
        r = _legacy("/seo/indicator-year/key-rate/2025", "forecasteconomy.com")
        assert r.status_code == 301
        assert r.headers["location"] == (
            "https://ru.forecasteconomy.com" + paths.russia_indicator_year("key-rate", 2025)
        )

    def test_www_counts_as_apex(self, monkeypatch):
        monkeypatch.setattr(settings, "apex_locale_en", True)
        r = _legacy("/seo/indicator/cpi", "www.forecasteconomy.com")
        assert r.headers["location"].startswith("https://ru.forecasteconomy.com/")

    def test_ru_host_stays_relative(self, monkeypatch):
        monkeypatch.setattr(settings, "apex_locale_en", True)
        r = _legacy("/seo/indicator/cpi", "ru.forecasteconomy.com")
        assert r.status_code == 301
        assert r.headers["location"] == paths.russia_indicator("cpi")

    def test_before_split_stays_relative(self, monkeypatch):
        monkeypatch.setattr(settings, "apex_locale_en", False)
        r = _legacy("/seo/indicator/cpi", "forecasteconomy.com")
        assert r.headers["location"] == paths.russia_indicator("cpi")

    def test_non_legacy_redirect_on_apex_stays_on_apex(self, monkeypatch):
        """Переименованный код на живом адресе — не старый русский адрес: остаётся на apex."""
        from app.main import app

        monkeypatch.setattr(settings, "apex_locale_en", True)
        r = TestClient(app).get(
            "/seo/indicator/inflation", follow_redirects=False,
            headers={"Host": "forecasteconomy.com", "User-Agent": "Googlebot/2.1"},
        )
        assert r.status_code == 301
        assert r.headers["location"] == paths.russia_indicator("cpi")


class TestRuGoogleNoindex:
    @pytest.mark.parametrize("path", [
        "/united-states/indicator/gdp/2020",
        "/germany/indicator/hicp-index/1999",
        "/united-states/region/colorado/bea-sainc5n-541/2008",
        "/netherlands/region/noord-holland/population/2015?mode=x",
    ])
    def test_world_year_pages_are_marked(self, path):
        assert is_ru_google_noindex_path(path)

    @pytest.mark.parametrize("path", [
        "/russia/indicator/key-rate/2025",
        "/russia/region/moskva/population/2020",
        "/currencies/indicator/usd-rub/2024",
        "/world/rating/gdp-usd/2020",
        "/united-states/indicator/gdp",
        "/united-states/indicator/gdp/2020-05",
        "/united-states/region/colorado",
        "/australia-vs-japan/hicp-index",
        "/",
    ])
    def test_other_pages_are_not_marked(self, path):
        assert not is_ru_google_noindex_path(path)

    def test_meta_only_on_russian_version(self, monkeypatch):
        monkeypatch.setattr(settings, "ru_google_noindex_world_years", True)
        assert googlebot_meta_for_path("/germany/indicator/gdp/2010", "ru") == GOOGLEBOT_NOINDEX_META
        assert googlebot_meta_for_path("/germany/indicator/gdp/2010", "en") == ""
        assert googlebot_meta_for_path("/russia/indicator/cpi/2010", "ru") == ""

    def test_flag_turns_it_off(self, monkeypatch):
        monkeypatch.setattr(settings, "ru_google_noindex_world_years", False)
        assert googlebot_meta_for_path("/germany/indicator/gdp/2010", "ru") == ""

    def test_document_head_carries_meta_and_keeps_robots_index(self, monkeypatch):
        from app.services.locale import reset_locale, set_locale
        from app.services.seo_renderer import AppAssets, compose_document

        monkeypatch.setattr(settings, "ru_google_noindex_world_years", True)
        assets = AppAssets(head_links="", body_scripts="")

        def doc(locale: str, path: str) -> str:
            token = set_locale(locale)
            try:
                return compose_document(
                    assets=assets, title="t", description="d", canonical_path=path,
                    body="<main>x</main>", include_app=False,
                )
            finally:
                reset_locale(token)

        ru_world = doc("ru", "/germany/indicator/gdp/2010")
        assert GOOGLEBOT_NOINDEX_META in ru_world
        assert '<meta name="robots" content="index, follow' in ru_world  # Яндекс индексирует
        assert GOOGLEBOT_NOINDEX_META not in doc("en", "/germany/indicator/gdp/2010")
        assert GOOGLEBOT_NOINDEX_META not in doc("ru", "/russia/indicator/cpi/2010")
