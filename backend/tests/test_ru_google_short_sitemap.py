"""Короткий sitemap для Google на ``ru.`` (решение владельца 13.11.2026, ADR-0030).

Робот Google на ``ru.`` получает по адресу ``/sitemap.xml`` индекс без трёх семейств
массовых годовых шардов. Яндекс, Bing, люди и apex (EN) получают полный индекс.
Адрес, ``robots.txt`` и сами файлы шардов одни для всех.
"""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from datetime import date

import pytest

from app.config import settings
from app.services import sitemap_static as sm
from app.services.index_policy import (
    google_short_sitemap_names,
    is_google_short_sitemap_excluded,
    is_google_sitemap_agent,
    ru_google_short_sitemap_enabled,
)
from app.services.site_urls import SiteUrl

RU = "ru.forecasteconomy.com"
APEX = "forecasteconomy.com"
GOOGLEBOT = (
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.8010.52 Mobile Safari/537.36 "
    "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)
YANDEXBOT = "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"
BINGBOT = "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
BROWSER = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"

# Порядок публикации (= порядок индекса) без трёх годовых семейств.
KEPT = [
    "core", "world-regions-1", "world-region-vs", "world-vs", "years", "months-1",
    "world-indicators-1", "regional-1",
]
MASS_YEARS = ["world-region-years-1", "regional-years-1", "world-years-1"]


class TestPolicy:
    def test_mass_year_families_are_excluded_and_order_kept(self):
        names = [
            "priority", "core", "today", "world-regions-1", "world-region-years-1",
            "world-region-years-307", "world-region-vs", "world-vs", "years", "months-2",
            "world-indicators-29", "regional-13", "regional-years-95", "world-years-555",
        ]
        assert google_short_sitemap_names(names) == [
            "priority", "core", "today", "world-regions-1", "world-region-vs", "world-vs",
            "years", "months-2", "world-indicators-29", "regional-13",
        ]

    @pytest.mark.parametrize("name", [
        "world-years-1", "world-region-years-42", "regional-years-95",
        "world-years", "world-region-years", "regional-years",  # старые генерации без номера
    ])
    def test_excluded(self, name):
        assert is_google_short_sitemap_excluded(name)

    @pytest.mark.parametrize("name", [
        "years", "months-1", "regional-1", "regional", "world-indicators-3", "world-regions-2",
        "world-region-vs", "world-vs", "priority", "core", "world", "world-ratings", "",
    ])
    def test_kept(self, name):
        assert not is_google_short_sitemap_excluded(name)

    def test_never_returns_an_empty_index(self):
        assert google_short_sitemap_names(["world-years-1", "regional-years-1"]) == [
            "world-years-1", "regional-years-1",
        ]

    @pytest.mark.parametrize("agent", [
        GOOGLEBOT,
        "Googlebot/2.1 (+http://www.google.com/bot.html)",
        "Googlebot-Image/1.0",
        "Mozilla/5.0 (compatible; Google-InspectionTool/1.0;)",
    ])
    def test_google_agents(self, agent):
        assert is_google_sitemap_agent(agent)

    @pytest.mark.parametrize("agent", [
        YANDEXBOT, BINGBOT, BROWSER, "GoogleOther", "AdsBot-Google (+http://www.google.com/adsbot.html)",
        "Mozilla/5.0 (compatible; YandexWebmaster/2.0; +http://yandex.com/bots)", "", None,
    ])
    def test_other_agents(self, agent):
        assert not is_google_sitemap_agent(agent)

    def test_enabled_only_on_ru_after_split_with_flag(self, monkeypatch):
        monkeypatch.setattr(settings, "apex_locale_en", True)
        monkeypatch.setattr(settings, "ru_google_short_sitemap", True)
        assert ru_google_short_sitemap_enabled(ru_host=True)
        assert not ru_google_short_sitemap_enabled(ru_host=False)
        monkeypatch.setattr(settings, "ru_google_short_sitemap", False)
        assert not ru_google_short_sitemap_enabled(ru_host=True)
        monkeypatch.setattr(settings, "ru_google_short_sitemap", True)
        monkeypatch.setattr(settings, "apex_locale_en", False)
        assert not ru_google_short_sitemap_enabled(ru_host=True)


@pytest.fixture
def publication(tmp_path, monkeypatch):
    import app.services.site_urls as urls

    monkeypatch.setattr(settings, "sitemap_dir", str(tmp_path))
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "ru_google_short_sitemap", True)
    monkeypatch.setattr(settings, "sitemap_priority_max_urls", 0)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")

    @asynccontextmanager
    async def session():
        yield None

    async def sections(db):
        yield "core", [SiteUrl("/russia", "2026-11-13", "daily", "0.8")]
        yield "world-regions-1", [SiteUrl("/united-states/region/texas/gdp", "2026-10-01", "monthly", "0.4")]
        yield "world-region-years-1", [
            SiteUrl("/united-states/region/texas/gdp/2020", "2020-12-01", "yearly", "0.4"),
        ]
        yield "world-region-vs", [
            SiteUrl("/united-states/region/texas-vs-ohio/gdp", "2026-10-01", "monthly", "0.4"),
        ]
        yield "world-vs", [SiteUrl("/australia-vs-japan/hicp-index", "2026-11-01", "monthly", "0.4")]
        yield "years", [SiteUrl("/russia/indicator/key-rate/2025", "2025-12-31", "yearly", "0.8")]
        yield "months-1", [SiteUrl("/russia/indicator/cpi/2026-10", "2026-10-31", "monthly", "0.4")]
        yield "world-indicators-1", [SiteUrl("/germany/indicator/de-gdp", "2026-11-01", "monthly", "0.4")]
        yield "regional-1", [SiteUrl("/russia/region/moskva/population", "2026-01-01", "yearly", "0.4")]
        yield "regional-years-1", [
            SiteUrl("/russia/region/moskva/population/2020", "2020-12-31", "yearly", "0.4"),
        ]
        yield "world-years-1", [SiteUrl("/germany/indicator/de-gdp/2010", "2010-01-01", "yearly", "0.4")]

    async def no_dynamic_chunks(db):
        return {}

    monkeypatch.setattr(sm, "analytics_session", session)
    monkeypatch.setattr(urls, "iter_url_sections", sections)
    monkeypatch.setattr(urls, "chunk_counts", no_dynamic_chunks)
    monkeypatch.setattr(sm, "today_msk", lambda: date(2026, 11, 13))
    asyncio.run(sm.build_static_sitemaps())
    return tmp_path


