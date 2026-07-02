"""Серверный лимит гостевых скачиваний (ADR-0007 Phase 2).

Данные публичны (любой может дёрнуть API), поэтому это не security-граница, а
жёсткий конверсионный гейт: гость получает N выгрузок на «сессию скачиваний»
(opaque cookie fe_dl + счётчик в Redis с TTL), дальше — приглашение войти.
Авторизованные (валидная сессия) — безлимит, счётчик не трогаем.
"""
import secrets

from app.config import settings
from app.core.cache import get_state_redis

DL_COOKIE = "fe_dl"
_PREFIX = "fe:dl:"


def new_download_id() -> str:
    return secrets.token_urlsafe(16)


async def consume_anon_download(dl_id: str) -> bool:
    """INCR счётчик гостевых скачиваний. True — в пределах лимита, False — превышен."""
    r = await get_state_redis()
    key = f"{_PREFIX}{dl_id}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, settings.download_anon_window_seconds)
    return count <= settings.download_anon_limit


async def remaining_anon_downloads(dl_id: str | None) -> int:
    """Сколько выгрузок ещё доступно гостю (для подсказок UI). Без инкремента."""
    limit = settings.download_anon_limit
    if not dl_id:
        return limit
    r = await get_state_redis()
    raw = await r.get(f"{_PREFIX}{dl_id}")
    used = int(raw) if raw else 0
    return max(0, limit - used)
