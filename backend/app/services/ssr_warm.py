"""Прогрев кэша SSR-страниц и API первого экрана (круг 12, зона SPEED).

Замер 12.10.2026 (боевой, публичные GET): страница из кэша Redis отдаётся за 0,15–0,2 с, а первый запрос после истечения TTL
(главная 300 с, показатели 900 с) стоит 1,1–1,6 с, страница страны 6–10 с, /api/v1/indicators 6 с. При небольшом потоке
посетителей TTL истекает между визитами, и «первым после истечения» оказывается заметная доля людей — это и есть большая часть
времени до первого экрана на телефоне (TTFB входит в FCP, Speed Index и TTI).

Задача планировщика ходит по тем же адресам, что браузер, через frontend (nginx → backend): код рендера и ключи кэша те же,
отдельной копии рендера нет. Интервал короче TTL главной, поэтому ключ обновляется почти сразу после истечения.
Выключено по умолчанию (`ssr_warm_enabled`), включается после выкладки одним флагом.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Хост задаёт язык (apex — en, ru. — ru): прогреваем оба.
WARM_HOSTS = ("forecasteconomy.com", "ru.forecasteconomy.com")
# Первый экран и то, что он запрашивает сразу после загрузки приложения.
WARM_PATHS = (
    "/",
    "/russia",
    "/russia/indicator/cpi",
    "/compare",
    "/world/rating",
    "/api/v1/indicators",
    "/api/v1/world/rating/concepts",
    "/api/v1/world/compare/snapshot/gdp-usd",
    "/api/v1/world/compare/map-series/gdp-usd",
)
WARM_USER_AGENT = "ForecastEconomy-ssr-warm/1"


async def warm_ssr_cache() -> dict[str, int]:
    """Один проход: GET каждого адреса для каждого хоста, по одному, чтобы не нагружать 4 vCPU."""
    base = settings.ssr_warm_base_url.rstrip("/")
    ok = 0
    failed = 0
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        for host in WARM_HOSTS:
            for path in WARM_PATHS:
                try:
                    response = await client.get(
                        f"{base}{path}",
                        headers={
                            "Host": host,
                            "X-Forwarded-Host": host,
                            "User-Agent": WARM_USER_AGENT,
                            "Accept-Encoding": "identity",
                        },
                    )
                    if response.status_code == 200:
                        ok += 1
                    else:
                        failed += 1
                        logger.warning("ssr warm %s%s -> %s", host, path, response.status_code)
                except Exception as exc:  # noqa: BLE001 — прогрев не должен ронять планировщик
                    failed += 1
                    logger.warning("ssr warm %s%s failed: %s", host, path, exc)
                await asyncio.sleep(0.2)
    return {"ok": ok, "failed": failed}


async def ssr_warm_job() -> None:
    """Задача планировщика: no-op, пока флаг выключен."""
    if not settings.ssr_warm_enabled:
        return
    result = await warm_ssr_cache()
    if result["failed"]:
        logger.warning("SSR warm-up: %s", result)
    else:
        logger.debug("SSR warm-up: %s", result)
