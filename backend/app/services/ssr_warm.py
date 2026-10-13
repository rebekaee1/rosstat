"""Прогрев кэша SSR-страниц и API первого экрана (круг 12, зона SPEED).

Замер 12.10.2026 (боевой, публичные GET): страница из кэша Redis отдаётся за 0,15–0,2 с, а первый запрос после истечения TTL
(главная 300 с, показатели 900 с) стоит 1,1–1,6 с, страница страны 6–10 с, /api/v1/indicators 6 с. При небольшом потоке
посетителей TTL истекает между визитами, и «первым после истечения» оказывается заметная доля людей — это и есть большая часть
времени до первого экрана на телефоне (TTFB входит в FCP, Speed Index и TTI).

Задача планировщика ходит по тем же адресам, что браузер, через frontend (nginx → backend): код рендера и ключи кэша те же,
отдельной копии рендера нет. Интервал короче TTL главной, поэтому ключ обновляется почти сразу после истечения.
Выключено по умолчанию (`ssr_warm_enabled`), включается после выкладки одним флагом.

Круг 12, SPEED2: помимо первого экрана прогреваются самые посещаемые страницы (топ `ssr_warm_top_n` по `daily_pages`
за 14 дней; обе языковые версии и API страны) — раз в ~9 минут и сразу после запуска планировщика. Вместе с
stale-while-revalidate (`ssr_swr`) запрос прогрева по устаревшей записи сам запускает её фоновый пересчёт. Вручную после
выкладки: `python -m app.services.ssr_warm` (выполняет проход «первый экран + топ», учитывая флаг).
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from urllib.parse import urlsplit

import httpx
from sqlalchemy import text

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
    # Канон рейтинга — страница показателя по умолчанию: `/world/rating` отвечает 301 на неё (backend, WORLD_RATING_DEFAULT_CONCEPT),
    # и прогрев каждые 45 с тратил два запроса впустую (журнал боевого 12.10.2026: «ssr warm …/world/rating -> 301»).
    # Совпадение с редиректом backend держит тест test_ssr_warm.
    "/world/rating/gdp-usd",
    "/api/v1/indicators",
    "/api/v1/world/rating/concepts",
    "/api/v1/world/compare/snapshot/gdp-usd",
    "/api/v1/world/compare/map-series/gdp-usd",
)
WARM_USER_AGENT = "ForecastEconomy-ssr-warm/1"


# Ключ Redis со списком топ-страниц: пересчёт раз в 6 часов, не на каждый проход.
_TOP_CACHE_KEY = "fe:warm:top:v1"
_TOP_CACHE_TTL = 6 * 3600
_TOP_EVERY_RUNS = 12  # ≈ раз в 9 минут при интервале 45 с
_PATH_RE = re.compile(r"^/[A-Za-z0-9._~/%-]{0,120}$")
# Служебные и личные адреса не прогреваем (не SSR-страницы или не публичны).
_SKIP_PREFIXES = ("/api", "/og", "/login", "/register", "/cabinet", "/admin", "/account", "/auth", "/embed", "/static")
_RUN_BUDGET_SECONDS = 240.0
_runs = 0
_REDIRECT_STATUSES = (301, 302, 307, 308)
# (хост, адрес из аналитики) -> канонический адрес после одного редиректа того же хоста: следующие проходы идут сразу на него.
_known_redirects: dict[tuple[str, str], str] = {}


def _normalise_top_path(page: str) -> str:
    """Адрес из аналитики без хвостового слэша (`/path/` у nginx — редирект на `/path`)."""
    page = (page or "").strip()
    if len(page) > 1:
        page = page.rstrip("/") or "/"
    return page


def _same_host_target(location: str | None, host: str) -> str | None:
    """Путь, на который ведёт редирект того же хоста (без query), иначе None."""
    if not location:
        return None
    parts = urlsplit(location)
    if parts.netloc and parts.netloc.lower() != host.lower():
        return None
    if parts.query or not _PATH_RE.match(parts.path or ""):
        return None
    return parts.path


async def top_paths(limit: int) -> list[str]:
    """Самые посещаемые адреса по `daily_pages` за 14 дней (кэш на 6 часов), без уже прогреваемых первого экрана."""
    if limit <= 0:
        return []
    import json

    from app.core.cache import get_redis
    from app.database import async_session

    try:
        redis = await get_redis()
        cached = await redis.get(_TOP_CACHE_KEY)
        if cached:
            return list(json.loads(cached))[:limit]
    except Exception:  # noqa: BLE001
        redis = None
    try:
        async with async_session() as db:
            rows = (
                await db.execute(
                    text(
                        "SELECT page, SUM(views) AS v FROM daily_pages "
                        "WHERE day >= (SELECT MAX(day) FROM daily_pages) - 13 "
                        "GROUP BY page ORDER BY v DESC LIMIT :n"
                    ),
                    {"n": max(limit * 3, 60)},
                )
            ).all()
    except Exception as exc:  # noqa: BLE001 — нет таблицы/базы: прогреваем только первый экран
        logger.warning("ssr warm top paths unavailable: %s", exc)
        return []
    first_screen = set(WARM_PATHS)
    paths: list[str] = []
    for page, _views in rows:
        page = _normalise_top_path(page)
        if (
            not page
            or page in first_screen
            or page in paths
            or page == "/"
            or not _PATH_RE.match(page)
            or page.startswith(_SKIP_PREFIXES)
        ):
            continue
        paths.append(page)
        if len(paths) >= limit:
            break
    if redis is not None and paths:
        try:
            await redis.set(_TOP_CACHE_KEY, json.dumps(paths), ex=_TOP_CACHE_TTL)
        except Exception:  # noqa: BLE001
            pass
    return paths


async def country_slugs() -> set[str]:
    from app.database import async_session

    try:
        async with async_session() as db:
            rows = (await db.execute(text("SELECT slug FROM world_countries WHERE is_active IS TRUE"))).all()
        return {r[0] for r in rows}
    except Exception:  # noqa: BLE001
        return set()


async def _get(client: httpx.AsyncClient, host: str, path: str, *, strict: bool, _followed: bool = False) -> bool:
    base = settings.ssr_warm_base_url.rstrip("/")
    path = _known_redirects.get((host, path), path) if not strict else path
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
            return True
        # Адреса из аналитики могут быть неканоническими: один редирект того же хоста прогреваем по месту назначения
        # (и запоминаем), чтобы запрос не пропал впустую. Первый экран редиректов не имеет — там это ошибка списка.
        if not strict and not _followed and response.status_code in _REDIRECT_STATUSES:
            target = _same_host_target(response.headers.get("location"), host)
            if target and target != path:
                _known_redirects[(host, path)] = target
                return await _get(client, host, target, strict=False, _followed=True)
        # Первый экран обязан отвечать 200; адреса из аналитики (мусорные, редиректы) — нет.
        if strict:
            logger.warning("ssr warm %s%s -> %s", host, path, response.status_code)
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — прогрев не должен ронять планировщик
        logger.warning("ssr warm %s%s failed: %s", host, path, exc)
        return False


async def warm_ssr_cache(*, include_top: bool = False) -> dict[str, int]:
    """Один проход: GET каждого адреса для каждого хоста, по одному, чтобы не нагружать 4 vCPU.

    ``include_top`` добавляет топ-страницы из аналитики и API их стран (бюджет прохода — 4 минуты).
    """
    ok = 0
    failed = 0
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        for host in WARM_HOSTS:
            for path in WARM_PATHS:
                if await _get(client, host, path, strict=True):
                    ok += 1
                else:
                    failed += 1
                await asyncio.sleep(0.2)
        if include_top and settings.ssr_warm_top_n > 0:
            tops = await top_paths(settings.ssr_warm_top_n)
            slugs = await country_slugs() if tops else set()
            for path in tops:
                targets = [path]
                head = path.strip("/")
                if head in slugs:
                    targets.append(f"/api/v1/world/countries/{head}")
                for host in WARM_HOSTS:
                    for target in targets:
                        if time.monotonic() - started > _RUN_BUDGET_SECONDS:
                            logger.info("ssr warm: top-страницы прерваны по бюджету времени")
                            return {"ok": ok, "failed": failed}
                        if await _get(client, host, target, strict=False):
                            ok += 1
                        else:
                            failed += 1
                        await asyncio.sleep(0.2)
    return {"ok": ok, "failed": failed}


async def ssr_warm_job() -> None:
    """Задача планировщика: no-op, пока флаг выключен."""
    global _runs
    if not settings.ssr_warm_enabled:
        return
    include_top = _runs % _TOP_EVERY_RUNS == 0
    _runs += 1
    result = await warm_ssr_cache(include_top=include_top)
    if result["failed"]:
        logger.warning("SSR warm-up: %s", result)
    else:
        logger.debug("SSR warm-up: %s", result)


if __name__ == "__main__":  # python -m app.services.ssr_warm — разовый проход после выкладки
    logging.basicConfig(level=logging.INFO)

    async def _main() -> None:
        if not settings.ssr_warm_enabled:
            print("ssr_warm_enabled выключен: прогрев не выполняется")
            return
        print(await warm_ssr_cache(include_top=True))

    asyncio.run(_main())
