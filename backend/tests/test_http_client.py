"""Tests for http_client proxy fallback."""

from unittest.mock import MagicMock, patch

import requests
from urllib3.util.retry import Retry

from app.services.http_client import (
    ProxyFallbackSession,
    create_session,
    resolve_etl_proxy_url,
    resolve_etl_socks_url,
    _TimeoutAdapter,
)


def test_create_session_has_timeout_adapter():
    s = create_session(timeout=30, proxy=False, socks=False)
    adapter = s.get_adapter("https://example.com")
    assert isinstance(adapter, _TimeoutAdapter)
    assert adapter._default_timeout == 30


def test_session_has_user_agent():
    s = create_session(proxy=False, socks=False)
    assert "ForecastEconomy" in s.headers.get("User-Agent", "")


def test_create_session_is_proxy_fallback_by_default():
    s = create_session(proxy=False, socks=False)
    assert isinstance(s, ProxyFallbackSession)
    assert s._proxy_url is None
    assert s._socks_url is None


def test_resolve_etl_proxy_prefers_dedicated(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "etl_http_proxy_url", "http://etl:1")
    monkeypatch.setattr(settings, "openrouter_proxy_url", "http://or:1")
    assert resolve_etl_proxy_url() == "http://etl:1"


def test_resolve_etl_proxy_falls_back_to_openrouter(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "etl_http_proxy_url", "")
    monkeypatch.setattr(settings, "openrouter_proxy_url", "http://or:1")
    assert resolve_etl_proxy_url() == "http://or:1"


def test_resolve_etl_socks(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "etl_socks_proxy_url", "socks5h://172.17.0.1:9050")
    assert resolve_etl_socks_url() == "socks5h://172.17.0.1:9050"


def test_proxy_then_socks_on_503(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "etl_http_proxy_url", "http://proxy.test:8888")
    monkeypatch.setattr(settings, "openrouter_proxy_url", "")
    monkeypatch.setattr(settings, "etl_socks_proxy_url", "socks5h://172.17.0.1:9050")

    s = create_session(proxy=True, socks=True, retry=Retry(total=0, raise_on_status=False))
    assert s._proxy_url == "http://proxy.test:8888"
    assert s._socks_url == "socks5h://172.17.0.1:9050"

    direct = MagicMock(spec=requests.Response)
    direct.status_code = 503
    via_http = MagicMock(spec=requests.Response)
    via_http.status_code = 503
    via_socks = MagicMock(spec=requests.Response)
    via_socks.status_code = 200

    calls: list[dict] = []

    def fake_request(self, method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        px = (kwargs.get("proxies") or {}).get("https")
        if px and px.startswith("socks5"):
            return via_socks
        if px:
            return via_http
        return direct

    with patch.object(requests.Session, "request", fake_request):
        resp = s.get("https://minfin.gov.ru/")

    assert resp.status_code == 200
    assert len(calls) == 3
    assert calls[0].get("proxies") in (None, {})
    assert calls[1]["proxies"]["https"] == "http://proxy.test:8888"
    assert calls[2]["proxies"]["https"] == "socks5h://172.17.0.1:9050"


def test_no_proxy_fallback_when_direct_ok(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "etl_http_proxy_url", "http://proxy.test:8888")
    monkeypatch.setattr(settings, "etl_socks_proxy_url", "socks5h://172.17.0.1:9050")
    s = create_session(proxy=True, socks=True, retry=Retry(total=0, raise_on_status=False))

    ok = MagicMock(spec=requests.Response)
    ok.status_code = 200
    calls = []

    def fake_request(self, method, url, **kwargs):
        calls.append(kwargs.get("proxies"))
        return ok

    with patch.object(requests.Session, "request", fake_request):
        resp = s.get("https://example.com/")

    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0] in (None, {})
