"""Stale-while-revalidate для SSR HTML и API (круг 12, SPEED2): устаревшее отдаётся сразу, пересчёт — один на ключ."""
from __future__ import annotations

import asyncio

import fakeredis
import fakeredis.aioredis
import pytest

import app.api.seo_pages as seo_pages
import app.core.cache as cache_mod
from app.config import settings
from app.services import ssr_swr


@pytest.fixture
def redis_pair(monkeypatch):
    """Один «сервер» Redis для текстового и бинарного клиентов кэша."""
    server = fakeredis.FakeServer()
    text_client = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    bin_client = fakeredis.aioredis.FakeRedis(server=server, decode_responses=False)
    monkeypatch.setattr(cache_mod, "_redis", text_client)
    monkeypatch.setattr(cache_mod, "_redis_bin", bin_client)
    return text_client, bin_client


@pytest.fixture
def swr_on(monkeypatch, redis_pair):
    monkeypatch.setattr(settings, "ssr_swr_enabled", True)
    monkeypatch.setattr(settings, "ssr_swr_stale_seconds", 3600)
    # Тесты кэша SSR (conftest) подменяют cache_get/cache_set; для SWR нужны настоящие.
    monkeypatch.setattr(seo_pages, "cache_get", cache_mod.ssr_cache_get)
    monkeypatch.setattr(seo_pages, "cache_set", cache_mod.ssr_cache_set)
    monkeypatch.setattr(seo_pages, "cache_get_swr", cache_mod.ssr_cache_get_swr)

    async def plain_key(ns, rest):
        return f"fe:{ns}:v0:{rest}"

    async def sig():
        return "sig"

    monkeypatch.setattr(seo_pages, "versioned_key", plain_key)
    monkeypatch.setattr(seo_pages, "_asset_sig", sig)
    ssr_swr._inflight.clear()
    return redis_pair


def _target(monkeypatch, value=("forecasteconomy.com", "/germany", "")):
    token = ssr_swr._target_var.set(value)
    monkeypatch.setattr(ssr_swr, "_replay", _record_replay)
    return token


replays: list[tuple[str, str, str]] = []


async def _record_replay(key, host, path, locale_header=""):
    replays.append((key, host, path))
    ssr_swr._inflight.discard(key)


def test_flag_is_off_by_default():
    assert settings.ssr_swr_enabled is False


def test_fresh_record_has_marker_and_longer_redis_ttl(swr_on):
    text_client, bin_client = swr_on

    async def go():
        await cache_mod.ssr_cache_set("fe:x:v0:ssr:a", "<html>1</html>", 300, stale_ttl=3600)
        ttl_value = await bin_client.ttl("fe:x:v0:ssr:a")
        ttl_marker = await bin_client.ttl("fe:x:v0:ssr:a:fresh")
        value, fresh = await cache_mod.ssr_cache_get_swr("fe:x:v0:ssr:a")
        return ttl_value, ttl_marker, value, fresh

    ttl_value, ttl_marker, value, fresh = asyncio.run(go())
    assert 3800 < ttl_value <= 3900 and 250 < ttl_marker <= 300
    assert (value, fresh) == ("<html>1</html>", True)


def test_stale_record_served_immediately_and_revalidated_once(swr_on, monkeypatch):
    replays.clear()
    calls = {"n": 0}

    async def render():
        calls["n"] += 1
        return 200, f"<html>v{calls['n']}</html>"

    async def go():
        _target(monkeypatch)
        s1, h1 = await seo_pages._cached_html("world", "world:germany:ru", 300, render)
        # срок «свежести» истёк: маркер пропал, значение осталось
        for k in [k async for k in swr_on[1].scan_iter(match="*:fresh")]:
            await swr_on[1].delete(k)
        s2, h2 = await seo_pages._cached_html("world", "world:germany:ru", 300, render)
        s3, h3 = await seo_pages._cached_html("world", "world:germany:ru", 300, render)
        await asyncio.sleep(0)
        return (s1, h1), (s2, h2), (s3, h3)

    first, second, third = asyncio.run(go())
    assert first == (200, "<html>v1</html>")
    assert second == (200, "<html>v1</html>"), "устаревшее отдаётся сразу, без рендера"
    assert third == (200, "<html>v1</html>")
    assert calls["n"] == 1, "рендер в пути запроса не вызывался"
    assert len(replays) == 1, "пересчёт один на ключ (замок в Redis), второй запрос его не дублирует"
    assert replays[0][1:] == ("forecasteconomy.com", "/germany")


def test_forced_revalidation_skips_cache_and_rewrites(swr_on, monkeypatch):
    calls = {"n": 0}

    async def render():
        calls["n"] += 1
        return 200, f"<html>v{calls['n']}</html>"

    async def go():
        await seo_pages._cached_html("world", "world:germany:ru", 300, render)
        token = ssr_swr._revalidate_var.set(True)
        try:
            _, forced = await seo_pages._cached_html("world", "world:germany:ru", 300, render)
        finally:
            ssr_swr._revalidate_var.reset(token)
        _, after = await seo_pages._cached_html("world", "world:germany:ru", 300, render)
        return forced, after

    forced, after = asyncio.run(go())
    assert forced == "<html>v2</html>"
    assert after == "<html>v2</html>"
    assert calls["n"] == 2


