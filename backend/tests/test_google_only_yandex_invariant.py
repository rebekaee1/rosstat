"""Инвариант ADR-0029/0030/0031 (совет 19.11.2026): массовые страницы закрываем только для Google.

Замер 19.11: 78 % входов из Яндекса (~7 650 за 30 дней, 90 % людей сайта) приходят на годовые
страницы — те, что Google считает массовыми. Любой механизм «меньше страниц для Google»
(метка ``googlebot``, запрет обхода в группе Googlebot, короткий sitemap по User-Agent) не
должен менять то, что видит Яндекс. Тест включает все флаги Google разом и проверяет страницы,
через которые люди приходят из Яндекса, на обоих хостах.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.services.index_policy import (
    googlebot_meta_for_path,
    is_google_sitemap_agent,
    robots_for_path,
)
from tests.test_year_mode_crawl_policy import _can_crawl

RU = "ru.forecasteconomy.com"
APEX = "forecasteconomy.com"

# Входы из Яндекса за 30 дней до 19.11.2026 (топ по `raw_metrika_visits`) и годовые страницы мира.
YANDEX_ENTRIES = [
    "/russia/indicator/fuel-diesel/2026",
    "/russia/indicator/fuel-ai92/2025",
    "/russia/indicator/cpi/2026",
    "/russia/indicator/gold-price/2026",
    "/world/rating/population/2026",
    "/currencies/indicator/usd-rub/2025",
    "/russia/indicator/key-rate",
    "/russia/region/moskva/population/2020",
    "/united-states/indicator/gdp/2020",
    "/united-states/region/colorado/bea-sainc5n-541/2008",
]
YANDEX_AGENTS = ["Yandex", "YandexBot"]


@pytest.fixture
def google_flags_on(monkeypatch):
    for name in ("apex_locale_en", "ru_google_noindex_world_years", "ru_google_disallow_world_years",
                 "ru_google_short_sitemap", "apex_google_short_sitemap",
                 "apex_google_noindex_years_without_demand"):
        if hasattr(settings, name):
            monkeypatch.setattr(settings, name, True)


@pytest.mark.parametrize("path", YANDEX_ENTRIES)
def test_meta_robots_stays_index_for_everyone(google_flags_on, path):
    assert robots_for_path(path).startswith("index, follow")


@pytest.mark.parametrize("locale", ["ru", "en"])
@pytest.mark.parametrize("path", YANDEX_ENTRIES)
def test_google_marks_are_addressed_to_googlebot_only(google_flags_on, path, locale):
    meta = googlebot_meta_for_path(path, locale)
    assert meta in ("", '<meta name="googlebot" content="noindex, follow">')
    assert 'name="robots"' not in meta and "yandex" not in meta.lower()


@pytest.mark.parametrize("host", [RU, APEX])
@pytest.mark.parametrize("agent", YANDEX_AGENTS)
@pytest.mark.parametrize("path", YANDEX_ENTRIES)
def test_yandex_may_crawl_every_entry_page(client, google_flags_on, host, agent, path):
    response = client.get("/robots.txt", headers={"Host": host})
    assert response.status_code == 200
    assert _can_crawl(response.text, agent, path)


@pytest.mark.parametrize("agent", [
    "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
    "Mozilla/5.0 (compatible; YandexImages/3.0; +http://yandex.com/bots)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
])
def test_short_sitemap_is_not_served_to_yandex(agent):
    assert not is_google_sitemap_agent(agent)
