"""Dynamic sitemap.xml, RSS feed and OG endpoints generated from the database."""
import asyncio
import hashlib
import logging
import re
from datetime import date, datetime, timezone
from email.utils import format_datetime
from html import escape
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData
from app.services.display import (
    annual_summary,
    display_value,
    display_value_text,
    format_date_locale,
    format_month_year,
    format_number_ru,
    is_cpi_index,
)
from app.services.locale import get_locale
from app.services.og_image import (
    fmt_signed,
    fmt_yoy,
    ru_period_lines,
    window_x_labels,
)
# CATEGORIES/PAGE_META/STATIC_PAGES реэкспортируются для тестов
# (test_sitemap_static_pages_constant) — сама генерация живёт в site_urls.py.
from app.services.seo_content import (  # noqa: F401
    CATEGORIES,
    CATEGORY_META,
    DOMAIN,
    PAGE_META,
    STATIC_PAGES,
)
from app.services.seo_renderer import render_category_html, render_home_html, render_indicator_html, render_page_html

logger = logging.getLogger(__name__)
router = APIRouter(tags=["seo"])


def _world_subject(name: str | None) -> str:
    """Суффикс частоты вырезает legacy-реестр (импорт внутри — RU-only путь)."""
    from app.data.legacy_redirects import strip_world_frequency_suffix

    return strip_world_frequency_suffix(name) or (name or "")


def _sitemap_priority(*, listed: bool, is_indicator: bool) -> str:
    """Приоритет crawl budget: главная и категории выше, derived-sibling ниже."""
    if not is_indicator:
        return "0.8"
    return "0.8" if listed else "0.5"


def _sitemap_lastmod(last_data: date | None, fallback: date) -> str:
    return (last_data or fallback).isoformat()


_SITEMAP_TTL = 6 * 3600


# --- OG-постеры: локализация подписей ----------------------------------------
#
# RU/EN строки живут здесь, чтобы не плодить публичные словари: постер —
# компактная поверхность, языковых пар меньше десятка. Неизвестная RU-подпись
# годового итога остаётся русской и на EN-хосте (не ломаем, а не выдумываем).

_ANNUAL_SUMMARY_EN = {
    "Рост цен за год": "Price growth over the year",
    "Итог за год (сумма)": "Year total",
    "Значение на конец года": "End-of-year value",
    "Среднее за год": "Yearly average",
}


def _annual_summary_label_en(label_ru: str) -> str:
    return _ANNUAL_SUMMARY_EN.get(label_ru, label_ru)


def _fmt_yoy_en(pct: float) -> str:
    """Аналог format_number_ru(signed=True) для пилюли EN-постера: «+6.1%»."""
    sign = "+" if pct >= 0 else "\u2212"
    return f"{sign}{abs(pct):.1f}%"


def _og_annual_compare(year: int, prev, cur, *, locale: str) -> str | None:
    """«к {year−1} году — ±X%» / «vs {year−1}: ±X%»; None, если базы нет."""
    try:
        prev_f, cur_f = float(prev), float(cur)
    except (TypeError, ValueError):
        return None
    if prev_f == 0.0:
        return None
    pct = round(((cur_f - prev_f) / abs(prev_f)) * 100.0, 1)
    if locale == "en":
        return f"vs {year - 1}: {_fmt_yoy_en(pct)}"
    return f"к {year - 1} году \u2014 {format_number_ru(pct, signed=True, locale=locale)} %"


def _og_monthly_subtitle(locale: str) -> str:
    if locale == "en":
        return "consumer price index, monthly change"
    return "индекс потребительских цен, изменение за месяц"


def _og_weekly_subtitle(locale: str) -> str:
    if locale == "en":
        return "consumer price index, weekly change"
    return "индекс потребительских цен, изменение за неделю"


def _inflation_pill(pct: float, *, locale: str) -> str:
    """Пилюля годовой инфляции: цепное произведение уже посчитал вызывающий."""
    value = fmt_yoy(pct, locale=locale)
    if locale == "en":
        return f"Annual inflation \u2014 {value}%"
    return f"Годовая инфляция \u2014 {value}%"


def _og_context(
    code: str,
    rows,
    *,
    unit: str,
    frequency: str,
    current_date,
    locale: str,
) -> dict:
    """Единая точка подписей J6-постера: subtitle/pill/период/суффикс единицы.

    RU-выдача совпадает с прежней построчной логикой веток в эндпоинте
    (тестируется). context_pill — только честный расчёт: цепная годовая
    инфляция при окне ≥12 месяцев; yoy-ряд сам является годовой метрикой.
    """
    loc = locale
    is_cpi = is_cpi_index(code)
    subtitle = context_pill = None

    if is_cpi and len(rows) >= 13 and current_date:
        # Полное окно: период + база сравнения + цепная годовая инфляция.
        period_text, _compare = ru_period_lines(current_date, rows[-2][1], locale=loc)
        subtitle = (
            _og_weekly_subtitle(loc)
            if (frequency or "").lower().startswith("week")
            else _og_monthly_subtitle(loc)
        )
        growth = 1.0
        for raw, _ in rows[-12:]:
            growth *= float(raw) / 100.0
        context_pill = _inflation_pill((growth - 1.0) * 100.0, locale=loc)
    elif current_date:
        # Остальные ряды (в т.ч. короткие окна): период без базы сравнения.
        period_text, _ = ru_period_lines(current_date, locale=loc)
    else:
        period_text = None

    return {
        "subtitle": subtitle,
        "context_pill": context_pill,
        "period_text": period_text,
        "unit_suffix": "%" if (unit == "%" or is_cpi) else None,
    }


def _request_sitemap_origin(request: Request) -> str:
    """Host-aware absolute origin for sitemap ``<loc>`` (ADR-0013 §F).

    Flag off + apex Host → ``settings.public_origin`` (current prod path).
    Host ``ru.*`` → ``https://ru.{apex}`` even before cutover.
    """
    from app.services.locale import get_request_origin, resolve_request_origin

    # Prefer middleware-bound origin; fall back if middleware skipped in tests.
    bound = get_request_origin()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    resolved = resolve_request_origin(host)
    return resolved if host else bound


def _sitemap_cache_key(kind: str, origin: str) -> str:
    host = urlparse(origin).hostname or "default"
    return f"fe:sitemap:{kind}:{host}"


def _render_urlset(urls, *, origin: str | None = None) -> str:
    """Render urlset with absolute ``<loc>`` on the given origin (default DOMAIN)."""
    base = (origin or DOMAIN).rstrip("/")
    entries = "\n".join(
        f"  <url>\n"
        f"    <loc>{base}{u.path}</loc>\n"
        f"    <lastmod>{u.lastmod}</lastmod>\n"
        f"    <changefreq>{u.changefreq}</changefreq>\n"
        f"    <priority>{u.priority}</priority>\n"
        f"  </url>"
        for u in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + entries
        + "\n</urlset>"
    )


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap_index(request: Request, db: AsyncSession = Depends(get_db)):
    """Sitemap-индекс: имена секций из SECTION_BUILDERS-реестра site_urls.

    Строится МГНОВЕННО: простые секции — статический список, чанковые группы
    разворачиваются из `chunk_counts` (дешёвые count-запросы, кэш). Ни одного
    URL при этом не собирается — монолитный проход 2 млн URL здесь больше не
    нужен (П-13). lastmod секций не ставится: поисковики читают lastmod самих
    секций, время индекса = момент сборки.

    ``<loc>`` абсолютные URL — на хосте запроса (apex vs ``ru.``). Пока
    ``apex_locale_en=false`` и трафик на apex — тот же русский sitemap на
    ``DOMAIN``, что и раньше.
    """
    from app.core.cache import cache_get, cache_set
    from app.services.site_urls import section_names

    origin = _request_sitemap_origin(request)
    cache_key = _sitemap_cache_key("index", origin)
    cached = await cache_get(cache_key)
    if cached:
        return _index_304_or_full(cached, request)

    names = await section_names(db)
    entries = "\n".join(
        f"  <sitemap>\n    <loc>{origin}/sitemap-{name}.xml</loc>\n  </sitemap>"
        for name in names
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + entries
        + "\n</sitemapindex>"
    )
    await cache_set(cache_key, xml, _SITEMAP_TTL)
    return _index_304_or_full(xml, request)


