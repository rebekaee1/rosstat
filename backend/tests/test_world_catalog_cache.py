"""Cold country-catalogue requests must not fan out across web workers."""

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api import world
from app.core import cache


def test_listing_repair_invalidates_catalog_and_surfaces_failure(auth_env, monkeypatch):
    """A manual listing repair must change the API generation after DB writes."""
    path = Path(__file__).resolve().parents[1] / "scripts" / "repair-world-listing.py"
    spec = importlib.util.spec_from_file_location("repair_world_listing_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    async def unchanged():
        return 0

    async def stats():
        return {"dup_name_groups": 0, "listed_empty_unit": 0}

    for name in (
        "purge_excluded_geos", "apply_editorial_listing_modes",
        "apply_defect_filters", "dedupe_same_frequency",
        "fold_frequency_cards", "dedupe_display_names",
        "apply_country_visibility", "unlist_eurostat_on_national_passports",
        "unlist_all_zero_series",
    ):
        monkeypatch.setattr(module, name, unchanged)

    async def retitle():
        return 0, {}

    monkeypatch.setattr(module, "retitle_all", retitle)
    monkeypatch.setattr(module, "_stats", stats)
    monkeypatch.setattr(module, "_audit_card_keys", stats)

    async def run():
        before = await cache.fresh_world_catalog_key("countries:v8:ru")
        assert await module.main() == 0
        after = await cache.fresh_world_catalog_key("countries:v8:ru")
        assert before != after

        async def failed_bump(*_namespaces):
            raise cache.WorldCatalogInvalidationError("state Redis unavailable")

        monkeypatch.setattr(module, "bump_namespaces", failed_bump)
        with pytest.raises(cache.WorldCatalogInvalidationError):
            await module.main()

    asyncio.run(run())


def test_cold_world_catalog_builds_once(auth_env, monkeypatch):
    monkeypatch.setattr(world, "get_locale", lambda: "ru")
    builds = 0

    async def build(_db):
        nonlocal builds
        builds += 1
        await asyncio.sleep(0.05)
        return {"countries": [], "total": 1}

    monkeypatch.setattr(world, "_build_world_countries_payload", build)

    async def run():
        return await asyncio.gather(*(world.list_countries(None) for _ in range(4)))

    responses = asyncio.run(run())
    assert builds == 1
    assert all(response.status_code == 200 for response in responses)
    assert all(json.loads(response.body)["total"] == 1 for response in responses)


def test_world_catalog_serves_bounded_stale_during_rebuild(auth_env, monkeypatch):
    monkeypatch.setattr(world, "get_locale", lambda: "ru")

    async def run():
        original = await cache.fresh_world_catalog_key("countries:v8:ru")
        await cache.set_versioned_durable_world_countries(
            "ru", original, {"countries": [], "total": 1},
        )
        await cache.bump_namespaces("world-catalog")
        started = asyncio.Event()
        finish = asyncio.Event()

        async def build(_db):
            started.set()
            await finish.wait()
            return {"countries": [], "total": 2}

        monkeypatch.setattr(world, "_build_world_countries_payload", build)
        builder = asyncio.create_task(world.list_countries(None))
        await asyncio.wait_for(started.wait(), timeout=2)
        waiting = await world.list_countries(None)
        assert waiting.status_code == 200
        assert waiting.headers["cache-control"] == "no-store"
        assert json.loads(waiting.body)["total"] == 1
        finish.set()
        rebuilt = await asyncio.wait_for(builder, timeout=2)
        assert rebuilt.headers["cache-control"].startswith("public")
        assert json.loads(rebuilt.body)["total"] == 2

    asyncio.run(run())


def test_world_catalog_does_not_publish_pre_bump_build(auth_env, monkeypatch):
    monkeypatch.setattr(world, "get_locale", lambda: "en")

    async def build(_db):
        await cache.bump_namespaces("world-catalog")
        return {"countries": [], "total": 1}

    monkeypatch.setattr(world, "_build_world_countries_payload", build)

    async def run():
        with pytest.raises(HTTPException) as error:
            await world.list_countries(None)
        assert error.value.status_code == 503
        current = await cache.fresh_world_catalog_key("countries:v8:en")
        assert await cache.cache_get(current) is None
        assert await cache.get_versioned_durable_world_countries("en", current) == (None, False)

    asyncio.run(run())


def test_world_catalog_rechecks_stale_deadline_after_failed_build(auth_env, monkeypatch):
    monkeypatch.setattr(world, "get_locale", lambda: "ru")

    async def run():
        original = await cache.fresh_world_catalog_key("countries:v8:ru")
        assert await cache.set_versioned_durable_world_countries(
            "ru", original, {"countries": [], "total": 1},
        )
        await cache.bump_namespaces("world-catalog")

        async def fail_after_grace(_db):
            state = await cache.get_state_redis()
            await state.delete(cache._world_countries_stale_key("ru"))
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(world, "_build_world_countries_payload", fail_after_grace)
        with pytest.raises(HTTPException) as error:
            await world.list_countries(None)
        assert error.value.status_code == 503

    asyncio.run(run())
