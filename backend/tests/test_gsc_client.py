"""Credential, pagination and quota boundaries for read-only Search Console."""
import asyncio
from datetime import date
import importlib.util
import json
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.services.gsc_client import GSC_SCOPE, GscClient, GscError, read_credentials


def _credentials():
    return {"type": "authorized_user", "client_id": "client", "client_secret": "secret",
            "refresh_token": "refresh", "scopes": [GSC_SCOPE]}


def _helper():
    path = Path(__file__).resolve().parents[1] / "scripts/google-search-console.py"
    spec = importlib.util.spec_from_file_location("gsc_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_refresh_retries_401_once_and_reuses_token():
    requests = []
    refreshes = 0

    def handler(request):
        nonlocal refreshes
        requests.append(request)
        if request.url.host == "oauth2.googleapis.com":
            refreshes += 1
            assert parse_qs(request.content.decode())["grant_type"] == ["refresh_token"]
            return httpx.Response(200, json={"access_token": f"token-{refreshes}", "expires_in": 3600, "scope": GSC_SCOPE})
        if request.headers["Authorization"] == "Bearer token-1":
            return httpx.Response(401)
        return httpx.Response(200, json={"siteEntry": []})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            api = GscClient(http, credentials=_credentials())
            assert await api.sites() == {"siteEntry": []}
            await api.sites()
    asyncio.run(run())
    assert refreshes == 2
    assert len(requests) == 5
    assert all("refresh" not in str(request.url) for request in requests)


def test_credential_permissions_and_exact_scope(tmp_path):
    path = tmp_path / "oauth.json"
    path.write_text(json.dumps(_credentials()))
    path.chmod(0o600)
    assert read_credentials(path)["client_id"] == "client"
    path.chmod(0o644)
    with pytest.raises(GscError, match="0600"):
        read_credentials(path)
    path.chmod(0o600)
    payload = _credentials()
    payload["scopes"].append("https://www.googleapis.com/auth/webmasters")
    path.write_text(json.dumps(payload))
    with pytest.raises(GscError, match="readonly"):
        read_credentials(path)


def test_search_pagination_image_dimensions_and_site_encoding():
    bodies = []

    def handler(request):
        assert "https%3A%2F%2Fru.forecasteconomy.com%2F" in request.url.raw_path.decode()
        body = json.loads(request.content)
        bodies.append(body)
        count = 25_000 if body["startRow"] == 0 else 1
        return httpx.Response(200, json={"rows": [{"keys": ["query", "page", "2026-09-01", "usa", "MOBILE"]}] * count})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            api = GscClient(http, token="token")
            return await api.search_day("https://ru.forecasteconomy.com/", date(2026, 9, 1),
                                        search_type="image", dimensions=("query", "page", "date", "country", "device"))
    report = asyncio.run(run())
    assert len(report["rows"]) == 25_001
    assert report["reached_row_cap"] is False
    assert [body["startRow"] for body in bodies] == [0, 25_000]
    assert all(body["type"] == "image" and body["dataState"] == "final" for body in bodies)
    assert all(body["startDate"] == body["endDate"] == "2026-09-01" for body in bodies)


def test_cap_is_reported_and_quota_errors_are_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("sitemaps"):
            return httpx.Response(429, json={"error": "never-log-this-payload"})
        return httpx.Response(200, json={"rows": [{"keys": []}] * 2})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            api = GscClient(http, token="token")
            report = await api.search_day("sc-domain:forecasteconomy.com", date(2026, 9, 1), max_rows=2)
            assert report["reached_row_cap"] is True
            with pytest.raises(GscError, match="HTTP 429") as caught:
                await api.sitemaps("sc-domain:forecasteconomy.com")
            assert "never-log" not in str(caught.value)
    asyncio.run(run())
    assert len(calls) == 2


def test_inspection_is_bounded_deduplicated_and_in_property():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"inspectionResult": {}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            api = GscClient(http, token="token")
            with pytest.raises(ValueError, match="20"):
                await api.inspect_sample("sc-domain:forecasteconomy.com", [f"https://forecasteconomy.com/{i}" for i in range(21)])
            with pytest.raises(ValueError, match="outside"):
                await api.inspect_sample("sc-domain:forecasteconomy.com", ["https://evilforecasteconomy.com/"])
            assert not requests
            result = await api.inspect_sample("sc-domain:forecasteconomy.com", ["https://ru.forecasteconomy.com/"] * 2)
            assert len(result) == 1
    asyncio.run(run())
    assert len(requests) == 1
    assert json.loads(requests[0].content)["siteUrl"] == "sc-domain:forecasteconomy.com"


def test_oauth_pkce_callback_state_and_private_file(tmp_path):
    helper = _helper()
    verifier = "a" * 64
    url = helper.authorization_url("client", "http://127.0.0.1:1/oauth/callback", "state", verifier)
    params = parse_qs(urlsplit(url).query)
    assert params["scope"] == [GSC_SCOPE]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"] != [verifier]
    assert "code_verifier" not in params
    path = tmp_path / "gsc-oauth.json"
    helper.private_write(path, "private")
    assert path.stat().st_mode & 0o777 == 0o600
    result = {}
    with helper.HTTPServer(("127.0.0.1", 0), helper.callback_handler("expected", result)) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/oauth/callback"
            wrong = httpx.get(base, params={"state": "wrong", "code": "secret-code"})
            assert wrong.status_code == 400 and result == {}
            valid = httpx.get(base, params={"state": "expected", "code": "secret-code"})
            assert valid.status_code == 200 and result == {"code": "secret-code"}
            assert "secret-code" not in valid.text
            assert valid.headers["cache-control"] == "no-store"
        finally:
            server.shutdown()
            thread.join()
