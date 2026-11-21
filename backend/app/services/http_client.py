"""Shared requests.Session with automatic retries and User-Agent for all ETL fetchers.

Proxy fallback chain (2026-07-12):
1. Direct
2. HTTP proxy — `RUSTATS_ETL_HTTP_PROXY_URL` or `RUSTATS_OPENROUTER_PROXY_URL`
3. SOCKS — `RUSTATS_ETL_SOCKS_PROXY_URL` (prod: host Tor `socks5h://172.18.0.1:9050`)

Ban-like statuses (403/407/429/503) and connection/timeout errors trigger the
next hop. Direct success never uses a proxy. SOCKS needs PySocks installed.

Заглушка «технические работы» (2026-11-02): 01-02.11.2026 rosstat.gov.ru стал отвечать на любой адрес одной
страницей «Сайт Росстата временно недоступен» (главная 200, остальное 404, 33 821 байт). Парсеры читали это как
«файл не найден», и вечерний ETL показал 45 разных ошибок вместо одной причины. Теперь такой ответ — `SourceMaintenance`
(`ConnectionError`, в тексте «unreachable»): взводится предохранитель хоста, ряды получают сетевой повтор и догрузку
после возвращения сайта (`tasks/scheduler.rosstat_recovery_job`).

Connect timeout and host breaker (2026-10-08): 07.10 rosstat.gov.ru 8 ч не
принимал соединения; `timeout=90` действовал и на connect, 4 попытки × 2 хопа ×
6 файлов-кандидатов ≈ час на индикатор, daily ETL шёл 9 ч. Теперь connect
ограничен (`CONNECT_TIMEOUT_*`, read остаётся от вызывающего), а хост, не
принявший соединение ни по одному хопу, `HOST_BREAKER_COOLDOWN_S` отвечает
мгновенной ошибкой без сети. Read timeout и HTTP-статусы предохранитель не
взводят: хост жив.
"""

from __future__ import annotations

import contextvars
import fcntl
import http.client
import logging
import os
import tempfile
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


# Хосты, у которых заглушка вместо данных - сбой источника, а не «файла нет». Метки - UTF-8 текста страницы.
_MAINTENANCE_HOSTS = ("rosstat.gov.ru", "gks.ru")
_MAINTENANCE_MARKERS = ("временно недоступен".encode(), "технические работы".encode())
_MAINTENANCE_SCAN_BYTES = 200_000


class SourceMaintenance(requests.ConnectionError):
    """Источник отвечает страницей-заглушкой «технические работы» вместо данных (не сетевой отказ и не «файла нет»)."""


class HostDisconnected(requests.ConnectionError):
    """Хост через прокси-хоп принял запрос и закрыл соединение без ответа (20.11.2026).

    Это свойство хоста, а не прокси: хоп не помечается недоступным, предохранитель хоста не взводится, бан-статус
    прежнего хопа ответом не подменяется. fedstat обрывает тяжёлую сетку dataGrid.do через 30–70 с счёта.
    """


def _host_dropped(exc: BaseException) -> bool:
    """В цепочке исключения есть `RemoteDisconnected`: запрос ушёл, хост закрыл соединение без ответа.

    urllib3 2.x при обрыве через HTTP-прокси сбрасывает признак «к прокси подключились» и оборачивает обрыв в
    `ProxyError('Unable to connect to proxy', RemoteDisconnected(...))`, поэтому по классу ошибки хоп от хоста не
    отличить — только по причине внутри.
    """
    seen: set[int] = set()
    stack: list[object] = [exc]
    while stack:
        cur = stack.pop()
        if not isinstance(cur, BaseException) or id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, http.client.RemoteDisconnected):
            return True
        stack.extend((cur.__cause__, cur.__context__, getattr(cur, "reason", None), *cur.args))
    return False


def _is_maintenance_stub(host: str, resp: requests.Response) -> bool:
    """HTML-ответ хоста из `_MAINTENANCE_HOSTS` с обеими метками заглушки. Настоящие страницы и файлы их не содержат."""
    if not any(host == h or host.endswith("." + h) for h in _MAINTENANCE_HOSTS):
        return False
    headers = getattr(resp, "headers", None)
    ctype = headers.get("content-type", "") if headers is not None else ""
    body = getattr(resp, "content", None)
    if not isinstance(ctype, str) or "html" not in ctype.lower() or not isinstance(body, (bytes, bytearray)):
        return False
    body = body[:_MAINTENANCE_SCAN_BYTES]
    return all(marker in body for marker in _MAINTENANCE_MARKERS)


