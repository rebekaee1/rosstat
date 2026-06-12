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
from app.services.seo_content import CATEGORIES, CATEGORY_META, DOMAIN, PAGE_META, STATIC_PAGES
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


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap_xml(db: AsyncSession = Depends(get_db)):
    today = date.today()

    urls = []
    for path, freq, priority in STATIC_PAGES:
        urls.append(
            f"  <url>\n"
            f"    <loc>{DOMAIN}{path}</loc>\n"
            f"    <lastmod>{today.isoformat()}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    for slug in CATEGORIES:
        urls.append(
            f"  <url>\n"
            f"    <loc>{DOMAIN}/category/{slug}</loc>\n"
            f"    <lastmod>{today.isoformat()}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n"
            f"    <priority>0.8</priority>\n"
            f"  </url>"
        )

    stmt = (
        select(
            Indicator.code,
            Indicator.is_listed,
            func.max(IndicatorData.date).label("last_data"),
        )
        .outerjoin(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(Indicator.is_active.is_(True))
        .group_by(Indicator.id, Indicator.code, Indicator.is_listed)
        .order_by(Indicator.code)
    )
    rows = (await db.execute(stmt)).all()
    for code, listed, last_data in rows:
        priority = _sitemap_priority(listed=listed, is_indicator=True)
        lastmod = _sitemap_lastmod(last_data, today)
        urls.append(
            f"  <url>\n"
            f"    <loc>{DOMAIN}/indicator/{code}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>daily</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    # Годовые landing-страницы /indicator/{code}/{year}: только listed
    # индикаторы с >= 2 точками за год (см. render_indicator_year_html).
    year_expr = func.extract("year", IndicatorData.date)
    year_stmt = (
        select(Indicator.code, year_expr.label("y"), func.max(IndicatorData.date))
        .join(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(Indicator.is_active.is_(True), Indicator.is_listed.is_(True))
        .group_by(Indicator.code, year_expr)
        .having(func.count(IndicatorData.id) >= 2)
        .order_by(Indicator.code, year_expr)
    )
    year_rows = (await db.execute(year_stmt)).all()
    current_year = today.year
    for code, year, last_data in year_rows:
        year = int(year)
        freq = "weekly" if year == current_year else "yearly"
        urls.append(
            f"  <url>\n"
            f"    <loc>{DOMAIN}/indicator/{code}/{year}</loc>\n"
            f"    <lastmod>{_sitemap_lastmod(last_data, today)}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>0.4</priority>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )

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
            .order_by(desc(IndicatorData.date))
            .limit(120)
        )
        rows = rows_q.all()
        values = [float(v) for v, _ in reversed(rows)]
        current_value, current_date = (rows[0] if rows else (None, None))
        unit = (indicator.unit or "").strip()
        value_text = (
            f"{_format_number(current_value)} {unit}".strip()
            if current_value is not None
            else "нет данных"
        )
        date_text = f"на {current_date.isoformat()}" if current_date else ""
        png = render_indicator_og(
            code=code,
            name=indicator.name,
            value_text=value_text,
            date_text=date_text,
            values=values,
        )
        store_og(code, png)
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
