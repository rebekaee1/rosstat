"""Universal public SEO HTML endpoints.

These routes are intended to be served to humans and bots alike via nginx.
They return route-specific HTML with enough content for indexing; React then
replaces the prerendered root with the interactive application.

ETag: content-hash каждого ответа; роботы с If-None-Match получают 304 и
не тратят crawl budget на неизменившиеся страницы (nginx отдаёт SSR с
no-cache для браузеров, но conditional-запросы ботов проходят насквозь).

HTML-кэш (П-14/П-15, риск Р-5): готовый SSR HTML кэшируется в Redis.
Бот-прожиг каталога (40k региональных URL) перестаёт стоить полного
рендера на каждый запрос. Три trap'а закрыты конструкцией ключа:
- stale-данные: ключи индикаторных страниц живут в namespace `fe:{code}:*`,
  который ETL инвалидирует при любом изменении данных ряда; страницы
  с «сегодняшней» датой включают текущую дату в ключ;
- asset-hash trap: ключ включает подпись Vite-ассетов — после rebuild
  фронта закэшированный HTML со старыми чанками не отдаётся;
- host/locale trap: ключ включает request origin host + locale — иначе
  ответ с ``ru.`` Host отравляет apex (и наоборот) absolute URL в
  canonical / OG / JSON-LD.
"""

