"""Universal public SEO HTML endpoints.

These routes are intended to be served to humans and bots alike via nginx.
They return route-specific HTML with enough content for indexing; React then
replaces the prerendered root with the interactive application.

ETag: content-hash каждого ответа; роботы с If-None-Match получают 304 и
не тратят crawl budget на неизменившиеся страницы (nginx отдаёт SSR с
no-cache для браузеров, но conditional-запросы ботов проходят насквозь).

HTML-кэш (П-14/П-15, риск Р-5): готовый SSR HTML кэшируется в Redis.
Бот-прожиг каталога (40k региональных URL) перестаёт стоить полного
рендера на каждый запрос. Два trap'а закрыты конструкцией ключа:
- stale-данные: ключи индикаторных страниц живут в namespace `fe:{code}:*`,
  который ETL инвалидирует при любом изменении данных ряда; страницы
  с «сегодняшней» датой включают текущую дату в ключ;
- asset-hash trap: ключ включает подпись Vite-ассетов — после rebuild
  фронта закэшированный HTML со старыми чанками не отдаётся.
"""

import asyncio
import hashlib
import re
from datetime import date as _date

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, versioned_key
from app.data.legacy_redirects import (
    LEGACY_REGION_SLUG_PREFIXES,
    resolve_legacy_indicator,
    resolve_unlisted_indicator,
    resolve_world_frequency_sibling,
)
from app.database import get_db
from app.services.seo_calendar import render_calendar_month_html
from app.services.seo_region_compare import render_region_vs_html
from app.services.seo_regional import (
    DEFAULT_MAP_CODE,
    render_region_html,
    render_region_indicator_html,
    render_region_rating_html,
    render_regions_home_html,
    render_regions_map_html,
)
from app.services.seo_today import render_today_hub_html, render_today_indicator_html
from app.services.seo_world import (
    render_world_country_html,
    render_world_home_html,
    render_world_indicator_html,
)
from app.services.seo_renderer import (
    render_category_html,
    render_home_html,
    render_indicator_html,
    render_indicator_year_html,
    render_page_html,
)

router = APIRouter(tags=["seo-pages"])

# TTL кэша HTML: региональные страницы — датасет годовой, безопасно долго;
# макро-страницы — короче (данные меняются ETL'ом, плюс namespace-инвалидация).
_SSR_TTL_INDICATOR = 900       # 15 мин; + инвалидация fe:{code}:* при ETL
_SSR_TTL_REGIONAL = 6 * 3600   # регион × показатель × год — обновляется раз в год
_SSR_TTL_WORLD = 6 * 3600      # мировой блок — внешний источник, обновляется пачками
_SSR_TTL_MISC = 1800


async def _asset_sig() -> str:
    """Подпись Vite-ассетов текущего фронта (asset-hash trap, Р-5)."""
    from app.services.seo_renderer import get_app_assets
    assets = await get_app_assets()
    return hashlib.md5(
        (assets.head_links + assets.body_scripts).encode()
    ).hexdigest()[:12]


async def _ssr_key(namespace: str, variant: str, sig: str) -> str:
    """`namespace` для индикаторных страниц = код индикатора — версия namespace
    бампается ETL-инвалидацией `cache_invalidate_indicator` (П-11, без SCAN)."""
    return await versioned_key(
        namespace, f"ssr:{hashlib.md5(variant.encode()).hexdigest()[:16]}:{sig}"
    )


# П-11 (stampede): бот-прожиг шлёт пачку одинаковых URL — на cache-miss рендер
# должен выполниться один раз, остальные ждут результат (in-process singleflight).
_render_locks: dict[str, asyncio.Lock] = {}
_RENDER_LOCKS_MAX = 2000


async def _cached_html(namespace: str, variant: str, ttl: int, render_coro_factory):
    """Вернуть (status, html) из кэша или отрендерить и закэшировать.

    Кэшируются только 200-е ответы: 404 не должен «прилипать» на TTL
    (индикатор мог появиться после деплоя/seed).
    """
    sig = await _asset_sig()
    key = await _ssr_key(namespace, variant, sig)
    cached = await cache_get(key)
    if isinstance(cached, str) and cached:
        return 200, cached

    if len(_render_locks) > _RENDER_LOCKS_MAX:
        _render_locks.clear()  # защита от роста на уникальных 404-путях
    lock = _render_locks.setdefault(key, asyncio.Lock())
    async with lock:
        cached = await cache_get(key)  # мог появиться, пока ждали лок
        if isinstance(cached, str) and cached:
            return 200, cached
        status, html = await render_coro_factory()
        if status == 200:
            await cache_set(key, html, ttl)
        return status, html