CONNECT_TIMEOUT_DIRECT = 15
# socks5h: connect включает построение цепочки Tor и TCP до цели.
CONNECT_TIMEOUT_PROXY = 30
HOST_BREAKER_COOLDOWN_S = 20 * 60

_breaker_lock = threading.Lock()
_host_down_until: dict[str, float] = {}
# Предохранитель хопа (2026-10-27): прокси-хоп, не принявший соединение к хосту, пропускается `HOP_BREAKER_COOLDOWN_S`.
# Tor с прода не доходит до rosstat.gov.ru вообще (проверка 27.10: прямой запрос 0,3 с, через Tor 000 за 40 с), а
# Росстат на закрытый файл текущего месяца (`ind_baza_2023_09-2026.xlsx`, `osn-MM-YYYY.pdf`) отвечает прямым 403
# со страницей «лимит подключений»: 403 уводил запрос в Tor, тот молчал 60 с, `ConnectionError` взводил предохранитель
# ХОСТА на 20 минут, и все остальные ряды Росстата вечернего ETL падали мгновенно (16.10, 22.10, 27.10).
HOP_BREAKER_COOLDOWN_S = 20 * 60
_hop_down_until: dict[tuple[str, str], float] = {}
# 20.11.2026: `ReadTimeout` на прокси-хопе предохранитель хопа не взводит (`_via_next_hop`) — хоп работает, медлит хост.
# Так же обрыв хостом без ответа (`HostDisconnected`): после него релей выключался, и наборы ЕМИСС получали прямой 403.


# Журнал сетевых сбоев текущего прогона парсера (circle 12, 2026-10-12).
# 09.10 rosstat.gov.ru на минуту не принял соединение, парсеры fuel-ai92 и
# inflation-weekly проглотили RequestException и вернули 0 точек; ETL записал
# parsed_zero и «вероятна смена layout источника», хотя вёрстка не менялась.
# BaseParser.run кладёт сюда список, сессия дописывает недоступность хоста
# (ConnectionError/Timeout после всех хопов, 5xx/403/429 в итоговом ответе);
# asyncio.to_thread копирует контекст, поэтому список виден из потока fetch.
_fetch_issues: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "etl_fetch_issues", default=None,
)


def begin_fetch_issues() -> contextvars.Token:
    """Начать сбор сетевых сбоев текущего прогона; вернуть токен для `end_fetch_issues`."""
    return _fetch_issues.set([])


def current_fetch_issues() -> list[str]:
    return list(_fetch_issues.get() or [])


def end_fetch_issues(token: contextvars.Token) -> None:
    _fetch_issues.reset(token)


def record_fetch_issue(message: str) -> None:
    issues = _fetch_issues.get()
    if issues is not None and len(issues) < 20:
        issues.append(message[:300])


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


def _hop_down_remaining(host: str, hop_url: str) -> float:
    with _breaker_lock:
        until = _hop_down_until.get((host, hop_url))
        if until is None:
            return 0.0
        left = until - time.monotonic()
        if left <= 0:
            _hop_down_until.pop((host, hop_url), None)
            return 0.0
        return left


def _mark_hop_down(host: str, hop_url: str) -> None:
    with _breaker_lock:
        _hop_down_until[(host, hop_url)] = time.monotonic() + HOP_BREAKER_COOLDOWN_S


def host_down_max_remaining() -> float:
    """Сколько секунд до снятия самого долгого предохранителя хоста (0 - ни один не взведён)."""
    with _breaker_lock:
        now = time.monotonic()
        return max([u - now for u in _host_down_until.values() if u > now] or [0.0])


def _mark_host_up(host: str) -> None:
    with _breaker_lock:
        _host_down_until.pop(host, None)


def _reset_host_breaker() -> None:
    """Для тестов: снять все отметки."""
    with _breaker_lock:
        _host_down_until.clear()
        _hop_down_until.clear()


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


