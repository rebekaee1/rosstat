"""Допуск в SSR-кэш «со второго раза» (27.10.2026): хвост страниц не занимает память с первого визита."""
from __future__ import annotations

import asyncio

import fakeredis
import fakeredis.aioredis
import pytest

import app.api.seo_pages as seo_pages
import app.core.cache as cache_mod
from app.config import settings


@pytest.fixture
def fake_redis(monkeypatch):
    server = fakeredis.FakeServer()
    text_client = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setattr(cache_mod, "_redis", text_client)
    return text_client


def test_admit_seen_first_false_then_true(fake_redis):
    async def go():
        first = await cache_mod.admit_seen("fe:x:v0:ssr:a", 3600)
        second = await cache_mod.admit_seen("fe:x:v0:ssr:a", 3600)
        other = await cache_mod.admit_seen("fe:x:v0:ssr:b", 3600)
        return first, second, other

    assert asyncio.run(go()) == (False, True, False)


def test_admit_seen_remembers_previous_window_but_not_two_back(fake_redis, monkeypatch):
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(cache_mod.time, "time", lambda: clock["t"])

    async def go():
        assert await cache_mod.admit_seen("k", 600) is False
        clock["t"] += 600  # следующее окно: прошлое ещё помнится
        assert await cache_mod.admit_seen("k", 600) is True
        clock["t"] += 600 * 3  # прошло больше двух окон без обращений к ключу
        assert await cache_mod.admit_seen("k", 600) is False

    asyncio.run(go())


def test_admit_bitmaps_expire_and_have_fixed_size(fake_redis):
    async def go():
        for i in range(50):
            await cache_mod.admit_seen(f"url-{i}", 3600)
        keys = [k async for k in fake_redis.scan_iter("fe:admit:*")]
        assert len(keys) == 1  # одна карта на окно, а не ключ на адрес
        ttl = await fake_redis.ttl(keys[0])
        assert 0 < ttl <= 2 * 3600 + 3600  # карта с TTL: политика volatile-lru её видит
        assert await fake_redis.strlen(keys[0]) <= (1 << 22) // 8

    asyncio.run(go())


def test_admit_seen_fails_open_when_redis_is_down(monkeypatch):
    class Broken:
        def pipeline(self, *a, **k):
            raise ConnectionError("redis down")

    async def broken():
        return Broken()

    monkeypatch.setattr(cache_mod, "get_redis", broken)
    assert asyncio.run(cache_mod.admit_seen("k", 3600)) is True


@pytest.fixture
def admit_env(monkeypatch, fake_redis):
    store: dict[str, str] = {}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl=None, **kw):
        store[key] = value

    async def plain_key(ns, rest):
        return f"fe:{ns}:v0:{rest}"

    async def sig():
        return "sig"

    monkeypatch.setattr(seo_pages, "cache_get", fake_get)
    monkeypatch.setattr(seo_pages, "cache_set", fake_set)
    monkeypatch.setattr(seo_pages, "versioned_key", plain_key)
    monkeypatch.setattr(seo_pages, "_asset_sig", sig)
    monkeypatch.setattr(seo_pages, "admit_seen", cache_mod.admit_seen)  # настоящий фильтр поверх fakeredis
    monkeypatch.setattr(settings, "ssr_admit_on_repeat_enabled", True)
    monkeypatch.setattr(settings, "ssr_swr_enabled", False)
    return store


def _render_counter():
    calls = {"n": 0}

    async def render():
        calls["n"] += 1
        return 200, "<html>год</html>"

    return calls, render


def test_tail_page_cached_only_on_second_visit(admit_env):
    calls, render = _render_counter()

    async def go():
        out = []
        for _ in range(4):
            out.append(await seo_pages._cached_html(
                "ssr-world", "world-year:de:x:2019:ru", 86400, render, admit_on_repeat=True,
            ))
        return out

    out = asyncio.run(go())
    assert all(s == 200 for s, _ in out)
    # 1-й визит: рендер без записи; 2-й: рендер и запись; 3-й и 4-й — из кэша.
    assert calls["n"] == 2
    assert len(admit_env) == 1


def test_one_visit_pages_do_not_touch_the_cache(admit_env):
    calls, render = _render_counter()

    async def go():
        for i in range(30):
            await seo_pages._cached_html(
                "ssr-world", f"world-year:de:x:{2000 + i}:ru", 86400, render, admit_on_repeat=True,
            )

    asyncio.run(go())
    assert admit_env == {}


def test_regular_pages_are_cached_immediately(admit_env):
    calls, render = _render_counter()

    async def go():
        await seo_pages._cached_html("cpi", "indicator:cpi::ru", 900, render)
        await seo_pages._cached_html("cpi", "indicator:cpi::ru", 900, render)

    asyncio.run(go())
    assert calls["n"] == 1
    assert len(admit_env) == 1


def test_switch_off_restores_write_on_first_visit(admit_env, monkeypatch):
    monkeypatch.setattr(settings, "ssr_admit_on_repeat_enabled", False)
    calls, render = _render_counter()

    async def go():
        await seo_pages._cached_html("ssr-world", "world-year:de:x:2019:ru", 86400, render, admit_on_repeat=True)
        await seo_pages._cached_html("ssr-world", "world-year:de:x:2019:ru", 86400, render, admit_on_repeat=True)

    asyncio.run(go())
    assert calls["n"] == 1
    assert len(admit_env) == 1


def test_404_is_never_stored_or_remembered(admit_env, fake_redis):
    async def render():
        return 404, "Not found"

    async def go():
        await seo_pages._cached_html("ssr-world", "world-year:de:x:1999:ru", 86400, render, admit_on_repeat=True)
        return [k async for k in fake_redis.scan_iter("fe:admit:*")]

    assert asyncio.run(go()) == []
    assert admit_env == {}


def test_background_revalidation_writes_without_admission(admit_env, monkeypatch):
    """Фоновый пересчёт (заголовок X-FE-Revalidate) пишет всегда: запись уже была допущена раньше."""
    from app.services import ssr_swr

    monkeypatch.setattr(settings, "ssr_swr_enabled", True)
    monkeypatch.setattr(settings, "ssr_swr_stale_seconds", 3600)

    async def fake_get_swr(key):
        return None, False

    monkeypatch.setattr(seo_pages, "cache_get_swr", fake_get_swr)
    calls, render = _render_counter()

    async def go():
        token = ssr_swr._revalidate_var.set(True)
        try:
            await seo_pages._cached_html("ssr-world", "world-year:de:x:2019:ru", 86400, render, admit_on_repeat=True)
        finally:
            ssr_swr._revalidate_var.reset(token)

    asyncio.run(go())
    assert calls["n"] == 1
    assert len(admit_env) == 1


def test_tail_routes_opt_in_and_hot_routes_do_not():
    """Какие маршруты идут через фильтр допуска: хвост — да, главная и каталоги — нет."""
    import inspect

    src = inspect.getsource(seo_pages)
    for renderer in (
        "render_indicator_year_html", "render_indicator_month_html", "render_world_indicator_html",
        "render_world_indicator_year_html", "render_region_indicator_year_html", "render_region_indicator_html",
        "render_subnational_indicator_year_html", "render_subnational_indicator_html",
    ):
        i = src.index(f"lambda: {renderer}(")
        assert "admit_on_repeat=True" in src[i:i + 260], renderer
    for renderer in ("render_home_html", "render_world_country_html", "render_world_rating_html", "render_indicator_html"):
        for part in src.split(f"lambda: {renderer}(")[1:]:
            assert "admit_on_repeat" not in part[:200], renderer
