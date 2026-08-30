"""IndexNow — мгновенное уведомление поисковиков об обновлённых URL.

Протокол: https://www.indexnow.org/ (Яндекс — участник, Bing — участник;
Google не поддерживает, но узнаёт обновления через sitemap lastmod).

Схема: после daily ETL scheduler собирает URL обновлённых индикаторов и
отправляет один batch-POST. Ключ подтверждается файлом
`frontend/public/{key}.txt` (отдаётся nginx как `https://host/{key}.txt`).

Fire-and-forget: ошибка пинга никогда не валит ETL — только warning в лог.

Языковой сплит (ADR-0013 §F): ``origin`` / ``host`` параметризованы — после
cutover можно пинговать ``ru.`` отдельно. Дефолт = ``settings.public_origin``
(текущий прод). Не вызывать второй хост, пока DNS/Caddy/ключ на нём не готовы.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# Лимит протокола IndexNow — 10 000 URL на один POST.
_BATCH_LIMIT = 10_000


async def ping_urls(
    paths: list[str],
    *,
    origin: str | None = None,
    host: str | None = None,
) -> bool:
    """Отправить batch обновлённых путей (`/russia/indicator/cpi`, …) в IndexNow.

    ``origin`` / ``host`` — для второго языкового хоста (``ru.``). По умолчанию
    берётся ``settings.public_origin`` (apex / текущий прод). Не пинговать
    ``ru.`` на прод, пока хост не живёт с TLS и key-файлом.

    Возвращает True, если все батчи приняты (HTTP 200/202). Списки длиннее
    лимита протокола (10 000 URL/запрос) разбиваются на последовательные POST.
    """
    if not settings.indexnow_enabled or not settings.indexnow_key or not paths:
        return False
    base = (origin or settings.public_origin).rstrip("/")
    if host:
        ping_host = host.split(":", 1)[0].strip().lower()
    else:
        ping_host = urlparse(base).hostname or settings.public_host
    unique_urls = [f"{base}{p}" for p in dict.fromkeys(paths)]
    ok = True
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(0, len(unique_urls), _BATCH_LIMIT):
                batch = unique_urls[i : i + _BATCH_LIMIT]
                payload = {
                    "host": ping_host,
                    "key": settings.indexnow_key,
                    "keyLocation": f"{base}/{settings.indexnow_key}.txt",
                    "urlList": batch,
                }
                response = await client.post(settings.indexnow_endpoint, json=payload)
                if response.status_code in (200, 202):
                    logger.info(
                        "IndexNow: pinged %d URL(s) host=%s (batch %d), status %d",
                        len(batch),
                        ping_host,
                        i // _BATCH_LIMIT + 1,
                        response.status_code,
                    )
                else:
                    ok = False
                    logger.warning(
                        "IndexNow: unexpected status %d for %d URL(s) host=%s: %s",
                        response.status_code,
                        len(batch),
                        ping_host,
                        response.text[:200],
                    )
        return ok
    except Exception as exc:
        logger.warning("IndexNow ping failed (host=%s): %s", ping_host, exc)
        return False


async def ping_updated_indicators(updated_codes: list[str]) -> bool:
    """Пинг после ETL: карточки обновлённых индикаторов + главная + «сегодня»."""
    if not updated_codes:
        return False
    from app.services import site_paths as paths
    from app.services.seo_today import TODAY_CODES

    url_paths = ["/"] + [paths.today()] + [
        paths.russia_indicator(code) for code in updated_codes
    ]
    url_paths += [
        paths.today(code) for code in updated_codes if code in TODAY_CODES
    ]
    ok = await ping_urls(url_paths)
    if settings.apex_locale_en:
        from app.services.locale import ru_public_origin
        ru_ok = await ping_urls(url_paths, origin=ru_public_origin())
        return ok and ru_ok
    return ok


async def ping_full_site(db, *, origin: str | None = None, host: str | None = None) -> int:
    """Полный обход: пингует ВСЕ публичные URL сайта (включая ~40k региональных).

    Используется разово после массового добавления страниц (региональный блок,
    рейтинги) и после деплоев, добавляющих новые секции. Возвращает число URL.
    ``origin``/``host`` — см. ``ping_urls`` (второй хост после cutover).
    """
    from app.services.site_urls import collect_all_paths

    paths = await collect_all_paths(db)
    if await ping_urls(paths, origin=origin, host=host):
        return len(paths)
    return 0
