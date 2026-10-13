"""Приоритетный шард sitemap-priority.xml: состав, размер, порядок, lastmod, хосты."""
import asyncio
import re
from contextlib import asynccontextmanager
from datetime import date

import pytest

from app.services import sitemap_priority as sp
from app.services import sitemap_static as sm
from app.services.site_urls import SiteUrl

TODAY = date(2026, 10, 12)


def _u(path, lastmod="2026-10-01", priority="0.5"):
    return SiteUrl(path, lastmod, "weekly", priority)


def test_normalize_demand_path():
    assert sp.normalize_demand_path("https://ru.forecasteconomy.com/russia/indicator/cpi/2026") == "/russia/indicator/cpi/2026"
    assert sp.normalize_demand_path("https://forecasteconomy.com/russia/") == "/russia"
    assert sp.normalize_demand_path("https://forecasteconomy.com/") == "/"
    assert sp.normalize_demand_path("/russia/indicator/key-rate") == "/russia/indicator/key-rate"
    # запросные варианты не канонические: в sitemap их нет
    assert sp.normalize_demand_path("https://forecasteconomy.com/indicator/imoex?mode=mom") is None
    assert sp.normalize_demand_path("https://forecasteconomy.com/a#b") is None
    assert sp.normalize_demand_path(None) is None
    assert sp.normalize_demand_path("not a path") is None


def test_collector_hubs_whole_demand_selected_rest_dropped():
    plan = sp.PriorityPlan()
    plan.add_ranked(["https://forecasteconomy.com/germany/indicator/de-gdp"], 1.0, "gsc")
    collector = sp.PriorityCollector(plan, TODAY, 100)
    collector.feed("core", [_u("/"), _u("/russia")])
    collector.feed("world", [_u("/germany")])
    collector.feed("world-indicators-1", [_u("/germany/indicator/de-gdp"), _u("/germany/indicator/de-other")])
    collector.feed("world-years-1", [_u("/germany/indicator/de-gdp/2010")])
    result = collector.result()
    paths = [u.path for u in result]
    assert paths == ["/", "/russia", "/germany", "/germany/indicator/de-gdp"]


def test_collector_keeps_exact_lastmod_of_source_url():
    plan = sp.PriorityPlan()
    plan.add("/germany/indicator/de-gdp", 1.0)
    collector = sp.PriorityCollector(plan, TODAY, 10)
    source = _u("/germany/indicator/de-gdp", lastmod="2025-12-31")
    collector.feed("world-indicators-1", [source])
    assert collector.result() == [source]


def test_collector_cap_keeps_hubs_then_best_scores():
    plan = sp.PriorityPlan()
    for index in range(10):
        plan.add(f"/p/{index}", float(index))
    collector = sp.PriorityCollector(plan, TODAY, 5)
    collector.feed("core", [_u("/"), _u("/russia")])
    collector.feed("world-indicators-1", [_u(f"/p/{index}") for index in range(10)])
    paths = [u.path for u in collector.result()]
    assert len(paths) == 5
    assert paths[:2] == ["/", "/russia"]
    assert paths[2:] == ["/p/9", "/p/8", "/p/7"]


def test_collector_deduplicates_and_zero_disables():
    plan = sp.PriorityPlan()
    plan.add("/x", 1.0)
    collector = sp.PriorityCollector(plan, TODAY, 10)
    collector.feed("core", [_u("/x")])
    collector.feed("regional-1", [_u("/x")])
    assert [u.path for u in collector.result()] == ["/x"]
    off = sp.PriorityCollector(plan, TODAY, 0)
    off.feed("core", [_u("/x")])
    assert off.result() == []


def test_recent_year_pages_of_russia_are_included_without_demand():
    collector = sp.PriorityCollector(sp.PriorityPlan(), TODAY, 10)
    collector.feed("years", [
        _u("/russia/indicator/cpi/2026"),
        _u("/russia/indicator/cpi/2025"),
        _u("/russia/indicator/cpi/2010"),
    ])
    assert [u.path for u in collector.result()] == [
        "/russia/indicator/cpi/2025", "/russia/indicator/cpi/2026",
    ]


def test_ranked_scores_weight_sources():
    plan = sp.PriorityPlan()
    plan.add_ranked(["/a", "/b"], 1.0, "gsc")
    plan.add_ranked(["/b"], 0.6, "visits")
    assert plan.scores["/a"] == pytest.approx(1.0)
    assert plan.scores["/b"] == pytest.approx(0.5 + 0.6)
    assert plan.sources == {"gsc": 2, "visits": 1}


