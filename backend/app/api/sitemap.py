"""Dynamic sitemap.xml, RSS feed and OG endpoints generated from the database."""
import logging
from datetime import date, datetime, timezone
from email.utils import format_datetime
from html import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData
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


def _sitemap_priority(*, listed: bool, is_indicator: bool) -> str:
    """Приоритет crawl budget: главная и категории выше, derived-sibling ниже."""
    if not is_indicator:
        return "0.8"
    return "0.8" if listed else "0.5"


def _sitemap_lastmod(last_data: date | None, fallback: date) -> str:
    return (last_data or fallback).isoformat()


_SITEMAP_TTL = 6 * 3600


def _render_urlset(urls) -> str:
    entries = "\n".join(
        f"  <url>\n"
        f"    <loc>{DOMAIN}{u.path}</loc>\n"
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
async def sitemap_index(db: AsyncSession = Depends(get_db)):
    """Sitemap-индекс: секции по типам страниц, регионы — чанками по ~10k.

    Секционирование даёт per-file статистику обхода в Вебмастере и честный
    lastmod на каждую часть (регионы обновляются раз в год, «сегодня» — ежедневно).
    """
    from app.core.cache import cache_get, cache_set
    from app.services.site_urls import collect_url_sections

    cached = await cache_get("fe:sitemap:index")
    if cached:
        return Response(content=cached, media_type="application/xml")

    sections = await collect_url_sections(db)
    today = date.today().isoformat()
    entries = "\n".join(
        f"  <sitemap>\n"
        f"    <loc>{DOMAIN}/sitemap-{name}.xml</loc>\n"
        f"    <lastmod>{max((u.lastmod for u in urls), default=today)}</lastmod>\n"
        f"  </sitemap>"
        for name, urls in sections.items()
        if urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + entries
        + "\n</sitemapindex>"
    )
    await cache_set("fe:sitemap:index", xml, _SITEMAP_TTL)
    return Response(content=xml, media_type="application/xml")


@router.api_route("/sitemap-{section}.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap_section(section: str, db: AsyncSession = Depends(get_db)):
    from app.core.cache import cache_get, cache_set
    from app.services.site_urls import collect_url_sections

    cache_key = f"fe:sitemap:section:{section}"
    cached = await cache_get(cache_key)
    if cached:
        return Response(content=cached, media_type="application/xml")

    sections = await collect_url_sections(db)
    urls = sections.get(section)
    if not urls:
        return Response(status_code=404)
    xml = _render_urlset(urls)
    await cache_set(cache_key, xml, _SITEMAP_TTL)
    return Response(content=xml, media_type="application/xml")


@router.api_route("/feed.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def rss_feed(db: AsyncSession = Depends(get_db)):
    """RSS 2.0 — последние обновления данных по listed-индикаторам.

    Item на индикатор: имя + актуальное значение, pubDate = дата последней
    точки. Поисковики и агрегаторы узнают об обновлениях без переобхода.
    """
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
        title = escape(f"{ind.name}: {float(value):.4g} {ind.unit or ''}".strip())
        desc_text = escape(
            f"{ind.name} — значение {float(value):.4g} {ind.unit or ''} на {dt.isoformat()}. "
            f"Источник: {ind.source}."
        )
        link = f"{DOMAIN}/indicator/{ind.code}"
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
        f"  <link>{DOMAIN}</link>\n"
        "  <description>Последние обновления макроэкономических индикаторов России: "
        "Росстат, Банк России, Минфин.</description>\n"
        "  <language>ru</language>\n"
        f'  <atom:link href="{DOMAIN}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(items)
        + "\n</channel>\n</rss>"
    )
    return Response(
        content=xml,
        media_type="application/rss+xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/api/v1/og-image/indicator/{code}.png", include_in_schema=False)
async def og_image_indicator(code: str, db: AsyncSession = Depends(get_db)):
    """PNG-превью индикатора для og:image (спарклайн + актуальное значение)."""
    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.seo_renderer import _format_number  # переиспользуем формат

    png = cached_og(code)
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
        # Превью «representativeOfPage»: вся история, прореженная до ~180 точек
        # (для дневных индексов last-120 показывало бы лишь ~4 месяца и дублировало
        # бы год на обеих X-метках). Форма ряда сохраняется, последняя точка — всегда.
        ordered = rows
        _MAXP = 180
        if len(ordered) > _MAXP:
            step = len(ordered) / _MAXP
            idx = sorted({int(i * step) for i in range(_MAXP)} | {len(ordered) - 1})
            ordered = [ordered[i] for i in idx]
        values = [float(v) for v, _ in ordered]
        current_value, current_date = (rows[-1] if rows else (None, None))
        unit = (indicator.unit or "").strip()
        value_text = (
            f"{_format_number(current_value)} {unit}".strip()
            if current_value is not None
            else "нет данных"
        )
        date_text = f"на {current_date.isoformat()}" if current_date else ""
        x_labels = None
        if len(ordered) >= 2:
            first_d, last_d = ordered[0][1], ordered[-1][1]
            x_labels = (
                (str(first_d.year), str(last_d.year))
                if first_d.year != last_d.year
                else (first_d.strftime("%m.%Y"), last_d.strftime("%m.%Y"))
            )
        png = render_indicator_og(
            code=code,
            name=indicator.name,
            value_text=value_text,
            date_text=date_text,
            values=values,
            x_labels=x_labels,
        )
        store_og(code, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/indicator/{code}/{year}.png", include_in_schema=False)
async def og_image_indicator_year(code: str, year: int, db: AsyncSession = Depends(get_db)):
    """PNG-превью индикатора за конкретный год для годовой landing-страницы.

    Спарклайн строится по точкам именно этого года, в шапке — метка «{year} год».
    Это «полезный материал» для Алисы/Нейро: на запрос «инфляция в 2024» поиск
    Яндекса может показать карточку с графиком за нужный год.
    """
    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.seo_renderer import _format_number

    cache_key = f"{code}:{year}"
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
        if len(rows) < 2:
            return Response(status_code=404)
        values = [float(v) for v, _ in rows]
        first_date = rows[0][1]
        last_value, last_date = rows[-1]
        unit = (indicator.unit or "").strip()
        avg = sum(values) / len(values)
        value_text = f"{_format_number(last_value)} {unit}".strip()
        # Среднее — сырой float (102.4667…); округляем до 2 знаков, чтобы подпись
        # не тащила шум после запятой.
        date_text = f"в среднем {_format_number(round(avg, 2))} {unit}".strip()
        png = render_indicator_og(
            code=code,
            name=indicator.name,
            value_text=value_text,
            date_text=date_text,
            values=values,
            period_text=f"{year} год",
            x_labels=(first_date.strftime("%d.%m"), last_date.strftime("%d.%m")),
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
    from app.models import Region, RegionDataPoint, RegionIndicator
    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.seo_regional import _fmt as _fmt_ru

    cache_key = f"region:{slug}:{code}"
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
        value_text = f"{_fmt_ru(values[-1])} {unit}".strip()
        png = render_indicator_og(
            code=cache_key,
            name=f"{indicator.name} — {region.name}",
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
