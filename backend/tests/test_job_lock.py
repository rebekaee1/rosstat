"""О-13 / F07: распределённая блокировка фоновых задач (lease с владельцем)."""

import asyncio

import fakeredis.aioredis
import pytest

from app.main import locked_job
from app.services.job_lease import (
    JOB_LOCK_GROUPS,
    JobLeaseLostError,
    job_lease_lost,
    lock_key_for,
)


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


# ── F07: heartbeat, владелец, потеря lease, группы ─────────────────────────


def test_heartbeat_extends_ttl_so_long_job_keeps_lock(fake_state_redis):
    """Задача живёт дольше TTL — ключ продлевается, конкурент всё равно пропущен."""
    key = lock_key_for("hb_job")
    observed = {}

    async def short_job():
        return "second-ran"

    second = locked_job(short_job, "hb_job", ttl_seconds=0.3)

    async def long_job():
        await asyncio.sleep(0.8)  # заметно больше TTL (0.3 c)
        observed["pttl"] = await fake_state_redis.pttl(key)
        observed["second"] = await second()
        return "done"

    wrapped = locked_job(long_job, "hb_job", ttl_seconds=0.3)

    async def scenario():
        result = await wrapped()
        return result, await fake_state_redis.get(key)

    result, after = asyncio.run(scenario())
    assert result == "done"
    assert observed["pttl"] > 0        # ключ жив спустя > TTL
    assert observed["second"] is None  # конкурент увидел лок и пропустил запуск
    assert after is None               # по завершении владелец ключ снял


def test_lock_value_is_unique_owner_token_per_run(fake_state_redis):
    seen = []

    async def job():
        seen.append(await fake_state_redis.get(lock_key_for("tok_job")))

    wrapped = locked_job(job, "tok_job", ttl_seconds=60)

    async def scenario():
        await wrapped()
        await wrapped()

    asyncio.run(scenario())
    assert len(seen) == 2 and all(seen)
    assert seen[0] != seen[1]


def test_lost_lease_cancels_job_and_raises(fake_state_redis):
    """Ключ пропал (истёк/FLUSH) — heartbeat это видит, задача отменяется."""
    progress = {"steps": 0, "finished": False, "cancelled": False, "flag": None}

    async def job():
        try:
            for _ in range(200):
                progress["steps"] += 1
                progress["flag"] = job_lease_lost()
                await asyncio.sleep(0.05)
            progress["finished"] = True
        except asyncio.CancelledError:
            progress["cancelled"] = True
            raise

    wrapped = locked_job(job, "lost_job", ttl_seconds=0.3)

    async def scenario():
        runner = asyncio.ensure_future(wrapped())
        await asyncio.sleep(0.05)
        await fake_state_redis.delete(lock_key_for("lost_job"))  # lease потерян
        with pytest.raises(JobLeaseLostError):
            await runner

    asyncio.run(scenario())
    assert progress["cancelled"] is True
    assert progress["finished"] is False
    assert progress["steps"] < 200  # прекратила писать, не дошла до конца


def test_lease_taken_by_other_owner_cancels_and_keeps_foreign_key(fake_state_redis):
    key = lock_key_for("steal_job")

    async def job():
        await asyncio.sleep(5)

    wrapped = locked_job(job, "steal_job", ttl_seconds=0.3)

    async def scenario():
        runner = asyncio.ensure_future(wrapped())
        await asyncio.sleep(0.05)
        await fake_state_redis.set(key, "someone-else", px=60_000)  # перехват
        with pytest.raises(JobLeaseLostError):
            await runner
        return await fake_state_redis.get(key)

    # Compare-and-delete: чужой ключ остался на месте.
    assert asyncio.run(scenario()) == "someone-else"


def test_release_only_by_owner_after_normal_finish(fake_state_redis):
    key = lock_key_for("own_job")

    async def job():
        # Чужой владелец подменил ключ, heartbeat ещё не успел (TTL большой):
        # по завершении ключ чужой — снимать его нельзя.
        await fake_state_redis.set(key, "other-owner", px=60_000)
        return "ok"

    wrapped = locked_job(job, "own_job", ttl_seconds=60)

    async def scenario():
        result = await wrapped()
        return result, await fake_state_redis.get(key)

    assert asyncio.run(scenario()) == ("ok", "other-owner")


def test_redis_error_during_heartbeat_is_not_a_loss(fake_state_redis, monkeypatch):
    """Redis моргнул на продлении: задача не отменяется, дорабатывает."""
    original_eval = fake_state_redis.eval
    calls = {"n": 0}

    async def flaky_eval(script, numkeys, *args):
        if "PEXPIRE" in script:
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("blip")
        return await original_eval(script, numkeys, *args)

    monkeypatch.setattr(fake_state_redis, "eval", flaky_eval)

    async def job():
        await asyncio.sleep(0.5)
        return "survived"

    wrapped = locked_job(job, "blip_job", ttl_seconds=0.3)
    assert asyncio.run(wrapped()) == "survived"
    assert calls["n"] >= 2  # после сбоя heartbeat продолжил продлевать


def test_daily_evening_and_late_etl_share_one_lock(fake_state_redis):
    etl_jobs = ("daily_etl", "evening_etl", "late_minfin_etl", "late_fred_etl")
    assert len({lock_key_for(j) for j in etl_jobs}) == 1
    assert set(etl_jobs) <= set(JOB_LOCK_GROUPS)
    # Независимая задача держит собственный ключ.
    assert lock_key_for("sitemap_build") != lock_key_for("daily_etl")

    calls = []

    async def daily():
        calls.append("daily")
        await asyncio.sleep(0.1)
        return "daily"

    async def evening():
        calls.append("evening")
        return "evening"

    w_daily = locked_job(daily, "daily_etl", ttl_seconds=60)
    w_evening = locked_job(evening, "evening_etl", ttl_seconds=60)

    async def scenario():
        return await asyncio.gather(w_daily(), w_evening())

    results = asyncio.run(scenario())
    assert sorted(results, key=str) == [None, "daily"]  # вечерний пропущен
    assert calls == ["daily"]


def test_job_exception_propagates_and_releases(fake_state_redis):
    async def job():
        raise ValueError("boom")

    wrapped = locked_job(job, "exc_job", ttl_seconds=60)

    async def scenario():
        with pytest.raises(ValueError):
            await wrapped()
        return await fake_state_redis.get(lock_key_for("exc_job"))

    assert asyncio.run(scenario()) is None