# ЕМИСС (fedstat.ru), 21.11.2026: с 20.11 fedstat отвечает 403 и адресу боевого, и релею; тестовый стенд он пускает.
# `RUSTATS_EMISS_PROXY_URL` — отдельный выход только для fedstat (прокси на стенде, открыт только адресу боевого и
# только для fedstat.ru). Запросы к fedstat идут сразу через него, без прямой попытки и без релея/Tor: лишние 403
# сами по себе похожи на перебор и продлевают бан. Пауза между запросами к fedstat — общая для всех процессов
# контейнера (файл-замок), `RUSTATS_EMISS_MIN_INTERVAL_SECONDS`: бан 20.11 пришёл после ~50 запросов подряд без пауз.
_EMISS_HOST = "fedstat.ru"


def _is_emiss_host(host: str) -> bool:
    return host == _EMISS_HOST or host.endswith("." + _EMISS_HOST)


def resolve_emiss_proxy_url() -> str | None:
    """Отдельный выход для fedstat.ru; пусто — обычная цепочка (прямо → HTTP-прокси → SOCKS)."""
    from app.config import settings

    url = (getattr(settings, "emiss_proxy_url", "") or "").strip()
    return url or None


def _emiss_min_interval() -> float:
    from app.config import settings

    try:
        return max(0.0, float(getattr(settings, "emiss_min_interval_seconds", 3.0)))
    except (TypeError, ValueError):
        return 3.0


_EMISS_THROTTLE_FILE = os.path.join(tempfile.gettempdir(), "fe-emiss-throttle")
_emiss_thread_lock = threading.Lock()


