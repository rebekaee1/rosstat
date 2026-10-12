"""Прогрев кэша SSR: идёт по обоим хостам, считает ответы и не падает на ошибках; флаг выключен по умолчанию."""
from __future__ import annotations

import asyncio

import httpx

from app.config import settings
from app.services import ssr_warm


def _run(coro):
    return asyncio.run(coro)


def test_flag_is_off_by_default():
    assert settings.ssr_warm_enabled is False


def test_warm_visits_every_path_for_both_hosts(monkeypatch):
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.headers["host"], request.url.path))
        return httpx.Response(200 if request.url.path != "/compare" else 503)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        ssr_warm.httpx, "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    monkeypatch.setattr(ssr_warm.settings, "ssr_warm_base_url", "http://frontend")

    async def no_sleep(_):
        return None

    monkeypatch.setattr(ssr_warm.asyncio, "sleep", no_sleep)
    result = _run(ssr_warm.warm_ssr_cache())
    total = len(ssr_warm.WARM_HOSTS) * len(ssr_warm.WARM_PATHS)
    assert len(seen) == total
    assert {h for h, _ in seen} == set(ssr_warm.WARM_HOSTS)
    assert result == {"ok": total - 2, "failed": 2}


def test_warm_survives_network_errors(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        ssr_warm.httpx, "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )

    async def no_sleep(_):
        return None

    monkeypatch.setattr(ssr_warm.asyncio, "sleep", no_sleep)
    result = _run(ssr_warm.warm_ssr_cache())
    assert result["ok"] == 0 and result["failed"] == len(ssr_warm.WARM_HOSTS) * len(ssr_warm.WARM_PATHS)


def test_job_is_noop_when_disabled(monkeypatch):
    called = []

    async def fake(**_kwargs):
        called.append(1)
        return {"ok": 0, "failed": 0}

    monkeypatch.setattr(ssr_warm, "warm_ssr_cache", fake)
    monkeypatch.setattr(ssr_warm.settings, "ssr_warm_enabled", False)
    _run(ssr_warm.ssr_warm_job())
    assert called == []
    monkeypatch.setattr(ssr_warm.settings, "ssr_warm_enabled", True)
    _run(ssr_warm.ssr_warm_job())
    assert called == [1]