def _index_304_or_full(xml: str, request: Request) -> Response:
    etag = _xml_etag(xml)
    headers = {"ETag": etag, "Cache-Control": "public, max-age=600"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=xml, media_type="application/xml", headers=headers)


@router.api_route("/sitemap-{section}.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap_section(
    section: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """URL-набор ОДНОЙ секции: сборка только запрошенной группы, ETag/304.

    Мусорное имя отсекается без БД (реестр секций / префикс чанковой группы).
    Холодный miss стоит одну группу (не монолит — фикс П-13: 40+ с и 504).
    Конкурентные запросы одной секции собирают её под Redis-локом один раз —
    остальные ждут готовый XML из кэша.
    """
    from app.core.cache import cache_get, cache_set, get_state_redis
    from app.services.site_urls import resolve_section, _chunked_prefix_for

    _known_static = frozenset(
        ("core", "today", "ratings", "maps", "regions", "region-vs",
         "world-ratings", "world", "calendar", "world-vs", "years", "months")
    )

    origin = _request_sitemap_origin(request)
    cache_key = _sitemap_cache_key(f"section:{section}", origin)
    etag_key = _sitemap_cache_key(f"section-etag:{section}", origin)
    cached = await cache_get(cache_key)
    if cached:
        etag = await cache_get(etag_key) or _xml_etag(cached)
        return _xml_304_or_full(cached, etag, request)

    # Мусорные имена отсекаются без БД: простая секция всегда существует
    # (статический реестр билдеров), чанковая валидируется по префиксу —
    # out-of-range чанк отсеет build_chunk пустой страницей → 404.
    chunk_name = _chunked_prefix_for(section)
    if chunk_name is None and section not in _known_static:
        return Response(status_code=404)

    # Лок на сборку: боты бьют по одной секции пачкой — собирать должен один
    # воркер, остальные ждут готовый XML из кэша. Redis-недоступность — не
    # повод для 5xx: собираем без лока (fail-open).
    got = False
    try:
        state = await get_state_redis()
        lock = state.lock(
            f"fe:sitemap:build-lock:{section}", timeout=120, blocking_timeout=30
        )
        got = await lock.acquire()
    except Exception:
        lock = None
        got = True
    try:
        if got:
            cached = await cache_get(cache_key)
            if cached:
                etag = await cache_get(etag_key) or _xml_etag(cached)
                return _xml_304_or_full(cached, etag, request)
            urls = await resolve_section(db, section)
            if urls is None or not urls:
                return Response(status_code=404)
            xml = _render_urlset(urls, origin=origin)
            await cache_set(cache_key, xml, _SITEMAP_TTL)
            await cache_set(etag_key, _xml_etag(xml), _SITEMAP_TTL)
        else:
            # Лок занят: коротко ждём кэш другого воркера.
            for _ in range(20):
                await asyncio.sleep(0.5)
                cached = await cache_get(cache_key)
                if cached:
                    break
            else:
                return Response(status_code=503, headers={"Retry-After": "5"})
            etag = await cache_get(etag_key) or _xml_etag(cached)
            return _xml_304_or_full(cached, etag, request)
    finally:
        if got and lock is not None:
            try:
                await lock.release()
            except Exception:  # лок мог истечь
                pass

    etag = await cache_get(etag_key) or _xml_etag(xml)
    return _xml_304_or_full(xml, etag, request)


def _xml_etag(xml: str) -> str:
    return f'W/"{hashlib.md5(xml.encode()).hexdigest()}"'


def _xml_http_date(dt: datetime) -> str:
    return format_datetime(dt.replace(microsecond=0), usegmt=True)


def _last_modified_from_xml(xml: str) -> datetime | None:
    """max(<lastmod>) urlset'а — HTTP-Last-Modified секции (или None)."""
    mods = re.findall(r"<lastmod>([^<]+)</lastmod>", xml)
    if not mods:
        return None
    try:
        return max(
            datetime.strptime(m[:10], "%Y-%m-%d") for m in mods
        )
    except ValueError:
        return None


def _xml_headers(xml: str, etag: str) -> dict[str, str]:
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=600",
    }
    last_mod = _last_modified_from_xml(xml)
    if last_mod is not None:
        # 23:59:59 UTC: секция, обновлённая «сегодня», валидна весь день.
        headers["Last-Modified"] = _xml_http_date(
            last_mod.replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        )
    return headers


def _xml_304_or_full(xml: str, etag: str, request: Request) -> Response:
    headers = _xml_headers(xml, etag)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    ims = request.headers.get("if-modified-since")
    if ims and "if-none-match" not in request.headers:
        last_mod = _last_modified_from_xml(xml)
        if last_mod is not None:
            try:
                ims_dt = datetime.strptime(
                    ims, "%a, %d %b %Y %H:%M:%S %Z"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                ims_dt = None
            # Секция обновляется в течение дня «своего» lastmod — отдаём 304
            # только когда Last-Modified секции строго старше IMS запроса.
            if ims_dt is not None:
                lm_utc = last_mod.replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
                if lm_utc <= ims_dt:
                    return Response(status_code=304, headers=headers)
    return Response(content=xml, media_type="application/xml", headers=headers)


def _render_seo_static(name: str, *, origin: str) -> str:
    """Substitute request origin into robots.txt / llms.txt templates.

    Locale=en → ``*.en.txt`` twin when present (AI crawlers / bots with X-FE-Locale).
    """
    from pathlib import Path

    from app.services.locale import get_locale

    base_dir = Path(__file__).resolve().parents[1] / "data" / "seo_static"
    loc = get_locale()
    if loc == "en":
        en_name = name.replace(".txt", ".en.txt") if name.endswith(".txt") else f"{name}.en"
        en_path = base_dir / en_name
        path = en_path if en_path.is_file() else base_dir / name
    else:
        path = base_dir / name
    text = path.read_text(encoding="utf-8")
    base = origin.rstrip("/")
    host = urlparse(base).hostname or "forecasteconomy.com"
    return text.replace("__PUBLIC_ORIGIN__", base).replace("__PUBLIC_HOST__", host)


@router.api_route("/robots.txt", methods=["GET", "HEAD"], include_in_schema=False)
async def robots_txt(request: Request):
    """Host-aware robots.txt (Host + Sitemap on request origin)."""
    origin = _request_sitemap_origin(request)
    body = _render_seo_static("robots.txt", origin=origin)
    return Response(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Vary": "Host",
        },
    )


@router.api_route("/llms.txt", methods=["GET", "HEAD"], include_in_schema=False)
async def llms_txt(request: Request):
    """Host-aware llms.txt for AI crawlers (absolute URLs on request origin)."""
    origin = _request_sitemap_origin(request)
    body = _render_seo_static("llms.txt", origin=origin)
    return Response(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Vary": "Host",
        },
    )


