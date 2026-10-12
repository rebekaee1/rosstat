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


def test_first_screen_has_no_redirecting_address():
    """Журнал боевого 12.10.2026: `/world/rating` отвечает 301 — прогрев берёт канон страницы по умолчанию."""
    from app.services import site_paths as paths
    from app.services.seo_world import WORLD_RATING_DEFAULT_CONCEPT

    assert "/world/rating" not in ssr_warm.WARM_PATHS
    assert paths.world_rating(WORLD_RATING_DEFAULT_CONCEPT) in ssr_warm.WARM_PATHS
    assert all(p == "/" or not p.endswith("/") for p in ssr_warm.WARM_PATHS)


def test_top_page_redirect_is_followed_once_and_remembered(monkeypatch):
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.headers["host"], request.url.path))
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://ru.forecasteconomy.com/new"})
        if request.url.path == "/away":
            return httpx.Response(301, headers={"location": "https://evil.example/x"})
        return httpx.Response(200)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            monkeypatch.setattr(ssr_warm, "_known_redirects", {})
            assert await ssr_warm._get(client, "ru.forecasteconomy.com", "/old", strict=False)
            assert await ssr_warm._get(client, "ru.forecasteconomy.com", "/old", strict=False)
            assert await ssr_warm._get(client, "ru.forecasteconomy.com", "/away", strict=False)

    monkeypatch.setattr(ssr_warm.settings, "ssr_warm_base_url", "http://frontend")
    _run(scenario())
    # Первый проход: /old -> /new; второй сразу /new; чужой хост не посещается.
    assert [p for _h, p in seen] == ["/old", "/new", "/new", "/away"]


def test_first_screen_redirect_is_still_a_failure(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(301, headers={"location": "/elsewhere"})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ssr_warm._get(client, "forecasteconomy.com", "/x", strict=True)

    monkeypatch.setattr(ssr_warm.settings, "ssr_warm_base_url", "http://frontend")
    assert _run(scenario()) is False


def test_top_paths_are_normalised_and_deduplicated():
    assert ssr_warm._normalise_top_path("/russia/indicator/cpi/") == "/russia/indicator/cpi"
    assert ssr_warm._normalise_top_path("/") == "/"
    assert ssr_warm._same_host_target("/a/b", "x.com") == "/a/b"
    assert ssr_warm._same_host_target("https://x.com/a?y=1", "x.com") is None
    assert ssr_warm._same_host_target("https://other.com/a", "x.com") is None
