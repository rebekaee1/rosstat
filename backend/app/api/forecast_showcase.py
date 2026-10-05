"""Публичный список прогнозов платформы: `GET /api/v1/forecasts/showcase`.

Витрина страницы «Прогнозы». Отдаёт только ряды, у которых платформа сама
строит прогноз на год вперёд (Россия и мировые ряды, прошедшие проверку на
прошлых данных). Собственных проекций МВФ в базе нет, и здесь их нет.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, versioned_key
from app.database import get_db
from app.services.forecast_showcase import (
    CACHE_KEY_REST,
    CACHE_TTL_SECONDS,
    build_showcase,
)
from app.services.locale import get_locale

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forecasts", tags=["forecasts"])

# Язык берётся из хоста, поэтому ответ зависит от Host.
_CACHE_CONTROL = "public, max-age=60, s-maxage=300, stale-while-revalidate=600"


async def showcase_payload(db: AsyncSession, locale: str | None = None) -> dict:
    """Витрина из Redis или сборка с нуля (используют API и серверный рендер)."""
    loc = locale or get_locale()
    key = await versioned_key("world", f"{CACHE_KEY_REST}:{loc}")
    cached = await cache_get(key)
    if isinstance(cached, dict) and cached.get("items") is not None:
        return cached
    payload = await build_showcase(db, loc)
    # Пустую витрину кэшируем коротко: данные могут появиться после загрузки.
    await cache_set(key, payload, CACHE_TTL_SECONDS if payload["items"] else 120)
    return payload


@router.get("/showcase")
async def get_forecast_showcase(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    payload = await showcase_payload(db)
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": _CACHE_CONTROL, "Vary": "Host"},
    )
