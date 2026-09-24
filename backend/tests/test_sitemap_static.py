"""Publication invariants: serving principals, hosts, failure and rebuilds."""
import asyncio
import gzip
import json
import stat
from contextlib import asynccontextmanager
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
    original = asyncio.run(sm.build_static_sitemaps())
    real_write = sm._write_xml
    writes = []

    def write(directory, name, xml):
        writes.append(directory.name)
        assert sm.read_stats() == original
        if len(writes) == 2:
            raise OSError("disk full")
        real_write(directory, name, xml)

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
