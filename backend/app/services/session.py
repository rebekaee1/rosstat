"""Серверные сессии в Redis (ADR-0007).

Opaque 256-bit id в httpOnly-куке; значение (user_id, csrf) — в Redis.
Sliding TTL, индекс-Set `fe:user_sessions:{uid}` для logout-all и purge при
удалении аккаунта. На каждый успешный вход минтим НОВЫЙ id (анти-fixation).
"""
import json
import secrets
import time
from typing import Optional

from app.core.cache import get_redis
from app.config import settings

SESSION_COOKIE = "fe_sess"
CSRF_COOKIE = "XSRF-TOKEN"
CSRF_HEADER = "X-XSRF-TOKEN"
OAUTH_COOKIE = "fe_oauth"

_SESS_PREFIX = "fe:sess:"
_USER_SESSIONS_PREFIX = "fe:user_sessions:"


def _sess_key(sid: str) -> str:
    return f"{_SESS_PREFIX}{sid}"


def _user_key(user_id: str) -> str:
    return f"{_USER_SESSIONS_PREFIX}{user_id}"


async def create_session(user_id: str) -> tuple[str, str]:
    """Создать сессию, вернуть (session_id, csrf_token)."""
    sid = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    ttl = settings.auth_session_ttl_seconds
    payload = json.dumps({"user_id": str(user_id), "csrf": csrf, "created_at": int(time.time())})
    r = await get_redis()
    pipe = r.pipeline()
    pipe.set(_sess_key(sid), payload, ex=ttl)
    pipe.sadd(_user_key(user_id), sid)
    pipe.expire(_user_key(user_id), ttl)
    await pipe.execute()
    return sid, csrf


async def load_session(sid: Optional[str]) -> Optional[dict]:
    """Прочитать сессию + sliding-refresh TTL. None если нет/протухла."""
    if not sid:
        return None
    r = await get_redis()
    raw = await r.get(_sess_key(sid))
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    ttl = settings.auth_session_ttl_seconds
    pipe = r.pipeline()
    pipe.expire(_sess_key(sid), ttl)
    pipe.expire(_user_key(data["user_id"]), ttl)
    await pipe.execute()
    data["sid"] = sid
    return data


async def destroy_session(sid: Optional[str]) -> None:
    if not sid:
        return
    r = await get_redis()
    raw = await r.get(_sess_key(sid))
    user_id = None
    if raw:
        try:
            user_id = json.loads(raw).get("user_id")
        except (ValueError, TypeError):
            user_id = None
    pipe = r.pipeline()
    pipe.delete(_sess_key(sid))
    if user_id:
        pipe.srem(_user_key(user_id), sid)
    await pipe.execute()


async def destroy_user_sessions(user_id: str) -> int:
    """Убить все сессии пользователя (logout-all / удаление аккаунта)."""
    r = await get_redis()
    uid = str(user_id)
    sids = await r.smembers(_user_key(uid))
    pipe = r.pipeline()
    for sid in sids:
        pipe.delete(_sess_key(sid))
    pipe.delete(_user_key(uid))
    await pipe.execute()
    return len(sids)
