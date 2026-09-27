"""П-14/П-15/П-11: Redis-кэш SSR HTML (риск Р-5: stale-данные и asset-hash trap).

Контракт `_cached_html`:
- 200-ответ кэшируется, повторный вызов не рендерит заново;
- 404 НЕ кэшируется (индикатор мог появиться после seed);
- смена подписи Vite-ассетов меняет ключ → закэшированный HTML со старыми
  чанками не отдаётся (asset-hash trap);
- ключи индикаторных страниц живут в версионированном namespace fe:{code}:v{N}
  — ETL-инвалидация бампает версию (П-11, без SCAN), старый ключ не читается.
"""

import asyncio

import pytest

import app.api.seo_pages as seo_pages
import app.core.cache as cache_mod


@pytest.fixture
def mem_cache(monkeypatch):
    store: dict[str, str] = {}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl=None):
        store[key] = value

    async def plain_key(ns, rest):
        return f"fe:{ns}:v0:{rest}"

    monkeypatch.setattr(seo_pages, "cache_get", fake_get)
    monkeypatch.setattr(seo_pages, "cache_set", fake_set)
    monkeypatch.setattr(seo_pages, "versioned_key", plain_key)
    return store


@pytest.fixture
def fixed_sig(monkeypatch):
    async def fake_sig():
        return "sig-aaa"

    monkeypatch.setattr(seo_pages, "_asset_sig", fake_sig)


def test_second_call_served_from_cache(mem_cache, fixed_sig):
    calls = {"n": 0}

    async def render():
        calls["n"] += 1
        return 200, "<html>страница</html>"

    async def run():
        s1, h1 = await seo_pages._cached_html("cpi", "indicator:cpi:", 900, render)
        s2, h2 = await seo_pages._cached_html("cpi", "indicator:cpi:", 900, render)
        return s1, h1, s2, h2

    s1, h1, s2, h2 = asyncio.run(run())
    assert (s1, s2) == (200, 200)
    assert h1 == h2
    assert calls["n"] == 1, "второй запрос обязан идти из кэша"


def test_404_not_cached(mem_cache, fixed_sig):
    calls = {"n": 0}

    async def render():
        calls["n"] += 1
        return 404, "Not found"

    async def run():
        await seo_pages._cached_html("nope", "indicator:nope:", 900, render)
        await seo_pages._cached_html("nope", "indicator:nope:", 900, render)

    asyncio.run(run())
    assert calls["n"] == 2, "404 не должен прилипать в кэше"
    assert mem_cache == {}


def test_asset_sig_change_busts_cache(mem_cache, monkeypatch):
    sigs = iter(["sig-old", "sig-new"])

    async def fake_sig():
        return next(sigs)

    monkeypatch.setattr(seo_pages, "_asset_sig", fake_sig)
    calls = {"n": 0}

    async def render():
        calls["n"] += 1
        return 200, f"<html>v{calls['n']}</html>"

    async def run():
        await seo_pages._cached_html("cpi", "indicator:cpi:", 900, render)
        return await seo_pages._cached_html("cpi", "indicator:cpi:", 900, render)

    _, html2 = asyncio.run(run())
    assert calls["n"] == 2, "смена ассетов = новый ключ = новый рендер"
    assert html2 == "<html>v2</html>"


def test_indicator_keys_live_in_etl_invalidated_namespace(fixed_sig, mem_cache):
    async def render():
        return 200, "<html>x</html>"

    asyncio.run(seo_pages._cached_html("cpi", "indicator:cpi:", 900, render))
    assert len(mem_cache) == 1
    key = next(iter(mem_cache))
    assert key.startswith("fe:cpi:"), (
        "ключ обязан попадать под cache_invalidate_indicator('cpi') → fe:cpi:*"
    )


