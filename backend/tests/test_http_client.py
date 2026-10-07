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


# --- 2026-10-08: connect timeout + host breaker (Росстат лежал 07.10, ETL шёл 9 ч) ---

import pytest

from app.services import http_client


@pytest.fixture(autouse=True)
def _clean_breaker():
    http_client._reset_host_breaker()
    yield
    http_client._reset_host_breaker()


def _capture_send_timeout(adapter, **kwargs):
    seen = {}

    def fake_send(self, request, **kw):
        seen.update(kw)
        r = MagicMock(spec=requests.Response)
        r.status_code = 200
        return r

    req = requests.Request("GET", "https://example.com/").prepare()
    with patch.object(requests.adapters.HTTPAdapter, "send", fake_send):
        adapter.send(req, **kwargs)
    return seen["timeout"]


def test_adapter_applies_default_when_requests_passes_none():
    adapter = _TimeoutAdapter(timeout=60)
    assert _capture_send_timeout(adapter, timeout=None) == (http_client.CONNECT_TIMEOUT_DIRECT, 60)


def test_adapter_caps_connect_but_keeps_read_timeout():
    adapter = _TimeoutAdapter(timeout=60)
    assert _capture_send_timeout(adapter, timeout=90) == (http_client.CONNECT_TIMEOUT_DIRECT, 90)
    assert _capture_send_timeout(
        adapter, timeout=90, proxies={"https": "socks5h://tor:9050"}
    ) == (http_client.CONNECT_TIMEOUT_PROXY, 90)
    assert _capture_send_timeout(adapter, timeout=(3, 7)) == (3, 7)


def _session_with_socks(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "etl_http_proxy_url", "off")
    monkeypatch.setattr(settings, "etl_socks_proxy_url", "socks5h://tor:9050")
    return create_session(retry=Retry(total=0, raise_on_status=False))


def test_host_breaker_fails_fast_after_all_hops_fail(monkeypatch):
    s = _session_with_socks(monkeypatch)
    calls = []

    def dead(self, method, url, **kwargs):
        calls.append(url)
        raise requests.ConnectTimeout("dead")

    with patch.object(requests.Session, "request", dead):
        with pytest.raises(requests.ConnectTimeout):
            s.get("https://rosstat.gov.ru/a.xlsx")
        assert len(calls) == 2  # direct + socks
        with pytest.raises(requests.ConnectionError, match="unreachable"):
            s.get("https://rosstat.gov.ru/b.xlsx")
        assert len(calls) == 2  # второй запрос в сеть не ходил


def test_host_breaker_is_per_host_and_expires(monkeypatch):
    s = _session_with_socks(monkeypatch)
    now = [1000.0]
    monkeypatch.setattr(http_client.time, "monotonic", lambda: now[0])
    ok = MagicMock(spec=requests.Response)
    ok.status_code = 200

    def route(self, method, url, **kwargs):
        if "rosstat" in url:
            raise requests.ConnectTimeout("dead")
        return ok

    with patch.object(requests.Session, "request", route):
        with pytest.raises(requests.ConnectTimeout):
            s.get("https://rosstat.gov.ru/a")
        assert s.get("https://cbr.ru/x").status_code == 200
        with pytest.raises(requests.ConnectionError, match="unreachable"):
            s.get("https://rosstat.gov.ru/b")
        now[0] += http_client.HOST_BREAKER_COOLDOWN_S + 1
        with pytest.raises(requests.ConnectTimeout):  # снова пробует сеть
            s.get("https://rosstat.gov.ru/c")


def test_host_breaker_ignores_read_timeout_and_http_errors(monkeypatch):
    s = _session_with_socks(monkeypatch)
    nf = MagicMock(spec=requests.Response)
    nf.status_code = 404

    def slow(self, method, url, **kwargs):
        if url.endswith("/slow"):
            raise requests.ReadTimeout("slow body")
        return nf

    with patch.object(requests.Session, "request", slow):
        with pytest.raises(requests.ReadTimeout):
            s.get("https://rosstat.gov.ru/slow")
        assert s.get("https://rosstat.gov.ru/missing").status_code == 404


def test_host_breaker_ignores_ssl_errors(monkeypatch):
    s = _session_with_socks(monkeypatch)
    ok = MagicMock(spec=requests.Response)
    ok.status_code = 200

    def ssl_then_ok(self, method, url, **kwargs):
        if url.endswith("/bad-ca"):
            raise requests.exceptions.SSLError("cert")
        return ok

    with patch.object(requests.Session, "request", ssl_then_ok):
        with pytest.raises(requests.exceptions.SSLError):
            s.get("https://rosstat.gov.ru/bad-ca")
        assert s.get("https://rosstat.gov.ru/ok").status_code == 200


def test_default_retry_limits_connect_attempts():
    assert http_client._RETRY_STRATEGY.connect == 1
    assert http_client._RETRY_STRATEGY.total == 3