def emiss_throttle() -> float:
    """Выдержать паузу между запросами к fedstat во всех процессах контейнера. Возвращает, сколько ждали (с)."""
    interval = _emiss_min_interval()
    if interval <= 0:
        return 0.0
    with _emiss_thread_lock:
        with open(_EMISS_THROTTLE_FILE, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                fh.seek(0)
                raw = fh.read().strip()
                try:
                    last = float(raw) if raw else 0.0
                except ValueError:
                    last = 0.0
                wait = last + interval - time.time()
                if wait > 0:
                    time.sleep(min(wait, interval))
                else:
                    wait = 0.0
                fh.seek(0)
                fh.truncate()
                fh.write(f"{time.time():.3f}")
                fh.flush()
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    return max(0.0, wait)


def _proxy_dict(url: str) -> dict[str, str]:
    return {"http": url, "https": url}


class ProxyFallbackSession(requests.Session):
    """Session that retries via HTTP then SOCKS after ban-like direct failures."""

    def __init__(
        self,
        proxy_url: str | None = None,
        socks_url: str | None = None,
        *,
        remember_detour: bool = False,
    ):
        super().__init__()
        self._proxy_url = (proxy_url or "").strip() or None
        self._socks_url = (socks_url or "").strip() or None
        # Обход, запомненный для хоста (20.11.2026): хост, закрытый для сети сервера, этой сессией идёт сразу
        # через сработавший прокси-хоп, а не ждёт каждый раз прямой таймаут. Выключено для ETL России.
        self._remember_detour = remember_detour
        self._detour_until: dict[str, tuple[int, float]] = {}

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
        if host and _is_emiss_host(host):
            emiss_throttle()
            emiss_resp = self._via_emiss_proxy(method, url, kwargs)
            if emiss_resp is not None:
                return emiss_resp
        detoured = self._try_detour(method, url, host, kwargs)
        if detoured is not None:
            return detoured
        left = _host_down_remaining(host) if host else 0.0
        if left:
            # Без записи парсеры, глотающие ошибку (недельные цены, недельная инфляция), давали «0 точек, смена вёрстки?».
            record_fetch_issue(f"{host} unreachable (host breaker, {left:.0f}s left)")
            raise requests.ConnectionError(
                f"{host} unreachable on all hops recently; skipping for {left:.0f}s more"
            )
        try:
            resp = self._request_hop(method, url, **kwargs)
        except requests.exceptions.SSLError:
            # Ошибка сертификата — свойство вызова (verify/CA), не недоступность хоста.
            record_fetch_issue(f"{host or url}: SSL error")
            raise
        except HostDisconnected as exc:
            # Хост жив (принял запрос через хоп): предохранитель хоста не взводится.
            record_fetch_issue(f"{host or url} disconnected: {type(exc).__name__}")
            raise
        except requests.ConnectionError as exc:
            if host:
                _mark_host_down(host)
                logger.warning(
                    "ETL host %s unreachable on all hops — fail fast for %ds",
                    host, HOST_BREAKER_COOLDOWN_S,
                )
            record_fetch_issue(f"{host or url} unreachable: {type(exc).__name__}")
            raise
        except requests.Timeout as exc:
            record_fetch_issue(f"{host or url} timeout: {type(exc).__name__}")
            raise
        if host and not kwargs.get("stream") and _is_maintenance_stub(host, resp):
            _mark_host_down(host)
            logger.warning(
                "ETL host %s отвечает страницей «технические работы» — fail fast for %ds",
                host, HOST_BREAKER_COOLDOWN_S,
            )
            record_fetch_issue(f"{host} unreachable: сайт на технических работах")
            raise SourceMaintenance(f"{host} unreachable: site is under maintenance (stub page instead of data)")
        if host:
            _mark_host_up(host)
        # 404 при переборе имён файлов — норма; сбой источника — 5xx и бан-статусы.
        if resp.status_code >= 500 or resp.status_code in _PROXY_FALLBACK_STATUSES:
            record_fetch_issue(f"{host or url}: HTTP {resp.status_code}")
        return resp

    def _via_emiss_proxy(
        self, method: str, url: str, kwargs: dict[str, Any],
    ) -> requests.Response | None:
        """fedstat через отдельный выход (`RUSTATS_EMISS_PROXY_URL`). None — выхода нет или он не принял соединение.

        Ответ fedstat через выход (в том числе 403) возвращается как есть: перебор остальных хопов только добавил бы
        отказов. Медленный ответ и обрыв хостом уходят наружу как в обычной цепочке (`ReadTimeout`, `HostDisconnected`).
        """
        emiss = resolve_emiss_proxy_url()
        if not emiss:
            return None
        hop_kwargs = {k: v for k, v in kwargs.items() if k != "proxies"}
        try:
            resp = self._request_hop(
                method, url, _proxy_hop=len(self._fallback_urls()), proxies=_proxy_dict(emiss), **hop_kwargs,
            )
        except requests.ReadTimeout:
            raise
        except _PROXY_FALLBACK_EXC as exc:
            if _host_dropped(exc):
                raise HostDisconnected(f"{_host(url)} closed the connection without a response via EMISS proxy") from exc
            logger.warning(
                "ETL %s %s: EMISS proxy unreachable (%s) — falling back to the usual chain",
                method, url, type(exc).__name__,
            )
            return None
        if resp.status_code in _PROXY_FALLBACK_STATUSES or resp.status_code >= 500:
            record_fetch_issue(f"{_host(url)}: HTTP {resp.status_code} via EMISS proxy")
        return resp

    def _try_detour(
        self, method: str, url: str, host: str, kwargs: dict[str, Any],
    ) -> requests.Response | None:
        """Запомненный обход: сразу через прокси-хоп; при его сбое обход забывается и идёт обычная цепочка."""
        if not self._remember_detour or not host:
            return None
        hop, until = self._detour_until.get(host, (0, 0.0))
        fallbacks = self._fallback_urls()
        if until <= time.monotonic() or hop >= len(fallbacks):
            self._detour_until.pop(host, None)
            return None
        try:
            resp = self._request_hop(
                method, url, _proxy_hop=hop + 1, proxies=_proxy_dict(fallbacks[hop]),
                **{k: v for k, v in kwargs.items() if k != "proxies"},
            )
        except _PROXY_FALLBACK_EXC:
            self._detour_until.pop(host, None)
            return None
        if resp.status_code in _PROXY_FALLBACK_STATUSES:
            self._detour_until.pop(host, None)
            return None
        return resp

    def _remember(self, url: str, hop: int, resp: requests.Response) -> None:
        if self._remember_detour and resp.status_code not in _PROXY_FALLBACK_STATUSES:
            host = _host(url)
            if host:
                self._detour_until[host] = (hop, time.monotonic() + HOP_BREAKER_COOLDOWN_S)

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
            if _hop_down_remaining(_host(url), nxt):
                logger.info("ETL %s %s: %s hop skipped (down recently)", method, url, nxt.split("://", 1)[0])
                raise
            logger.warning(
                "ETL %s %s failed (%s) — retry via %s",
                method,
                url,
                type(exc).__name__,
                nxt.split("://", 1)[0],
            )
            return self._via_next_hop(method, url, hop, nxt, kwargs, banned_resp=None)

        if (
            not caller_proxies
            and hop < len(fallbacks)
            and resp.status_code in _PROXY_FALLBACK_STATUSES
        ):
            nxt = fallbacks[hop]
            if _hop_down_remaining(_host(url), nxt):
                logger.info(
                    "ETL %s %s → HTTP %s; %s hop skipped (down recently)",
                    method, url, resp.status_code, nxt.split("://", 1)[0],
                )
                return resp
            logger.warning(
                "ETL %s %s → HTTP %s — retry via %s",
                method,
                url,
                resp.status_code,
                nxt.split("://", 1)[0],
            )
            return self._via_next_hop(method, url, hop, nxt, kwargs, banned_resp=resp)
        # HTTP/SOCKS hop returned ban-status → try next fallback if any
        if (
            caller_proxies
            and hop < len(fallbacks)
            and resp.status_code in _PROXY_FALLBACK_STATUSES
        ):
            nxt = fallbacks[hop]
            if _hop_down_remaining(_host(url), nxt):
                return resp
            logger.warning(
                "ETL proxy hop failed HTTP %s — retry via %s",
                resp.status_code,
                nxt.split("://", 1)[0],
            )
            return self._via_next_hop(method, url, hop, nxt, kwargs, banned_resp=resp)
        return resp

    def _via_next_hop(
        self,
        method: str,
        url: str,
        hop: int,
        nxt: str,
        kwargs: dict[str, Any],
        *,
        banned_resp: requests.Response | None,
    ) -> requests.Response:
        """Выполнить следующий хоп. Если прокси не принял соединение, пометить хоп недоступным для хоста.

        Когда прежний хоп УЖЕ получил ответ хоста (бан-статус, например 403 Росстата), отказ прокси не делает хост
        недоступным: возвращаем исходный ответ вместо `ConnectionError`, иначе сработает предохранитель хоста.

        `ReadTimeout` (20.11.2026) — не отказ хопа: прокси соединение принял, медленно отвечает сам хост. Хоп не
        помечается недоступным, и ошибка уходит наружу как есть, а не подменяется бан-статусом прежнего хопа.
        До правки тяжёлый запрос ЕМИСС (>60 с через релей) взводил предохранитель релея на 20 минут, и все
        следующие запросы к fedstat — в том числе другие задачи — падали с прямым «HTTP 403» адреса прода.

        Обрыв хостом (`RemoteDisconnected` в цепочке, 20.11.2026) — тоже не отказ хопа: fedstat закрывает соединение
        на тяжёлой сетке через 30–70 с. Наружу уходит `HostDisconnected`, хоп остаётся рабочим, 403 не подставляется.
        """
        try:
            resp = self._request_hop(
                method, url, _proxy_hop=hop + 1, proxies=_proxy_dict(nxt), **kwargs,
            )
            self._remember(url, hop, resp)
            return resp
        except (requests.ReadTimeout, HostDisconnected):
            raise
        except _PROXY_FALLBACK_EXC as exc:
            if _host_dropped(exc):
                logger.warning(
                    "ETL %s %s: host closed the connection via %s hop without a response — hop stays up",
                    method, url, nxt.split("://", 1)[0],
                )
                raise HostDisconnected(f"{_host(url)} closed the connection without a response via proxy") from exc
            _mark_hop_down(_host(url), nxt)
            if banned_resp is not None:
                logger.warning(
                    "ETL %s %s: %s hop unreachable — keeping HTTP %s from the previous hop",
                    method, url, nxt.split("://", 1)[0], banned_resp.status_code,
                )
                return banned_resp
            raise


def create_source_session(
    *,
    adapter: HTTPAdapter | None = None,
    timeout: int = 60,
) -> ProxyFallbackSession:
    """Сессия официального источника, который может закрыть сеть сервера (мировые адаптеры, 20.11.2026).

    Сначала прямой запрос; отказ сети (таймаут, обрыв) или бан-статус 403/407/429/503 — повтор через ETL-прокси
    (HTTP, затем SOCKS), и хост дальше идёт сразу через сработавший хоп. Своих заголовков и повторов не добавляет:
    их задаёт адаптер. Без настроенных прокси ведёт себя как обычная сессия.
    """
    s = ProxyFallbackSession(
        proxy_url=resolve_etl_proxy_url(), socks_url=resolve_etl_socks_url(), remember_detour=True,
    )
    mounted = adapter or _TimeoutAdapter(timeout=timeout, max_retries=0)
    s.mount("https://", mounted)
    s.mount("http://", mounted)
    return s


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
