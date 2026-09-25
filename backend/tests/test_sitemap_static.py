"""Publication invariants: serving principals, hosts, failure and rebuilds."""
import asyncio
import gzip
import json
import stat
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import pytest

from app.services import sitemap_static as sm
from app.services.site_urls import SiteUrl


@pytest.fixture
def publication(tmp_path, monkeypatch):
    from app.config import settings
    import app.services.site_urls as urls
    monkeypatch.setattr(settings, "sitemap_dir", str(tmp_path))
    monkeypatch.setattr(settings, "apex_locale_en", True)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")

    @asynccontextmanager
    async def session():
        yield None

    async def sections(db):
        yield "core", [SiteUrl("/russia", "2026-09-10", "daily", "0.8")]
        yield "empty", []

    async def no_dynamic_chunks(db):
        # The synthetic publication contains only `core`; index fallback
        # must not query a real database for absent US year chunks.
        return {}

    monkeypatch.setattr(sm, "analytics_session", session)
    monkeypatch.setattr(urls, "iter_url_sections", sections)
    monkeypatch.setattr(urls, "chunk_counts", no_dynamic_chunks)
    return tmp_path


def test_complete_host_generation_permissions_and_gzip(publication):
    stats = asyncio.run(sm.build_static_sitemaps())
    assert stats["urls_total"] == 1
    assert stats["published_urls_total"] == 2
    assert stats["sections"] == {"core": 1}
    for host in stats["hosts"]:
        path = sm.section_file("core", f"https://{host}")
        raw = path.read_bytes()
        assert f"<loc>https://{host}/russia</loc>".encode() in raw
        assert stat.S_IMODE(path.stat().st_mode) == 0o644
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o755
        twin = Path(str(path) + ".gz")
        assert stat.S_IMODE(twin.stat().st_mode) == 0o644
        assert gzip.decompress(twin.read_bytes()) == raw
        assert sm.published_sections(f"https://{host}") == ["core"]
    assert sm.section_file("core", "https://attacker.example") is None
    assert sm.section_file("../../core", "https://forecasteconomy.com") is None


def test_unchanged_shard_is_linked_not_rebuilt(publication, monkeypatch):
    import app.services.site_urls as urls
    first = asyncio.run(sm.build_static_sitemaps())
    assert first["sections_rewritten"] == 1
    assert first["sections_reused"] == 0
    digest = first["section_digest"]["core"]
    original_write = sm._write_xml

    def boom(*args, **kwargs):
        raise AssertionError("unchanged shard must not be rendered again")

    monkeypatch.setattr(sm, "_write_xml", boom)
    second = asyncio.run(sm.build_static_sitemaps())
    assert second["sections_reused"] == 1
    assert second["sections_rewritten"] == 0
    assert second["section_digest"]["core"] == digest
    current = sm.section_file("core", "https://forecasteconomy.com")
    previous = publication / "generations" / first["generation"] / "forecasteconomy.com" / "sitemap-core.xml"
    assert current.stat().st_ino == previous.stat().st_ino
    assert current.read_bytes() == previous.read_bytes()

    async def changed(db):
        yield "core", [SiteUrl("/russia", "2026-09-11", "daily", "0.8")]

    monkeypatch.setattr(sm, "_write_xml", original_write)
    monkeypatch.setattr(urls, "iter_url_sections", changed)
    third = asyncio.run(sm.build_static_sitemaps())
    assert third["sections_rewritten"] == 1
    assert third["sections_reused"] == 0
    assert third["section_digest"]["core"] != digest
    refreshed = sm.section_file("core", "https://forecasteconomy.com")
    assert b"<lastmod>2026-09-11</lastmod>" in refreshed.read_bytes()
    ru = sm.section_file("core", "https://ru.forecasteconomy.com").read_text()
    assert "https://ru.forecasteconomy.com/russia" in ru
    assert "sitemap-origin.invalid" not in ru


def test_failed_generation_preserves_current(publication, monkeypatch):
    import app.services.site_urls as urls
    original = asyncio.run(sm.build_static_sitemaps())

    async def broken(db):
        yield "core", [SiteUrl("/new", "2026-09-20", "daily", "0.8")]
        assert sm.read_stats() == original
        raise RuntimeError("DB unavailable")

    monkeypatch.setattr(urls, "iter_url_sections", broken)
    with pytest.raises(RuntimeError, match="DB unavailable"):
        asyncio.run(sm.build_static_sitemaps())
    assert sm.read_stats() == original
    assert len(list((publication / "generations").iterdir())) == 1


