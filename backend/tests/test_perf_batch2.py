"""Perf batch 2 (2026-09-26): SSR-кэш (zlib, legacy-чтение, TTL лет, home,
world-vs peek), OG-диск (исторический TTL, ограниченная уборка) и bulk
«последнее наблюдение» (LATERAL ↔ прежний window-запрос).
"""

import asyncio
import json
import os
import time
from datetime import date
from pathlib import Path

import pytest

import app.api.seo_pages as seo_pages
import app.core.cache as cache_mod
from app.services import og_image
from app.services import world_subnational_queries as wsq


# ── SSR cache: zlib + backward-compatible read ─────────────────────────────


def test_encode_decode_roundtrip_and_ratio():
    html = "<html><body>" + "Инфляция в Дании 2,3% " * 2000 + "</body></html>"
    raw = cache_mod.encode_ssr_html(html)
    assert raw.startswith(b"\x00z1")
    assert len(raw) * 5 < len(html.encode())
    assert cache_mod.decode_ssr_value(raw) == html


def test_decode_legacy_uncompressed_values():
    html = "<html>старый формат</html>"
    assert cache_mod.decode_ssr_value(json.dumps(html)) == html
    assert cache_mod.decode_ssr_value(json.dumps(html).encode()) == html
    assert cache_mod.decode_ssr_value(None) is None
    assert cache_mod.decode_ssr_value(json.dumps({"a": 1})) == {"a": 1}


@pytest.fixture
def fake_bin_redis(monkeypatch):
    fakeredis = pytest.importorskip("fakeredis")
    server = fakeredis.FakeServer()
    r = fakeredis.aioredis.FakeRedis(server=server, decode_responses=False)
    monkeypatch.setattr(cache_mod, "_redis_bin", r)
    return r


def test_ssr_cache_set_get_compressed(fake_bin_redis):
    async def run():
        html = "<html>" + "x" * 5000 + "</html>"
        await cache_mod.ssr_cache_set("fe:k:v0:ssr:1:sig", html, 60)
        raw = await fake_bin_redis.get("fe:k:v0:ssr:1:sig")
        assert raw.startswith(b"\x00z1") and len(raw) < 200
        assert await fake_bin_redis.ttl("fe:k:v0:ssr:1:sig") == 60
        assert await cache_mod.ssr_cache_get("fe:k:v0:ssr:1:sig") == html
        # Значение, записанное прежним кодом (json.dumps через текстовый клиент).
        await fake_bin_redis.set("fe:k:v0:ssr:2:sig", json.dumps("<html>old</html>"))
        assert await cache_mod.ssr_cache_get("fe:k:v0:ssr:2:sig") == "<html>old</html>"
        assert await cache_mod.ssr_cache_get("fe:k:v0:ssr:missing") is None

    asyncio.run(run())


def test_ssr_cache_get_fails_open(monkeypatch):
    async def boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr(cache_mod, "get_redis_bin", boom)

    async def run():
        assert await cache_mod.ssr_cache_get("fe:x:ssr:y") is None
        await cache_mod.ssr_cache_set("fe:x:ssr:y", "<html></html>", 5)  # не бросает

    asyncio.run(run())


def test_seo_pages_uses_compressed_ssr_cache_functions():
    # conftest патчит seo_pages.cache_get/cache_set; сами имена — SSR-варианты.
    import importlib

    src = Path(importlib.import_module("app.api.seo_pages").__file__).read_text()
    assert "ssr_cache_get as cache_get" in src
    assert "ssr_cache_set as cache_set" in src


# ── TTL: закрытые годы живут дольше ────────────────────────────────────────


def test_year_ttl_historical_only():
    this_year = date.today().year
    base = 900
    assert seo_pages._year_ttl(this_year, base) == base
    assert seo_pages._year_ttl(this_year + 1, base) == base
    assert seo_pages._year_ttl(this_year - 1, base) == max(base, seo_pages._SSR_TTL_HISTORICAL_YEAR)
    assert seo_pages._year_ttl(str(this_year - 5), base) >= 24 * 3600
    assert seo_pages._year_ttl("abc", base) == base


# ── Route-level: home cached, world-vs reads its cache ─────────────────────


@pytest.fixture
def mem_cache(monkeypatch):
    store: dict[str, str] = {}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl=None):
        store[key] = value

    async def sig():
        return "sig-test"

    monkeypatch.setattr(seo_pages, "cache_get", fake_get)
    monkeypatch.setattr(seo_pages, "cache_set", fake_set)
    monkeypatch.setattr(seo_pages, "_asset_sig", sig)
    return store


