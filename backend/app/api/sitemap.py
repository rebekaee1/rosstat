"""Dynamic sitemap.xml generated from active indicators in the database."""
import logging
from datetime import date
from html import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator

logger = logging.getLogger(__name__)
router = APIRouter(tags=["seo"])

DOMAIN = "https://forecasteconomy.com"

STATIC_PAGES = [
    ("/", "daily", "1.0"),
    ("/about", "monthly", "0.5"),
    ("/privacy", "monthly", "0.3"),
    ("/compare", "weekly", "0.6"),
    ("/calendar", "daily", "0.7"),
    ("/calculator", "monthly", "0.6"),
    ("/widgets", "monthly", "0.4"),
    ("/demographics", "monthly", "0.7"),
]

CATEGORIES = [
    "prices", "rates", "labor", "gdp", "finance",
    "trade", "population", "business", "science",
]


@router.get("/sitemap.xml", include_in_schema=False)
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


@router.get("/api/v1/og/indicator/{code}", include_in_schema=False)
async def og_indicator(code: str, db: AsyncSession = Depends(get_db)):
    """Pre-rendered HTML with OG meta tags for social media bots."""
    q = await db.execute(select(Indicator).where(Indicator.code == code))
    indicator = q.scalar_one_or_none()
    if not indicator:
        return Response(content="Not found", status_code=404)

    title = escape(f"{indicator.name} — Forecast Economy")
    desc = escape((indicator.description or f"{indicator.name}: данные и аналитика")[:200])
    url = f"{DOMAIN}/indicator/{escape(code)}"

    html = f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Forecast Economy">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
</head>
<body><h1>{title}</h1><p>{desc}</p></body>
</html>"""
    return Response(content=html, media_type="text/html")