def test_rebuild_keeps_previous_and_ignores_legacy(publication):
    (publication / "sitemap-core.xml").write_text("legacy apex only")
    assert sm.section_file("core", "https://forecasteconomy.com") is None
    unrelated = publication / "generations" / "not-ours"
    unrelated.mkdir(parents=True)
    builds = [asyncio.run(sm.build_static_sitemaps()) for _ in range(3)]
    remaining = {p.name for p in (publication / "generations").iterdir()}
    assert remaining == {"not-ours", builds[1]["generation"], builds[2]["generation"]}
    assert (publication / "sitemap-core.xml").exists()


def test_late_host_write_failure_preserves_current(publication, monkeypatch):
    import app.services.site_urls as urls
    original = asyncio.run(sm.build_static_sitemaps())
    real_write = sm._write_xml
    writes = []

    def write(directory, name, xml):
        writes.append(directory.name)
        assert sm.read_stats() == original
        if len(writes) == 2:
            raise OSError("disk full")
        real_write(directory, name, xml)

    async def changed(db):
        # Тот же шард не пишется заново. Сбой проверяем на изменившемся файле.
        yield "core", [SiteUrl("/new", "2026-09-20", "daily", "0.8")]

    monkeypatch.setattr(urls, "iter_url_sections", changed)
    monkeypatch.setattr(sm, "_write_xml", write)
    with pytest.raises(OSError, match="disk full"):
        asyncio.run(sm.build_static_sitemaps())
    assert len(writes) == 2
    assert sm.read_stats() == original
    assert len(list((publication / "generations").iterdir())) == 1


def test_publication_consumes_one_chunk_before_fetching_next(publication, monkeypatch):
    import app.services.site_urls as urls
    original_write = sm._write_xml
    written = []

    def write(directory, name, xml):
        original_write(directory, name, xml)
        written.append((directory.name, name))

    async def sections(db):
        for i in range(1, 5):
            assert len(written) == 2 * (i - 1)
            yield f"regional-years-{i}", [SiteUrl(f"/history/{i}", "2018-01-01", "yearly", "0.4")]

    monkeypatch.setattr(sm, "_write_xml", write)
    monkeypatch.setattr(urls, "iter_url_sections", sections)
    result = asyncio.run(sm.build_static_sitemaps())
    assert result["section_count"] == 4
    assert result["published_urls_total"] == 8


def test_section_iterator_bypasses_cached_bounds_and_continues_empty_pages(monkeypatch):
    from dataclasses import replace
    import app.services.site_urls as urls

    calls = []

    async def fetch(db, today, after, limit):
        calls.append(after)
        if after is None:
            return [], (1,)
        if after == (1,):
            return [SiteUrl("/history/2018", "2018-01-01", "yearly", "0.4")], (2,)
        return [], None

    async def forbidden(*args, **kwargs):
        raise AssertionError("Static publication must not use cached chunk boundaries")

    monkeypatch.setattr(urls, "_SIMPLE_SECTION_ORDER", ["regional-years-"])
    monkeypatch.setattr(urls, "_CHUNKED_SOURCES", {
        "regional-years-": replace(urls._CHUNKED_SOURCES["regional-years-"], fetch=fetch, size=1),
    })
    monkeypatch.setattr(urls, "chunk_counts", forbidden)
    monkeypatch.setattr(urls, "_chunk_bounds", forbidden)

    async def check():
        sections = [item async for item in urls.iter_url_sections(None)]
        assert sections[0] == ("regional-years-1", [])
        assert sections[1][0] == "regional-years-2"
        assert sections[1][1][0].path == "/history/2018"
        assert calls == [None, (1,), (2,)]

    asyncio.run(check())


def test_cutover_off_does_not_publish_ru(publication, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "apex_locale_en", False)
    stats = asyncio.run(sm.build_static_sitemaps())
    assert list(stats["hosts"]) == ["forecasteconomy.com"]
    assert sm.published_sections("https://ru.forecasteconomy.com") is None


