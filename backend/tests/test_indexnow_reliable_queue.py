"""F12: IndexNow-очередь переживает падение процесса между взятием партии и ACK.

Партия переносится в processing (а не SPOP-ится), ACK удаляет её, зависшая
дольше таймаута возвращается в очередь следующим drain.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import fakeredis.aioredis
import pytest

import app.core.cache as cache_mod
import app.services.indexnow as inx

T0 = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


class _Crash(BaseException):
    """Имитация убитого процесса: не перехватывается `except Exception`."""


class _Env:
    def __init__(self, monkeypatch):
        self.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        self.now = [T0]
        self.posts = []
        self.status = [200]
        self.host = inx.settings.public_host
        env = self

        async def _get_state_redis():
            return env.redis

        class _Resp:
            text = "ok"

            def __init__(self, code):
                self.status_code = code
                self.headers = {}

        class _Client:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, json=None):
                env.posts.append(json)
                return _Resp(env.status[0])

        monkeypatch.setattr(cache_mod, "get_state_redis", _get_state_redis)
        monkeypatch.setattr(inx, "_utc_now", lambda: env.now[0])
        monkeypatch.setattr(inx.httpx, "AsyncClient", _Client)
        monkeypatch.setattr(inx.settings, "indexnow_enabled", True)
        monkeypatch.setattr(inx.settings, "indexnow_key", "k" * 32)
        monkeypatch.setattr(inx.settings, "apex_locale_en", False, raising=False)

    async def queued(self):
        return await self.redis.smembers(f"in:queue:{self.host}")

    async def processing_keys(self):
        return [k async for k in self.redis.scan_iter(f"in:proc:{self.host}:*")]

    async def index(self):
        return await self.redis.zrange(f"in:proc-idx:{self.host}", 0, -1)


@pytest.fixture
def env(monkeypatch):
    return _Env(monkeypatch)


PATHS = [f"/russia/indicator/p{n}" for n in range(3)]


def test_success_acks_batch_and_leaves_no_processing_state(env):
    async def scenario():
        await inx.enqueue_paths(PATHS, host=env.host)
        sent = await inx.drain_indexnow_queue()
        return sent, await env.queued(), await env.processing_keys(), await env.index()

    sent, queued, proc, idx = asyncio.run(scenario())
    assert sent == 3 and not queued and not proc and not idx
    assert len(env.posts) == 1


def test_crash_after_claim_keeps_batch_and_next_drain_returns_it_after_timeout(env, monkeypatch):
    async def crashing_ping(*args, **kwargs):
        raise _Crash()

    async def scenario():
        await inx.enqueue_paths(PATHS, host=env.host)
        monkeypatch.setattr(inx, "ping_urls", crashing_ping)
        with pytest.raises(_Crash):
            await inx.drain_indexnow_queue()
        # URL не потеряны: в processing, очередь пуста.
        return await env.queued(), len(await env.processing_keys()), len(await env.index())

    assert asyncio.run(scenario()) == (set(), 1, 1)


def test_stale_batch_returns_to_queue_and_is_delivered(env, monkeypatch):
    real_ping = inx.ping_urls

    async def crashing_ping(*args, **kwargs):
        raise _Crash()

    async def scenario():
        await inx.enqueue_paths(PATHS, host=env.host)
        monkeypatch.setattr(inx, "ping_urls", crashing_ping)
        with pytest.raises(_Crash):
            await inx.drain_indexnow_queue()
        monkeypatch.setattr(inx, "ping_urls", real_ping)

        # До таймаута следующий drain зависшую партию не трогает (она может быть в полёте).
        env.now[0] = T0 + timedelta(seconds=inx._PROCESSING_TIMEOUT - 60)
        early = await inx.drain_indexnow_queue()
        still_processing = len(await env.processing_keys())

        # После таймаута — возвращает и отправляет.
        env.now[0] = T0 + timedelta(seconds=inx._PROCESSING_TIMEOUT + 60)
        late = await inx.drain_indexnow_queue()
        return early, still_processing, late, await env.queued(), await env.processing_keys(), await env.index()

    early, still_processing, late, queued, proc, idx = asyncio.run(scenario())
    assert (early, still_processing) == (0, 1)
    assert late == 3 and not queued and not proc and not idx
    assert sorted(url for post in env.posts for url in post["urlList"]) == sorted(
        f"{inx.settings.public_origin.rstrip('/')}{p}" for p in PATHS
    )


def test_failed_ping_requeues_unsent_urls_and_clears_processing(env):
    env.status[0] = 500

    async def scenario():
        await inx.enqueue_paths(PATHS, host=env.host)
        sent = await inx.drain_indexnow_queue()
        return sent, await env.queued(), await env.processing_keys(), await env.index()

    sent, queued, proc, idx = asyncio.run(scenario())
    assert sent == 0 and queued == set(PATHS) and not proc and not idx


def test_exception_during_drain_returns_batch_immediately_and_reraises(env, monkeypatch):
    async def broken_ping(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(inx, "ping_urls", broken_ping)

    async def scenario():
        await inx.enqueue_paths(PATHS, host=env.host)
        with pytest.raises(RuntimeError):
            await inx.drain_indexnow_queue()
        return await env.queued(), await env.processing_keys(), await env.index()

    queued, proc, idx = asyncio.run(scenario())
    assert queued == set(PATHS) and not proc and not idx


def test_failure_of_the_return_path_still_leaves_batch_recoverable(env, monkeypatch):
    async def broken_ping(*args, **kwargs):
        raise RuntimeError("boom")

    async def broken_ack(*args, **kwargs):
        raise ConnectionError("redis gone")

    monkeypatch.setattr(inx, "ping_urls", broken_ping)
    monkeypatch.setattr(inx, "_ack_batch", broken_ack)

    async def scenario():
        await inx.enqueue_paths(PATHS, host=env.host)
        with pytest.raises(RuntimeError):
            await inx.drain_indexnow_queue()
        return await env.queued(), len(await env.processing_keys()), len(await env.index())

    assert asyncio.run(scenario()) == (set(), 1, 1)


def test_claims_are_disjoint_and_debounced_urls_are_dropped_on_ack(env):
    async def scenario():
        await inx.enqueue_paths(PATHS, host=env.host)
        _, first = await inx._claim_batch(env.redis, env.host, 2)
        _, second = await inx._claim_batch(env.redis, env.host, 2)
        empty_id, empty = await inx._claim_batch(env.redis, env.host, 2)
        assert len(first) == 2 and len(second) == 1
        assert set(first).isdisjoint(second) and set(first) | set(second) == set(PATHS)
        assert empty_id is None and empty == []

        # Уже отправленные (debounce) URL при ACK не возвращаются и не шлются повторно.
        await env.redis.flushall()
        await inx.enqueue_paths(PATHS, host=env.host)
        for path in PATHS:
            await env.redis.set(f"in:sent:{env.host}:{path}", "1")
        sent = await inx.drain_indexnow_queue()
        return sent, await env.queued(), await env.processing_keys()

    sent, queued, proc = asyncio.run(scenario())
    assert sent == 0 and not queued and not proc and not env.posts