import asyncio
import hashlib
import re
from datetime import date as _date

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, versioned_key
from app.services import site_paths as paths
from app.services.attribution_query import merge_attribution_query
from app.services.locale import get_locale
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
    render_region_ratings_hub_html,
    render_regions_home_html,
    render_regions_map_html,
)
from app.services.seo_indicator_month import render_indicator_month_html
from app.services.seo_today import render_today_hub_html, render_today_indicator_html
from app.services.seo_world import (
    WORLD_RATING_DEFAULT_CONCEPT,
    render_world_country_html,
    render_world_indicator_html,
    render_world_rating_html,
)
from app.services.seo_world_compare import render_world_vs_html
from app.services.seo_regional_year import render_region_indicator_year_html
from app.services.seo_renderer import (
    render_categories_hub_html,
    render_category_html,
    render_home_html,
    render_indicator_html,
    render_indicator_year_html,
    render_not_found_html,
    render_page_html,
)
from app.services.seo_world_year import render_world_indicator_year_html

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
    бампается ETL-инвалидацией `cache_invalidate_indicator` (П-11, без SCAN).

    Variant folds locale + request-origin host so host-aware absolute URLs
    (canonical / OG / JSON-LD) cannot cross-contaminate apex vs ``ru.``.
    """
    from urllib.parse import urlparse

    from app.services.locale import get_locale, get_request_origin

    loc = get_locale()
    host = urlparse(get_request_origin()).hostname or "default"
    folded = f"{variant}|{loc}|{host}"
    return await versioned_key(
        namespace, f"ssr:{hashlib.md5(folded.encode()).hexdigest()[:16]}:{sig}"
    )


# П-11 (stampede): бот-прожиг шлёт пачку одинаковых URL — на cache-miss рендер
# должен выполниться один раз, остальные ждут результат (in-process singleflight).
_render_locks: dict[str, asyncio.Lock] = {}
_RENDER_LOCKS_MAX = 2000
# Параллельные miss'ы разных URL не должны забрать весь QueuePool.
_RENDER_SEM = asyncio.Semaphore(6)


async def _cached_html(namespace: str, variant: str, ttl: int, render_coro_factory):
    """Вернуть (status, html) из кэша или отрендерить и закэшировать.

    Кэшируются только 200-е ответы: 404 не должен «прилипать» на TTL
    (индикатор мог появиться после деплоя/seed).

    Preview-локаль (``?preview_locale=`` / X-FE-Locale override) всегда
    рендерится свежим ходом и в кэш не попадает: иначе страница с
    ``robots noindex`` закэшировалась бы под обычным ключом и после
    кутовера/на EN-хосте отдавалась каноническим ботам.
    """
    from app.services.locale import is_preview_locale

    if is_preview_locale():
        return await render_coro_factory()

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
        async with _RENDER_SEM:
            status, html = await render_coro_factory()
        if status == 200:
            await cache_set(key, html, ttl)
        return status, html


def _permanent_redirect(path: str, request: Request | None = None) -> Response:
    """301 на канонический публичный путь (А-2/А-3 + path-cut).

    Location — относительный (`/russia/indicator/cpi`), без хоста и схемы:
    браузер и робот резолвят против текущего запроса (localhost:3000 и
    https://forecasteconomy.com одинаково; нет потери порта и даунгрейда HTTPS).
    Абсолютный канон живёт в `<link rel="canonical">` целевой страницы.
    ``ysclid`` / ``yclid`` / UTM с исходного URL переезжают на Location —
    иначе Метрика теряет фразу после path-cut.
    """
    if not path.startswith("/"):
        path = f"/{path}"
    path = merge_attribution_query(path, request)
    return Response(
        status_code=301,
        headers={"Location": path, "Cache-Control": "no-cache"},
    )


def _html_response(status_code: int, html: str, request: Request | None = None) -> Response:
    headers = {"Cache-Control": "no-cache"}
    if status_code == 404 and "<html" not in html.lower():
        # Рендереры возвращают голый маркер («Not found», «<h1>…</h1>») —
        # наружу всегда уходит брендовая 404 с навигацией, не сырой текст.
        from app.services.seo_renderer import render_not_found_html
        text = re.sub(r"<[^>]+>", "", html).strip()
        # Empty / generic "Not found" → locale-aware default message.
        html = render_not_found_html(
            text if text and text not in ("Not found", "Страница не найдена") else None
        )
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
@router.api_route("/seo/not-found", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_not_found():
    """Брендовая 404 для nginx catch-all (unknown URL → error_page)."""
    return _html_response(404, render_not_found_html())


@router.api_route("/seo/page/home", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_home(request: Request, db: AsyncSession = Depends(get_db)):
    return _html_response(200, await render_home_html(db), request)


@router.api_route("/seo/page/{page}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_page(page: str, request: Request):
    status, html = await render_page_html(page)
    return _html_response(status, html, request)


@router.api_route("/seo/category", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_categories_hub(request: Request, db: AsyncSession = Depends(get_db)):
    status, html = await render_categories_hub_html(db)
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
    # А-2/А-3 + path-cut: резолвер уже отдаёт финальный /russia/… путь.
    target = resolve_legacy_indicator(code) or resolve_unlisted_indicator(code)
    if target:
        return _permanent_redirect(target, request)
    # Старый публичный /indicator/{code} (X-Path-Cut-Legacy) → канон /russia/…
    if request.headers.get("x-path-cut-legacy") == "1":
        dest = paths.russia_indicator(code)
        if mode:
            dest = f"{dest}?mode={mode}"
        return _permanent_redirect(dest, request)
    status, html = await _cached_html(
        code, f"indicator:{code}:{mode or ''}:{get_locale()}", _SSR_TTL_INDICATOR,
        lambda: render_indicator_html(code, db, mode=mode),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/regions", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_regions(request: Request, db: AsyncSession = Depends(get_db)):
    # Legacy share URLs (prod 9226c77): /regions?view=map&indicator=&year=
    # → канон /russia/region/map/{code}?year=
    if request.query_params.get("view") == "map":
        raw = request.query_params.get("indicator") or DEFAULT_MAP_CODE
        code = raw if re.fullmatch(r"[a-z0-9-]+", raw, re.I) else DEFAULT_MAP_CODE
        target = paths.region_map(code)
        year = request.query_params.get("year")
        if year and re.fullmatch(r"\d{4}", year):
            target = f"{target}?year={year}"
        return _permanent_redirect(target, request)
    status, html = await render_regions_home_html(db)
    return _html_response(status, html, request)


@router.api_route("/seo/regions/map/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_regions_map(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    year_raw = request.query_params.get("year")
    year = int(year_raw) if year_raw and re.fullmatch(r"\d{4}", year_raw) else None
    status, html = await _cached_html(
        "ssr-region", f"regions-map:{code}:{year or ''}:{get_locale()}", _SSR_TTL_REGIONAL,
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
        "ssr-region", f"region:{slug}:{get_locale()}", _SSR_TTL_REGIONAL,
        lambda: render_region_html(slug, db),
    )
    if status == 404:
        canonical = await _canonical_region_slug(slug, db)
        if canonical:
            return _permanent_redirect(paths.region(canonical), request)
    return _html_response(status, html, request)


@router.api_route("/seo/region/{slug}/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_region_indicator(
    slug: str, code: str, request: Request, db: AsyncSession = Depends(get_db)
):
    status, html = await _cached_html(
        "ssr-region", f"region:{slug}:{code}:{get_locale()}", _SSR_TTL_REGIONAL,
        lambda: render_region_indicator_html(slug, code, db),
    )
    if status == 404:
        canonical = await _canonical_region_slug(slug, db)
        if canonical:
            return _permanent_redirect(paths.region_indicator(canonical, code), request)
    return _html_response(status, html, request)


@router.api_route("/seo/region-rating", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_region_ratings_hub(request: Request, db: AsyncSession = Depends(get_db)):
    status, html = await _cached_html(
        "ssr-region", f"region-rating-hub:{get_locale()}", _SSR_TTL_REGIONAL,
        lambda: render_region_ratings_hub_html(db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/region-rating/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_region_rating(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    status, html = await _cached_html(
        "ssr-region", f"region-rating:{code}:{get_locale()}", _SSR_TTL_REGIONAL,
        lambda: render_region_rating_html(code, db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/region-vs/{slug_a}-vs-{slug_b}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_region_vs(
    slug_a: str, slug_b: str, request: Request, db: AsyncSession = Depends(get_db)
):
    status, html = await _cached_html(
        "ssr-region", f"region-vs:{slug_a}:{slug_b}:{get_locale()}", _SSR_TTL_REGIONAL,
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
        code, f"today:{code}:{_date.today().isoformat()}:{get_locale()}", _SSR_TTL_INDICATOR,
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
        # Категория (снятый ряд) — без годового хвоста.
        if "/category/" in base_path:
            return _permanent_redirect(target.split("?")[0], request)
        return _permanent_redirect(f"{base_path}/{year}", request)
    if request.headers.get("x-path-cut-legacy") == "1":
        return _permanent_redirect(paths.russia_indicator_year(code, year), request)
    status, html = await _cached_html(
        code, f"indicator-year:{code}:{year}:{get_locale()}", _SSR_TTL_INDICATOR,
        lambda: render_indicator_year_html(code, year, db),
    )
    return _html_response(status, html, request)


@router.api_route(
    "/seo/indicator-month/{code}/{period}",
    methods=["GET", "HEAD"], include_in_schema=False,
)
async def seo_indicator_month(
    code: str, period: str, request: Request, db: AsyncSession = Depends(get_db)
):
    if not re.fullmatch(r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])", period):
        return _html_response(404, "Not found")
    status, html = await _cached_html(
        code, f"indicator-month:{code}:{period}:{get_locale()}", _SSR_TTL_INDICATOR,
        lambda: render_indicator_month_html(code, int(period[:4]), int(period[5:]), db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/world", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_world_home(request: Request):
    """Витрина мира переехала на главную: карта, рейтинг и каталог стран теперь там.

    Отдельная страница дублировала главную один в один, поэтому она снята,
    а ссылочный вес адреса передаётся постоянным перенаправлением.
    """
    return _permanent_redirect(paths.home(), request)


@router.api_route("/seo/world/rating", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_world_rating_default(request: Request):
    return _permanent_redirect(paths.world_rating(WORLD_RATING_DEFAULT_CONCEPT), request)


async def _rating_year_info(
    concept_slug: str, db: AsyncSession
) -> tuple[int | None, list[int]]:
    """(дефолтный год, все годы с данными) рейтинга; (None, []) — нет рейтинга."""
    from app.services.seo_world import build_world_rating_payload

    try:
        payload = await build_world_rating_payload(concept_slug, db)
    except Exception:
        return None, []
    if not payload:
        return None, []
    return payload.get("active_year"), list(payload.get("years") or [])


@router.api_route("/seo/world/rating/{concept_slug}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_world_rating(
    concept_slug: str, request: Request, db: AsyncSession = Depends(get_db)
):
    year_raw = request.query_params.get("year")
    # Легаси ?year= — 301 сразу в конечную точку (Фаза 10): дефолтный год — на
    # базу (она и есть его self-canonical), не-дефолтный — на path-канон.
    if year_raw and re.fullmatch(r"\d{4}", year_raw):
        default_year, years = await _rating_year_info(concept_slug, db)
        requested = int(year_raw)
        if requested in years:
            if default_year is not None and requested == default_year:
                return _permanent_redirect(paths.world_rating(concept_slug), request)
            return _permanent_redirect(paths.world_rating_year(concept_slug, requested), request)
    status, html = await _cached_html(
        "ssr-world", f"world-rating:{concept_slug}::{get_locale()}", _SSR_TTL_WORLD,
        lambda: render_world_rating_html(concept_slug, db),
    )
    return _html_response(status, html, request)


@router.api_route(
    "/seo/world/rating/{concept_slug}/{year}",
    methods=["GET", "HEAD"], include_in_schema=False,
)
async def seo_world_rating_year(
    concept_slug: str, year: str, request: Request, db: AsyncSession = Depends(get_db)
):
    if not re.fullmatch(r"(?:19|20)\d{2}", year):
        return _html_response(404, "Not found")
    # Один контент — один URL (Фаза 10): path-канон дефолтного года уходит 301
    # на базу (она и есть его self-canonical), год без данных — честная 404,
    # а не подмена контента чужим годом (софт-404).
    requested = int(year)
    default_year, years = await _rating_year_info(concept_slug, db)
    if requested not in years:
        return _html_response(404, "Not found")
    if default_year is not None and requested == default_year:
        return _permanent_redirect(paths.world_rating(concept_slug), request)
    status, html = await _cached_html(
        "ssr-world", f"world-rating:{concept_slug}:{year}:{get_locale()}", _SSR_TTL_WORLD,
        lambda: render_world_rating_html(concept_slug, db, year=requested),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/world/{slug}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_world_country(
    slug: str, request: Request, db: AsyncSession = Depends(get_db)
):
    if request.headers.get("x-path-cut-legacy") == "1":
        return _permanent_redirect(paths.country(slug), request)
    status, html = await _cached_html(
        "ssr-world", f"world:{slug}:{get_locale()}", _SSR_TTL_WORLD,
        lambda: render_world_country_html(slug, db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/world/{slug}/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_world_indicator(
    slug: str, code: str, request: Request, db: AsyncSession = Depends(get_db)
):
    # Вторичные частоты → финальный /{slug}/indicator/{primary}?mode=…
    target = await resolve_world_frequency_sibling(db, slug, code)
    if target:
        return _permanent_redirect(target, request)
    if request.headers.get("x-path-cut-legacy") == "1":
        mode = request.query_params.get("mode")
        dest = paths.indicator(slug, code)
        if mode:
            dest = f"{dest}?mode={mode}"
        return _permanent_redirect(dest, request)
    status, html = await _cached_html(
        "ssr-world", f"world:{slug}:{code}:{get_locale()}", _SSR_TTL_WORLD,
        lambda: render_world_indicator_html(slug, code, db),
    )
    return _html_response(status, html, request)


@router.api_route(
    "/seo/world-indicator-year/{slug}/{code}/{year}",
    methods=["GET", "HEAD"], include_in_schema=False,
)
async def seo_world_indicator_year(
    slug: str, code: str, year: str, request: Request, db: AsyncSession = Depends(get_db)
):
    if not re.fullmatch(r"(?:19|20)\d{2}", year):
        return _html_response(404, "Not found")
    # Вторичные частоты → финальный /{slug}/indicator/{primary} (query отрезаем,
    # годовой лендинг живёт только на primary-ряде).
    target = await resolve_world_frequency_sibling(db, slug, code)
    if target:
        return _permanent_redirect(f"{target.split('?')[0]}/{year}", request)
    if request.headers.get("x-path-cut-legacy") == "1":
        return _permanent_redirect(paths.indicator_year(slug, code, year), request)
    status, html = await _cached_html(
        "ssr-world", f"world-year:{slug}:{code}:{year}:{get_locale()}", _SSR_TTL_WORLD,
        lambda: render_world_indicator_year_html(slug, code, int(year), db),
    )
    return _html_response(status, html, request)


@router.api_route("/seo/world-vs/{pair}/{concept}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_world_vs(
    pair: str, concept: str, request: Request, db: AsyncSession = Depends(get_db)
):
    # «-vs-» — внутренний разделитель пары, слаги стран сами содержат дефисы:
    # разрез строго по последнему «-vs-» (слаг «united-states» не разъедается).
    if "-vs-" not in pair:
        return _html_response(404, "Not found")
    slug_a, slug_b = pair.rsplit("-vs-", 1)
    if not slug_a or not slug_b:
        return _html_response(404, "Not found")
    status, payload = await render_world_vs_html(slug_a, slug_b, concept, db)
    if status == 301:
        # Редирект до кэша: каноническая пара переезжает, не-канонический
        # URL никогда не должен закэшироваться как содержимое.
        return _permanent_redirect(payload, request)
    if status == 200:
        # Кэшируется только 200 (как в singleflight _cached_html): ключ —
        # каноническая упорядоченная пара, рендер уже выполнен один раз.
        sig = await _asset_sig()
        key = await _ssr_key(
            "ssr-world",
            f"world-vs:{slug_a}:{slug_b}:{concept}:{get_locale()}", sig,
        )
        await cache_set(key, payload, _SSR_TTL_WORLD)
    return _html_response(status, payload, request)


@router.api_route(
    "/seo/region-indicator-year/{slug}/{code}/{year}",
    methods=["GET", "HEAD"], include_in_schema=False,
)
async def seo_region_indicator_year(
    slug: str, code: str, year: str, request: Request, db: AsyncSession = Depends(get_db)
):
    if not re.fullmatch(r"(?:19|20)\d{2}", year):
        return _html_response(404, "Not found")
    status, html = await _cached_html(
        "ssr-region", f"region-year:{slug}:{code}:{year}:{get_locale()}", _SSR_TTL_REGIONAL,
        lambda: render_region_indicator_year_html(slug, code, int(year), db),
    )
    # А-2: короткий слаг региона → канонический с префиксом («tatarstan» →
    # «respublika-tatarstan»), тот же guard, что у двухсегментной карточки.
    if status == 404:
        canonical = await _canonical_region_slug(slug, db)
        if canonical:
            return _permanent_redirect(paths.region_indicator(canonical, code) + f"/{year}", request)
    return _html_response(status, html, request)
