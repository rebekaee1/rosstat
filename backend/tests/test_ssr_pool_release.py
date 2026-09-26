"""Инцидент 2026-09-26: ожидание SSR-кэша не держит соединение пула.

Резолверы /seo/world* делают SELECT до `_cached_html`; раньше сессия
оставалась «idle in transaction», пока запрос ждал singleflight-лок или
`_RENDER_SEM`. На холодном кэше под краулерами ожидающие забирали QueuePool,
рендеры внутри семафора не получали соединение, /health/ready висел >8s.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

import app.api.seo_pages as seo_pages


@pytest.fixture
def mem_cache(monkeypatch):
    store: dict[str, str] = {}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl=None):
        store[key] = value

    async def plain_key(ns, rest):
        return f"fe:{ns}:v0:{rest}"

    async def fake_sig():
        return "sig-aaa"

    monkeypatch.setattr(seo_pages, "cache_get", fake_get)
    monkeypatch.setattr(seo_pages, "cache_set", fake_set)
    monkeypatch.setattr(seo_pages, "versioned_key", plain_key)
    monkeypatch.setattr(seo_pages, "_asset_sig", fake_sig)
    return store


def _engine(tmp: str):
    return create_async_engine(
        f"sqlite+aiosqlite:///{Path(tmp) / 'pool.db'}",
        poolclass=AsyncAdaptedQueuePool, pool_size=2, max_overflow=0, pool_timeout=1,
    )


def test_waiters_release_connections_while_render_runs(mem_cache):
    """5 конкурентных miss'ов, у каждого уже был SELECT (резолвер).

    Пул 2 соединения: без release ожидающие держали бы оба, и рендер внутри
    лока не получил бы соединение (TimeoutError). С release — рендер идёт,
    а во время рендера занято не больше 1 соединения (сам рендер).
    """

    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            engine = _engine(tmp)
            maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            peak = {"during_render": 0}

            async def request():
                db = maker()
                try:
                    await db.execute(text("SELECT 1"))  # резолвер до кэша

                    async def render():
                        await db.execute(text("SELECT 2"))
                        await asyncio.sleep(0.05)
                        peak["during_render"] = max(
                            peak["during_render"], engine.pool.checkedout()
                        )
                        return 200, "<html>ok</html>"

                    return await seo_pages._cached_html(
                        "ssr-world", "world:x:y:en", 60, render, db=db,
                    )
                finally:
                    await db.close()

            # Два первых запроса занимают весь пул до входа в _cached_html.
            results = await asyncio.gather(*[request() for _ in range(5)])
            checked_out_after = engine.pool.checkedout()
            await engine.dispose()
            return results, peak["during_render"], checked_out_after

    results, during_render, after = asyncio.run(run())
    assert all(r == (200, "<html>ok</html>") for r in results)
    assert during_render <= 1, "ожидающие лок не должны держать соединения пула"
    assert after == 0


def test_release_commits_open_transaction_and_keeps_objects():
    class FakeSession:
        def __init__(self):
            self.committed = 0
            self.rolled_back = 0
            self._tx = True

        def in_transaction(self):
            return self._tx

        async def commit(self):
            self.committed += 1
            self._tx = False

        async def rollback(self):
            self.rolled_back += 1

    s = FakeSession()
    asyncio.run(seo_pages._release_db(s))
    asyncio.run(seo_pages._release_db(s))  # уже без транзакции — no-op
    asyncio.run(seo_pages._release_db(None))
    assert (s.committed, s.rolled_back) == (1, 0)


def test_release_falls_back_to_rollback_on_commit_error():
    class Broken:
        rolled_back = 0

        def in_transaction(self):
            return True

        async def commit(self):
            raise RuntimeError("connection is closed")

        async def rollback(self):
            Broken.rolled_back += 1

    asyncio.run(seo_pages._release_db(Broken()))
    assert Broken.rolled_back == 1


def test_all_seo_cached_routes_pass_request_session():
    """Каждый вызов `_cached_html` в seo_pages передаёт db=db (иначе release не работает)."""
    src = Path(seo_pages.__file__).read_text()
    calls = src.count("await _cached_html(")
    assert calls > 0
    assert src.count("db=db,") >= calls
