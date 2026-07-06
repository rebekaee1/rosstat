"""Анти-брутфорс lockout по (идентификатор, ip) в Redis (ADR-0007).

Ответ при блокировке — 423 Locked (НЕ 429): фронтовый axios-интерсептор
ретраит 429/503, что повторно зашлёт креды. 423 он не ретраит.

Политика при недоступности state-Redis — fail-open (осознанно, Н-11):
fail-closed запер бы ВЕСЬ вход при любом сбое Redis, что хуже временного
отключения анти-брутфорса. Но деградация не должна быть немой: каждый отказ
логируется error'ом с маркером, state-Redis виден в readiness (`/health/ready`),
всплеск ловится по логам/5xx-мониторингу.
"""
import logging
import time

from app.core.cache import get_state_redis
from app.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "fe:login_fail:"
# Троттлинг однотипных error-логов при лежащем Redis (не заливать лог).
_LOG_EVERY_SECONDS = 60
_last_log_ts = 0.0


def _log_fail_open(op: str) -> None:
    global _last_log_ts
    now = time.monotonic()
    if now - _last_log_ts >= _LOG_EVERY_SECONDS:
        _last_log_ts = now
        logger.error(
            "LOCKOUT FAIL-OPEN: state-Redis unavailable (%s) — brute-force "
            "protection disabled until Redis recovers", op, exc_info=True,
        )


def _key(scope: str, ident: str, ip: str) -> str:
    return f"{_PREFIX}{scope}:{ident}|{ip}"


async def is_locked(scope: str, ident: str, ip: str) -> bool:
    try:
        r = await get_state_redis()
        val = await r.get(_key(scope, ident, ip))
        return val is not None and int(val) >= settings.auth_login_max_fails
    except Exception:
        _log_fail_open("is_locked")
        return False  # fail-open: недоступность Redis не должна запирать вход


async def record_failure(scope: str, ident: str, ip: str) -> None:
    try:
        r = await get_state_redis()
        k = _key(scope, ident, ip)
        n = await r.incr(k)
        if n == 1:
            await r.expire(k, settings.auth_login_lockout_seconds)
    except Exception:
        _log_fail_open("record_failure")


async def reset(scope: str, ident: str, ip: str) -> None:
    try:
        r = await get_state_redis()
        await r.delete(_key(scope, ident, ip))
    except Exception:
        _log_fail_open("reset")