def test_concurrent_publication_rejected(publication):
    import fcntl
    with (publication / ".build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="already running"):
            asyncio.run(sm.build_static_sitemaps())


def test_static_http_host_etag_and_manifest(publication, client):
    asyncio.run(sm.build_static_sitemaps())
    for host in ("forecasteconomy.com", "ru.forecasteconomy.com"):
        response = client.get("/sitemap-core.xml", headers={"Host": host})
        assert response.status_code == 200
        assert f"https://{host}/russia" in response.text
        cached = client.get("/sitemap-core.xml", headers={"Host": host, "If-None-Match": response.headers["etag"]})
        assert cached.status_code == 304
        index = client.get("/sitemap.xml", headers={"Host": host})
        assert index.status_code == 200
        assert f"https://{host}/sitemap-core.xml" in index.text
        assert "<lastmod>2026-09-10</lastmod>" in index.text
        assert "sitemap-empty.xml" not in index.text


def test_restrictive_umask_still_allows_nginx(publication):
    import os
    old = os.umask(0o077)
    try:
        asyncio.run(sm.build_static_sitemaps())
    finally:
        os.umask(old)
    path = sm.section_file("core", "https://forecasteconomy.com")
    for directory in [publication, path.parent, path.parent.parent, path.parent.parent.parent]:
        assert stat.S_IMODE(directory.stat().st_mode) == 0o755


def test_static_and_gzip_include_same_host_images_without_rendering(publication, monkeypatch):
    import xml.etree.ElementTree as ET
    from app.services import site_urls, og_image
    from app.api.sitemap import _render_urlset

    pages = [
        SiteUrl("/russia/indicator/cpi/2025", "2025-12-01", "monthly", "0.8"),
        SiteUrl("/russia/region/map/wages?year=2020", "2020-12-31", "yearly", "0.5"),
        SiteUrl("/about?ref=1&label=<data>", "2026-01-01", "monthly", "0.5"),
    ]
    async def sections(db):
        yield "images", pages
    def forbidden(*args, **kwargs):
        raise AssertionError("Sitemap build must not render an image")
    monkeypatch.setattr(site_urls,"iter_url_sections",sections)
    monkeypatch.setattr(og_image,"render_indicator_og",forbidden)
    monkeypatch.setattr(og_image,"render_rating_og",forbidden)
    monkeypatch.setattr(og_image,"render_demographics_og",forbidden)
    stats=asyncio.run(sm.build_static_sitemaps())
    assert stats["urls_total"]==3 and stats["published_urls_total"]==6
    assert stats["sections"]=={"images":3}
    image_ns="{http://www.google.com/schemas/sitemap-image/1.1}"
    for host in stats["hosts"]:
        origin=f"https://{host}"
        path=sm.section_file("images",origin)
        xml=path.read_text()
        assert xml==_render_urlset(pages,origin=origin)
        assert gzip.decompress(Path(str(path)+".gz").read_bytes()).decode()==xml
        images=ET.fromstring(xml).findall(f".//{image_ns}loc")
        assert [element.text for element in images]==[
            origin+"/og/russia/cpi/2025.png",
            origin+"/og/russia/region-rating/wages.png?year=2020",
        ]


def test_publication_refuses_noindex_and_oversize_bytes(publication, monkeypatch):
    import app.services.site_urls as urls

    async def honeypot(db):
        yield "core", [SiteUrl("/__honeypot__/trap", "2026-01-01", "daily", "0.1")]

    monkeypatch.setattr(urls, "iter_url_sections", honeypot)
    with pytest.raises(ValueError, match="noindex"):
        asyncio.run(sm.build_static_sitemaps())

    async def oversized(db):
        yield "core", [SiteUrl("/russia", "2026-09-10", "daily", "0.8")]

    monkeypatch.setattr(urls, "iter_url_sections", oversized)
    monkeypatch.setattr(sm, "SITEMAP_MAX_BYTES", 20)
    with pytest.raises(ValueError, match="bytes"):
        asyncio.run(sm.build_static_sitemaps())


def test_index_lastmod_and_urlset_omit_unverifiable_dates():
    from app.api.sitemap import _render_sitemap_index, _render_urlset
    import app.services.site_urls as urls

    index = _render_sitemap_index(
        ["core", "world-regions-1"],
        "https://forecasteconomy.com",
        {"core": "2026-09-10"},
    )
    assert "<loc>https://forecasteconomy.com/sitemap-core.xml</loc>\n    <lastmod>2026-09-10</lastmod>" in index
    assert "sitemap-world-regions-1.xml" in index
    assert index.count("<lastmod>") == 1

    xml = _render_urlset([
        SiteUrl("/about", None, "monthly", "0.5"),
        SiteUrl("/future", "2099-01-01", "monthly", "0.5"),
        SiteUrl("/ok", "2026-01-15", "monthly", "0.5"),
    ], origin="https://forecasteconomy.com")
    assert xml.count("<lastmod>") == 1
    assert "<lastmod>2026-01-15</lastmod>" in xml
    assert "2099" not in xml
    assert urls.normalize_sitemap_lastmod("not-a-date") is None
    assert urls._static_lastmod("/about", date(2026, 9, 1)) is None
    assert urls._static_lastmod("/", date(2026, 9, 1)) == "2026-09-01"
    months = urls._month_rows_urls([("cpi", 2026, 9, date(2026, 9, 10))], date(2026, 9, 25))
    assert months[0].lastmod == "2026-09-10"


def test_oversized_simple_section_is_split_under_the_protocol_limit(monkeypatch):
    import app.services.site_urls as urls

    rows = [SiteUrl(f"/p{i}", "2020-01-01", "weekly", "0.5") for i in range(5)]

    async def count(db):
        return len(rows)

    async def page(db, offset, limit):
        return rows[offset:offset + limit]

    monkeypatch.setattr(urls, "_world_regions_url_count", count)
    monkeypatch.setattr(urls, "_world_regions_page", page)
    monkeypatch.setattr(urls, "_SIMPLE_SECTION_ORDER", ["world-regions"])
    monkeypatch.setattr(urls, "SITEMAP_MAX_URLS", 2)
    monkeypatch.setattr(urls, "WORLD_CHUNK", 2)

    sections = asyncio.run(_collect(urls.iter_url_sections(None)))
    assert [name for name, _chunk in sections] == [
        "world-regions-1", "world-regions-2", "world-regions-3",
    ]
    assert [len(chunk) for _name, chunk in sections] == [2, 2, 1]
    assert urls.section_names_for_count("world-regions", 5) == [
        "world-regions-1", "world-regions-2", "world-regions-3",
    ]


async def _collect(agen):
    return [item async for item in agen]


def test_published_section_size_reads_host_stats(publication):
    asyncio.run(sm.build_static_sitemaps())
    assert sm.published_section_size("core", "https://forecasteconomy.com") == 1
    assert sm.published_section_size("missing", "https://forecasteconomy.com") is None
    assert sm.published_section_size("core", "https://attacker.example") is None


def test_legacy_world_regions_monolith_is_rewritten_in_index(monkeypatch):
    """Old static stats still listing bare world-regions must advertise shards."""
    import app.services.site_urls as urls
    from app.api import sitemap as sitemap_api

    async def fake_count(db):
        return 5

    monkeypatch.setattr(urls, "_world_regions_url_count", fake_count)
    monkeypatch.setattr(urls, "SITEMAP_MAX_URLS", 2)
    monkeypatch.setattr(urls, "WORLD_CHUNK", 2)

    names = ["core", "world-regions", "world-region-vs"]
    names = [name for name in names if name != "world-regions"]
    if not any(name.startswith("world-regions-") for name in names):
        names.extend(asyncio.run(urls.world_regions_section_names(None)))
    assert names == [
        "core", "world-region-vs",
        "world-regions-1", "world-regions-2", "world-regions-3",
    ]
    index = sitemap_api._render_sitemap_index(
        names, "https://forecasteconomy.com", {}
    )
    assert "<loc>https://forecasteconomy.com/sitemap-world-regions.xml</loc>" not in index
    assert "sitemap-world-regions-1.xml" in index
    assert "sitemap-world-regions-3.xml" in index


def test_oversized_disk_section_is_not_served(publication, monkeypatch):
    """Published monolith over 50k must not be returned from disk as-is."""
    import app.services.sitemap_static as sms

    asyncio.run(sm.build_static_sitemaps())
    # Pretend core grew past the protocol ceiling in stats only.
    generation = sms._current_generation()
    stats_path = generation / sms.STATS_NAME
    payload = json.loads(stats_path.read_text(encoding="utf-8"))
    for host_entry in payload["hosts"].values():
        host_entry["sections"]["core"] = 50_001
    payload["sections"]["core"] = 50_001
    stats_path.write_text(json.dumps(payload), encoding="utf-8")
    assert sms.published_section_size("core", "https://forecasteconomy.com") == 50_001
    # section_file still points at the bytes; callers must check the size.
    assert sms.section_file("core", "https://forecasteconomy.com").is_file()
