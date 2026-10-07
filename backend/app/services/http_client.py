"""Shared requests.Session with automatic retries and User-Agent for all ETL fetchers.

Proxy fallback chain (2026-07-12):
1. Direct
2. HTTP proxy — `RUSTATS_ETL_HTTP_PROXY_URL` or `RUSTATS_OPENROUTER_PROXY_URL`
3. SOCKS — `RUSTATS_ETL_SOCKS_PROXY_URL` (prod: host Tor `socks5h://172.18.0.1:9050`)

Ban-like statuses (403/407/429/503) and connection/timeout errors trigger the
next hop. Direct success never uses a proxy. SOCKS needs PySocks installed.

Connect timeout and host breaker (2026-10-08): 07.10 rosstat.gov.ru 8 ч не
принимал соединения; `timeout=90` действовал и на connect, 4 попытки × 2 хопа ×
6 файлов-кандидатов ≈ час на индикатор, daily ETL шёл 9 ч. Теперь connect
ограничен (`CONNECT_TIMEOUT_*`, read остаётся от вызывающего), а хост, не
принявший соединение ни по одному хопу, `HOST_BREAKER_COOLDOWN_S` отвечает
мгновенной ошибкой без сети. Read timeout и HTTP-статусы предохранитель не
взводят: хост жив.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Do NOT put 403/429/503 here — ProxyFallbackSession must see them once and
# hop to HTTP/SOCKS. urllib3 MaxRetry on those statuses would raise RetryError
# before our fallback runs (prod Minfin trap, 2026-07-12).
# connect=1: хост, молча отбрасывающий SYN, повторами не оживает — один повтор
# от сетевого блипа, дальше следующий хоп и предохранитель (2026-10-08).
_RETRY_STRATEGY = Retry(
    total=3,
    connect=1,
    backoff_factor=2,
    status_forcelist=[408, 500, 502, 504],
    allowed_methods=["GET", "POST"],
)

_PROXY_FALLBACK_STATUSES = frozenset({403, 407, 429, 503})
_PROXY_FALLBACK_EXC = (
    requests.ConnectionError,
    requests.Timeout,
    requests.exceptions.RetryError,
)


CONNECT_TIMEOUT_DIRECT = 15
# socks5h: connect включает построение цепочки Tor и TCP до цели.
CONNECT_TIMEOUT_PROXY = 30
HOST_BREAKER_COOLDOWN_S = 20 * 60

_breaker_lock = threading.Lock()
_host_down_until: dict[str, float] = {}


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _host_down_remaining(host: str) -> float:
    with _breaker_lock:
        until = _host_down_until.get(host)
        if until is None:
            return 0.0
        left = until - time.monotonic()
        if left <= 0:
            _host_down_until.pop(host, None)
            return 0.0
        return left


def _mark_host_down(host: str) -> None:
    with _breaker_lock:
        _host_down_until[host] = time.monotonic() + HOST_BREAKER_COOLDOWN_S


def _mark_host_up(host: str) -> None:
    with _breaker_lock:
        _host_down_until.pop(host, None)


def _reset_host_breaker() -> None:
    """Для тестов: снять все отметки."""
    with _breaker_lock:
        _host_down_until.clear()


class _TimeoutAdapter(HTTPAdapter):
    """HTTPAdapter: default read timeout and capped connect timeout.

    requests всегда передаёт `timeout=None`, поэтому прежний `setdefault` не
    срабатывал и запросы без явного timeout могли висеть бесконечно.
    Скалярный timeout вызывающего становится read timeout; connect ограничен.
    """

    def __init__(self, timeout: int = 60, **kwargs):
        self._default_timeout = timeout
        super().__init__(**kwargs)

    def send(self, request, **kwargs):
        t = kwargs.get("timeout")
        if t is None:
            t = self._default_timeout
        if isinstance(t, (int, float)):
            cap = CONNECT_TIMEOUT_PROXY if kwargs.get("proxies") else CONNECT_TIMEOUT_DIRECT
            t = (min(cap, t), t)
        kwargs["timeout"] = t
        return super().send(request, **kwargs)


def resolve_etl_proxy_url() -> str | None:
    """Outbound HTTP proxy for ETL: dedicated env, else OpenRouter proxy.

    Dedicated value ``off`` / ``none`` / ``-`` disables the HTTP hop (SOCKS-only
    fallback), without falling back to OpenRouter.
    """
    from app.config import settings

    dedicated = (settings.etl_http_proxy_url or "").strip()
    if dedicated.lower() in {"off", "none", "-"}:
        return None
    if dedicated:
        return dedicated
    shared = (settings.openrouter_proxy_url or "").strip()
    return shared or None


def resolve_etl_socks_url() -> str | None:
    """Outbound SOCKS proxy for ETL (e.g. host Tor reachable from Docker)."""
    from app.config import settings

    socks = (settings.etl_socks_proxy_url or "").strip()
    return socks or None


def _proxy_dict(url: str) -> dict[str, str]:
    return {"http": url, "https": url}


class ProxyFallbackSession(requests.Session):
    """Session that retries via HTTP then SOCKS after ban-like direct failures."""

    def __init__(
        self,
        proxy_url: str | None = None,
        socks_url: str | None = None,
    ):
        super().__init__()
        self._proxy_url = (proxy_url or "").strip() or None
        self._socks_url = (socks_url or "").strip() or None

    def _fallback_urls(self) -> list[str]:
        out: list[str] = []
        for u in (self._proxy_url, self._socks_url):
            if u and u not in out:
                out.append(u)
        return out

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        if "_proxy_hop" in kwargs or kwargs.get("proxies"):
            return self._request_hop(method, url, **kwargs)
        host = _host(url)
        left = _host_down_remaining(host) if host else 0.0
        if left:
            raise requests.ConnectionError(
                f"{host} unreachable on all hops recently; skipping for {left:.0f}s more"
            )
        try:
            resp = self._request_hop(method, url, **kwargs)
        except requests.exceptions.SSLError:
            # Ошибка сертификата — свойство вызова (verify/CA), не недоступность хоста.
            raise
        except requests.ConnectionError:
            if host:
                _mark_host_down(host)
                logger.warning(
                    "ETL host %s unreachable on all hops — fail fast for %ds",
                    host, HOST_BREAKER_COOLDOWN_S,
                )
            raise
        if host:
            _mark_host_up(host)
        return resp

    def _request_hop(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        hop = int(kwargs.pop("_proxy_hop", 0))
        # Pop so recursive retries can pass a fresh proxies= without collision.
        caller_proxies = kwargs.pop("proxies", None)
        fallbacks = self._fallback_urls()

        try:
            resp = super().request(method, url, proxies=caller_proxies, **kwargs)
        except _PROXY_FALLBACK_EXC as exc:
            if caller_proxies or hop >= len(fallbacks):
                raise
            nxt = fallbacks[hop]
            logger.warning(
                "ETL %s %s failed (%s) — retry via %s",
                method,
                url,
                type(exc).__name__,
                nxt.split("://", 1)[0],
            )
            return self._request_hop(
                method,
                url,
                _proxy_hop=hop + 1,
                proxies=_proxy_dict(nxt),
                **kwargs,
            )

        if (
            not caller_proxies
            and hop < len(fallbacks)
            and resp.status_code in _PROXY_FALLBACK_STATUSES
        ):
            nxt = fallbacks[hop]
            logger.warning(
                "ETL %s %s → HTTP %s — retry via %s",
                method,
                url,
                resp.status_code,
                nxt.split("://", 1)[0],
            )
            return self._request_hop(
                method,
                url,
                _proxy_hop=hop + 1,
                proxies=_proxy_dict(nxt),
                **kwargs,
            )
        # HTTP/SOCKS hop returned ban-status → try next fallback if any
        if (
            caller_proxies
            and hop < len(fallbacks)
            and resp.status_code in _PROXY_FALLBACK_STATUSES
        ):
            nxt = fallbacks[hop]
            logger.warning(
                "ETL proxy hop failed HTTP %s — retry via %s",
                resp.status_code,
                nxt.split("://", 1)[0],
            )
            return self._request_hop(
                method,
                url,
                _proxy_hop=hop + 1,
                proxies=_proxy_dict(nxt),
                **kwargs,
            )
        return resp


def create_session(
    timeout: int = 60,
    *,
    retry: Retry | None = None,
    proxy: str | None | bool = True,
    socks: str | None | bool = True,
) -> requests.Session:
    """Build a Session with retries and optional HTTP/SOCKS proxy fallback.

    `proxy` / `socks`:
      - True (default) — resolve from settings when set
      - False / None — skip that hop
      - str — use that URL
    """
    if proxy is True:
        proxy_url = resolve_etl_proxy_url()
    elif not proxy:
        proxy_url = None
    else:
        proxy_url = str(proxy).strip() or None

    if socks is True:
        socks_url = resolve_etl_socks_url()
    elif not socks:
        socks_url = None
    else:
        socks_url = str(socks).strip() or None

    s = ProxyFallbackSession(proxy_url=proxy_url, socks_url=socks_url)
    adapter = _TimeoutAdapter(timeout=timeout, max_retries=retry or _RETRY_STRATEGY)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.3",
    })
    return s
