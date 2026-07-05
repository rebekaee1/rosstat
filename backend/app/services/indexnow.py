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


# Лимит протокола IndexNow — 10 000 URL на один POST.
_BATCH_LIMIT = 10_000


async def ping_urls(paths: list[str]) -> bool:
    """Отправить batch обновлённых путей (`/indicator/cpi`, …) в IndexNow.

    Возвращает True, если все батчи приняты (HTTP 200/202). Списки длиннее
    лимита протокола (10 000 URL/запрос) разбиваются на последовательные POST.
    """
    if not settings.indexnow_enabled or not settings.indexnow_key or not paths:
        return False
    unique_urls = [f"{DOMAIN}{p}" for p in dict.fromkeys(paths)]
    ok = True
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(0, len(unique_urls), _BATCH_LIMIT):
                batch = unique_urls[i:i + _BATCH_LIMIT]
                payload = {
                    "host": _HOST,
                    "key": settings.indexnow_key,
                    "keyLocation": f"{DOMAIN}/{settings.indexnow_key}.txt",
                    "urlList": batch,
                }
                response = await client.post(settings.indexnow_endpoint, json=payload)
                if response.status_code in (200, 202):
                    logger.info(
                        "IndexNow: pinged %d URL(s) (batch %d), status %d",
                        len(batch), i // _BATCH_LIMIT + 1, response.status_code,
                    )
                else:
                    ok = False
                    logger.warning(
                        "IndexNow: unexpected status %d for %d URL(s): %s",
                        response.status_code, len(batch), response.text[:200],
                    )
        return ok
    except Exception as exc:
        logger.warning("IndexNow ping failed: %s", exc)
        return False


async def ping_updated_indicators(updated_codes: list[str]) -> bool:
    """Пинг после ETL: карточки обновлённых индикаторов + главная + «сегодня»."""
    if not updated_codes:
        return False
    from app.services.seo_today import TODAY_CODES

    paths = ["/", "/today"] + [f"/indicator/{code}" for code in updated_codes]
    paths += [f"/today/{code}" for code in updated_codes if code in TODAY_CODES]
    return await ping_urls(paths)


async def ping_full_site(db) -> int:
    """Полный обход: пингует ВСЕ публичные URL сайта (включая ~40k региональных).

    Используется разово после массового добавления страниц (региональный блок,
    рейтинги) и после деплоев, добавляющих новые секции. Возвращает число URL.
    """
    from app.services.site_urls import collect_all_paths

    paths = await collect_all_paths(db)
    if await ping_urls(paths):
        return len(paths)
    return 0
