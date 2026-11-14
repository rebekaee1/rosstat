"""Apex (EN) для Google: короткий sitemap и метка googlebot на годовых без спроса (ADR-0031, 14.11.2026).

Робот Google на apex получает индекс ``/sitemap.xml`` без трёх годовых семейств, как на ``ru.``.
Годовые страницы стран мира, регионов мира и регионов России, которых нет в опубликованном
``sitemap-priority.xml``, получают ``<meta name="googlebot" content="noindex, follow">``.
Показатели России с годами, карточки, сравнения — без метки. Нет шарда или спроса — метки нет.
"""

from __future__ import annotations

import asyncio
import os
import re
from contextlib import asynccontextmanager
from datetime import date

import pytest

from app.config import settings
from app.services import index_policy as ip
from app.services import sitemap_static as sm
from app.services.index_policy import (
    GOOGLEBOT_NOINDEX_META,
    googlebot_meta_for_path,
    is_apex_google_year_path,
)
from app.services.site_urls import SiteUrl

APEX = "forecasteconomy.com"
RU = "ru.forecasteconomy.com"
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
YANDEXBOT = "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"
DEMAND_YEAR = "/united-states/region/texas/gdp/2020"
NO_DEMAND_YEAR = "/germany/indicator/de-gdp/2010"
MASS_YEARS = {"world-region-years-1", "regional-years-1", "world-years-1"}


@pytest.fixture(autouse=True)
def fresh_demand_cache(monkeypatch):
    monkeypatch.setattr(ip, "_apex_demand", {"checked": None, "key": None, "paths": None})
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "apex_google_noindex_years_without_demand", True)
    monkeypatch.setattr(settings, "apex_google_short_sitemap", True)


