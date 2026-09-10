"""Regression checks for warm disk-cache memory and ASGI responsiveness."""
import asyncio
import contextvars
import threading

import pytest
from fastapi import HTTPException

from app.services import og_image, og_render


@pytest.fixture
def isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(og_image, "_CACHE", {})
    monkeypatch.setattr(og_image, "_DISK_DIR", tmp_path)
    monkeypatch.setattr(og_image, "_CACHE_MAX", 3)
    monkeypatch.setattr(og_image, "_CACHE_MAX_BYTES", 100)
    return tmp_path


def test_disk_promotions_obey_memory_bounds(isolated_cache):
    for n in range(8):
        og_image._disk_path(str(n)).write_bytes(b"x" * 40)
    for n in range(8):
        assert og_image.cached_og(str(n)) == b"x" * 40
        assert len(og_image._CACHE) <= 3
        assert sum(len(v[1]) for v in og_image._CACHE.values()) <= 100
    assert og_image.cached_og("0") == b"x" * 40  # eviction preserves disk copy


def test_store_repairs_preexisting_oversized_cache(isolated_cache):
    og_image._CACHE.update({str(n): (float(n), b"x") for n in range(10)})
    og_image.store_og("new", b"new")
    assert len(og_image._CACHE) == 3
    assert og_image.cached_og("new") == b"new"


def test_oversized_png_served_without_retention(isolated_cache):
    og_image.store_og("large", b"x" * 101)
    assert og_image.cached_og("large") == b"x" * 101
    assert "large" not in og_image._CACHE


def test_render_is_off_loop_and_preserves_context():
    locale = contextvars.ContextVar("test_locale", default="ru")
    async def scenario():
        locale.set("en")
        loop_thread = threading.get_ident()
        def render():
            assert threading.get_ident() != loop_thread
            return locale.get().encode()
        assert await og_render.render_og_async(render) == b"en"
    asyncio.run(scenario())


def test_render_queue_bounded_and_cancellation_keeps_running_slot(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(og_render, "_SLOTS", slots)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    def render():
        started.set()
        try:
            assert release.wait(5)
            return b"png"
        finally:
            finished.set()
    async def scenario():
        task = asyncio.create_task(og_render.render_og_async(render))
        try:
            for _ in range(200):
                if started.is_set():
                    break
                await asyncio.sleep(.005)
            assert started.is_set()  # event loop still progresses during render
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            with pytest.raises(HTTPException) as exc:
                await og_render.render_og_async(lambda: b"excess")
            assert exc.value.status_code == 503
            assert exc.value.headers["Retry-After"] == "5"
        finally:
            release.set()
            for _ in range(200):
                if finished.is_set() and slots.acquire(blocking=False):
                    slots.release()
                    break
                await asyncio.sleep(.005)
        assert await og_render.render_og_async(lambda: b"next") == b"next"
    asyncio.run(scenario())


@pytest.mark.parametrize("ua", ["Claude-User/1.0", "Claude-SearchBot/1.0", "OAI-SearchBot/1.3", "ChatGPT-User/1.0", "meta-externalfetcher/1.1", "meta-webindexer/1.1"])
def test_user_and_search_retrieval_agents_preserved(ua):
    from app.services.scrape_guard import is_search_bot_ua
    assert is_search_bot_ua(ua)


def test_parallel_disk_writers_publish_complete_unique_files(isolated_cache, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path

    barrier = threading.Barrier(2)
    observed = []
    original_replace = Path.replace
    payloads = [b"first" * 100_000, b"second" * 100_000]
    def synchronized_replace(source, target):
        observed.append((source, source.read_bytes()))
        barrier.wait(timeout=5)
        return original_replace(source, target)
    monkeypatch.setattr(Path, "replace", synchronized_replace)
    monkeypatch.setattr(og_image.random, "random", lambda: 1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(og_image.store_og, "same-key", body) for body in payloads]
        for future in futures:
            future.result(timeout=10)
    assert len({path for path, _ in observed}) == 2
    assert {body for _, body in observed} == set(payloads)
    assert og_image._disk_path("same-key").read_bytes() in payloads
    assert not list(isolated_cache.glob("*.tmp"))


def test_failed_publication_removes_temporary_file(isolated_cache, monkeypatch):
    from pathlib import Path

    def fail_replace(source, target):
        raise OSError("simulated disk publication failure")
    monkeypatch.setattr(Path, "replace", fail_replace)
    og_image.store_og("failure", b"png")
    assert og_image.cached_og("failure") == b"png"  # memory remains usable
    assert not list(isolated_cache.glob("*.tmp"))
