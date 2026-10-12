"""Stale-while-revalidate для SSR HTML и тяжёлых API (круг 12, зона SPEED2).

Замер 12.10.2026: после истечения TTL первый посетитель ждёт рендер на глазах (главная 1,1–1,6 с, страна 5,8–9,7 с,
`/api/v1/indicators` до 6 с на боевом), а при малом потоке (≈ 300 заходов на главную за две недели) «первым после истечения»
оказывается заметная доля людей и поисковых роботов. Режим SWR отдаёт запись по истёкшему сроку сразу (она живёт ещё
`ssr_swr_stale_seconds`), а пересчёт идёт в фоне одним запросом на ключ.

Как устроено
------------
* Запись: значение живёт в Redis `ttl + stale` секунд, маркер `<key>:fresh` — `ttl` секунд (`core/cache.py`). Нет маркера
  при наличии значения = устарело. Формат значения не меняется: флаг можно выключить в любой момент.
* Чтение устаревшего: ответ отдаётся сразу, затем `schedule_revalidate` берёт замок `fe:swr:lock:<md5 ключа>` (SET NX, общий
  для всех процессов) и в фоне запрашивает ту же публичную страницу через nginx (`ssr_swr_base_url`) с заголовком
  `X-FE-Revalidate`. Так пересчёт идёт тем же кодом, тем же ключом и со свежей сессией базы, а не с сессией уже
  закрытого запроса.
* Заголовок пересчёта принимается только с правильным HMAC-токеном (`revalidate_token`): снаружи принудительный рендер
  в обход кэша вызвать нельзя. Запрос с токеном пропускает чтение кэша, рендерит под тем же single-flight (замок
  процесса и `_RENDER_SEM`) и записывает свежее значение.
* Версии ключей (`fe:ver:*`, ETL) и очистка SSR при релизе работают как раньше: новый ключ — промах, старые записи просто
  не читаются.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from contextvars import ContextVar
from typing import Any, Awaitable, Callable

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

REVALIDATE_HEADER = "x-fe-revalidate"
REVALIDATE_USER_AGENT = "ForecastEconomy-swr/1"
# Замок пересчёта: пока идёт запрос (до 60 с) и ещё немного после, чтобы упавший пересчёт не повторялся каждую секунду.
_LOCK_SECONDS = 90
_REPLAY_TIMEOUT = 60.0

_revalidate_var: ContextVar[bool] = ContextVar("fe_swr_revalidate", default=False)
# (хост, путь с запросом, значение X-FE-Locale) публичного запроса — по ним фон повторяет тот же адрес.
_target_var: ContextVar[tuple[str, str, str] | None] = ContextVar("fe_swr_target", default=None)
_inflight: set[str] = set()
_tasks: set[asyncio.Task] = set()


def swr_enabled() -> bool:
    return bool(settings.ssr_swr_enabled)


def revalidate_token() -> str:
    """HMAC-токен заголовка пересчёта: общий для процессов деплоя, снаружи не угадывается."""
    secret = settings.ssr_swr_token or settings.scrape_bind_secret or settings.database_url
    return hmac.new(secret.encode(), b"fe-ssr-swr-revalidate/v1", hashlib.sha256).hexdigest()[:40]


def revalidate_requested() -> bool:
    """Текущий запрос — фоновый пересчёт: кэш не читается, значение будет перезаписано."""
    return _revalidate_var.get()


def stale_window() -> int:
    return max(int(settings.ssr_swr_stale_seconds), 0)


def _target_for(request) -> tuple[str, str, str] | None:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    if not host:
        return None
    path = request.url.path
    query = request.url.query
    original = request.headers.get("x-original-uri")
    locale_header = request.headers.get("x-fe-locale", "")
    # nginx передаёт публичный адрес страницы в X-Original-URI; для API берём собственный путь запроса.
    if original and path.startswith("/seo/") and original.startswith("/") and not original.startswith("//"):
        return host, original, locale_header
    return host, f"{path}?{query}" if query else path, locale_header


def bind_request(request) -> tuple:
    """Вызывается из LocaleMiddleware: запоминает признак пересчёта и адрес публичного запроса."""
    if not swr_enabled():
        return ()
    supplied = request.headers.get(REVALIDATE_HEADER, "")
    is_reval = bool(supplied) and hmac.compare_digest(supplied, revalidate_token())
    # Предпросмотр языка (?preview_locale=…) кэш не использует и не пересчитывается.
    from app.services.locale import is_preview_locale

    preview = is_preview_locale()
    return (
        _revalidate_var.set(is_reval),
        _target_var.set(None if (is_reval or preview) else _target_for(request)),
    )


def unbind_request(tokens: tuple) -> None:
    if not tokens:
        return
    _revalidate_var.reset(tokens[0])
    _target_var.reset(tokens[1])


async def _acquire_lock(key: str) -> bool:
    from app.core.cache import get_redis

    digest = hashlib.md5(key.encode()).hexdigest()
    try:
        redis = await get_redis()
        return bool(await redis.set(f"fe:swr:lock:{digest}", "1", nx=True, ex=_LOCK_SECONDS))
    except Exception:  # noqa: BLE001 — без Redis пересчёт не запускаем (иначе шторм)
        return False


async def _release_lock(key: str) -> None:
    from app.core.cache import get_redis

    digest = hashlib.md5(key.encode()).hexdigest()
    try:
        redis = await get_redis()
        await redis.delete(f"fe:swr:lock:{digest}")
    except Exception:  # noqa: BLE001
        pass


async def _replay(key: str, host: str, path: str, locale_header: str = "") -> None:
    base = (settings.ssr_swr_base_url or settings.ssr_warm_base_url).rstrip("/")
    ok = False
    try:
        async with httpx.AsyncClient(timeout=_REPLAY_TIMEOUT, follow_redirects=False) as client:
            response = await client.get(
                f"{base}{path}",
                headers={
                    "Host": host,
                    "X-Forwarded-Host": host,
                    "User-Agent": REVALIDATE_USER_AGENT,
                    "Accept-Encoding": "identity",
                    REVALIDATE_HEADER: revalidate_token(),
                    **({"X-FE-Locale": locale_header} if locale_header else {}),
                },
            )
            ok = response.status_code == 200
            if not ok:
                logger.warning("swr revalidate %s%s -> %s", host, path, response.status_code)
    except Exception as exc:  # noqa: BLE001 — фон не должен падать в журнал трассировкой на каждый сбой сети
        logger.warning("swr revalidate %s%s failed: %s", host, path, exc)
    finally:
        _inflight.discard(key)
        if ok:
            await _release_lock(key)


async def schedule_revalidate(key: str) -> bool:
    """Запустить фоновый пересчёт ключа, если его ещё никто не пересчитывает. Возвращает True, если запущен."""
    target = _target_var.get()
    if target is None or key in _inflight:
        return False
    if not await _acquire_lock(key):
        return False
    _inflight.add(key)
    host, path, locale_header = target
    task = asyncio.get_running_loop().create_task(_replay(key, host, path, locale_header))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return True


async def api_cache_get(
    key: str,
    getter: Callable[[str], Awaitable[Any]] | None = None,
) -> Any:
    """`cache_get` для JSON-ответов API с SWR: при выключенном флаге — ровно `getter(key)` (прежнее поведение).

    ``getter`` — `cache_get` модуля вызывающего (тесты подменяют его на модуле).
    """
    from app.core.cache import cache_get, cache_get_swr

    if not swr_enabled():
        return await (getter or cache_get)(key)
    if revalidate_requested():
        return None
    value, fresh = await cache_get_swr(key)
    if value is None:
        return None
    if not fresh:
        await schedule_revalidate(key)
    return value


async def api_cache_set(
    key: str,
    value: Any,
    ttl: int,
    setter: Callable[..., Awaitable[Any]] | None = None,
) -> None:
    """`cache_set` для JSON-ответов API с SWR: при выключенном флаге — прежний вызов `setter(key, value, ttl)`."""
    from app.core.cache import cache_set

    if swr_enabled():
        await cache_set(key, value, ttl, stale_ttl=stale_window())
        return
    await (setter or cache_set)(key, value, ttl)
