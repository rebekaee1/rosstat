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


async def _store_payload(key: str, payload: dict) -> None:
    # Пустую витрину кэшируем коротко: данные могут появиться после загрузки.
    await cache_set(key, payload, CACHE_TTL_SECONDS if payload["items"] else 120)


async def showcase_payload(db: AsyncSession, locale: str | None = None) -> dict:
    """Витрина из Redis или сборка с нуля (используют API и серверный рендер)."""
    loc = locale or get_locale()
    key = await versioned_key("world", f"{CACHE_KEY_REST}:{loc}")
    cached = await cache_get(key)
    if isinstance(cached, dict) and cached.get("items") is not None:
        return cached
    payload = await build_showcase(db, loc)
    await _store_payload(key, payload)
    return payload


# Прогрев: холодная сборка витрины дорогая (на загруженной машине дольше 25 с),
# а первый посетитель после истечения ключа (30 минут) или после загрузки данных
# (смена версии `world`) ждал её сам и видел «Загружаем данные…». Прогрев
# запускается при старте и по расписанию чаще срока жизни ключа.
WARM_LOCALES: tuple[str, ...] = ("ru", "en")


async def warm_showcase_cache(*, force: bool = False) -> dict[str, int]:
    """Собрать витрину обоих языков заранее. Возвращает {язык: число карточек}.

    `force=False` ничего не пересобирает, если ключ текущей версии уже лежит в
    кэше (старт процесса); по расписанию вызывается с `force=True`, чтобы ключ
    не успевал истечь. Ошибка одного языка не мешает другому."""
    from app.database import async_session
    from app.services.locale import reset_locale, set_locale

    warmed: dict[str, int] = {}
    for loc in WARM_LOCALES:
        token = set_locale(loc)
        try:
            key = await versioned_key("world", f"{CACHE_KEY_REST}:{loc}")
            if not force:
                cached = await cache_get(key)
                if isinstance(cached, dict) and cached.get("items") is not None:
                    warmed[loc] = len(cached["items"])
                    continue
            async with async_session() as db:
                payload = await build_showcase(db, loc)
            await _store_payload(key, payload)
            warmed[loc] = len(payload["items"])
        except Exception:
            logger.warning("forecast showcase warm-up failed (%s)", loc, exc_info=True)
        finally:
            reset_locale(token)
    return warmed


async def forecast_showcase_warm_job() -> None:
    """Задача планировщика: держит витрину прогнозов в кэше горячей."""
    warmed = await warm_showcase_cache(force=True)
    logger.info("Forecast showcase warm-up: %s", warmed)


@router.get("/showcase")
async def get_forecast_showcase(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    payload = await showcase_payload(db)
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": _CACHE_CONTROL, "Vary": "Host"},
    )