def test_home_rendered_once_then_cached(client, mem_cache, monkeypatch):
    calls = {"n": 0}

    async def fake_home(db):
        calls["n"] += 1
        return "<html>home</html>"

    monkeypatch.setattr(seo_pages, "render_home_html", fake_home)
    r1 = client.get("/seo/page/home")
    r2 = client.get("/seo/page/home")
    assert r1.status_code == r2.status_code == 200
    assert r1.text == r2.text == "<html>home</html>"
    assert calls["n"] == 1
    assert len(mem_cache) == 1 and ":dashboard:" in next(iter(mem_cache))


def test_world_vs_served_from_cache_on_second_hit(client, mem_cache, monkeypatch):
    calls = {"n": 0}

    async def fake_vs(a, b, concept, db):
        calls["n"] += 1
        return 200, f"<html>{a} vs {b} {concept}</html>"

    monkeypatch.setattr(seo_pages, "render_world_vs_html", fake_vs)
    url = "/seo/world-vs/denmark-vs-united-states/inflation"
    r1 = client.get(url)
    r2 = client.get(url)
    assert r1.status_code == r2.status_code == 200
    assert r1.text == r2.text
    assert calls["n"] == 1


def test_world_vs_redirect_never_cached(client, mem_cache, monkeypatch):
    async def fake_vs(a, b, concept, db):
        return 301, "/world-vs/a-vs-b/inflation"

    monkeypatch.setattr(seo_pages, "render_world_vs_html", fake_vs)
    r = client.get("/seo/world-vs/b-vs-a/inflation", follow_redirects=False)
    assert r.status_code == 301
    assert mem_cache == {}


# ── OG disk cache: historical TTL + bounded cleanup ────────────────────────


@pytest.fixture
def og_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(og_image, "_DISK_DIR", tmp_path)
    with og_image._CACHE_LOCK:
        og_image._CACHE.clear()
    yield tmp_path
    with og_image._CACHE_LOCK:
        og_image._CACHE.clear()


def test_historical_og_uses_prefixed_file_and_long_ttl(og_dir, monkeypatch):
    asyncio.run(og_image.store_og_async("world-year:dk:2019", b"PNG-H", historical=True))
    files = [p.name for p in og_dir.iterdir()]
    assert len(files) == 1 and files[0].startswith("h-") and files[0].endswith(".png")
    path = og_dir / files[0]
    # Старше часового TTL, но моложе исторического: из памяти выкинуто — читается с диска.
    old = time.time() - 5 * 3600
    os.utime(path, (old, old))
    with og_image._CACHE_LOCK:
        og_image._CACHE.clear()
    assert og_image.cached_og("world-year:dk:2019", historical=True) == b"PNG-H"
    with og_image._CACHE_LOCK:
        og_image._CACHE.clear()
    # Не-исторический ключ того же кода — другой файл, его нет.
    assert og_image.cached_og("world-year:dk:2019") is None


def test_current_og_keeps_short_ttl(og_dir):
    og_image.store_og("indicator:cpi", b"PNG-C")
    path = next(og_dir.iterdir())
    assert not path.name.startswith("h-")
    old = time.time() - og_image._DISK_TTL - 60
    os.utime(path, (old, old))
    with og_image._CACHE_LOCK:
        og_image._CACHE.clear()
    assert og_image.cached_og("indicator:cpi") is None


def test_cleanup_removes_expired_and_bounds_size(og_dir, monkeypatch):
    now = time.time()
    # протухшие (старше 2×TTL своего класса)
    stale = og_dir / "a.png"
    stale.write_bytes(b"x" * 10)
    os.utime(stale, (now - 3 * og_image._DISK_TTL,) * 2)
    stale_h = og_dir / "h-b.png"
    stale_h.write_bytes(b"x" * 10)
    os.utime(stale_h, (now - 3 * og_image._DISK_TTL_HISTORICAL,) * 2)
    # исторический, старше часового TTL, но живой
    live_h = og_dir / "h-c.png"
    live_h.write_bytes(b"x" * 10)
    os.utime(live_h, (now - 3 * og_image._DISK_TTL,) * 2)
    # объём: 5 свежих по 100 байт при лимите 300 → останутся самые новые
    for i in range(5):
        p = og_dir / f"n{i}.png"
        p.write_bytes(b"y" * 100)
        os.utime(p, (now - 100 + i,) * 2)
    (og_dir / "keep.tmp").write_bytes(b"z")  # не-PNG не трогаем
    monkeypatch.setattr(og_image, "_DISK_MAX_BYTES", 300)
    stats = og_image.cleanup_og_disk(now)
    names = {p.name for p in og_dir.iterdir()}
    assert "a.png" not in names and "h-b.png" not in names
    assert "keep.tmp" in names
    total = sum((og_dir / n).stat().st_size for n in names if n.endswith(".png"))
    assert total <= 270
    assert "n4.png" in names and "n0.png" not in names
    assert stats["removed"] >= 4


