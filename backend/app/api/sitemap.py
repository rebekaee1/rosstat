"""Dynamic sitemap.xml generated from active indicators in the database."""
import logging
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator
from app.services.seo_content import CATEGORIES, CATEGORY_META, DOMAIN, PAGE_META, STATIC_PAGES
from app.services.seo_renderer import render_category_html, render_home_html, render_indicator_html, render_page_html

logger = logging.getLogger(__name__)
router = APIRouter(tags=["seo"])


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap_xml(db: AsyncSession = Depends(get_db)):
    today = date.today().isoformat()

    urls = []
    for path, freq, priority in STATIC_PAGES:
        urls.append(
            f"  <url>\n"
            f"    <loc>{DOMAIN}{path}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    for slug in CATEGORIES:
        urls.append(
            f"  <url>\n"
            f"    <loc>{DOMAIN}/category/{slug}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>daily</changefreq>\n"
            f"    <priority>0.8</priority>\n"
            f"  </url>"
        )

    q = await db.execute(
        select(Indicator.code)
        .where(Indicator.is_active.is_(True))
        .order_by(Indicator.code)
    )
    for (code,) in q.all():
        urls.append(
            f"  <url>\n"
            f"    <loc>{DOMAIN}/indicator/{code}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>daily</changefreq>\n"
            f"    <priority>0.8</priority>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )

    return Response(content=xml, media_type="application/xml")


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
