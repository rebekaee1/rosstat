"""Universal public SEO HTML endpoints.

These routes are intended to be served to humans and bots alike via nginx.
They return route-specific HTML with enough content for indexing; React then
replaces the prerendered root with the interactive application.

ETag: content-hash каждого ответа; роботы с If-None-Match получают 304 и
не тратят crawl budget на неизменившиеся страницы (nginx отдаёт SSR с
no-cache для браузеров, но conditional-запросы ботов проходят насквозь).
"""

import hashlib

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.seo_regional import (
    render_region_html,
    render_region_indicator_html,
    render_regions_home_html,
)
from app.services.seo_renderer import (
    render_category_html,
    render_home_html,
    render_indicator_html,
    render_indicator_year_html,
    render_page_html,
)

router = APIRouter(tags=["seo-pages"])


def _html_response(status_code: int, html: str, request: Request | None = None) -> Response:
    headers = {"Cache-Control": "no-cache"}
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
    status, html = await render_indicator_html(code, db, mode=mode)
    return _html_response(status, html, request)


@router.api_route("/seo/regions", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_regions(request: Request, db: AsyncSession = Depends(get_db)):
    status, html = await render_regions_home_html(db)
    return _html_response(status, html, request)


@router.api_route("/seo/region/{slug}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_region(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    status, html = await render_region_html(slug, db)
    return _html_response(status, html, request)


@router.api_route("/seo/region/{slug}/{code}", methods=["GET", "HEAD"], include_in_schema=False)
async def seo_region_indicator(
    slug: str, code: str, request: Request, db: AsyncSession = Depends(get_db)
):
    status, html = await render_region_indicator_html(slug, code, db)
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
    status, html = await render_indicator_year_html(code, year, db)
    return _html_response(status, html, request)