def _urlset(paths: list[str], host: str = APEX) -> str:
    body = "".join(f"<url><loc>https://{host}{path}</loc></url>\n" for path in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset>\n{body}</urlset>\n'


@pytest.fixture
def demand_file(tmp_path, monkeypatch):
    """Опубликованный шард apex: 1 000 годовых страниц со спросом + хабы."""
    years = [f"/united-states/region/texas/gdp/{1000 + i}" for i in range(ip.APEX_DEMAND_MIN_YEARS)]
    file = tmp_path / "sitemap-priority.xml"
    file.write_text(_urlset(["/", "/russia"] + years + [DEMAND_YEAR]), encoding="utf-8")
    monkeypatch.setattr(sm, "section_file", lambda name, origin: file if name == "priority" else None)
    return file


class TestYearPattern:
    @pytest.mark.parametrize("path", [
        "/germany/indicator/de-gdp/2010",
        "/united-states/region/texas/gdp/2020",
        "/russia/region/moskva/population/2020",  # регион России + год на apex — массовый тип
        "/netherlands/region/noord-holland/population/2015?mode=x",
    ])
    def test_mass_year_pages(self, path):
        assert is_apex_google_year_path(path)

    @pytest.mark.parametrize("path", [
        "/russia/indicator/key-rate/2025",  # годы показателей России — ядро
        "/currencies/indicator/usd-rub/2024",
        "/world/rating/gdp-usd/2020",
        "/germany/indicator/de-gdp",
        "/germany/indicator/de-gdp/2026-05",
        "/united-states/region/texas",
        "/united-states/region/texas/gdp",
        "/australia-vs-japan/hicp-index",
        "/",
    ])
    def test_other_pages(self, path):
        assert not is_apex_google_year_path(path)


class TestMeta:
    def test_year_without_demand_is_marked_and_with_demand_is_not(self, demand_file):
        assert googlebot_meta_for_path(NO_DEMAND_YEAR, "en") == GOOGLEBOT_NOINDEX_META
        assert googlebot_meta_for_path(DEMAND_YEAR, "en") == ""
        assert googlebot_meta_for_path(DEMAND_YEAR + "/", "en") == ""
        assert googlebot_meta_for_path("/russia/region/moskva/population/2020", "en") == GOOGLEBOT_NOINDEX_META

    def test_core_pages_are_never_marked(self, demand_file):
        for path in ("/russia/indicator/key-rate/2025", "/germany/indicator/de-gdp",
                     "/australia-vs-japan/hicp-index", "/"):
            assert googlebot_meta_for_path(path, "en") == ""

    def test_ru_host_keeps_its_own_rule(self, demand_file, monkeypatch):
        """На ru. действует ADR-0029: регион России с годом — без метки, спрос не смотрится."""
        monkeypatch.setattr(settings, "ru_google_noindex_world_years", True)
        assert googlebot_meta_for_path("/russia/region/moskva/population/2020", "ru") == ""
        assert googlebot_meta_for_path(DEMAND_YEAR, "ru") == GOOGLEBOT_NOINDEX_META

    def test_flag_off_and_before_split(self, demand_file, monkeypatch):
        monkeypatch.setattr(settings, "apex_google_noindex_years_without_demand", False)
        assert googlebot_meta_for_path(NO_DEMAND_YEAR, "en") == ""
        monkeypatch.setattr(settings, "apex_google_noindex_years_without_demand", True)
        monkeypatch.setattr(settings, "apex_locale_en", False)
        assert googlebot_meta_for_path(NO_DEMAND_YEAR, "en") == ""

    def test_unknown_demand_marks_nothing(self, monkeypatch):
        monkeypatch.setattr(sm, "section_file", lambda name, origin: None)
        assert googlebot_meta_for_path(NO_DEMAND_YEAR, "en") == ""

    def test_hubs_only_shard_marks_nothing(self, tmp_path, monkeypatch):
        """Ночной сбой источников спроса: шард из хабов — метки нет ни у одной страницы."""
        file = tmp_path / "sitemap-priority.xml"
        file.write_text(_urlset(["/", "/russia", DEMAND_YEAR]), encoding="utf-8")
        monkeypatch.setattr(sm, "section_file", lambda name, origin: file)
        assert googlebot_meta_for_path(NO_DEMAND_YEAR, "en") == ""

    def test_new_generation_is_reread(self, demand_file, monkeypatch):
        assert googlebot_meta_for_path(NO_DEMAND_YEAR, "en") == GOOGLEBOT_NOINDEX_META
        years = [f"/germany/indicator/de-gdp/{1000 + i}" for i in range(ip.APEX_DEMAND_MIN_YEARS)]
        demand_file.write_text(_urlset(years + [NO_DEMAND_YEAR]), encoding="utf-8")
        stat = demand_file.stat()
        os.utime(demand_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
        # Проверка файла не чаще раза в 5 минут: до неё ответ прежний.
        assert googlebot_meta_for_path(NO_DEMAND_YEAR, "en") == GOOGLEBOT_NOINDEX_META
        monkeypatch.setattr(ip, "_APEX_DEMAND_RECHECK_SECONDS", 0.0)
        assert googlebot_meta_for_path(NO_DEMAND_YEAR, "en") == ""
        assert googlebot_meta_for_path(DEMAND_YEAR, "en") == GOOGLEBOT_NOINDEX_META

    def test_document_head(self, demand_file):
        from app.services.locale import reset_locale, set_locale
        from app.services.seo_renderer import AppAssets, compose_document

        assets = AppAssets(head_links="", body_scripts="")

        def doc(path: str) -> str:
            token = set_locale("en")
            try:
                return compose_document(
                    assets=assets, title="t", description="d", canonical_path=path,
                    body="<main>x</main>", include_app=False,
                )
            finally:
                reset_locale(token)

        marked = doc(NO_DEMAND_YEAR)
        assert GOOGLEBOT_NOINDEX_META in marked
        assert '<meta name="robots" content="index, follow' in marked  # Bing и Яндекс индексируют
        assert GOOGLEBOT_NOINDEX_META not in doc(DEMAND_YEAR)


# --- sitemap по HTTP --------------------------------------------------------------------------


@pytest.fixture
def publication(tmp_path, monkeypatch):
    import app.services.site_urls as urls
    from app.services.sitemap_priority import PriorityPlan

    monkeypatch.setattr(settings, "sitemap_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ru_google_short_sitemap", True)
    monkeypatch.setattr(settings, "sitemap_priority_max_urls", 100)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")

    @asynccontextmanager
    async def session():
        yield None

    async def sections(db):
        yield "core", [SiteUrl("/russia", "2026-11-13", "daily", "0.8")]
        yield "world-region-years-1", [SiteUrl(DEMAND_YEAR, "2020-12-01", "yearly", "0.4")]
        yield "world-vs", [SiteUrl("/australia-vs-japan/hicp-index", "2026-11-01", "monthly", "0.4")]
        yield "years", [SiteUrl("/russia/indicator/key-rate/2025", "2025-12-31", "yearly", "0.8")]
        yield "regional-years-1", [
            SiteUrl("/russia/region/moskva/population/2020", "2020-12-31", "yearly", "0.4"),
        ]
        yield "world-years-1", [SiteUrl(NO_DEMAND_YEAR, "2010-01-01", "yearly", "0.4")]

    async def no_dynamic_chunks(db):
        return {}

    async def plan():
        demand = PriorityPlan()
        demand.add(DEMAND_YEAR, 1.0)
        return demand

    monkeypatch.setattr(sm, "analytics_session", session)
    monkeypatch.setattr(sm, "_load_priority_plan", plan)
    monkeypatch.setattr(urls, "iter_url_sections", sections)
    monkeypatch.setattr(urls, "chunk_counts", no_dynamic_chunks)
    monkeypatch.setattr(sm, "today_msk", lambda: date(2026, 11, 14))
    asyncio.run(sm.build_static_sitemaps())
    return tmp_path


def _names(response) -> list[str]:
    return re.findall(r"/sitemap-([a-z0-9-]+)\.xml</loc>", response.text)


class TestApexSitemap:
    def test_googlebot_on_apex_gets_short_index_with_plain_priority(self, publication, client):
        response = client.get("/sitemap.xml", headers={"Host": APEX, "User-Agent": GOOGLEBOT})
        assert response.status_code == 200
        names = _names(response)
        assert names[0] == "priority"  # на apex годы не закрыты в robots.txt — общий шард
        assert "priority-google" not in names
        assert not MASS_YEARS & set(names)
        assert {"core", "world-vs", "years"} <= set(names)
        assert "User-Agent" in response.headers["Vary"]
        priority = client.get("/sitemap-priority.xml", headers={"Host": APEX, "User-Agent": GOOGLEBOT})
        assert priority.status_code == 200
        assert f"https://{APEX}{DEMAND_YEAR}" in priority.text

    def test_yandex_on_apex_gets_the_full_index(self, publication, client):
        response = client.get("/sitemap.xml", headers={"Host": APEX, "User-Agent": YANDEXBOT})
        assert MASS_YEARS <= set(_names(response))
        assert "User-Agent" in response.headers["Vary"]

    def test_apex_flag_off(self, publication, client, monkeypatch):
        monkeypatch.setattr(settings, "apex_google_short_sitemap", False)
        response = client.get("/sitemap.xml", headers={"Host": APEX, "User-Agent": GOOGLEBOT})
        assert MASS_YEARS <= set(_names(response))
        assert "User-Agent" not in response.headers.get("Vary", "")

    def test_ru_still_swaps_priority_for_google(self, publication, client, monkeypatch):
        monkeypatch.setattr(settings, "ru_google_disallow_world_years", True)
        names = _names(client.get("/sitemap.xml", headers={"Host": RU, "User-Agent": GOOGLEBOT}))
        assert "priority-google" in names and "priority" not in names

    def test_published_shard_is_the_demand_list(self, publication, monkeypatch):
        """Метка читает тот же опубликованный файл, что получает робот (порог снижен для теста)."""
        assert googlebot_meta_for_path(NO_DEMAND_YEAR, "en") == ""  # одна годовая < порога
        monkeypatch.setattr(ip, "APEX_DEMAND_MIN_YEARS", 1)
        monkeypatch.setattr(ip, "_apex_demand", {"checked": None, "key": None, "paths": None})
        assert googlebot_meta_for_path(NO_DEMAND_YEAR, "en") == GOOGLEBOT_NOINDEX_META
        assert googlebot_meta_for_path(DEMAND_YEAR, "en") == ""


def test_gsc_pages_report_is_a_demand_source():
    """Отчёт страниц Search Console (со скрытыми запросами) — свой источник спроса шарда."""
    import inspect

    from sqlalchemy.dialects import postgresql

    from app.services import sitemap_priority as sp

    seen = {}

    class Result:
        def all(self):
            return [("https://forecasteconomy.com" + NO_DEMAND_YEAR,), ("https://ru.forecasteconomy.com/russia",)]

    class FakeDb:
        async def execute(self, statement):
            seen["sql"] = str(statement.compile(dialect=postgresql.dialect()))
            return Result()

    plan = sp.PriorityPlan()
    asyncio.run(sp._load_gsc_pages(FakeDb(), plan, date(2026, 11, 14)))
    assert "FROM gsc_page_daily" in seen["sql"] and "GROUP BY gsc_page_daily.page" in seen["sql"]
    assert plan.sources == {"gsc_pages": 2}
    assert plan.scores[NO_DEMAND_YEAR] > 0 and plan.scores["/russia"] > 0
    assert "_load_gsc_pages" in inspect.getsource(sp.load_priority_plan)