def test_singleflight_renders_once_for_concurrent_misses(mem_cache, fixed_sig):
    calls = {"n": 0}

    async def slow_render():
        calls["n"] += 1
        await asyncio.sleep(0.02)
        return 200, "<html>тяжёлый рендер</html>"

    async def run():
        return await asyncio.gather(*[
            seo_pages._cached_html("cpi", "indicator:cpi:", 900, slow_render)
            for _ in range(5)
        ])

    results = asyncio.run(run())
    assert calls["n"] == 1, "П-11: конкурентные miss'ы не должны рендерить 5 раз"
    assert all(r == (200, "<html>тяжёлый рендер</html>") for r in results)


# --- П-11: версионированная инвалидация (fakeredis, без SCAN) ----------------


@pytest.fixture
def fake_cache_redis(monkeypatch):
    import fakeredis.aioredis

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache_mod, "_redis", fake)
    cache_mod._ver_local.clear()
    yield fake
    cache_mod._ver_local.clear()


def test_invalidate_bumps_version_and_hides_old_keys(fake_cache_redis):
    async def run():
        key1 = await cache_mod.versioned_key("cpi", "detail")
        await cache_mod.cache_set(key1, {"v": 1}, 300)
        assert await cache_mod.cache_get(key1) == {"v": 1}

        await cache_mod.cache_invalidate_indicator("cpi")

        key2 = await cache_mod.versioned_key("cpi", "detail")
        assert key2 != key1, "после инвалидации версия namespace обязана смениться"
        assert await cache_mod.cache_get(key2) is None, "новый ключ = cache-miss"
        return key1, key2

    key1, key2 = asyncio.run(run())
    assert key1.startswith("fe:cpi:v") and key2.startswith("fe:cpi:v")


def test_invalidate_covers_list_and_dashboard_namespaces(fake_cache_redis):
    async def run():
        k_list = await cache_mod.versioned_key("indicators", "list:all")
        k_dash = await cache_mod.versioned_key("dashboard", "sparklines")
        await cache_mod.cache_invalidate_indicator("cpi")
        return (
            k_list != await cache_mod.versioned_key("indicators", "list:all"),
            k_dash != await cache_mod.versioned_key("dashboard", "sparklines"),
        )

    list_bumped, dash_bumped = asyncio.run(run())
    assert list_bumped, "листинг индикаторов обязан инвалидироваться"
    assert dash_bumped, "dashboard-спарклайны обязаны инвалидироваться"


def test_local_version_cache_survives_redis_outage(fake_cache_redis, monkeypatch):
    async def run():
        key1 = await cache_mod.versioned_key("cpi", "detail")

        async def broken():
            raise ConnectionError("redis down")

        monkeypatch.setattr(cache_mod, "get_redis", broken)
        cache_mod._ver_local.clear()
        key2 = await cache_mod.versioned_key("cpi", "detail")
        return key1, key2

    key1, key2 = asyncio.run(run())
    assert key2 == "fe:cpi:v0:detail", "fail-open: без Redis версия дефолтная"


@pytest.fixture
def fake_world_catalog_redis(monkeypatch):
    import fakeredis.aioredis

    cache = fakeredis.aioredis.FakeRedis(decode_responses=True)
    state = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache_mod, "_redis", cache)
    monkeypatch.setattr(cache_mod, "_state_redis", state)
    cache_mod._ver_local.clear()
    yield cache, state
    cache_mod._ver_local.clear()


def test_world_catalog_durable_mirror_survives_cache_flush(fake_world_catalog_redis):
    cache, _state = fake_world_catalog_redis

    async def run():
        key = await cache_mod.versioned_key("world-catalog", "countries:v8:ru")
        assert key == "fe:world-catalog:g2:v0:countries:v8:ru"
        assert await cache_mod.set_versioned_durable_world_countries(
            "ru", key, {"total": 54},
        )
        await cache.set(key, '{"total":54}', ex=600)
        await cache.flushdb()  # manual recovery; state Redis is untouched
        cache_mod._ver_local.clear()
        after = await cache_mod.versioned_key("world-catalog", "countries:v8:ru")
        payload, stale = await cache_mod.get_versioned_durable_world_countries("ru", after)
        return key, after, payload, stale

    key, after, payload, stale = asyncio.run(run())
    assert after == key
    assert (payload, stale) == ({"total": 54}, False)


