"""The release gate must not roll back for one transient OG rate limit."""

import importlib.util
from pathlib import Path

import httpx
import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dual-host-release-gate.py"
SPEC = importlib.util.spec_from_file_location("dual_host_release_gate", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        return next(self.responses)


def image_response(status=200, *, content_type="image/png", size=1000):
    return httpx.Response(status, headers={"content-type": content_type}, content=b"x" * size)


def test_og_429_retries_until_valid_image(monkeypatch):
    sleeps = []
    monkeypatch.setattr(gate.time, "sleep", sleeps.append)
    client = FakeClient([httpx.Response(429), httpx.Response(429), image_response()])

    assert gate._check_og_image(client, "https://example.test/og/cpi.png") == (True, 200)
    assert sleeps == [2, 4]
    assert len(client.urls) == 3


def test_og_persistent_429_still_fails_after_bounded_backoff(monkeypatch):
    sleeps = []
    monkeypatch.setattr(gate.time, "sleep", sleeps.append)
    client = FakeClient([httpx.Response(429)] * 5)

    assert gate._check_og_image(client, "https://example.test/og/cpi.png") == (False, 429)
    assert sleeps == [2, 4, 8, 16]
    assert len(client.urls) == 5


@pytest.mark.parametrize("response", [
    httpx.Response(404),
    httpx.Response(503),
    image_response(content_type="text/html"),
    image_response(size=999),
])
def test_og_bad_response_fails_without_retry(monkeypatch, response):
    sleeps = []
    monkeypatch.setattr(gate.time, "sleep", sleeps.append)
    client = FakeClient([response])

    assert gate._check_og_image(client, "https://example.test/og/cpi.png") == (False, response.status_code)
    assert sleeps == []
    assert len(client.urls) == 1


def test_og_429_followed_by_bad_image_still_fails(monkeypatch):
    sleeps = []
    monkeypatch.setattr(gate.time, "sleep", sleeps.append)
    client = FakeClient([httpx.Response(429), image_response(content_type="text/html")])

    assert gate._check_og_image(client, "https://example.test/og/cpi.png") == (False, 200)
    assert sleeps == [2]
    assert len(client.urls) == 2
