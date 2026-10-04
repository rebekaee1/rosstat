"""Public federated discovery; read-only, bounded and locale-aware."""

import hashlib

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.database import get_db
from app.services.locale import get_locale
from app.services.search import federated_search
from app.services.search_intent import SEARCH_VERSION, normalize

router = APIRouter(tags=["search"])

# Visitors repeat the same short queries; a result costs 0.5–2 s of CPU. Entries
# expire quickly instead of following data publication: availability of a series
# may lag by this much, never more.
_RESULT_TTL_SECONDS = 600


def _cache_key(q: str, limit: int) -> str:
    digest = hashlib.sha1(normalize(q).encode("utf-8")).hexdigest()[:20]
    return f"fe:search:{SEARCH_VERSION}:{get_locale()}:{limit}:{digest}"


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
    result = await federated_search(db, q, limit=limit)
    await cache_set(key, result, ttl=_RESULT_TTL_SECONDS)
    return result
