"""Public federated discovery; read-only, bounded and locale-aware."""

import asyncio
import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.database import get_db
from app.services.locale import get_locale
from app.services.search import federated_search
from app.services.search_latest import attach_latest
from app.services.search_intent import SEARCH_VERSION, normalize

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])

# Visitors repeat the same short queries; a result costs 0.5–2 s of CPU. Entries
# expire quickly instead of following data publication: availability of a series
# may lag by this much, never more.
_RESULT_TTL_SECONDS = 600

# Последний удачный ответ на тот же запрос. 11–12.11.2026 поиск шесть раз давал всплеск 5xx: база стояла на чтении
# с диска, и каждый запрос, даже повторный («врп», «инфляция»), упирался в statement_timeout и отвечал 500.
# Теперь при отказе базы повторный запрос получает вчерашний ответ, а новый — честное 503 «повторите» вместо 500.
# Срок сутки: состав каталога меняется реже, а устаревший ответ отдаётся только вместо ошибки.
_LAST_GOOD_TTL_SECONDS = 24 * 3600
_RETRY_AFTER_SECONDS = 15
# Отказ базы или её ожидания. Ошибка в самом поиске сюда не входит и остаётся 500: её нельзя прятать.
_DATABASE_FAILURES = (DBAPIError, asyncio.TimeoutError, OSError)


# Ревизия кэша меняется, когда меняется порядок или состав выдачи при том же публичном
# `version` ответа (клиент сверяет `version`, поэтому его не трогаем): без этого после выкладки
# 10 минут отдавались бы ответы прежнего ранжирования. 2026-10-08: страна первой, курс лиры,
# годовая инфляция выше индекса, значение и график у 24 строк.
# r3 (08.10, круг 10): ряды страны выше рядов её штатов при запросе «ВВП США»; разговорные слова («что такое»).
# r4 (08.11, Z4): региональные показатели свёрнуты в строку «Россия» со списком регионов; товары средних цен.
_CACHE_REVISION = "r5"


def _cache_key(q: str, limit: int) -> str:
    digest = hashlib.sha1(normalize(q).encode("utf-8")).hexdigest()[:20]
    return f"fe:search:{SEARCH_VERSION}:{_CACHE_REVISION}:{get_locale()}:{limit}:{digest}"


def _last_good_key(key: str) -> str:
    return f"{key}:last"


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=256),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Countries, indicators and data-backed regional destinations."""
    key = _cache_key(q, limit)
    cached = await cache_get(key)
    if cached is not None:
        return cached
    try:
        result = await federated_search(db, q, limit=limit)
    except _DATABASE_FAILURES as exc:
        last_good = await cache_get(_last_good_key(key))
        if last_good is not None:
            logger.warning("search: database failed (%s), served the last good answer", type(exc).__name__)
            return last_good
        logger.warning("search: database failed (%s), no earlier answer for this query", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Search is temporarily unavailable",
            headers={"Retry-After": str(_RETRY_AFTER_SECONDS)},
        ) from exc
    try:
        # Latest value and a short trend for the first rows; presentation only, never reorders.
        await attach_latest(db, result.get("results") or [])
    except Exception:
        logger.warning("search latest-value enrichment skipped", exc_info=True)
    await cache_set(key, result, ttl=_RESULT_TTL_SECONDS)
    await cache_set(_last_good_key(key), result, ttl=_LAST_GOOD_TTL_SECONDS)
    return result
