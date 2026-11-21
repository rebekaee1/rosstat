"""Tests for http_client proxy fallback."""

from unittest.mock import MagicMock, patch

import time

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


# --- 2026-10-27: 403 Росстата + молчащий Tor не взводят предохранитель хоста ---


def _resp(status):
    r = MagicMock(spec=requests.Response)
    r.status_code = status
    return r


def _tor_only_session(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "etl_http_proxy_url", "off")
    monkeypatch.setattr(settings, "etl_socks_proxy_url", "socks5h://172.18.0.1:9050")
    return create_session(proxy=False, socks=True, retry=Retry(total=0, raise_on_status=False))


def test_ban_status_with_dead_proxy_hop_returns_403_and_keeps_host_up(monkeypatch):
    s = _tor_only_session(monkeypatch)
    calls = []

    def fake_request(self, method, url, **kwargs):
        px = (kwargs.get("proxies") or {}).get("https")
        calls.append(px)
        if px:
            raise requests.exceptions.ConnectTimeout("tor silent")
        return _resp(403)

    with patch.object(requests.Session, "request", fake_request):
        resp = s.get("https://rosstat.gov.ru/storage/mediabank/ind_baza_2023_09-2026.xlsx")
        assert resp.status_code == 403  # ответ хоста, не ConnectionError
        assert http_client._host_down_remaining("rosstat.gov.ru") == 0  # хост жив
        # второй такой же запрос: Tor-хоп пропущен, лишней минуты ожидания нет
        calls.clear()
        resp2 = s.get("https://rosstat.gov.ru/storage/mediabank/osn-10-2026.pdf")
    assert resp2.status_code == 403
    assert calls == [None]


def test_other_files_still_work_after_403_and_dead_tor(monkeypatch):
    s = _tor_only_session(monkeypatch)

    def fake_request(self, method, url, **kwargs):
        if (kwargs.get("proxies") or {}).get("https"):
            raise requests.exceptions.ConnectTimeout("tor silent")
        return _resp(403 if "09-2026" in url else 200)

    with patch.object(requests.Session, "request", fake_request):
        assert s.get("https://rosstat.gov.ru/storage/mediabank/ind_baza_2023_09-2026.xlsx").status_code == 403
        assert s.get("https://rosstat.gov.ru/storage/mediabank/ind_baza_2023_08-2026.xlsx").status_code == 200


def test_direct_and_proxy_both_down_still_arms_host_breaker(monkeypatch):
    s = _tor_only_session(monkeypatch)

    def fake_request(self, method, url, **kwargs):
        raise requests.exceptions.ConnectTimeout("down")

    with patch.object(requests.Session, "request", fake_request):
        with pytest.raises(requests.ConnectionError):
            s.get("https://rosstat.gov.ru/x")
    assert http_client._host_down_remaining("rosstat.gov.ru") > 0
    assert http_client.host_down_max_remaining() > 0


def _relay_session(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "etl_http_proxy_url", "http://relay.test:8888")
    monkeypatch.setattr(settings, "etl_socks_proxy_url", "")
    return create_session(proxy=True, socks=False, retry=Retry(total=0, raise_on_status=False))


def test_slow_host_via_relay_does_not_arm_hop_breaker(monkeypatch):
    """20.11.2026: медленный ответ fedstat через релей (ReadTimeout) не выключал релей на 20 минут и не превращался в 403."""
    s = _relay_session(monkeypatch)
    calls: list[str | None] = []
    slow = [True]

    def fake_request(self, method, url, **kwargs):
        px = (kwargs.get("proxies") or {}).get("https")
        calls.append(px)
        if not px:
            return _resp(403)  # адрес прода fedstat режет всегда
        if slow[0]:
            raise requests.ReadTimeout("fedstat считает сетку дольше таймаута")
        return _resp(200)

    with patch.object(requests.Session, "request", fake_request):
        with pytest.raises(requests.ReadTimeout):
            s.post("https://www.fedstat.ru/indicator/dataGrid.do?id=31074")
        assert http_client._hop_down_remaining("www.fedstat.ru", "http://relay.test:8888") == 0
        assert http_client._host_down_remaining("www.fedstat.ru") == 0
        slow[0] = False
        calls.clear()
        assert s.post("https://www.fedstat.ru/indicator/dataGrid.do?id=57693").status_code == 200
    assert calls == [None, "http://relay.test:8888"]


def test_relay_refusing_connection_still_arms_hop_breaker(monkeypatch):
    s = _relay_session(monkeypatch)

    def fake_request(self, method, url, **kwargs):
        if (kwargs.get("proxies") or {}).get("https"):
            raise requests.exceptions.ConnectTimeout("relay silent")
        return _resp(403)

    with patch.object(requests.Session, "request", fake_request):
        assert s.post("https://www.fedstat.ru/indicator/dataGrid.do?id=1").status_code == 403
    assert http_client._hop_down_remaining("www.fedstat.ru", "http://relay.test:8888") > 0


def _host_dropped_via_proxy() -> requests.exceptions.ProxyError:
    """Как на проде 20.11.2026: urllib3 2.x заворачивает обрыв хостом за HTTP-прокси в ProxyError «Unable to connect»."""
    import http.client

    from urllib3.exceptions import MaxRetryError, ProxyError

    reason = ProxyError("Unable to connect to proxy", http.client.RemoteDisconnected(
        "Remote end closed connection without response"))
    return requests.exceptions.ProxyError(MaxRetryError(None, "/indicator/dataGrid.do?id=31074", reason=reason))


