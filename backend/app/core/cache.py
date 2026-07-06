import asyncio
import json
import logging
import time
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

from redis.asyncio import Redis
from app.config import settings

logger = logging.getLogger(__name__)
_redis: Optional[Redis] = None
_state_redis: Optional[Redis] = None
_redis_lock = asyncio.Lock()


async def get_redis() -> Redis:
    global _redis
    if _redis is not None:
        return _redis
    async with _redis_lock:
        if _redis is None:
            _redis = Redis.from_url(settings.redis_url, decode_responses=True)
        return _redis


def _state_redis_url() -> str:
    """URL Redis для долгоживущего состояния (сессии, lockout, гостевые лимиты).

    Отдельный logical DB (по умолчанию /1 при кэше в /0): деплойный
    `redis-cli FLUSHDB` чистит ТОЛЬКО кэш и не разлогинивает пользователей.
    До этого фикса (2026-07-02) каждый FLUSHDB сносил и сессии — «авторизация
    слетала» после любого деплоя с derived-правками.
    """
    if settings.state_redis_url:
        return settings.state_redis_url
    parsed = urlparse(settings.redis_url)
    path = parsed.path or "/0"
    try:
        db = int(path.lstrip("/") or "0")
    except ValueError:
        db = 0
    return urlunparse(parsed._replace(path=f"/{db + 1}"))


async def get_state_redis() -> Redis:
    """Подключение к state-DB (сессии/lockout/квоты) — переживает FLUSHDB кэша."""
    global _state_redis
    if _state_redis is not None:
        return _state_redis
    async with _redis_lock:
        if _state_redis is None:
            _state_redis = Redis.from_url(_state_redis_url(), decode_responses=True)
        return _state_redis


async def close_redis():
    global _redis, _state_redis
    if _redis:
        await _redis.aclose()
        _redis = None
    if _state_redis:
        await _state_redis.aclose()
        _state_redis = None


# Н-17: fail-open кэша считаем — единичный сбой это warning, всплеск (Redis
# лежит) должен быть виден как метрика (/metrics) и error-лог каждые N сбоев.
failure_counters: dict[str, int] = {"cache_get": 0, "cache_set": 0, "cache_invalidate": 0}
_ESCALATE_EVERY = 100


def _note_cache_failure(op: str, detail: str) -> None:
    failure_counters[op] += 1
    if failure_counters[op] % _ESCALATE_EVERY == 0:
        logger.error(
            "Redis cache degraded: %s failed %d times total (%s)",
            op, failure_counters[op], detail,
        )
    else:
        logger.warning("Redis %s failed for '%s', proceeding without cache", op, detail)


async def cache_get(key: str) -> Optional[Any]:
    try:
        r = await get_redis()
        val = await r.get(key)
        if val is not None:
            return json.loads(val)
    except Exception:
        _note_cache_failure("cache_get", key)
    return None


async def cache_set(key: str, value: Any, ttl: int | None = None):
    try:
        r = await get_redis()
        ttl = ttl or settings.cache_ttl_data
        await r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        _note_cache_failure("cache_set", key)


# --- П-11: версионированные namespace вместо pattern-delete -----------------
#
# Инвалидация раньше делала 6 SCAN-проходов по всему keyspace на КАЖДЫЙ
# обновившийся индикатор — массовый derived-апдейт (сотни кодов) = тысячи SCAN.
# Теперь ключ включает версию namespace (`fe:{ns}:v{N}:{rest}`), инвалидация —
# один INCR `fe:ver:{ns}`: старые ключи мгновенно перестают читаться и
# протухают по своему TTL (на проде — allkeys-lru).
#
# Версию каждого namespace держим в per-process кэше на _VER_LOCAL_TTL секунд,
# чтобы не платить лишний Redis-GET на каждое чтение; цена — до 5 секунд
# устаревания после инвалидации из ДРУГОГО процесса (TTL данных был 300–3600с,
# это заведомо приемлемо). Свой bump сбрасывает локальную запись сразу.

_VER_LOCAL_TTL = 5.0
_ver_local: dict[str, tuple[float, str]] = {}


async def _ns_version(ns: str) -> str:
    now = time.monotonic()
    hit = _ver_local.get(ns)
    if hit and now - hit[0] < _VER_LOCAL_TTL:
        return hit[1]
    try:
        r = await get_redis()
        ver = await r.get(f"fe:ver:{ns}") or "0"
    except Exception:
        # fail-open: без Redis чтение кэша всё равно мимо, версия не важна
        ver = hit[1] if hit else "0"
    _ver_local[ns] = (now, ver)
    return ver


async def versioned_key(ns: str, rest: str) -> str:
    """Ключ кэша в инвалидируемом namespace: `fe:{ns}:v{N}:{rest}`."""
    return f"fe:{ns}:v{await _ns_version(ns)}:{rest}"


async def bump_namespaces(*namespaces: str) -> None:
    """Инвалидация namespace'ов одним pipeline INCR (без SCAN)."""
    try:
        r = await get_redis()
        async with r.pipeline(transaction=False) as pipe:
            for ns in namespaces:
                pipe.incr(f"fe:ver:{ns}")
            await pipe.execute()
    except Exception:
        _note_cache_failure("cache_invalidate", ",".join(namespaces))
    for ns in namespaces:
        _ver_local.pop(ns, None)


async def cache_invalidate_indicator(code: str):
    """После ETL/derived-апдейта: сам код (detail/data/SSR/embed живут в
    namespace кода), общий листинг и dashboard-спарклайны."""
    await bump_namespaces(code, "indicators", "dashboard")