@router.api_route("/feed.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def rss_feed(request: Request, db: AsyncSession = Depends(get_db)):
    """RSS 2.0 — последние обновления данных по listed-индикаторам.

    Item на индикатор: имя + актуальное значение, pubDate = дата последней
    точки. Поисковики и агрегаторы узнают об обновлениях без переобхода.

    Absolute links follow request Host (apex vs ``ru.``), same as sitemap.
    """
    from app.services import site_paths as paths
    from app.services.i18n_display import public_name
    from app.services.seo_i18n import indicator_copy_en

    loc = get_locale()
    origin = _request_sitemap_origin(request)
    last_point = (
        select(
            IndicatorData.indicator_id,
            func.max(IndicatorData.date).label("last_date"),
        )
        .group_by(IndicatorData.indicator_id)
        .subquery()
    )
    stmt = (
        select(Indicator, IndicatorData.value, IndicatorData.date)
        .join(last_point, last_point.c.indicator_id == Indicator.id)
        .join(
            IndicatorData,
            (IndicatorData.indicator_id == Indicator.id)
            & (IndicatorData.date == last_point.c.last_date),
        )
        .where(Indicator.is_active.is_(True), Indicator.is_listed.is_(True))
        .order_by(desc(IndicatorData.date), Indicator.code)
        .limit(60)
    )
    rows = (await db.execute(stmt)).all()

    items = []
    for ind, value, dt in rows:
        pub = format_datetime(datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc))
        # Display-adapter: CPI-индекс → изменение цен («+0,17 % за месяц»),
        # русские числа и даты — сырой «100.2 %» в RSS был классом инцидента.
        shown = display_value_text(ind.code, value, ind.unit, ind.frequency, locale=loc)
        name_loc = public_name(
            ind.name,
            ((indicator_copy_en(ind.code) or {}).get("name") if loc == "en" else None)
            or ind.name_en,
            locale=loc,
        )
        title = escape(f"{name_loc}: {shown}")
        desc_text = escape(
            f"{name_loc} \u2014 значение {shown} на {format_date_locale(dt, locale=loc)}. "
            f"Источник: {ind.source}."
        )
        link = f"{origin}{paths.russia_indicator(ind.code)}"
        items.append(
            f"  <item>\n"
            f"    <title>{title}</title>\n"
            f"    <link>{link}</link>\n"
            f"    <guid isPermaLink=\"false\">{ind.code}-{dt.isoformat()}</guid>\n"
            f"    <pubDate>{pub}</pubDate>\n"
            f"    <description>{desc_text}</description>\n"
            f"  </item>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "<channel>\n"
        "  <title>Forecast Economy — обновления экономических данных России</title>\n"
        f"  <link>{origin}</link>\n"
        "  <description>Последние обновления макроэкономических индикаторов России: "
        "Росстат, Банк России, Минфин.</description>\n"
        "  <language>ru</language>\n"
        f'  <atom:link href="{origin}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(items)
        + "\n</channel>\n</rss>"
    )
    return Response(
        content=xml,
        media_type="application/rss+xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=1800", "Vary": "Host"},
    )


