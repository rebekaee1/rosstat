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

    async def names(db):
        return ["core", "empty"]

    async def resolve(db, name):
        return [] if name == "empty" else [SiteUrl("/russia", "2026-09-10", "daily", "0.8")]

    monkeypatch.setattr(sm, "analytics_session", session)
    monkeypatch.setattr(urls, "section_names", names)
    monkeypatch.setattr(urls, "resolve_section", resolve)
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

    async def broken(db, name):
        raise RuntimeError("DB unavailable")

    monkeypatch.setattr(urls, "resolve_section", broken)
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