def test_world_catalog_last_good_survives_two_bumps_without_extending_grace(
    fake_world_catalog_redis,
):
    _cache, state = fake_world_catalog_redis

    async def run():
        old = await cache_mod.versioned_key("world-catalog", "countries:v8:en")
        await cache_mod.set_versioned_durable_world_countries("en", old, {"total": 54})
        await cache_mod.bump_namespaces("world-catalog")
        current = await cache_mod.versioned_key("world-catalog", "countries:v8:en")
        fresh = await cache_mod.get_versioned_durable_world_countries("en", current)
        stale = await cache_mod.get_versioned_durable_world_countries(
            "en", current, allow_stale=True,
        )
        grace_key = cache_mod._world_countries_stale_key("en")
        first_ttl = await state.ttl(grace_key)
        first_deadline = await state.get(grace_key)
        assert first_ttl > 0
        await cache_mod.bump_namespaces("world-catalog")
        next_key = await cache_mod.versioned_key("world-catalog", "countries:v8:en")
        two_bumps = await cache_mod.get_versioned_durable_world_countries(
            "en", next_key, allow_stale=True,
        )
        second_ttl = await state.ttl(grace_key)
        second_deadline = await state.get(grace_key)
        await state.delete(grace_key)  # first bump's grace expired
        expired = await cache_mod.get_versioned_durable_world_countries(
            "en", next_key, allow_stale=True,
        )
        await cache_mod.bump_namespaces("world-catalog")
        third_key = await cache_mod.versioned_key("world-catalog", "countries:v8:en")
        no_renewal = await cache_mod.get_versioned_durable_world_countries(
            "en", third_key, allow_stale=True,
        )
        return (
            fresh, stale, two_bumps, first_ttl, second_ttl,
            first_deadline, second_deadline, expired, no_renewal,
        )

    (
        fresh, stale, two_bumps, first_ttl, second_ttl,
        first_deadline, second_deadline, expired, no_renewal,
    ) = asyncio.run(run())
    assert fresh == (None, False)
    assert stale == ({"total": 54}, True)
    assert two_bumps == ({"total": 54}, True)
    assert second_ttl <= first_ttl
    assert second_deadline == first_deadline
    assert expired == (None, False)
    assert no_renewal == (None, False)


def test_world_catalog_late_builder_cannot_poison_current_generation(fake_world_catalog_redis):
    _cache, state = fake_world_catalog_redis

    async def run():
        old = await cache_mod.versioned_key("world-catalog", "countries:v8:ru")
        await cache_mod.bump_namespaces("world-catalog")
        current = await cache_mod.versioned_key("world-catalog", "countries:v8:ru")
        # The check bypasses the five-second local version memo, as another
        # worker can bump the state generation during a cold SQL build.
        cache_mod._ver_local["world-catalog"] = (float("inf"), "0")
        assert await cache_mod.versioned_key("world-catalog", "countries:v8:ru") == old
        assert await cache_mod.fresh_world_catalog_key("countries:v8:ru") == current
        assert not await cache_mod.is_current_world_countries_key("ru", old)
        assert await cache_mod.get_versioned_durable_world_countries("ru", old) == (None, False)
        assert not await cache_mod.set_versioned_durable_world_countries(
            "ru", old, {"total": 53},
        )
        assert await cache_mod.set_versioned_durable_world_countries(
            "ru", current, {"total": 54},
        )
        assert await state.get(cache_mod._world_countries_pointer_key("ru")) == current
        assert not await state.exists(cache_mod._world_countries_stale_key("ru"))
        return await cache_mod.get_versioned_durable_world_countries("ru", current)

    assert asyncio.run(run()) == ({"total": 54}, False)


