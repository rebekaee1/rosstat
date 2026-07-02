"""Транзит OAuth-флоу в Redis (ADR-0007).

state → {provider, code_verifier, intent, next, user_id?}. TTL короткий.
Одноразовое потребление: consume_state читает и сразу удаляет ключ.
"""
import json

from app.core.cache import get_state_redis
from app.config import settings

_PREFIX = "fe:oauth:"


async def store_state(state: str, payload: dict) -> None:
    r = await get_state_redis()
    await r.set(_PREFIX + state, json.dumps(payload), ex=settings.auth_oauth_state_ttl_seconds)


async def consume_state(state: str) -> dict | None:
    if not state:
        return None
    r = await get_state_redis()
    key = _PREFIX + state
    raw = await r.get(key)
    await r.delete(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None
