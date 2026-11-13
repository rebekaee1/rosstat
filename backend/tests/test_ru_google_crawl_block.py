"""Запрет обхода годовых страниц стран мира роботу Google на ``ru.`` (13.11.2026).

Руководство Google об обходе больших сайтов: метка ``noindex`` обход не экономит, ненужные
в поиске адреса закрывают в ``robots.txt``. Те же адреса, что с 11.11 несут метку
``googlebot`` (ADR-0029), на ``ru.`` закрыты для обхода роботом Google. Россия, валюты,
карточки, сравнения, OG-картинки, остальные роботы и apex не затронуты.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.services.index_policy import (
    RU_GOOGLE_CRAWL_BLOCK_RULES,
    add_rules_to_agent_group,
    is_ru_google_noindex_path,
    ru_google_crawl_block_rules,
)
from tests.test_year_mode_crawl_policy import _can_crawl

RU = "ru.forecasteconomy.com"
APEX = "forecasteconomy.com"

BLOCKED = [
    "/united-states/indicator/gdp/2020",
    "/germany/indicator/hicp-index/1999",
    "/france/indicator/fr-ilc_lvhl13-a2-dch1-total-pc/2007",
    "/united-states/region/colorado/bea-sainc5n-541/2008",
    "/netherlands/region/noord-holland/population/2015",
    "/united-states/region/alabama/unemployment-rate/1976",
]
OPEN = [
    "/",
    "/russia/indicator/key-rate",
    "/russia/indicator/key-rate/2025",
    "/russia/indicator/cpi/2026-10",
    "/russia/region/moskva/population/2020",
    "/russia/region/moskva/population",
    "/currencies/indicator/usd-rub/2024",
    "/world/rating/gdp-usd/2020",
    "/united-states/indicator/gdp",
    "/united-states/region/colorado",
    "/united-states/region/colorado/bea-sainc5n-541",
    "/united-states/region/map/bea-sainc5n-541?year=2020",
    "/united-states/region-vs/texas-vs-ohio",
    "/united-states/regions",
    "/australia-vs-japan/hicp-index",
    "/russia/calendar/2026/11",
    "/sitemap-world-years-1.xml",
    # Картинки страниц — открыты, в том числе у России.
    "/og/russia/region/moskva/population/2020.png",
    "/og/russia/key-rate/2025.png",
    "/og/united-states/gdp/2020.png",
    "/og/world/united-states/region/texas/bea-sasummary-6/2020.png",
]


@pytest.fixture
def split_on(monkeypatch):
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "ru_google_disallow_world_years", True)


def _robots(client, host: str) -> str:
    response = client.get("/robots.txt", headers={"Host": host})
    assert response.status_code == 200
    return response.text


class TestRulesOnRu:
    @pytest.mark.parametrize("path", BLOCKED)
    def test_world_year_pages_are_closed_for_googlebot(self, client, split_on, path):
        text = _robots(client, RU)
        assert is_ru_google_noindex_path(path)
        assert not _can_crawl(text, "Googlebot", path)

    @pytest.mark.parametrize("path", OPEN)
    def test_everything_else_stays_open_for_googlebot(self, client, split_on, path):
        assert _can_crawl(_robots(client, RU), "Googlebot", path)

    @pytest.mark.parametrize("agent", ["Yandex", "bingbot", "*"])
    @pytest.mark.parametrize("path", BLOCKED)
    def test_other_robots_are_untouched(self, client, split_on, agent, path):
        assert _can_crawl(_robots(client, RU), agent, path)

    def test_only_the_googlebot_group_grows(self, client, split_on, monkeypatch):
        with_rules = _robots(client, RU)
        monkeypatch.setattr(settings, "ru_google_disallow_world_years", False)
        without = _robots(client, RU)
        assert with_rules != without
        added = [line for line in with_rules.splitlines() if line not in without.splitlines()]
        assert added == list(RU_GOOGLE_CRAWL_BLOCK_RULES)
        # Строки стоят внутри группы Googlebot, до следующей группы.
        lines = with_rules.splitlines()
        start = lines.index("User-agent: Googlebot")
        end = lines.index("", start)
        assert lines[end - len(RU_GOOGLE_CRAWL_BLOCK_RULES):end] == list(RU_GOOGLE_CRAWL_BLOCK_RULES)
        assert [line for line in with_rules.splitlines() if line.lower().startswith("sitemap:")] == [
            f"Sitemap: https://{RU}/sitemap.xml"
        ]


class TestScope:
    @pytest.mark.parametrize("path", BLOCKED)
    def test_apex_is_untouched(self, client, split_on, path):
        text = _robots(client, APEX)
        assert _can_crawl(text, "Googlebot", path)
        assert "/*/indicator/*/1" not in text

    @pytest.mark.parametrize("path", BLOCKED)
    def test_flag_off_opens_the_pages(self, client, split_on, monkeypatch, path):
        monkeypatch.setattr(settings, "ru_google_disallow_world_years", False)
        assert _can_crawl(_robots(client, RU), "Googlebot", path)

    def test_rules_need_ru_host_split_and_flag(self, monkeypatch):
        monkeypatch.setattr(settings, "apex_locale_en", True)
        monkeypatch.setattr(settings, "ru_google_disallow_world_years", True)
        assert ru_google_crawl_block_rules(ru_host=True) == RU_GOOGLE_CRAWL_BLOCK_RULES
        assert ru_google_crawl_block_rules(ru_host=False) == ()
        monkeypatch.setattr(settings, "apex_locale_en", False)
        assert ru_google_crawl_block_rules(ru_host=True) == ()


class TestGroupEdit:
    TEXT = "User-agent: *\nAllow: /\n\nUser-agent: Googlebot\nAllow: /\nDisallow: /api/\n\nUser-agent: Yandex\nAllow: /\n"

    def test_rules_go_to_the_end_of_the_group(self):
        out = add_rules_to_agent_group(self.TEXT, "Googlebot", ("Disallow: /x/",))
        assert out == (
            "User-agent: *\nAllow: /\n\nUser-agent: Googlebot\nAllow: /\nDisallow: /api/\nDisallow: /x/\n\n"
            "User-agent: Yandex\nAllow: /\n"
        )

    def test_last_group_without_trailing_blank_line(self):
        out = add_rules_to_agent_group("User-agent: Googlebot\nAllow: /", "googlebot", ("Disallow: /x/",))
        assert out == "User-agent: Googlebot\nAllow: /\nDisallow: /x/"

    def test_missing_group_or_empty_rules_change_nothing(self):
        assert add_rules_to_agent_group(self.TEXT, "Bingbot", ("Disallow: /x/",)) == self.TEXT
        assert add_rules_to_agent_group(self.TEXT, "Googlebot", ()) == self.TEXT


def test_every_allow_rule_outranks_the_disallow_it_answers():
    """У Google побеждает более длинное правило: разрешение обязано быть длиннее запрета."""
    disallow = [line.split(": ", 1)[1] for line in RU_GOOGLE_CRAWL_BLOCK_RULES if line.startswith("Disallow")]
    allow = [line.split(": ", 1)[1] for line in RU_GOOGLE_CRAWL_BLOCK_RULES if line.startswith("Allow")]
    assert len(disallow) == 4 and len(allow) == 8
    for rule in allow:
        kind = "/indicator/" if "/indicator/" in rule else "/region/"
        rivals = [d for d in disallow if kind in d and d[-1] == rule[-1]]
        assert rivals and all(len(rule) > len(d) for d in rivals), rule


# --- Приоритетный шард для Google ---------------------------------------------

GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
YANDEXBOT = "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"


@pytest.fixture
def priority_publication(tmp_path, monkeypatch, split_on):
    import asyncio
    from contextlib import asynccontextmanager
    from datetime import date

    import app.services.site_urls as urls
    from app.services import sitemap_static as sm
    from app.services.site_urls import SiteUrl

    monkeypatch.setattr(settings, "sitemap_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ru_google_short_sitemap", True)
    monkeypatch.setattr(settings, "sitemap_priority_max_urls", 0)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")

    @asynccontextmanager
    async def session():
        yield None

    async def sections(db):
        # Шард с именем приоритетного: адрес России и годовая страница другой страны.
        yield "priority", [
            SiteUrl("/russia/indicator/key-rate", "2026-11-13", "daily", "0.8"),
            SiteUrl("/united-states/indicator/gdp/2020", "2020-12-31", "yearly", "0.4"),
            SiteUrl("/united-states/indicator/gdp", "2026-10-01", "monthly", "0.4"),
        ]
        yield "core", [SiteUrl("/russia", "2026-11-13", "daily", "0.8")]

    async def no_dynamic_chunks(db):
        return {}

    monkeypatch.setattr(sm, "analytics_session", session)
    monkeypatch.setattr(urls, "iter_url_sections", sections)
    monkeypatch.setattr(urls, "chunk_counts", no_dynamic_chunks)
    monkeypatch.setattr(sm, "today_msk", lambda: date(2026, 11, 13))
    asyncio.run(sm.build_static_sitemaps())
    return tmp_path


def _index_names(client, host, agent):
    import re

    response = client.get("/sitemap.xml", headers={"Host": host, "User-Agent": agent})
    assert response.status_code == 200
    return re.findall(r"/sitemap-([a-z0-9-]+)\.xml</loc>", response.text), response.text


class TestGooglePriorityShard:
    def test_google_index_on_ru_points_to_the_filtered_shard(self, priority_publication, client):
        names, text = _index_names(client, RU, GOOGLEBOT)
        assert names == ["priority-google", "core"]
        assert "<lastmod>2026-11-13</lastmod>" in text.split("sitemap-core.xml")[0]

    def test_filtered_shard_drops_only_blocked_urls(self, priority_publication, client):
        shard = client.get("/sitemap-priority-google.xml", headers={"Host": RU, "User-Agent": GOOGLEBOT})
        assert shard.status_code == 200
        assert f"https://{RU}/russia/indicator/key-rate</loc>" in shard.text
        assert f"https://{RU}/united-states/indicator/gdp</loc>" in shard.text
        assert "/united-states/indicator/gdp/2020" not in shard.text
        assert shard.text.count("<url>") == shard.text.count("</url>") == 2
        assert shard.text.rstrip().endswith("</urlset>")
        again = client.get(
            "/sitemap-priority-google.xml",
            headers={"Host": RU, "User-Agent": GOOGLEBOT, "If-None-Match": shard.headers["etag"]},
        )
        assert again.status_code == 304

    def test_other_robots_keep_the_full_priority_shard(self, priority_publication, client):
        names, _ = _index_names(client, RU, YANDEXBOT)
        assert names == ["priority", "core"]
        full = client.get("/sitemap-priority.xml", headers={"Host": RU, "User-Agent": YANDEXBOT})
        assert "/united-states/indicator/gdp/2020" in full.text

    def test_apex_has_no_google_shard(self, priority_publication, client):
        names, _ = _index_names(client, APEX, GOOGLEBOT)
        assert names == ["priority", "core"]
        assert client.get("/sitemap-priority-google.xml", headers={"Host": APEX}).status_code == 404

    def test_without_crawl_block_google_keeps_the_common_shard(self, priority_publication, client, monkeypatch):
        monkeypatch.setattr(settings, "ru_google_disallow_world_years", False)
        names, _ = _index_names(client, RU, GOOGLEBOT)
        assert names == ["priority", "core"]
        assert client.get("/sitemap-priority-google.xml", headers={"Host": RU}).status_code == 404
