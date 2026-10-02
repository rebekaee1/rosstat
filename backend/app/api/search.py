"""Public federated discovery; read-only, bounded and locale-aware."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.search import federated_search

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=256),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Countries, indicators and data-backed regional destinations."""
    return await federated_search(db, q, limit=limit)
