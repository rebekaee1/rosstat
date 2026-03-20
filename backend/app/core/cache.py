import json
import logging
from typing import Any, Optional
from redis.asyncio import Redis
from app.config import settings

logger = logging.getLogger(__name__)
_redis: Optional[Redis] = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


async def cache_get(key: str) -> Optional[Any]:
    try:
        r = await get_redis()
        val = await r.get(key)
        if val:
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
