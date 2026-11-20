"""Раздел «Туризм»: `GET /api/v1/tourism/overview` — регионы и страны мира для страницы раздела.

Российские ряды страница берёт обычным списком категории (`/indicators?category=Туризм`); здесь —
этажи «Регионы России» и «Мир». Сборка и кэш — app/services/tourism_showcase.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.tourism_showcase import tourism_overview

router = APIRouter(prefix="/tourism", tags=["tourism"])


@router.get("/overview")
async def tourism_overview_endpoint(db: AsyncSession = Depends(get_db)):
    return await tourism_overview(db)