def _permanent_redirect(path: str) -> Response:
    """301 на канонический публичный URL (А-2/А-3): абсолютный Location —
    ответ уходит роботу через nginx-proxy, относительный путь двусмыслен."""
    from app.services.seo_renderer import DOMAIN
    return Response(
        status_code=301,
        headers={"Location": f"{DOMAIN}{path}", "Cache-Control": "no-cache"},
    )


def _html_response(status_code: int, html: str, request: Request | None = None) -> Response:
    headers = {"Cache-Control": "no-cache"}
    if status_code == 404 and "<html" not in html.lower():
        # Рендереры возвращают голый маркер («Not found», «<h1>…</h1>») —
        # наружу всегда уходит брендовая 404 с навигацией, не сырой текст.
        from app.services.seo_renderer import render_not_found_html
        text = re.sub(r"<[^>]+>", "", html).strip()
        html = render_not_found_html(text if text and text != "Not found" else "Страница не найдена")
    if status_code == 200:
        etag = f'W/"{hashlib.md5(html.encode()).hexdigest()}"'
        headers["ETag"] = etag
        if request is not None and request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
    return Response(
        content=html,
        status_code=status_code,
        media_type="text/html; charset=utf-8",
        headers=headers,
    )


# methods GET+HEAD: роботы (и curl -I) проверяют страницы HEAD-запросом —
# чистый @router.get отвечал бы 405.
@router.api_route("/seo/page/home", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_home(request: Request, db: AsyncSession = Depends(get_db)):
    return _html_response(200, await render_home_html(db), request)


@router.api_route("/seo/page/{page}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_page(page: str, request: Request):
    status, html = await render_page_html(page)
    return _html_response(status, html, request)


@router.api_route("/seo/category/{slug}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_category(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    status, html = await render_category_html(slug, db)
    return _html_response(status, html, request)


@router.api_route("/seo/indicator/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_indicator(
    code: str,
    request: Request,
    mode: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    # А-2: переименованные коды → 301 на актуальную карточку.
    # А-3: unlisted sibling-ряды (generic-режимы, bespoke-легаси) → 301 на
    # канонический URL семьи вместо 404 — робот не выбрасывает старый URL.
    # Variant-члены групп (топливо, разделы ИПП) резолвером не покрываются
    # намеренно: у них собственные живые карточки.
    target = resolve_legacy_indicator(code) or resolve_unlisted_indicator(code)
    if target:
        return _permanent_redirect(target)
    status, html = await _cached_html(
        code, f"indicator:{code}:{mode or ''}", _SSR_TTL_INDICATOR,
        lambda: render_indicator_html(code, db, mode=mode),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/regions", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_regions(request: Request, db: AsyncSession = Depends(get_db)):
    # Legacy share URLs (prod 9226c77): /regions?view=map&indicator=&year=
    # → канон /regions/map/{code}?year=
    if request.query_params.get("view") == "map":
        raw = request.query_params.get("indicator") or DEFAULT_MAP_CODE
        code = raw if re.fullmatch(r"[a-z0-9-]+", raw, re.I) else DEFAULT_MAP_CODE
        target = f"/regions/map/{code}"
        year = request.query_params.get("year")
        if year and re.fullmatch(r"\d{4}", year):
            target = f"{target}?year={year}"
        return _permanent_redirect(target)
    status, html = await render_regions_home_html(db)
    return _html_response(status, html, request)


@router.api_route("/seo/regions/map/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_regions_map(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    year_raw = request.query_params.get("year")
    year = int(year_raw) if year_raw and re.fullmatch(r"\d{4}", year_raw) else None
    status, html = await _cached_html(
        "ssr-region", f"regions-map:{code}:{year or ''}", _SSR_TTL_REGIONAL,
        lambda: render_regions_map_html(code, db, year=year),
    )
    return _html_response(status, html, request)


async def _canonical_region_slug(slug: str, db: AsyncSession) -> str | None:
    """А-2: старый короткий слаг региона → канонический с префиксом
    («tatarstan» → «respublika-tatarstan»), если такой регион существует."""
    from sqlalchemy import select

    from app.models import Region

    for prefix in LEGACY_REGION_SLUG_PREFIXES:
        candidate = f"{prefix}{slug}"
        q = await db.execute(select(Region.slug).where(Region.slug == candidate))
        if q.scalar_one_or_none():
            return candidate
    return None


@router.api_route("/seo/region/{slug}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_region(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    status, html = await _cached_html(
        "ssr-region", f"region:{slug}", _SSR_TTL_REGIONAL,
        lambda: render_region_html(slug, db),
    )
    if status == 404:
        canonical = await _canonical_region_slug(slug, db)
        if canonical:
            return _permanent_redirect(f"/region/{canonical}")
    return _html_response(status, html, request)


@router.api_route("/seo/region/{slug}/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_region_indicator(
    slug: str, code: str, request: Request, db: AsyncSession = Depends(get_db)
):
    status, html = await _cached_html(
        "ssr-region", f"region:{slug}:{code}", _SSR_TTL_REGIONAL,
        lambda: render_region_indicator_html(slug, code, db),
    )
    if status == 404:
        canonical = await _canonical_region_slug(slug, db)
        if canonical:
            return _permanent_redirect(f"/region/{canonical}/{code}")
    return _html_response(status, html, request)


@router.api_route("/seo/region-rating/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_region_rating(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    status, html = await _cached_html(
        "ssr-region", f"region-rating:{code}", _SSR_TTL_REGIONAL,
        lambda: render_region_rating_html(code, db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/region-vs/{slug_a}-vs-{slug_b}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_region_vs(
    slug_a: str, slug_b: str, request: Request, db: AsyncSession = Depends(get_db)
):
    status, html = await _cached_html(
        "ssr-region", f"region-vs:{slug_a}:{slug_b}", _SSR_TTL_REGIONAL,
        lambda: render_region_vs_html(slug_a, slug_b, db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/today", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_today_hub(request: Request, db: AsyncSession = Depends(get_db)):
    status, html = await render_today_hub_html(db)
    return _html_response(status, html, request)


@router.api_route("/seo/today/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_today_indicator(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    # «Сегодня» в заголовке: текущая дата в variant — смена суток гарантированно
    # инвалидирует, даже без ETL (freshness-guard В-4 не должен кэшем ломаться).
    status, html = await _cached_html(
        code, f"today:{code}:{_date.today().isoformat()}", _SSR_TTL_INDICATOR,
        lambda: render_today_indicator_html(code, db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/calendar-month/{year}/{month}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_calendar_month(
    year: int, month: int, request: Request, db: AsyncSession = Depends(get_db)
):
    status, html = await render_calendar_month_html(year, month, db)
    return _html_response(status, html, request)


@router.api_route("/seo/indicator-year/{code}/{year}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_indicator_year(
    code: str,
    year: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if year < 1990 or year > 2100:
        return _html_response(404, "Not found")
    # Годовые landing легаси/sibling-кодов — 301 на годовую страницу канона.
    target = resolve_legacy_indicator(code) or resolve_unlisted_indicator(code)
    if target:
        base_path = target.split("?")[0]
        return _permanent_redirect(f"{base_path}/{year}")
    status, html = await _cached_html(
        code, f"indicator-year:{code}:{year}", _SSR_TTL_INDICATOR,
        lambda: render_indicator_year_html(code, year, db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/world", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_world_home(request: Request, db: AsyncSession = Depends(get_db)):
    status, html = await _cached_html(
        "ssr-world", "world-home", _SSR_TTL_WORLD,
        lambda: render_world_home_html(db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/world/{slug}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_world_country(
    slug: str, request: Request, db: AsyncSession = Depends(get_db)
):
    status, html = await _cached_html(
        "ssr-world", f"world:{slug}", _SSR_TTL_WORLD,
        lambda: render_world_country_html(slug, db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/world/{slug}/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_world_indicator(
    slug: str, code: str, request: Request, db: AsyncSession = Depends(get_db)
):
    # Вторичные частоты (квартал/год) → 301 на primary?mode=level-{freq},
    # как resolve_unlisted_indicator для российских sibling-рядов.
    target = await resolve_world_frequency_sibling(db, slug, code)
    if target:
        return _permanent_redirect(target)
    # Нулевые/скрытые ряды не редиректим на страну — просто 404.
    # Исключение из выбора (listing/variants) делается в API/repair.
    status, html = await _cached_html(
        "ssr-world", f"world:{slug}:{code}", _SSR_TTL_WORLD,
        lambda: render_world_indicator_html(slug, code, db),
    )
    return _html_response(status, html, request)