def test_maybe_cleanup_rate_limited(og_dir, monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(og_image, "cleanup_og_disk", lambda: calls.__setitem__("n", calls["n"] + 1))
    monkeypatch.setattr(og_image, "_last_cleanup", 0.0)
    og_image._maybe_cleanup()
    og_image._maybe_cleanup()
    assert calls["n"] == 1


# ── Latest points: portable fallback + (opt-in) Postgres LATERAL parity ────


def _sqlite_session(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base

    db_path = tmp_path / "latest.db"
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def test_latest_points_fallback_on_sqlite(tmp_path):
    from sqlalchemy import insert

    from app.models import SubnationalDataPoint, WorldDataPoint

    engine, Session = _sqlite_session(tmp_path)

    async def run():
        async with Session() as db:
            await db.execute(insert(WorldDataPoint), [
                {"indicator_id": 1, "date": date(2020, 1, 1), "value": 1},
                {"indicator_id": 1, "date": date(2022, 1, 1), "value": 3},
                {"indicator_id": 1, "date": date(2021, 1, 1), "value": 2},
                {"indicator_id": 2, "date": date(2019, 1, 1), "value": 9},
            ])
            await db.execute(insert(SubnationalDataPoint), [
                {"indicator_id": 5, "region_id": 7, "period": date(2020, 1, 1), "value": 1},
                {"indicator_id": 5, "region_id": 7, "period": date(2023, 1, 1), "value": 4},
                {"indicator_id": 5, "region_id": 7, "period": date(2021, 1, 1), "value": 2},
                {"indicator_id": 5, "region_id": 8, "period": date(2024, 1, 1), "value": 99},
                {"indicator_id": 6, "region_id": 7, "period": date(2018, 1, 1), "value": 6},
            ])
            await db.commit()
            world = await wsq.latest_world_points(db, [1, 2, 3])
            region = await wsq.latest_region_points(db, 7, [5, 6, 42], limit=2)
            empty = await wsq.latest_world_points(db, [])
        await engine.dispose()
        return world, region, empty

    world, region, empty = asyncio.run(run())
    assert world == {1: (date(2022, 1, 1), 3.0), 2: (date(2019, 1, 1), 9.0)}
    assert region == {
        5: [(date(2023, 1, 1), 4.0), (date(2021, 1, 1), 2.0)],
        6: [(date(2018, 1, 1), 6.0)],
    }
    assert empty == {}


PG_URL = os.environ.get("RUSTATS_PERF_PG_URL")


@pytest.mark.skipif(not PG_URL, reason="set RUSTATS_PERF_PG_URL to a populated Postgres")
def test_lateral_matches_window_on_postgres():
    """LATERAL-путь отдаёт ровно то же, что прежний window-запрос (реальные данные)."""
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import SubnationalDataPoint, WorldIndicator

    async def run():
        engine = create_async_engine(PG_URL)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            regions = (await db.execute(text(
                "select region_id from subnational_data_points group by region_id "
                "order by count(*) desc limit 4"))).scalars().all()
            for rid in regions:
                ids = (await db.execute(
                    select(SubnationalDataPoint.indicator_id)
                    .where(SubnationalDataPoint.region_id == rid).distinct()
                )).scalars().all()
                for n in (1, 2):
                    new = await wsq.latest_region_points(db, rid, list(ids), limit=n)
                    old = await wsq._latest_region_points_window(db, rid, list(ids), limit=n)
                    assert new == old, (rid, n)
            countries = (await db.execute(text(
                "select country_id from world_indicators where is_listed "
                "group by country_id order by count(*) desc limit 3"))).scalars().all()
            for cid in countries:
                ids = (await db.execute(
                    select(WorldIndicator.id).where(WorldIndicator.country_id == cid).limit(3000)
                )).scalars().all()
                new = await wsq.latest_world_points(db, list(ids))
                old = await wsq._latest_world_points_window(db, list(ids))
                assert new == old, cid
        await engine.dispose()

    asyncio.run(run())
