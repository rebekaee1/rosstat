"""Анти-брутфорс lockout по (идентификатор, ip) в Redis (ADR-0007).

Ответ при блокировке — 423 Locked (НЕ 429): фронтовый axios-интерсептор
ретраит 429/503, что повторно зашлёт креды. 423 он не ретраит.
"""
from app.core.cache import get_redis
from app.config import settings

_PREFIX = "fe:login_fail:"


def _key(scope: str, ident: str, ip: str) -> str:
    return f"{_PREFIX}{scope}:{ident}|{ip}"


async def is_locked(scope: str, ident: str, ip: str) -> bool:
    try:
        r = await get_redis()
        val = await r.get(_key(scope, ident, ip))
        return val is not None and int(val) >= settings.auth_login_max_fails
    except Exception:
        return False  # fail-open: недоступность Redis не должна запирать вход


async def record_failure(scope: str, ident: str, ip: str) -> None:
    try:
        r = await get_redis()
        k = _key(scope, ident, ip)
        n = await r.incr(k)
        if n == 1:
            await r.expire(k, settings.auth_login_lockout_seconds)
    except Exception:
        pass


async def reset(scope: str, ident: str, ip: str) -> None:
    try:
        r = await get_redis()
        await r.delete(_key(scope, ident, ip))
    except Exception:
        pass
