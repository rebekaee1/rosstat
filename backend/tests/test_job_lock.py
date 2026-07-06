"""О-13: распределённый лок мутационных джобов планировщика."""

import asyncio

import fakeredis.aioredis
import pytest

from app.main import locked_job


@pytest.fixture
def fake_state_redis(monkeypatch):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _get_state_redis():
        return redis

    import app.core.cache as cache_mod
    monkeypatch.setattr(cache_mod, "get_state_redis", _get_state_redis)
    return redis


def test_second_concurrent_run_is_skipped(fake_state_redis):
    calls = []

    async def job():
        calls.append(1)
        await asyncio.sleep(0.05)
        return "done"

    wrapped = locked_job(job, "test_job", ttl_seconds=60)

    async def scenario():
        return await asyncio.gather(wrapped(), wrapped())

    results = asyncio.run(scenario())
    # Один исполнитель отработал, второй увидел лок и вышел.
    assert sorted(results, key=str) == [None, "done"]
    assert len(calls) == 1


def test_lock_released_after_run(fake_state_redis):
    async def job():
        return "ok"

    wrapped = locked_job(job, "release_job", ttl_seconds=60)

    async def scenario():
        first = await wrapped()
        second = await wrapped()  # лок снят — второй запуск проходит
        return first, second

    assert asyncio.run(scenario()) == ("ok", "ok")


def test_fail_open_when_redis_down(monkeypatch):
    async def _broken():
        raise ConnectionError("redis down")

    import app.core.cache as cache_mod
    monkeypatch.setattr(cache_mod, "get_state_redis", _broken)

    async def job():
        return "ran"

    wrapped = locked_job(job, "failopen_job", ttl_seconds=60)
    # Redis лежит — job всё равно исполняется (single-instance допущение).
    assert asyncio.run(wrapped()) == "ran"