def test_flag_off_keeps_plain_behavior(monkeypatch, redis_pair):
    monkeypatch.setattr(settings, "ssr_swr_enabled", False)
    store = {}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl=None):
        store[key] = value

    async def plain_key(ns, rest):
        return f"fe:{ns}:v0:{rest}"

    async def sig():
        return "sig"

    monkeypatch.setattr(seo_pages, "cache_get", fake_get)
    monkeypatch.setattr(seo_pages, "cache_set", fake_set)
    monkeypatch.setattr(seo_pages, "versioned_key", plain_key)
    monkeypatch.setattr(seo_pages, "_asset_sig", sig)
    calls = {"n": 0}

    async def render():
        calls["n"] += 1
        return 200, "<html>x</html>"

    async def go():
        await seo_pages._cached_html("a", "v", 300, render)
        await seo_pages._cached_html("a", "v", 300, render)

    asyncio.run(go())
    assert calls["n"] == 1 and len(store) == 1


def test_api_cache_helpers(swr_on, monkeypatch):
    replays.clear()

    async def go():
        _target(monkeypatch, ("forecasteconomy.com", "/api/v1/indicators", ""))
        await ssr_swr.api_cache_set("fe:indicators:v0:list", [{"a": 1}], 60)
        fresh = await ssr_swr.api_cache_get("fe:indicators:v0:list")
        await swr_on[0].delete("fe:indicators:v0:list:fresh")
        stale = await ssr_swr.api_cache_get("fe:indicators:v0:list")
        await asyncio.sleep(0)
        return fresh, stale

    fresh, stale = asyncio.run(go())
    assert fresh == [{"a": 1}] and stale == [{"a": 1}]
    assert len(replays) == 1 and replays[0][2] == "/api/v1/indicators"


def test_api_cache_helpers_use_plain_getter_when_off(monkeypatch):
    monkeypatch.setattr(settings, "ssr_swr_enabled", False)
    seen = {}

    async def getter(key):
        seen["get"] = key
        return {"ok": 1}

    async def setter(key, value, ttl=None):
        seen["set"] = (key, value, ttl)

    async def go():
        got = await ssr_swr.api_cache_get("k", getter)
        await ssr_swr.api_cache_set("k", {"v": 1}, 5, setter)
        return got

    assert asyncio.run(go()) == {"ok": 1}
    assert seen == {"get": "k", "set": ("k", {"v": 1}, 5)}


class _Req:
    def __init__(self, headers, path="/seo/world/germany", query=""):
        self.headers = headers

        class _Url:
            pass

        self.url = _Url()
        self.url.path = path
        self.url.query = query


def test_revalidate_header_needs_valid_token(monkeypatch):
    monkeypatch.setattr(settings, "ssr_swr_enabled", True)
    good = ssr_swr.bind_request(_Req({"host": "x", ssr_swr.REVALIDATE_HEADER: ssr_swr.revalidate_token()}))
    try:
        assert ssr_swr.revalidate_requested() is True
        assert ssr_swr._target_var.get() is None, "пересчёт не порождает пересчётов"
    finally:
        ssr_swr.unbind_request(good)
    bad = ssr_swr.bind_request(_Req({"host": "x", ssr_swr.REVALIDATE_HEADER: "guess"}))
    try:
        assert ssr_swr.revalidate_requested() is False
    finally:
        ssr_swr.unbind_request(bad)


def test_target_uses_original_uri_only_for_seo_paths(monkeypatch):
    monkeypatch.setattr(settings, "ssr_swr_enabled", True)
    seo = ssr_swr.bind_request(
        _Req({"host": "ru.forecasteconomy.com", "x-original-uri": "/germany?x=1"}, path="/seo/world/germany")
    )
    try:
        assert ssr_swr._target_var.get() == ("ru.forecasteconomy.com", "/germany?x=1", "")
    finally:
        ssr_swr.unbind_request(seo)
    api = ssr_swr.bind_request(
        _Req({"host": "forecasteconomy.com", "x-original-uri": "/evil"}, path="/api/v1/indicators", query="a=1")
    )
    try:
        assert ssr_swr._target_var.get() == ("forecasteconomy.com", "/api/v1/indicators?a=1", "")
    finally:
        ssr_swr.unbind_request(api)
    hostile = ssr_swr.bind_request(
        _Req({"host": "forecasteconomy.com", "x-original-uri": "//evil.example/"}, path="/seo/page/home")
    )
    try:
        assert ssr_swr._target_var.get() == ("forecasteconomy.com", "/seo/page/home", "")
    finally:
        ssr_swr.unbind_request(hostile)


def test_flag_off_binds_nothing(monkeypatch):
    monkeypatch.setattr(settings, "ssr_swr_enabled", False)
    assert ssr_swr.bind_request(_Req({"host": "x"})) == ()
