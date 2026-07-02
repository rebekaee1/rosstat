import asyncio
import json
import logging
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
        await _redis.close()
        _redis = None
    if _state_redis:
        await _state_redis.close()
        _state_redis = None


async def cache_get(key: str) -> Optional[Any]:
    try:
        r = await get_redis()
        val = await r.get(key)
        if val is not None:
            return json.loads(val)
    except Exception:
        logger.warning("Redis cache_get failed for key '%s', proceeding without cache", key)
    return None


async def cache_set(key: str, value: Any, ttl: int | None = None):
    try:
        r = await get_redis()
        ttl = ttl or settings.cache_ttl_data
        await r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        logger.warning("Redis cache_set failed for key '%s', skipping", key)


async def cache_delete_pattern(pattern: str):
    try:
        r = await get_redis()
        keys = []
        async for key in r.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await r.delete(*keys)
    except Exception:
        logger.warning("Redis cache_delete_pattern failed for '%s', skipping", pattern)


async def cache_invalidate_indicator(code: str):
    await cache_delete_pattern(f"fe:{code}:*")
    await cache_delete_pattern("fe:indicators:*")
    await cache_delete_pattern(f"fe:embed:spark:{code}:*")
    await cache_delete_pattern(f"fe:embed:card:{code}:*")
    await cache_delete_pattern(f"fe:embed:badge:{code}:*")
    await cache_delete_pattern("fe:dashboard:*")
