"""Universal public SEO HTML endpoints.

These routes are intended to be served to humans and bots alike via nginx.
They return route-specific HTML with enough content for indexing; React then
replaces the prerendered root with the interactive application.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.seo_renderer import (
    render_category_html,
    render_home_html,
    render_indicator_html,
    render_page_html,
)

router = APIRouter(tags=["seo-pages"])


def _html_response(status_code: int, html: str) -> Response:
    return Response(
        content=html,
        status_code=status_code,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/seo/page/home", include_in_schema=False)
async def seo_home(db: AsyncSession = Depends(get_db)):
    return _html_response(200, await render_home_html(db))


@router.get("/seo/page/{page}", include_in_schema=False)
async def seo_page(page: str):
    status, html = await render_page_html(page)
    return _html_response(status, html)


@router.get("/seo/category/{slug}", include_in_schema=False)
async def seo_category(slug: str, db: AsyncSession = Depends(get_db)):
    status, html = await render_category_html(slug, db)
    return _html_response(status, html)


@router.get("/seo/indicator/{code}", include_in_schema=False)
async def seo_indicator(code: str, db: AsyncSession = Depends(get_db)):
    status, html = await render_indicator_html(code, db)
    return _html_response(status, html)
