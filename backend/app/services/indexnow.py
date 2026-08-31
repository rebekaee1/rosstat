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

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# Лимит протокола IndexNow — 10 000 URL на один POST.
# Рабочий батч очереди меньше: 500–1000, чтобы 429 не сжигал весь реестр.
_BATCH_LIMIT = 10_000
_QUEUE_BATCH = 800
_DEBOUNCE_TTL = 24 * 3600
_QUEUE_PREFIX = "in:queue:"
_DEBOUNCE_PREFIX = "in:sent:"


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
                elif response.status_code == 429:
                    retry_after = (getattr(response, "headers", None) or {}).get("Retry-After", "")
                    ok = False
                    logger.warning(
                        "IndexNow: 429 host=%s Retry-After=%s batch=%d",
                        ping_host, retry_after, i // _BATCH_LIMIT + 1,
                    )
                    # Вежливая пауза перед следующим батчем/drain: делим
                    # Remaining на 2 (не ждём дольше минуты — хвост дозальёт
                    # следующий drain через 10 минут).
                    try:
                        delay = min(int(float(retry_after)), 60)
                    except (TypeError, ValueError):
                        delay = 30
                    await asyncio.sleep(max(delay, 5))
                    break
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
    from app.services.display import today_msk
    from app.services.seo_today import TODAY_CODES

    year = today_msk().year
    url_paths = ["/"] + [paths.today()] + [
        paths.russia_indicator(code) for code in updated_codes
    ]
    url_paths += [
        paths.russia_indicator_year(code, year) for code in updated_codes
    ]
    url_paths += [
        paths.russia_indicator_year(code, year - 1) for code in updated_codes
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
    """Приоритетные секции (хабы/карточки), не слепой проход всех 2M URL.

    Длинный хвост (годовые региональные/мировые) обходит очередь переобхода
    Вебмастера, не IndexNow. ``origin``/``host`` — второй хост после cutover.
    """
    return await ping_sections(db, origin=origin, host=host)


async def ping_sections(db, *, origin: str | None = None, host: str | None = None) -> int:
    """Стриминг простых секций ``site_urls.section_names_static`` в очередь IndexNow."""
    from app.services.site_urls import resolve_section, section_names_static

    total = 0
    for name in section_names_static():
        urls = await resolve_section(db, name)
        if not urls:
            continue
        paths = [
            (u.path if hasattr(u, "path") else u.get("loc") or u.get("path"))
            for u in urls
        ]
        paths = [p for p in paths if p]
        total += await enqueue_paths(paths, origin=origin, host=host)
    return total


def _ping_host(origin: str | None, host: str | None) -> str:
    from urllib.parse import urlparse

    base = (origin or settings.public_origin).rstrip("/")
    if host:
        return host.split(":", 1)[0].strip().lower()
    return urlparse(base).hostname or settings.public_host


async def enqueue_paths(
    paths: list[str],
    *,
    origin: str | None = None,
    host: str | None = None,
) -> int:
    """Положить пути в Redis-очередь (дедуп, debounce 24ч на drain)."""
    if not settings.indexnow_enabled or not settings.indexnow_key or not paths:
        return 0
    from app.core.cache import get_state_redis

    ping_host = _ping_host(origin, host)
    redis = await get_state_redis()
    unique = list(dict.fromkeys(paths))
    await redis.sadd(f"{_QUEUE_PREFIX}{ping_host}", *unique)
    return len(unique)


async def drain_indexnow_queue(*, limit: int = _QUEUE_BATCH) -> int:
    """Снять батч из очереди каждого известного хоста и пингануть."""
    from app.core.cache import get_state_redis
    from app.services.locale import ru_public_origin

    redis = await get_state_redis()
    hosts = [settings.public_host]
    origins = {settings.public_host: settings.public_origin}
    if settings.apex_locale_en:
        ru_host = "ru.forecasteconomy.com"
        hosts.append(ru_host)
        origins[ru_host] = ru_public_origin()
    sent = 0
    for ping_host in hosts:
        queue_key = f"{_QUEUE_PREFIX}{ping_host}"
        batch = await redis.spop(queue_key, limit)
        if not batch:
            continue
        if isinstance(batch, (bytes, str)):
            batch = [batch]
        fresh: list[str] = []
        for path in batch:
            path = path.decode() if isinstance(path, bytes) else path
            if await redis.exists(f"{_DEBOUNCE_PREFIX}{ping_host}:{path}"):
                continue
            fresh.append(path)
        if not fresh:
            continue
        ok = await ping_urls(fresh, origin=origins.get(ping_host), host=ping_host)
        if ok:
            pipe = redis.pipeline()
            for path in fresh:
                pipe.set(
                    f"{_DEBOUNCE_PREFIX}{ping_host}:{path}",
                    "1",
                    ex=_DEBOUNCE_TTL,
                )
            await pipe.execute()
            sent += len(fresh)
        else:
            await redis.sadd(queue_key, *fresh)
    return sent


async def indexnow_drain_job() -> None:
    n = await drain_indexnow_queue()
    if n:
        logger.info("IndexNow drain: pinged %d URL(s)", n)


async def indexnow_warm_job() -> None:
    """Еженедельная warm-подпитка очереди (dual-host план, Фаза B/C).

    Кладёт в очередь IndexNow: (1) статические секции-хабы (core/today/
    ratings/regions/world — без years-чанков), (2) demand-URL из
    webmaster_search_queries (потерянные показы). Debounce 24ч на URL
    отсекает уже отправленное; drain */10 мин раздаёт батчи по хостам.
    """
    from app.core.cache import get_state_redis
    from app.services.demand_router import priority_recrawl_paths
    from app.services.locale import ru_public_origin

    if not settings.indexnow_enabled or not settings.indexnow_key:
        return
    redis = await get_state_redis()
    lock = await redis.set("in:warm:lock", "1", nx=True, ex=6 * 3600)
    if not lock:
        return  # другой воркер уже греет

    try:
        from app.database import async_session

        async with async_session() as db:
            hosts = [(None, None)]  # дефолт apex
            if settings.apex_locale_en:
                hosts.append((
                    ru_public_origin(),
                    "ru.forecasteconomy.com",
                ))
            for origin, host in hosts:
                await ping_sections(db, origin=origin, host=host)
                demand_paths = [
                    path for path, _lost in await priority_recrawl_paths(
                        db, days=30, limit=150
                    )
                ]
                if demand_paths:
                    await enqueue_paths(demand_paths, origin=origin, host=host)
        logger.info("IndexNow warm: hubs + demand-URL queued")
    finally:
        await redis.delete("in:warm:lock")
