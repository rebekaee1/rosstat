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
    ("/calculator", "monthly", "0.6"),
    ("/demographics", "monthly", "0.7"),
    # Hidden from nav until ready: /compare, /calendar, /widgets
]

CATEGORIES = [
    "prices", "rates", "labor", "gdp", "finance",
    "trade", "population", "business", "science",
]


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


# og-image-v2: новый URL после ребрендинга RuStats→Forecast Economy,
# чтобы соцсети сбросили закэшированное превью со старым логотипом.
OG_IMAGE = f"{DOMAIN}/og-image-v2.png"

CATEGORY_META = {
    "prices": ("Цены и инфляция в России", "ИПЦ, инфляция, цены на жильё — данные Росстата и прогнозы."),
    "rates": ("Процентные ставки в России", "Ключевая ставка ЦБ, RUONIA, ипотека, депозиты — данные Банка России."),
    "finance": ("Финансы и валюты России", "Курсы валют, золото, денежная масса, кредиты, бюджет — данные ЦБ РФ и Минфина."),
    "labor": ("Рынок труда России", "Безработица, зарплаты, занятость — ежемесячные данные Росстата."),
    "gdp": ("ВВП и экономический рост России", "ВВП, потребление, госрасходы, инвестиции — квартальные данные Росстата."),
    "population": ("Население России", "Численность, рождаемость, смертность, пенсионеры — демографические данные Росстата."),
    "trade": ("Внешняя торговля России", "Экспорт, импорт, торговый баланс, текущий счёт — квартальные данные Банка России."),
    "business": ("Бизнес и инвестиции в России", "ИПП, розничная торговля, ввод жилья, инвестиции — данные Росстата."),
    "science": ("Наука и образование в России", "Аспиранты, организации НИР, инновационная активность — данные Росстата."),
}

PAGE_META = {
    "about": ("О проекте Forecast Economy", "Бесплатная аналитическая платформа макроэкономических данных России. 80+ индикаторов, данные Росстата и ЦБ РФ."),
    "privacy": ("Политика конфиденциальности — Forecast Economy", "Как Forecast Economy обрабатывает данные посетителей."),
    "compare": ("Сравнение индикаторов — Forecast Economy", "Сравнивайте любые два макроэкономических индикатора России на одном графике."),
    "calculator": ("Калькулятор инфляции — Forecast Economy", "Рассчитайте обесценивание денег за любой период. Данные ИПЦ Росстата с 1991 года."),
    "calendar": ("Экономический календарь России — Forecast Economy", "Расписание публикации макроэкономических данных: Росстат, ЦБ РФ, Минфин."),
    "demographics": ("Возрастная структура населения России — Forecast Economy", "Дети, трудоспособные, старше трудоспособного — данные Росстата с 1990 года."),
    "widgets": ("Виджеты Forecast Economy", "Встраиваемые графики, карточки и тикеры для вашего сайта."),
}


def _og_html(title: str, desc: str, url: str) -> str:
    t = escape(title)
    d = escape(desc[:300])
    u = escape(url)
    return f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{u}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{u}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Forecast Economy">
<meta property="og:image" content="{OG_IMAGE}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="ru_RU">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{OG_IMAGE}">
</head>
<body><h1>{t}</h1><p>{d}</p></body>
</html>"""


@router.get("/api/v1/og/indicator/{code}", include_in_schema=False)
async def og_indicator(code: str, db: AsyncSession = Depends(get_db)):
    """Pre-rendered HTML with OG meta tags for social media bots."""
    q = await db.execute(select(Indicator).where(Indicator.code == code))
    indicator = q.scalar_one_or_none()
    if not indicator:
        return Response(content="Not found", status_code=404)

    title = f"{indicator.name} — Forecast Economy"
    desc = (indicator.description or f"{indicator.name}: данные и аналитика")[:300]
    url = f"{DOMAIN}/indicator/{code}"
    return Response(content=_og_html(title, desc, url), media_type="text/html")


@router.get("/api/v1/og/category/{slug}", include_in_schema=False)
async def og_category(slug: str):
    """Pre-rendered HTML with OG meta tags for category pages."""
    meta = CATEGORY_META.get(slug)
    if not meta:
        return Response(content="Not found", status_code=404)
    title, desc = meta
    title = f"{title} — Forecast Economy"
    url = f"{DOMAIN}/category/{slug}"
    return Response(content=_og_html(title, desc, url), media_type="text/html")


@router.get("/api/v1/og/page/{page}", include_in_schema=False)
async def og_page(page: str):
    """Pre-rendered HTML with OG meta tags for static pages."""
    meta = PAGE_META.get(page)
    if not meta:
        return Response(content="Not found", status_code=404)
    title, desc = meta
    url = f"{DOMAIN}/{page}" if page != "home" else DOMAIN
    return Response(content=_og_html(title, desc, url), media_type="text/html")