@router.get("/api/v1/og-image/indicator/{code}.png", include_in_schema=False)
async def og_image_indicator(code: str, db: AsyncSession = Depends(get_db)):
    """PNG-превью индикатора для og:image (спарклайн + актуальное значение)."""
    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.i18n_display import public_name
    from app.services.seo_i18n import indicator_copy_en

    loc = get_locale()
    cache_key = f"j6:{loc}:{code}"
    png = cached_og(cache_key)
    if png is None:
        q = await db.execute(
            select(Indicator).where(Indicator.code == code, Indicator.is_active.is_(True))
        )
        indicator = q.scalar_one_or_none()
        if not indicator:
            return Response(status_code=404)
        rows_q = await db.execute(
            select(IndicatorData.value, IndicatorData.date)
            .where(IndicatorData.indicator_id == indicator.id)
            .order_by(IndicatorData.date)  # старое → новое, вся история
        )
        rows = rows_q.all()
        current_value, current_date = (rows[-1] if rows else (None, None))
        unit = (indicator.unit or "").strip()
        value_text = display_value_text(code, current_value, unit, indicator.frequency, locale=loc)
        date_text = (
            f"на {format_date_locale(current_date, locale=loc)}" if current_date else ""
        )
        # Окно ленты — последние 24 точки (не вся история с 1991: иначе
        # недавняя динамика схлопывается в прямую).
        window = rows[-24:] if len(rows) > 24 else rows
        values = [
            v if (v := display_value(code, raw)) is not None else 0.0
            for raw, _ in window
        ]
        x_labels = None
        if len(window) >= 2:
            x_labels = window_x_labels(window[0][1], window[-1][1], locale=loc)
        shown_last = display_value(code, current_value)
        core_number = (
            fmt_signed(shown_last) if shown_last is not None else value_text
        )
        ctx = _og_context(
            code,
            rows,
            unit=unit,
            frequency=indicator.frequency or "",
            current_date=current_date,
            locale=loc,
        )
        overlay = indicator_copy_en(code) if loc == "en" else None
        name = public_name(
            indicator.name,
            (overlay or {}).get("name") or indicator.name_en,
            locale=loc,
        )
        png = render_indicator_og(
            code=code,
            name=name,
            value_text=core_number,
            date_text=date_text,
            values=values,
            x_labels=x_labels,
            period_text=ctx["period_text"],
            subtitle=ctx["subtitle"],
            context_pill=ctx["context_pill"],
            unit_suffix=ctx["unit_suffix"],
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/api/v1/og-image/indicator/{code}/{period}.png",
    include_in_schema=False,
)
async def og_image_indicator_month(code: str, period: str, db: AsyncSession = Depends(get_db)):
    """PNG месячного лендинга /russia/indicator/{code}/{year}-{mm}.

    При ≥2 точках месяца — спарклайн внутри месяца; при одной точке (monthly
    ряд) — окно соседних 12 месяцев по последним точкам каждого месяца.
    Объявлен до годового эндпоинта: FastAPI матчит маршруты по порядку
    объявления, и «2026-07» не должен упасть в годовую ветку.
    """
    import re

    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.i18n_display import public_name
    from app.services.seo_i18n import indicator_copy_en
    from app.services.seo_indicator_month import (
        _month_last_values,
        _neighbor_month_window,
    )

    if not re.fullmatch(r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])", period):
        # Годовой период («2025») летит в этот роут только потому, что FastAPI
        # матчит маршруты по порядку объявления, — делегируем годовому постеру.
        if re.fullmatch(r"(?:19|20)\d{2}", period):
            return await og_image_indicator_year(code, int(period), db)
        return Response(status_code=404)
    year, month = int(period[:4]), int(period[5:])

    loc = get_locale()
    cache_key = f"j6:month:{loc}:{code}:{period}"
    png = cached_og(cache_key)
    if png is None:
        q = await db.execute(
            select(Indicator).where(Indicator.code == code, Indicator.is_active.is_(True))
        )
        indicator = q.scalar_one_or_none()
        if not indicator:
            return Response(status_code=404)
        rows_q = await db.execute(
            select(IndicatorData.value, IndicatorData.date)
            .where(
                IndicatorData.indicator_id == indicator.id,
                func.extract("year", IndicatorData.date) == year,
                func.extract("month", IndicatorData.date) == month,
            )
            .order_by(IndicatorData.date)
        )
        rows = rows_q.all()
        if not rows:
            return Response(status_code=404)

        last_value, last_date = rows[-1]
        unit = (indicator.unit or "").strip()
        value_text = display_value_text(code, last_value, unit, indicator.frequency, locale=loc)
        period_text = format_month_year(last_date, locale=loc) or period
        is_cpi = is_cpi_index(code)

        if len(rows) >= 2:
            values = [
                v if (v := display_value(code, raw)) is not None else 0.0
                for raw, _d in rows
            ]
            x_labels = (rows[0][1].strftime("%d.%m"), last_date.strftime("%d.%m"))
        else:
            # Одна точка за месяц: окно соседних месяцев (одна точка на
            # графике бессодержательна — та же логика, что у годового постера).
            by_month = await _month_last_values(db, indicator.id)
            window = _neighbor_month_window(by_month, year, month)
            if len(window) < 2:
                shown = display_value(code, float(last_value))
                values = [shown if shown is not None else 0.0] * 2
                x_labels = (period, period)
            else:
                values = [
                    v if (v := display_value(code, by_month[key][0])) is not None else 0.0
                    for key in window
                ]
                x_labels = window_x_labels(by_month[window[0]][1], by_month[window[-1]][1], locale=loc)

        shown_last = display_value(code, last_value)
        core_number = fmt_signed(shown_last) if shown_last is not None else value_text
        overlay = indicator_copy_en(code) if loc == "en" else None
        name = public_name(
            indicator.name,
            (overlay or {}).get("name") or indicator.name_en,
            locale=loc,
        )
        png = render_indicator_og(
            code=cache_key,
            name=name,
            value_text=core_number,
            date_text=f"на {format_date_locale(last_date, locale=loc)}",
            values=values,
            period_text=period_text,
            x_labels=x_labels,
            subtitle=_og_monthly_subtitle(loc) if is_cpi else None,
            unit_suffix="%" if (unit == "%" or is_cpi) else None,
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/indicator/{code}/{year}.png", include_in_schema=False)
async def og_image_indicator_year(code: str, year: int, db: AsyncSession = Depends(get_db)):
    """PNG-превью индикатора за конкретный год для годовой landing-страницы.

    При ≥2 точках за год — спарклайн внутри года. При одной точке (годовые ряды)
    рисуем окно соседних лет: одна точка на графике бессмысленна, а контекст
    истории остаётся содержательным для Алисы/Нейро.
    """
    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.i18n_display import public_name
    from app.services.seo_i18n import indicator_copy_en
    from app.services.seo_renderer import (
        neighbor_year_window,
        yearly_last_points,
    )
    from app.services.site_urls import YEAR_LANDING_MIN_POINTS

    loc = get_locale()
    cache_key = f"j6:{loc}:{code}:{year}"
    png = cached_og(cache_key)
    if png is None:
        q = await db.execute(
            select(Indicator).where(Indicator.code == code, Indicator.is_active.is_(True))
        )
        indicator = q.scalar_one_or_none()
        if not indicator:
            return Response(status_code=404)
        rows_q = await db.execute(
            select(IndicatorData.value, IndicatorData.date)
            .where(
                IndicatorData.indicator_id == indicator.id,
                func.extract("year", IndicatorData.date) == year,
            )
            .order_by(IndicatorData.date)
        )
        rows = rows_q.all()
        if len(rows) < YEAR_LANDING_MIN_POINTS:
            return Response(status_code=404)
        raw_values = [float(v) for v, _ in rows]
        first_date = rows[0][1]
        last_value, last_date = rows[-1]
        unit = (indicator.unit or "").strip()
        is_cpi = is_cpi_index(code)
        # Display-adapter: спарклайн и подписи в пользовательской семантике
        # (CPI — изменение цен), годовой итог — по природе ряда (сумма для
        # потоков, конец года для запасов, цепной рост для CPI), а не
        # «среднее за год» для всего подряд.
        summary_label, summary_text = annual_summary(code, raw_values, unit)
        value_text = display_value_text(code, last_value, unit, indicator.frequency, locale=loc)
        if loc == "en":
            date_text = f"{_annual_summary_label_en(summary_label)} \u2014 {summary_text}"
        else:
            date_text = f"{summary_label.lower()} \u2014 {summary_text}"

        if len(rows) >= 2:
            values = [
                v if (v := display_value(code, raw)) is not None else 0.0
                for raw in raw_values
            ]
            x_labels = (first_date.strftime("%d.%m"), last_date.strftime("%d.%m"))
        else:
            # Одна точка за год: график соседних лет (иначе area-chart пустой).
            series = await yearly_last_points(db, indicator.id)
            window = neighbor_year_window(series, year, size=10)
            if len(window) < 2:
                # Крайний случай — совсем короткая история: дублируем точку,
                # чтобы превью не 404ило (страница при этом уже 200).
                shown = display_value(code, float(last_value))
                values = [shown if shown is not None else 0.0] * 2
                x_labels = (str(year), str(year))
            else:
                values = [
                    v if (v := display_value(code, raw)) is not None else 0.0
                    for _y, raw, _d in window
                ]
                x_labels = (str(window[0][0]), str(window[-1][0]))
            # Подпись даты — изменение к прошлому году, если есть.
            prev = next((raw for y, raw, _d in series if y == year - 1), None)
            compare = None
            if prev is not None:
                cur_s = display_value(code, float(last_value))
                prev_s = display_value(code, float(prev))
                if cur_s is not None and prev_s is not None and prev_s != 0:
                    pct = ((cur_s - prev_s) / abs(prev_s)) * 100.0
                    if loc == "en":
                        compare = f"vs {year - 1} \u2014 {_fmt_yoy_en(pct)}"
                    else:
                        compare = (
                            f"к {year - 1} году \u2014 "
                            f"{format_number_ru(pct, signed=True, locale=loc)} %"
                        )
            if compare is not None:
                date_text = compare

        shown_last = display_value(code, last_value)
        year_number = fmt_signed(shown_last) if shown_last is not None else value_text
        year_unit = "%" if (unit == "%" or is_cpi) else None
        year_pill = None
        if is_cpi and len(raw_values) >= 2:
            yoy = 1.0
            for raw in raw_values:
                yoy *= float(raw) / 100.0
            pct = (yoy - 1.0) * 100.0
            year_pill = (
                f"Over {year} \u2014 {fmt_yoy(pct)}%"
                if loc == "en"
                else f"За {year} год \u2014 {fmt_yoy(pct)}%"
            )
        overlay = indicator_copy_en(code) if loc == "en" else None
        name = public_name(
            indicator.name,
            (overlay or {}).get("name") or indicator.name_en,
            locale=loc,
        )
        png = render_indicator_og(
            code=code,
            name=name,
            value_text=year_number,
            date_text=date_text,
            values=values,
            period_text=f"{year} год",
            x_labels=x_labels,
            subtitle=_og_monthly_subtitle(loc) if is_cpi else None,
            context_pill=year_pill,
            unit_suffix=year_unit,
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/region/{slug}/{code}.png", include_in_schema=False)
async def og_image_region_indicator(slug: str, code: str, db: AsyncSession = Depends(get_db)):
    """PNG-график регионального показателя: og:image + видимый <img> SSR-страницы."""
    from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN
    from app.data.i18n.regions_en import REGIONS_EN
    from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint
    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.seo_regional import _fmt as _fmt_ru

    loc = get_locale()
    cache_key = f"region:{loc}:{slug}:{code}"
    png = cached_og(cache_key)
    if png is None:
        region = (await db.execute(
            select(Region).where(Region.slug == slug)
        )).scalar_one_or_none()
        indicator = (await db.execute(
            select(RegionIndicator).where(RegionIndicator.code == code)
        )).scalar_one_or_none()
        if not region or not indicator:
            return Response(status_code=404)
        # месячные витрины приоритетнее годовых: у показателя заполнена одна из таблиц
        mrows = (await db.execute(
            select(RegionMonthlyPoint.month, RegionMonthlyPoint.value)
            .where(RegionMonthlyPoint.indicator_id == indicator.id,
                   RegionMonthlyPoint.region_id == region.id)
            .order_by(RegionMonthlyPoint.month)
        )).all()
        if mrows:
            values = [float(v) for _m, v in mrows]
            first_p, last_p = mrows[0][0], mrows[-1][0]
            months_ru = (
                "января", "февраля", "марта", "апреля", "мая", "июня",
                "июля", "августа", "сентября", "октября", "ноября", "декабря",
            )
            date_text = (
                f"{months_ru[last_p % 100 - 1]} {last_p // 100}"
                if loc != "en" else f"{last_p % 100:02d}/{last_p // 100}"
            )
            x_labels = (f"{first_p // 100}", f"{last_p // 100}")
            unit = (indicator.unit or "").strip()
            if loc == "en":
                value_text = f"{format_number_ru(values[-1], locale='en')} {unit}".strip()
                ind_name = (REGION_INDICATORS_EN.get(code) or {}).get("name") or indicator.name
                region_name = REGIONS_EN.get(slug) or region.name
            else:
                value_text = f"{_fmt_ru(values[-1])} {unit}".strip()
                ind_name, region_name = indicator.name, region.name
            png = render_indicator_og(
                code=cache_key,
                name=f"{ind_name} \u2014 {region_name}",
                value_text=value_text,
                date_text=date_text,
                values=values,
                x_labels=x_labels,
                period_text="помесячно" if loc != "en" else "monthly",
            )
            store_og(cache_key, png)
            return Response(
                content=png,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=3600"},
            )
        rows = (await db.execute(
            select(RegionDataPoint.year, RegionDataPoint.value)
            .where(RegionDataPoint.indicator_id == indicator.id,
                   RegionDataPoint.region_id == region.id)
            .order_by(RegionDataPoint.year)
        )).all()
        if len(rows) < 2:
            return Response(status_code=404)
        values = [float(v) for _y, v in rows]
        unit = (indicator.unit or "").strip()
        if loc == "en":
            value_text = f"{format_number_ru(values[-1], locale='en')} {unit}".strip()
            ind_name = (REGION_INDICATORS_EN.get(code) or {}).get("name") or indicator.name
            region_name = REGIONS_EN.get(slug) or region.name
        else:
            value_text = f"{_fmt_ru(values[-1])} {unit}".strip()
            ind_name, region_name = indicator.name, region.name
        png = render_indicator_og(
            code=cache_key,
            name=f"{ind_name} \u2014 {region_name}",
            value_text=value_text,
            date_text=f"{rows[-1][0]} год",
            values=values,
            x_labels=(str(rows[0][0]), str(rows[-1][0])),
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/api/v1/og-image/region/{slug}/{code}/{year}.png",
    include_in_schema=False,
)
async def og_image_region_indicator_year(
    slug: str, code: str, year: int, db: AsyncSession = Depends(get_db)
):
    """PNG годового лендинга региона /russia/region/{slug}/{code}/{year}.

    Региональные ряды — годовые (одна точка на год): рисуем окно соседних
    лет вокруг выбранного года и изменение к прошлому году, иначе график из
    одной точки бессодержателен для Алисы/Нейро.
    """
    from app.models import Region, RegionDataPoint, RegionIndicator
    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.seo_i18n import (
        region_display_name,
        region_indicator_copy,
    )
    from app.services.seo_renderer import neighbor_year_window

    loc = get_locale()
    cache_key = f"j6:ryear:{loc}:{slug}:{code}:{year}"
    png = cached_og(cache_key)
    if png is None:
        region = (
            await db.execute(select(Region).where(Region.slug == slug))
        ).scalar_one_or_none()
        indicator = (
            await db.execute(
                select(RegionIndicator).where(
                    RegionIndicator.code == code,
                    RegionIndicator.is_listed.is_(True),
                )
            )
        ).scalar_one_or_none()
        if region is None or indicator is None:
            return Response(status_code=404)

        # Ряд одноточечный на год: держим даты виртуальными (31 декабря),
        # чтобы neighbor_year_window получил ожидаемую форму (y, v, d).
        series_pairs = [
            (int(y), float(v), date(int(y), 12, 31))
            for y, v in (
                await db.execute(
                    select(RegionDataPoint.year, RegionDataPoint.value)
                    .where(
                        RegionDataPoint.indicator_id == indicator.id,
                        RegionDataPoint.region_id == region.id,
                    )
                    .order_by(RegionDataPoint.year)
                )
            ).all()
        ]
        if len(series_pairs) < 2 or not any(y == year for y, _v, _d in series_pairs):
            return Response(status_code=404)

        window = neighbor_year_window(series_pairs, year, size=10)
        values = [v for _y, v, _d in window]
        x_labels = (str(window[0][0]), str(window[-1][0]))

        unit_raw = (indicator.unit or "").strip()
        copy = region_indicator_copy(
            code, name_ru=indicator.name, unit_ru=unit_raw, locale=loc
        )
        unit = (copy["unit"] or "").strip()
        last_value = next(v for y, v, _d in series_pairs if y == year)
        value_text = f"{format_number_ru(last_value, locale=loc)} {unit}".strip()
        prev_value = next((v for y, v, _d in series_pairs if y == year - 1), None)
        compare = (
            _og_annual_compare(year, prev_value, last_value, locale=loc)
            if prev_value is not None
            else None
        )
        date_text = compare or (
            str(year) if loc == "en" else f"{year} год"
        )

        ind_name = copy["name"] or indicator.name
        region_name = region_display_name(slug, region.name)
        png = render_indicator_og(
            code=cache_key,
            name=f"{ind_name} \u2014 {region_name}",
            value_text=value_text,
            date_text=date_text,
            values=values,
            x_labels=x_labels,
            period_text=str(year) if loc == "en" else f"{year} год",
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/region-rating/{code}.png", include_in_schema=False)
async def og_image_region_rating(code: str, db: AsyncSession = Depends(get_db)):
    """PNG-барчарт рейтинга регионов: og:image + видимый <img> на /region-rating."""
    from app.data.region_indicator_polarity import (
        region_rating_is_achievement,
        region_rating_order_by,
    )
    from app.models import Region, RegionDataPoint, RegionIndicator
    from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN
    from app.services.locale import get_locale
    from app.services.og_image import cached_og, render_rating_og, store_og

    loc = get_locale()
    cache_key = f"rating:v2:{loc}:{code}"
    png = cached_og(cache_key)
    if png is None:
        indicator = (await db.execute(
            select(RegionIndicator).where(RegionIndicator.code == code)
        )).scalar_one_or_none()
        if not indicator:
            return Response(status_code=404)
        last_year = (await db.execute(
            select(func.max(RegionDataPoint.year))
            .join(Region, Region.id == RegionDataPoint.region_id)
            .where(RegionDataPoint.indicator_id == indicator.id, Region.kind == "region")
        )).scalar_one_or_none()
        if last_year is None:
            return Response(status_code=404)
        rows = (await db.execute(
            select(Region.name, RegionDataPoint.value)
            .join(Region, Region.id == RegionDataPoint.region_id)
            .where(RegionDataPoint.indicator_id == indicator.id,
                   RegionDataPoint.year == last_year,
                   Region.kind == "region")
            .order_by(region_rating_order_by(
                RegionDataPoint.value, indicator.code, indicator.table_code
            ))
        )).all()
        if len(rows) < 5:
            return Response(status_code=404)
        achievement = region_rating_is_achievement(indicator.code, indicator.table_code)
        # Подпись порядка: RU — прежние строки, EN — лексика _rating_copy
        # («regions with the best/largest values») без новых переводов.
        order_label = (
            ("best values" if achievement else "largest values")
            if loc == "en"
            else ("лучшие значения" if achievement else "наибольшие значения")
        )
        png = render_rating_og(
            name=(REGION_INDICATORS_EN.get(indicator.code) or {}).get("name")
            or indicator.name,
            year=int(last_year),
            unit=(indicator.unit or "").strip(),
            rows=[(n, float(v)) for n, v in rows],
            total=len(rows),
            order_label=order_label,
            locale=loc,
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/today.png", include_in_schema=False)
async def og_image_today_hub(db: AsyncSession = Depends(get_db)):
    """PNG-сводка «Экономика России сегодня» для хаба /today."""
    from app.services.og_image import cached_og, render_today_hub_og, store_og
    from app.services.seo_i18n import today_spec_en
    from app.services.seo_today import (
        TODAY_CODES, TODAY_SPECS, _format_number, _indicator_with_rows, _locale_date,
    )
    from datetime import date as _date

    loc = get_locale()
    cache_key = f"today-hub:{loc}"
    png = cached_og(cache_key)
    if png is None:
        items: list[tuple[str, str]] = []
        for code in TODAY_CODES:
            spec = TODAY_SPECS[code]
            indicator, rows = await _indicator_with_rows(db, spec.series_code, limit=1)
            if indicator is None or not rows:
                continue
            en_overlay = today_spec_en(code) if loc == "en" else None
            query = (en_overlay or {}).get("query") or spec.query
            unit = (indicator.unit or "").strip()
            items.append((query, f"{_format_number(rows[0].value)} {unit}".strip()))
        if not items:
            return Response(status_code=404)
        png = render_today_hub_og(
            date_text=_locale_date(_date.today()), items=items, locale=loc,
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/region-vs/{slug_a}-vs-{slug_b}.png", include_in_schema=False)
async def og_image_region_vs(slug_a: str, slug_b: str, db: AsyncSession = Depends(get_db)):
    """PNG-таблица сравнения двух регионов для /region-vs."""
    from app.services.og_image import cached_og, render_region_vs_og, store_og
    from app.services.region_compare_data import build_region_compare_payload
    from app.services.seo_regional import _fmt as _fmt_ru

    loc = get_locale()
    # Payload строится по get_locale() (имена регионов: REGIONS_EN на EN),
    # поэтому локаль обязана быть в ключе — иначе залипает язык картинки.
    cache_key = f"vs:{loc}:{slug_a}:{slug_b}"
    png = cached_og(cache_key)
    if png is None:
        payload = await build_region_compare_payload(slug_a, slug_b, db)
        if payload is None:
            return Response(status_code=404)

        _UNIT_SHORT = {
            "тысяч человек": "тыс. чел.",
            "в процентах": "%",
            "рублей": "руб.",
            "миллионов рублей": "млн руб.",
        }

        def _vu(v, unit):
            v = float(v)
            u = (unit or "").strip()
            # ВРП/инвестиции в «миллионах рублей» — конвертируем в трлн/млрд,
            # иначе «32 339 002 миллионов рублей» не влезает в колонку картинки.
            if u == "миллионов рублей":
                if abs(v) >= 1_000_000:
                    return f"{_fmt_ru(round(v / 1_000_000, 1))} трлн руб."
                if abs(v) >= 1_000:
                    return f"{_fmt_ru(round(v / 1_000, 1))} млрд руб."
            return f"{_fmt_ru(v)} {_UNIT_SHORT.get(u, u)}".strip()

        rows = [
            (r["name"], _vu(r["a"]["value"], r["unit"]), _vu(r["b"]["value"], r["unit"]))
            for r in payload["rows"]
        ]
        if not rows:
            return Response(status_code=404)
        png = render_region_vs_og(
            name_a=payload["region_a"]["name"],
            name_b=payload["region_b"]["name"],
            rows=rows,
            eyebrow_label=(
                "comparing Russian regions" if loc == "en" else "сравнение регионов"
            ),
            title_separator=" and " if loc == "en" else " и ",
            footer_note="Rosstat data" if loc == "en" else "данные Росстата",
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/api/v1/og-image/world-vs/{slug_a}-vs-{slug_b}/{concept_slug}.png",
    include_in_schema=False,
)
async def og_image_world_vs(
    slug_a: str, slug_b: str, concept_slug: str, db: AsyncSession = Depends(get_db)
):
    """PNG-таблица сравнения двух стран для /{a}-vs-{b}/{concept}.

    Строится тем же сопоставимым срезом, что SSR-страница (seo_world_compare):
    concept-контракт или национальный crosswalk, режим уровня/изменения за
    год решает движок рейтингов. Декларирован до /og-image/world/{slug}.png —
    иначе FastAPI отдал бы путь страны «france-vs-germany» в карточку страны.
    """
    from app.data.world_concepts import CONCEPT_BY_SLUG, concept_public_name, concept_public_unit
    from app.database import async_session
    from app.models import WorldCountry
    from app.services.og_image import cached_og, render_region_vs_og, store_og
    from app.services.seo_world import _country_label, _fmt
    from app.services.seo_world_compare import (
        _fetch_compare_candidates,
        _load_pair_series,
        _match_concept_pair,
    )
    from app.services.world_rank_values import (
        apply_rank_series,
        ranking_display_name,
        ranking_public_unit,
        ranking_value_mode,
    )

    loc = get_locale()
    en = loc == "en"
    canon_a, canon_b = sorted((slug_a, slug_b))
    cache_key = f"vs:{loc}:{canon_a}:{canon_b}:{concept_slug}"
    png = cached_og(cache_key)
    if png is None:
        concept = CONCEPT_BY_SLUG.get(concept_slug)
        if concept is None or "compare" not in concept.enabled_surfaces:
            return Response(status_code=404)

        async def _build(session: AsyncSession) -> Response:
            country_a = (await session.execute(
                select(WorldCountry).where(
                    WorldCountry.slug == slug_a, WorldCountry.is_active.is_(True)
                )
            )).scalar_one_or_none()
            country_b = (await session.execute(
                select(WorldCountry).where(
                    WorldCountry.slug == slug_b, WorldCountry.is_active.is_(True)
                )
            )).scalar_one_or_none()
            if country_a is None or country_b is None or slug_a == slug_b:
                return Response(status_code=404)
            candidates = await _fetch_compare_candidates(session, country_a, country_b)
            ind_a, ind_b = _match_concept_pair(candidates, concept, country_a, country_b)
            if ind_a is None or ind_b is None:
                return Response(status_code=404)
            raw_a, raw_b = await _load_pair_series(session, ind_a, ind_b)
            mode = ranking_value_mode(
                concept.slug, ((country_a, ind_a), (country_b, ind_b))
            )
            series_a = apply_rank_series(raw_a, mode)
            series_b = apply_rank_series(raw_b, mode)
            if len(series_a) < 2 or len(series_b) < 2:
                return Response(status_code=404)

            unit_ru = ranking_public_unit(
                mode, concept_public_unit(concept, locale="ru"), locale="ru"
            )
            unit = ranking_public_unit(
                mode, concept_public_unit(concept, locale=loc), locale=loc
            )
            pct_like = mode == "yoy" or unit_ru.strip().startswith("%")
            name = ranking_display_name(
                mode, concept.slug, concept_public_name(concept, locale=loc), locale=loc,
            )

            def _val(series: list[tuple]) -> str:
                value = series[-1][1]
                return f"{_fmt(value)}%" if pct_like else f"{_fmt(value)} {unit}".strip()

            rows = [(
                name,
                _val(series_a),
                _val(series_b),
            )]
            diff = series_a[-1][1] - series_b[-1][1]
            if abs(diff) >= 5e-9:
                diff_sfx = (
                    (" п.п." if not en else " pp") if pct_like else f" {unit}"
                )
                leader = (
                    _country_label(country_a) if diff > 0 else _country_label(country_b)
                )
                rows.append((
                    "Разница" if not en else "Difference",
                    f"+{_fmt(abs(diff))}{diff_sfx} — {leader}",
                    "",
                ))
            png = render_region_vs_og(
                name_a=_country_label(country_a),
                name_b=_country_label(country_b),
                rows=rows,
                eyebrow_label="сравнение стран" if not en else "country comparison",
                footer_note="forecasteconomy.com",
            )
            store_og(cache_key, png)
            return Response(
                content=png,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=3600"},
            )

        async with async_session() as session:
            return await _build(session)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/world/{slug}.png", include_in_schema=False)
async def og_image_world_country(slug: str, db: AsyncSession = Depends(get_db)):
    """PNG-сводка страны для /world/{slug}: og:image + видимый <img> SSR."""
    from app.data.eurostat_units_ru import unit_suffix
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator
    from app.services.display import format_number_ru, localize_unit
    from app.services.og_image import cached_og, render_world_country_og, store_og

    loc = get_locale()
    cache_key = f"world:{loc}:{slug}"
    png = cached_og(cache_key)
    if png is None:
        country = (
            await db.execute(
                select(WorldCountry).where(
                    WorldCountry.slug == slug,
                    WorldCountry.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if country is None:
            return Response(status_code=404)

        inds = (
            await db.execute(
                select(WorldIndicator)
                .where(
                    WorldIndicator.country_id == country.id,
                    WorldIndicator.is_listed.is_(True),
                )
                .order_by(WorldIndicator.points_count.desc(), WorldIndicator.name_ru)
                .limit(12)
            )
        ).scalars().all()
        if not inds:
            return Response(status_code=404)

        ids = [i.id for i in inds]
        rn = func.row_number().over(
            partition_by=WorldDataPoint.indicator_id,
            order_by=WorldDataPoint.date.desc(),
        ).label("rn")
        sub = (
            select(
                WorldDataPoint.indicator_id,
                WorldDataPoint.value,
                rn,
            )
            .where(WorldDataPoint.indicator_id.in_(ids))
            .subquery()
        )
        latest = {
            iid: float(value)
            for iid, value in (
                await db.execute(
                    select(sub.c.indicator_id, sub.c.value).where(sub.c.rn == 1)
                )
            ).all()
        }
        items: list[tuple[str, str]] = []
        for ind in inds:
            if ind.id not in latest:
                continue
            if loc == "en":
                unit_raw = (ind.unit_ru or ind.unit or "").strip()
                unit = localize_unit(unit_suffix(unit_raw)) or unit_raw
                label = (ind.name_en or "").strip() or ind.name_ru
            else:
                unit = unit_suffix((ind.unit_ru or ind.unit or "").strip())
                label = ind.name_ru
            label = label if len(label) <= 42 else label[:41] + "…"
            value_text = f"{format_number_ru(latest[ind.id], locale=loc)} {unit}".strip()
            items.append((label, value_text))
            if len(items) >= 6:
                break
        if not items:
            return Response(status_code=404)

        n_listed = (
            await db.execute(
                select(func.count()).select_from(WorldIndicator).where(
                    WorldIndicator.country_id == country.id,
                    WorldIndicator.is_listed.is_(True),
                )
            )
        ).scalar() or len(inds)

        if loc == "en":
            png = render_world_country_og(
                country_name=country.name_en,
                indicators_count=int(n_listed),
                items=items,
                eyebrow_label="world economy",
                title_template="Economy of {country}",
                count_template=f"{int(n_listed)} indicators — Eurostat",
                footer_note="official Eurostat data",
            )
        else:
            from app.services.seo_world import _genitive

            png = render_world_country_og(
                country_name=_genitive(country),
                indicators_count=int(n_listed),
                items=items,
            )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/world-rating/{concept_slug}.png", include_in_schema=False)
async def og_image_world_rating(concept_slug: str, db: AsyncSession = Depends(get_db)):
    """PNG-барчарт рейтинга стран: og:image + видимый <img> на /world/rating."""
    from app.data.eurostat_units_ru import unit_suffix
    from app.services.og_image import cached_og, render_world_rating_og, store_og
    from app.services.seo_world import build_world_rating_payload

    loc = get_locale()
    cache_key = f"world-rating:{loc}:{concept_slug}"
    png = cached_og(cache_key)
    if png is None:
        payload = await build_world_rating_payload(concept_slug, db)
        if not payload or not payload["items"]:
            return Response(status_code=404)
        concept = payload["concept"]
        # Подпись порядка: RU — прежние формулировки, EN — лексика
        # world.rating.sortAsc/sortDesc из существующего словаря.
        if loc == "en":
            order_label = (
                "ascending" if concept["default_sort"] == "asc" else "descending"
            )
        else:
            order_label = (
                "по возрастанию"
                if concept["default_sort"] == "asc"
                else "по убыванию"
            )
        unit = concept["unit"]
        if loc != "en":
            unit = unit_suffix(unit) or unit
        png = render_world_rating_og(
            name=concept["name"],
            year=int(payload["active_year"]),
            unit=unit,
            rows=[
                (item["country_name"], float(item["value"]))
                for item in payload["items"]
            ],
            total=int(payload["coverage"]["with_data"]),
            order_label=order_label,
            locale=loc,
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/api/v1/og-image/world-rating/{concept_slug}/{year}.png", include_in_schema=False
)
async def og_image_world_rating_year(
    concept_slug: str, year: str, db: AsyncSession = Depends(get_db)
):
    """PNG-барчарт рейтинга за конкретный год: og:image годовой страницы рейтинга.

    Годовая OG-картинка обязана показывать свой год: Алиса/Нейро берут картинку
    из DOM страницы — несовпадение года на картинке и в таблице = обман среза.
    """
    if not re.fullmatch(r"(?:19|20)\d{2}", year):
        return Response(status_code=404)
    from app.data.eurostat_units_ru import unit_suffix
    from app.services.og_image import cached_og, render_world_rating_og, store_og
    from app.services.seo_world import build_world_rating_payload

    loc = get_locale()
    cache_key = f"world-rating:{loc}:{concept_slug}:{year}"
    png = cached_og(cache_key)
    if png is None:
        payload = await build_world_rating_payload(
            concept_slug, db, year=int(year)
        )
        if not payload or not payload["items"]:
            return Response(status_code=404)
        if int(payload["active_year"]) != int(year):
            # Запрошенный год не имеет данных — 404, а не картинка чужого года.
            return Response(status_code=404)
        concept = payload["concept"]
        if loc == "en":
            order_label = (
                "ascending" if concept["default_sort"] == "asc" else "descending"
            )
        else:
            order_label = (
                "по возрастанию"
                if concept["default_sort"] == "asc"
                else "по убыванию"
            )
        unit = concept["unit"]
        if loc != "en":
            unit = unit_suffix(unit) or unit
        png = render_world_rating_og(
            name=concept["name"],
            year=int(year),
            unit=unit,
            rows=[
                (item["country_name"], float(item["value"]))
                for item in payload["items"]
            ],
            total=int(payload["coverage"]["with_data"]),
            order_label=order_label,
            locale=loc,
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/world/{slug}/{code}.png", include_in_schema=False)
async def og_image_world_indicator(
    slug: str, code: str, db: AsyncSession = Depends(get_db)
):
    """PNG-график мирового показателя: og:image + видимый <img> SSR-страницы."""
    from app.data.eurostat_units_ru import unit_suffix
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator
    from app.services.og_image import cached_og, render_indicator_og, store_og

    loc = get_locale()
    cache_key = f"world:{loc}:{slug}:{code}"
    png = cached_og(cache_key)
    if png is None:
        country = (
            await db.execute(
                select(WorldCountry).where(
                    WorldCountry.slug == slug,
                    WorldCountry.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        indicator = (
            await db.execute(
                select(WorldIndicator).where(
                    WorldIndicator.code == code,
                    WorldIndicator.is_listed.is_(True),
                )
            )
        ).scalar_one_or_none()
        if (
            country is None
            or indicator is None
            or indicator.country_id != country.id
        ):
            return Response(status_code=404)
        rows = (
            await db.execute(
                select(WorldDataPoint.date, WorldDataPoint.value)
                .where(WorldDataPoint.indicator_id == indicator.id)
                .order_by(WorldDataPoint.date)
            )
        ).all()
        if len(rows) < 2:
            return Response(status_code=404)
        values = [float(v) for _d, v in rows]
        unit = unit_suffix((indicator.unit_ru or indicator.unit or "").strip())
        value_text = f"{format_number_ru(values[-1], locale=loc)} {unit}".strip()
        last_date = rows[-1][0]
        first_date = rows[0][0]
        date_text = format_month_year(last_date, locale=loc) or last_date.isoformat()

        if loc == "en":
            # EN: предложный падеж не нужен — просто «in {Name}»; имя берём
            # только у curated/composed рядов, «сырое» eurostat-имя не показываем.
            en_ok = (
                indicator.name_quality in ("curated", "composed")
                and (indicator.name_en or "").strip()
            )
            subject = (indicator.name_en.strip() if en_ok else None) \
                or _world_subject(indicator.name_ru)
            name = f"{subject} in {country.name_en}"
        else:
            from app.data.eurostat_titles_ru import country_prepositional

            subject = _world_subject(indicator.name_ru)
            prep = country_prepositional(country.slug, country.name_ru)
            name = f"{subject} в {prep}"
        png = render_indicator_og(
            code=cache_key,
            name=name,
            value_text=value_text,
            date_text=date_text,
            values=values,
            x_labels=(str(first_date.year), str(last_date.year)),
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/api/v1/og-image/world/{country_slug}/{code}/{year}.png",
    include_in_schema=False,
)
async def og_image_world_indicator_year(
    country_slug: str, code: str, year: int, db: AsyncSession = Depends(get_db)
):
    """PNG годового лендинга мира /{country}/indicator/{code}/{year}.

    При ≥2 точках внутри года — спарклайн года; при одной точке (годовые ряды)
    — окно соседних лет по последним точкам каждого года, иначе график пуст.
    Подписи страны/имени/единицы — те же, что у базового мирового постера.
    """
    from app.data.eurostat_titles_ru import country_prepositional
    from app.data.eurostat_units_ru import unit_suffix
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator
    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.seo_renderer import neighbor_year_window
    from app.services.site_urls import WORLD_YEAR_LANDING_MIN_POINTS

    loc = get_locale()
    cache_key = f"j6:wyear:{loc}:{country_slug}:{code}:{year}"
    png = cached_og(cache_key)
    if png is None:
        country = (
            await db.execute(
                select(WorldCountry).where(
                    WorldCountry.slug == country_slug,
                    WorldCountry.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        indicator = (
            await db.execute(
                select(WorldIndicator).where(
                    WorldIndicator.code == code,
                    WorldIndicator.is_listed.is_(True),
                )
            )
        ).scalar_one_or_none()
        if (
            country is None
            or indicator is None
            or indicator.country_id != country.id
        ):
            return Response(status_code=404)

        rows = (
            await db.execute(
                select(WorldDataPoint.date, WorldDataPoint.value)
                .where(
                    WorldDataPoint.indicator_id == indicator.id,
                    func.extract("year", WorldDataPoint.date) == year,
                )
                .order_by(WorldDataPoint.date)
            )
        ).all()
        if len(rows) < WORLD_YEAR_LANDING_MIN_POINTS:
            return Response(status_code=404)

        unit = unit_suffix((indicator.unit_ru or indicator.unit or "").strip())
        value_text = f"{format_number_ru(float(rows[-1][1]), locale=loc)} {unit}".strip()

        if len(rows) >= 2:
            # Спарклайн внутри года: точки с подписями даты начала и конца.
            values = [float(v) for _d, v in rows]
            x_labels = (
                rows[0][0].strftime("%d.%m"),
                rows[-1][0].strftime("%d.%m"),
            )
            date_text = (
                f"на {format_date_locale(rows[-1][0], locale=loc)}"
                if loc != "en"
                else format_date_locale(rows[-1][0], locale="en")
            )
        else:
            # Одна точка за год: последние точки каждого года всей истории.
            history = (
                await db.execute(
                    select(WorldDataPoint.date, WorldDataPoint.value)
                    .where(WorldDataPoint.indicator_id == indicator.id)
                    .order_by(WorldDataPoint.date)
                )
            ).all()
            last_by_year: dict[int, tuple[float, date]] = {}
            for d, v in history:
                known = last_by_year.get(d.year)
                if known is None or d >= known[1]:
                    last_by_year[d.year] = (float(v), d)
            series_lp = [
                (y, v, d) for y, (v, d) in sorted(last_by_year.items())
            ]
            window = neighbor_year_window(series_lp, year, size=10)
            if len(window) < 2:
                values = [float(rows[-1][1])] * 2
                x_labels = (str(year), str(year))
            else:
                values = [v for _y, v, _d in window]
                x_labels = (str(window[0][0]), str(window[-1][0]))
            prev_value = next(
                (v for y, v, _d in series_lp if y == year - 1), None
            )
            compare = _og_annual_compare(
                year, prev_value, float(rows[-1][1]), locale=loc
            ) if prev_value is not None else None
            date_text = compare or ""

        if loc == "en":
            en_ok = (
                indicator.name_quality in ("curated", "composed")
                and (indicator.name_en or "").strip()
            )
            subject = (indicator.name_en.strip() if en_ok else None) \
                or _world_subject(indicator.name_ru)
            name = f"{subject} in {country.name_en}"
        else:
            subject = _world_subject(indicator.name_ru)
            prep = country_prepositional(country.slug, country.name_ru)
            name = f"{subject} в {prep}"

        png = render_indicator_og(
            code=cache_key,
            name=name,
            value_text=value_text,
            date_text=date_text,
            values=values,
            x_labels=x_labels,
            period_text=str(year) if loc == "en" else f"{year} год",
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _html_response(status_code: int, html: str) -> Response:
    return Response(content=html, status_code=status_code, media_type="text/html; charset=utf-8")


@router.get("/api/v1/og/indicator/{code}", include_in_schema=False)
async def og_indicator(code: str, db: AsyncSession = Depends(get_db)):
    """Backward-compatible social-preview endpoint using the universal renderer."""
    status, html = await render_indicator_html(code, db)
    return _html_response(status, html)


@router.get("/api/v1/og/category/{slug}", include_in_schema=False)
async def og_category(slug: str, db: AsyncSession = Depends(get_db)):
    """Backward-compatible social-preview endpoint using the universal renderer."""
    status, html = await render_category_html(slug, db)
    return _html_response(status, html)


@router.get("/api/v1/og/page/{page}", include_in_schema=False)
async def og_page(page: str, db: AsyncSession = Depends(get_db)):
    """Backward-compatible social-preview endpoint using the universal renderer."""
    if page == "home":
        return _html_response(200, await render_home_html(db))
    status, html = await render_page_html(page)
    return _html_response(status, html)