def test_world_catalog_successful_build_resets_only_its_locale_grace(fake_world_catalog_redis):
    _cache, state = fake_world_catalog_redis

    async def run():
        ru_old = await cache_mod.fresh_world_catalog_key("countries:v8:ru")
        en_old = await cache_mod.fresh_world_catalog_key("countries:v8:en")
        assert await cache_mod.set_versioned_durable_world_countries(
            "ru", ru_old, {"total": 1},
        )
        assert await cache_mod.set_versioned_durable_world_countries(
            "en", en_old, {"total": 1},
        )
        await cache_mod.bump_namespaces("world-catalog")
        en_deadline = await state.get(cache_mod._world_countries_stale_key("en"))
        ru_new = await cache_mod.fresh_world_catalog_key("countries:v8:ru")
        assert await cache_mod.set_versioned_durable_world_countries(
            "ru", ru_new, {"total": 2},
        )
        assert not await state.exists(cache_mod._world_countries_stale_key("ru"))
        await cache_mod.bump_namespaces("world-catalog")
        ru_current = await cache_mod.fresh_world_catalog_key("countries:v8:ru")
        en_current = await cache_mod.fresh_world_catalog_key("countries:v8:en")
        return (
            await cache_mod.get_versioned_durable_world_countries(
                "ru", ru_current, allow_stale=True,
            ),
            await cache_mod.get_versioned_durable_world_countries(
                "en", en_current, allow_stale=True,
            ),
            await state.get(cache_mod._world_countries_stale_key("en")),
            en_deadline,
        )

    ru, en, after, before = asyncio.run(run())
    assert ru == ({"total": 2}, True)
    assert en == ({"total": 1}, True)
    assert after == before


def test_world_catalog_mirror_has_bounded_absolute_age(fake_world_catalog_redis, monkeypatch):
    now = cache_mod.time.time()
    monkeypatch.setattr(cache_mod.time, "time", lambda: now)

    async def run():
        key = await cache_mod.fresh_world_catalog_key("countries:v8:ru")
        assert await cache_mod.set_versioned_durable_world_countries(
            "ru", key, {"total": 54},
        )
        assert await cache_mod.get_versioned_durable_world_countries("ru", key) == (
            {"total": 54}, False,
        )
        monkeypatch.setattr(
            cache_mod.time, "time",
            lambda: now + cache_mod._WORLD_COUNTRIES_MAX_FRESH_SECONDS + 1,
        )
        return await cache_mod.get_versioned_durable_world_countries("ru", key)

    assert asyncio.run(run()) == (None, False)


def test_world_catalog_invalidation_failure_is_explicit(fake_world_catalog_redis, monkeypatch):
    _cache, state = fake_world_catalog_redis
    calls = 0

    async def broken_eval(*_args):
        nonlocal calls
        calls += 1
        raise ConnectionError("state Redis unavailable")

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(state, "eval", broken_eval)
    monkeypatch.setattr(cache_mod.asyncio, "sleep", no_sleep)
    before = cache_mod.failure_counters["cache_invalidate"]
    with pytest.raises(cache_mod.WorldCatalogInvalidationError):
        asyncio.run(cache_mod.bump_namespaces("world-catalog"))
    assert calls == 3
    assert cache_mod.failure_counters["cache_invalidate"] == before + 1


def test_world_catalog_build_lock_is_shared(fake_world_catalog_redis):
    async def run():
        async with cache_mod.world_countries_build_lock("ru", wait_seconds=0) as first:
            assert first
            async with cache_mod.world_countries_build_lock("ru", wait_seconds=0) as second:
                assert not second
        async with cache_mod.world_countries_build_lock("ru", wait_seconds=0) as third:
            return third

    assert asyncio.run(run())