def test_host_closing_connection_via_relay_keeps_relay_and_is_not_403(monkeypatch):
    """20.11.2026: fedstat обрывал тяжёлую сетку через релей; обрыв выключал релей на 20 минут и выдавался за «HTTP 403»."""
    s = _relay_session(monkeypatch)
    calls: list[str | None] = []
    drop = [True]

    def fake_request(self, method, url, **kwargs):
        px = (kwargs.get("proxies") or {}).get("https")
        calls.append(px)
        if not px:
            return _resp(403)
        if drop[0]:
            raise _host_dropped_via_proxy()
        return _resp(200)

    with patch.object(requests.Session, "request", fake_request):
        with pytest.raises(http_client.HostDisconnected):
            s.post("https://www.fedstat.ru/indicator/dataGrid.do?id=57806")
        assert http_client._hop_down_remaining("www.fedstat.ru", "http://relay.test:8888") == 0
        assert http_client._host_down_remaining("www.fedstat.ru") == 0
        drop[0] = False
        calls.clear()
        assert s.post("https://www.fedstat.ru/indicator/dataGrid.do?id=31076").status_code == 200
    assert calls == [None, "http://relay.test:8888"]


def test_host_dropped_is_found_only_by_remote_disconnected():
    assert http_client._host_dropped(_host_dropped_via_proxy())
    assert not http_client._host_dropped(requests.exceptions.ProxyError("Cannot connect to proxy: refused"))
    assert not http_client._host_dropped(requests.exceptions.ConnectTimeout("relay silent"))


# ── ЕМИСС: отдельный выход и пауза (21.11.2026) ─────────────────────────────


def test_emiss_goes_straight_via_emiss_proxy(monkeypatch):
    """fedstat при заданном RUSTATS_EMISS_PROXY_URL идёт сразу через него: без прямой попытки и без релея/Tor."""
    from app.config import settings
    from app.services import http_client as hc

    monkeypatch.setattr(settings, "emiss_proxy_url", "http://stand:8899")
    calls: list = []

    def fake_request(self, method, url, proxies=None, **kw):
        calls.append(proxies)
        r = requests.Response()
        r.status_code = 200
        r._content = b"ok"
        return r

    monkeypatch.setattr(requests.Session, "request", fake_request)
    s = hc.ProxyFallbackSession(proxy_url="http://relay:1", socks_url="socks5h://tor:9050")
    resp = s.get("https://www.fedstat.ru/indicator/31448")
    assert resp.status_code == 200
    assert calls == [{"http": "http://stand:8899", "https": "http://stand:8899"}]


def test_emiss_403_via_emiss_proxy_is_not_retried_elsewhere(monkeypatch):
    """403 через выход ЕМИСС возвращается как есть: перебор релея и Tor только умножил бы отказы."""
    from app.config import settings
    from app.services import http_client as hc

    monkeypatch.setattr(settings, "emiss_proxy_url", "http://stand:8899")
    calls: list = []

    def fake_request(self, method, url, proxies=None, **kw):
        calls.append(proxies)
        r = requests.Response()
        r.status_code = 403
        return r

    monkeypatch.setattr(requests.Session, "request", fake_request)
    s = hc.ProxyFallbackSession(proxy_url="http://relay:1", socks_url="socks5h://tor:9050")
    assert s.get("https://www.fedstat.ru/indicator/31448").status_code == 403
    assert len(calls) == 1


def test_emiss_proxy_down_falls_back_to_usual_chain(monkeypatch):
    """Выход ЕМИСС не принял соединение — обычная цепочка (прямо → релей → Tor)."""
    from app.config import settings
    from app.services import http_client as hc

    monkeypatch.setattr(settings, "emiss_proxy_url", "http://stand:8899")
    calls: list = []

    def fake_request(self, method, url, proxies=None, **kw):
        calls.append(proxies)
        if proxies and "stand" in proxies.get("https", ""):
            raise requests.exceptions.ProxyError("stand down")
        r = requests.Response()
        r.status_code = 200
        return r

    monkeypatch.setattr(requests.Session, "request", fake_request)
    s = hc.ProxyFallbackSession(proxy_url="http://relay:1")
    assert s.get("https://www.fedstat.ru/indicator/31448").status_code == 200
    assert calls[0]["https"] == "http://stand:8899" and calls[1] is None


def test_other_hosts_ignore_emiss_proxy(monkeypatch):
    """Выход ЕМИСС только для fedstat.ru: остальные хосты идут прежней цепочкой."""
    from app.config import settings
    from app.services import http_client as hc

    monkeypatch.setattr(settings, "emiss_proxy_url", "http://stand:8899")
    calls: list = []

    def fake_request(self, method, url, proxies=None, **kw):
        calls.append(proxies)
        r = requests.Response()
        r.status_code = 200
        return r

    monkeypatch.setattr(requests.Session, "request", fake_request)
    hc.ProxyFallbackSession(proxy_url="http://relay:1").get("https://www.cbr.ru/")
    assert calls == [None]


def test_emiss_throttle_spaces_requests(monkeypatch, tmp_path):
    """Пауза между запросами к fedstat общая для процессов (файл-замок): второй запрос ждёт остаток интервала."""
    from app.config import settings
    from app.services import http_client as hc

    monkeypatch.setattr(settings, "emiss_min_interval_seconds", 0.3)
    monkeypatch.setattr(hc, "_EMISS_THROTTLE_FILE", str(tmp_path / "throttle"))
    assert hc.emiss_throttle() == 0.0
    t0 = time.time()
    waited = hc.emiss_throttle()
    assert waited > 0.1 and time.time() - t0 >= 0.2
