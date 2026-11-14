"""Серверный счётчик упоров в лимит скачиваний (14.11.2026).

Браузерное событие `download_limit` теряется у тех, кто отказался от аналитики или режет
скрипты блокировщиком. Сервер видит каждый отказ 403 `download_limit` сам
(`api/export.py::consume_anon_quota`). Решение (утверждено 14.11.2026): **без миграции** —
Redis state-DB, хэш на день МСК `fe:wall:YYYY-MM-DD`, поле `<формат>|<путь страницы>`,
значение — число отказов; TTL 120 дней. **Без IP, cookie, user-agent и любых идентификаторов**:
только день, нормализованный путь (без хоста, query и якоря) и формат файла.

Сбой Redis не меняет ответ пользователю: отказ 403 уходит как раньше, счёт просто теряется.
Сервер не отличает роботов от людей; браузер пишет только при работающем JS. Поэтому отчёт
показывает обе цифры рядом, а не одну «правильную».
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from urllib.parse import urlsplit

from app.services.analytics_period import Period

logger = logging.getLogger(__name__)

KEY_PREFIX = "fe:wall:"
TTL_SECONDS = 120 * 24 * 3600
MAX_PATH = 200
FORMATS = frozenset({"csv", "xlsx"})


def normalize_path(raw: str | None) -> str:
    """Путь страницы без хоста, query, якоря и хвостового «/»; не путь → «unknown»."""
    if not raw:
        return "unknown"
    try:
        path = urlsplit(str(raw)).path or ""
    except ValueError:
        return "unknown"
    if not path.startswith("/") or path.startswith("//"):
        return "unknown"
    path = "/" + "/".join(p for p in path.split("/") if p)
    return path[:MAX_PATH]


def field_for(fmt: str | None, page: str | None) -> str:
    f = (fmt or "").lower()
    return f"{f if f in FORMATS else 'other'}|{normalize_path(page)}"


def key_for(day: date) -> str:
    return f"{KEY_PREFIX}{day.isoformat()}"


async def record_wall(fmt: str | None, page: str | None, day: date | None = None) -> None:
    """+1 отказ за день. Никогда не бросает исключений."""
    try:
        from app.core.cache import get_state_redis
        from app.services.display import today_msk

        r = await get_state_redis()
        key = key_for(day or today_msk())
        pipe = r.pipeline(transaction=False)
        pipe.hincrby(key, field_for(fmt, page), 1)
        pipe.expire(key, TTL_SECONDS)
        await pipe.execute()
    except Exception:  # noqa: BLE001 — счёт не важнее ответа пользователю
        logger.warning("wall counter: Redis write failed", exc_info=True)


async def read_walls(period: Period) -> dict[str, int] | None:
    """`{«формат|путь»: число}` за дни периода; None, если Redis не ответил (≠ ноль)."""
    try:
        from app.core.cache import get_state_redis

        r = await get_state_redis()
        out: dict[str, int] = {}
        day = period.start_date
        while day <= period.end_date:
            for field, value in (await r.hgetall(key_for(day))).items():
                out[field] = out.get(field, 0) + int(value)
            day += timedelta(days=1)
        return out
    except Exception:  # noqa: BLE001
        logger.warning("wall counter: Redis read failed", exc_info=True)
        return None