def _index(client, host: str, agent: str | None, **extra):
    headers = {"Host": host, **extra}
    if agent is not None:
        headers["User-Agent"] = agent
    return client.get("/sitemap.xml", headers=headers)


def _names(response) -> list[str]:
    return re.findall(r"/sitemap-([a-z0-9-]+)\.xml</loc>", response.text)


class TestIndexOverHttp:
    def test_googlebot_on_ru_gets_the_short_index(self, publication, client):
        response = _index(client, RU, GOOGLEBOT)
        assert response.status_code == 200
        assert _names(response) == KEPT
        assert f"https://{RU}/sitemap-core.xml" in response.text
        assert "Vary" in response.headers and "User-Agent" in response.headers["Vary"]

    @pytest.mark.parametrize("agent", [YANDEXBOT, BINGBOT, BROWSER, None])
    def test_everyone_else_on_ru_gets_the_full_index(self, publication, client, agent):
        response = _index(client, RU, agent)
        assert response.status_code == 200
        names = _names(response)
        assert set(MASS_YEARS) <= set(names)
        assert [name for name in names if name not in MASS_YEARS] == KEPT
        assert "User-Agent" in response.headers["Vary"]

    def test_variants_do_not_share_cache_or_etag(self, publication, client):
        """Порядок запросов не важен: вариант робота не протекает к остальным."""
        short = _index(client, RU, GOOGLEBOT)
        full = _index(client, RU, YANDEXBOT)
        short_again = _index(client, RU, GOOGLEBOT)
        assert _names(short) == _names(short_again) == KEPT
        assert set(MASS_YEARS) <= set(_names(full))
        assert short.headers["etag"] != full.headers["etag"]
        # ETag полного индекса не даёт роботу Google 304 на короткий, и наоборот.
        assert _index(client, RU, GOOGLEBOT, **{"If-None-Match": full.headers["etag"]}).status_code == 200
        assert _index(client, RU, YANDEXBOT, **{"If-None-Match": short.headers["etag"]}).status_code == 200
        assert _index(client, RU, GOOGLEBOT, **{"If-None-Match": short.headers["etag"]}).status_code == 304

    def test_live_cache_keeps_the_variants_apart(self, publication, client, monkeypatch):
        """С рабочим кэшем: ключ короткого индекса свой, полный не подменяется."""
        import app.core.cache as cache

        store: dict[str, str] = {}

        async def fake_get(key):
            return store.get(key)

        async def fake_set(key, value, ttl=None):
            store[key] = value

        monkeypatch.setattr(cache, "cache_get", fake_get)
        monkeypatch.setattr(cache, "cache_set", fake_set)
        for _ in range(2):  # второй проход читает из кэша
            assert _names(_index(client, RU, GOOGLEBOT)) == KEPT
            assert set(MASS_YEARS) <= set(_names(_index(client, RU, YANDEXBOT)))
            assert set(MASS_YEARS) <= set(_names(_index(client, APEX, GOOGLEBOT)))
        index_keys = sorted(key for key in store if ":index:" in key)
        assert len(index_keys) == 3
        assert [key for key in index_keys if "google-short" in key] == [
            key for key in index_keys if "google-short" in key and key.endswith(RU)
        ]
        assert sum("google-short" in key for key in index_keys) == 1

    def test_apex_is_untouched_for_googlebot(self, publication, client):
        response = _index(client, APEX, GOOGLEBOT)
        assert set(MASS_YEARS) <= set(_names(response))
        assert "User-Agent" not in response.headers.get("Vary", "")
        assert response.text == _index(client, APEX, YANDEXBOT).text

    def test_flag_off_returns_the_full_index_to_googlebot(self, publication, client, monkeypatch):
        monkeypatch.setattr(settings, "ru_google_short_sitemap", False)
        response = _index(client, RU, GOOGLEBOT)
        assert set(MASS_YEARS) <= set(_names(response))
        assert "User-Agent" not in response.headers.get("Vary", "")

    def test_shard_files_and_robots_stay_the_same_for_googlebot(self, publication, client):
        """Меняется только индекс: шарды доступны, robots.txt ведёт на тот же адрес."""
        for name in MASS_YEARS:
            shard = client.get(f"/sitemap-{name}.xml", headers={"Host": RU, "User-Agent": GOOGLEBOT})
            assert shard.status_code == 200
            assert f"https://{RU}/" in shard.text
        for agent in (GOOGLEBOT, YANDEXBOT):
            robots = client.get("/robots.txt", headers={"Host": RU, "User-Agent": agent})
            assert robots.status_code == 200
            sitemap_lines = [line for line in robots.text.splitlines() if line.lower().startswith("sitemap:")]
            assert sitemap_lines == [f"Sitemap: https://{RU}/sitemap.xml"]
