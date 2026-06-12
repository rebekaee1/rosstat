"""IndexNow — мгновенное уведомление поисковиков об обновлённых URL.

Протокол: https://www.indexnow.org/ (Яндекс — участник, Bing — участник;
Google не поддерживает, но узнаёт обновления через sitemap lastmod).

Схема: после daily ETL scheduler собирает URL обновлённых индикаторов и
отправляет один batch-POST. Ключ подтверждается файлом
`frontend/public/{key}.txt` (отдаётся nginx как `https://host/{key}.txt`).

Fire-and-forget: ошибка пинга никогда не валит ETL — только warning в лог.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.services.seo_content import DOMAIN

logger = logging.getLogger(__name__)

_HOST = DOMAIN.removeprefix("https://").removeprefix("http://")


async def ping_urls(paths: list[str]) -> bool:
    """Отправить batch обновлённых путей (`/indicator/cpi`, …) в IndexNow.

    Возвращает True при HTTP 200/202. Лимит протокола — 10 000 URL за запрос;
    у нас порядка сотни, не разбиваем.
    """
    if not settings.indexnow_enabled or not settings.indexnow_key or not paths:
        return False
    payload = {
        "host": _HOST,
        "key": settings.indexnow_key,
        "keyLocation": f"{DOMAIN}/{settings.indexnow_key}.txt",
        "urlList": [f"{DOMAIN}{p}" for p in dict.fromkeys(paths)],
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(settings.indexnow_endpoint, json=payload)
        if response.status_code in (200, 202):
            logger.info("IndexNow: pinged %d URL(s), status %d", len(payload["urlList"]), response.status_code)
            return True
        logger.warning(
            "IndexNow: unexpected status %d for %d URL(s): %s",
            response.status_code, len(payload["urlList"]), response.text[:200],
        )
        return False
    except Exception as exc:
        logger.warning("IndexNow ping failed: %s", exc)
        return False


async def ping_updated_indicators(updated_codes: list[str]) -> bool:
    """Пинг после ETL: карточки обновлённых индикаторов + главная."""
    if not updated_codes:
        return False
    paths = ["/"] + [f"/indicator/{code}" for code in updated_codes]
    return await ping_urls(paths)