@pytest.fixture
def publication(tmp_path, monkeypatch):
    from app.config import settings
    import app.services.site_urls as urls
    monkeypatch.setattr(settings, "sitemap_dir", str(tmp_path))
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")
    monkeypatch.setattr(settings, "sitemap_priority_max_urls", 100)

    @asynccontextmanager
    async def session():
        yield None

    async def sections(db):
        yield "core", [
            SiteUrl("/", "2026-10-10", "daily", "1.0"),
            SiteUrl("/russia/indicator/key-rate", "2026-10-09", "daily", "0.8"),
        ]
        yield "world-indicators-1", [
            SiteUrl("/germany/indicator/de-gdp", "2026-06-30", "weekly", "0.5"),
            SiteUrl("/germany/indicator/de-rare", "2019-01-01", "weekly", "0.5"),
        ]
        yield "world-years-1", [SiteUrl("/germany/indicator/de-gdp/2010", "2010-12-31", "yearly", "0.4")]

    async def no_dynamic_chunks(db):
        return {}

    async def plan(db, today):
        result = sp.PriorityPlan()
        result.add("/germany/indicator/de-gdp", 1.0)
        return result

    monkeypatch.setattr(sm, "analytics_session", session)
    monkeypatch.setattr(urls, "iter_url_sections", sections)
    monkeypatch.setattr(urls, "chunk_counts", no_dynamic_chunks)
    monkeypatch.setattr(sp, "load_priority_plan", plan)
    monkeypatch.setattr(sm, "today_msk", lambda: date(2026, 10, 12))
    return tmp_path


def test_generation_publishes_priority_first_for_both_hosts(publication):
    stats = asyncio.run(sm.build_static_sitemaps())
    assert list(stats["sections"])[0] == "priority"
    assert stats["sections"]["priority"] == 3
    # адреса приоритетного шарда повторяют основные и в общий счёт не входят
    assert stats["urls_total"] == 5
    assert stats["priority_urls"] == 3
    for host in ("forecasteconomy.com", "ru.forecasteconomy.com"):
        origin = f"https://{host}"
        assert sm.published_sections(origin)[0] == "priority"
        xml = sm.section_file("priority", origin).read_text()
        locs = re.findall(r"<loc>([^<]+)</loc>", xml)
        assert locs == [
            f"{origin}/",
            f"{origin}/russia/indicator/key-rate",
            f"{origin}/germany/indicator/de-gdp",
        ]
        # lastmod = дата данных страницы, как в основном шарде
        assert "<lastmod>2026-06-30</lastmod>" in xml
        assert "<lastmod>2019-01-01</lastmod>" not in xml
        assert "de-rare" not in xml and "/2010" not in xml


def test_priority_urls_are_a_subset_of_registry_without_noindex(publication):
    asyncio.run(sm.build_static_sitemaps())
    origin = "https://forecasteconomy.com"
    priority = set(sm.published_section_paths("priority", origin))
    registry = set()
    for name in sm.published_sections(origin):
        if name != "priority":
            registry.update(sm.published_section_paths(name, origin))
    assert priority and priority <= registry
    from app.services.index_policy import is_noindex_path
    assert not [path for path in priority if is_noindex_path(path)]


def test_index_lists_priority_first_over_http(publication, client):
    asyncio.run(sm.build_static_sitemaps())
    for host in ("forecasteconomy.com", "ru.forecasteconomy.com"):
        index = client.get("/sitemap.xml", headers={"Host": host})
        assert index.status_code == 200
        names = re.findall(r"/sitemap-([a-z0-9-]+)\.xml</loc>", index.text)
        assert names[0] == "priority"
        shard = client.get("/sitemap-priority.xml", headers={"Host": host})
        assert shard.status_code == 200
        assert f"https://{host}/germany/indicator/de-gdp" in shard.text


def test_registry_walk_yields_priority_paths_once(publication):
    asyncio.run(sm.build_static_sitemaps())
    walked = list(sm.iter_published_paths("https://forecasteconomy.com"))
    assert walked.count("/germany/indicator/de-gdp") == 1
    assert walked[0] == "/"
    assert len(walked) == len(set(walked)) == 5


def test_unchanged_priority_shard_is_reused(publication):
    first = asyncio.run(sm.build_static_sitemaps())
    second = asyncio.run(sm.build_static_sitemaps())
    assert second["section_digest"]["priority"] == first["section_digest"]["priority"]
    assert second["sections_rewritten"] == 0


def test_demand_failure_keeps_hubs(publication, monkeypatch):
    async def broken(db, today):
        raise RuntimeError("gsc table missing")

    monkeypatch.setattr(sp, "load_priority_plan", broken)
    stats = asyncio.run(sm.build_static_sitemaps())
    assert stats["sections"]["priority"] == 2  # только хаб core
    assert stats["urls_total"] == 5


def test_setting_zero_disables_priority(publication, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "sitemap_priority_max_urls", 0)
    stats = asyncio.run(sm.build_static_sitemaps())
    assert "priority" not in stats["sections"]
    assert stats["priority_urls"] == 0


def test_dynamic_fallback_never_advertises_priority(monkeypatch):
    from app.services import site_urls
    assert "priority" not in site_urls.section_names_static()
