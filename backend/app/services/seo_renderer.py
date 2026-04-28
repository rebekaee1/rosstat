"""Universal server-rendered SEO HTML for public pages."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import date
from html import escape
from typing import Iterable

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Indicator, IndicatorData
from app.services.seo_content import (
    CATEGORIES,
    CATEGORY_META,
    DOMAIN,
    GLOBAL_INDICATOR_BLOCKS,
    INDICATOR_BLOCKS,
    OG_IMAGE,
    PAGE_META,
    CategorySeo,
    PageSeo,
    SeoBlock,
)

logger = logging.getLogger(__name__)

TRACKING_PARAMS = [
    "etext", "ybaip", "yclid", "ysclid", "gclid", "fbclid", "_openstat",
    "openstat", "clid", "yandex_referrer", "_ga", "utm_source", "utm_medium",
    "utm_campaign", "utm_term", "utm_content", "utm_referrer", "from", "ref",
    "ref_src", "source", "mc_cid", "mc_eid", "igshid",
]

HIDDEN_FROM_LISTING = {"inflation-annual", "inflation-quarterly", "inflation-weekly"}


@dataclass(frozen=True)
class AppAssets:
    head_links: str
    body_scripts: str


_APP_ASSETS: AppAssets | None = None
_APP_ASSETS_EXPIRES = 0.0
_APP_ASSETS_TTL = 300


def _fallback_assets() -> AppAssets:
    return AppAssets(
        head_links=(
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Playfair+Display:ital,wght@0,700;1,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">\n'
            '<link rel="icon" href="/favicon.ico" sizes="any">\n'
            '<link rel="icon" type="image/svg+xml" href="/favicon.svg">\n'
            '<link rel="icon" type="image/png" href="/favicon.png" sizes="32x32">'
        ),
        body_scripts='<script type="module" src="/src/main.jsx"></script>',
    )


async def get_app_assets() -> AppAssets:
    """Fetch and cache the built Vite shell assets from the frontend container."""
    global _APP_ASSETS, _APP_ASSETS_EXPIRES
    now = time.monotonic()
    if _APP_ASSETS and now < _APP_ASSETS_EXPIRES:
        return _APP_ASSETS

    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(settings.seo_app_shell_url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        head_links = []
        for link in soup.find_all("link"):
            rel = {r.lower() for r in (link.get("rel") or [])}
            if rel & {"stylesheet", "modulepreload", "preconnect", "icon", "shortcut icon"}:
                head_links.append(str(link))
        body_scripts = []
        for script in soup.find_all("script"):
            if script.get("src") and script.get("type") == "module":
                body_scripts.append(str(script))
        _APP_ASSETS = AppAssets("\n".join(head_links), "\n".join(body_scripts))
        _APP_ASSETS_EXPIRES = now + _APP_ASSETS_TTL
        return _APP_ASSETS
    except Exception as exc:
        logger.warning("Failed to fetch frontend app shell from %s: %s", settings.seo_app_shell_url, exc)
        _APP_ASSETS = _fallback_assets()
        _APP_ASSETS_EXPIRES = now + 30
        return _APP_ASSETS


def clean_text(value: str | None, fallback: str = "") -> str:
    if not value:
        return fallback
    return re.sub(r"\s+", " ", value).strip()


def _format_date(value: date | None) -> str:
    return value.isoformat() if value else "нет данных"


def _format_number(value) -> str:
    if value is None:
        return "нет данных"
    number = float(value)
    if abs(number) >= 1000:
        return f"{number:,.2f}".replace(",", " ")
    return f"{number:.4f}".rstrip("0").rstrip(".")


def _absolute(path: str) -> str:
    if path == "/":
        return DOMAIN
    return f"{DOMAIN}{path}"


def _link(path: str, label: str) -> str:
    return f'<a href="{escape(path)}">{escape(label)}</a>'


def _links_list(links: Iterable[tuple[str, str]]) -> str:
    items = [f"<li>{_link(path, label)}</li>" for path, label in links]
    return "<ul>" + "".join(items) + "</ul>" if items else ""


def _json_script(data: dict) -> str:
    return (
        '<script type="application/ld+json">'
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )


def _breadcrumbs(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index + 1,
                "name": name,
                "item": _absolute(path),
            }
            for index, (path, name) in enumerate(items)
        ],
    }


def _site_json_ld() -> dict:
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": f"{DOMAIN}/#website",
                "url": DOMAIN,
                "name": "Forecast Economy",
                "inLanguage": "ru-RU",
                "publisher": {"@id": f"{DOMAIN}/#organization"},
            },
            {
                "@type": "Organization",
                "@id": f"{DOMAIN}/#organization",
                "name": "Forecast Economy",
                "url": DOMAIN,
                "email": "contact@forecasteconomy.com",
            },
        ],
    }


def _metrika_script() -> str:
    tracking_json = json.dumps(TRACKING_PARAMS, ensure_ascii=False)
    return f"""<script>
(function(m,e,t,r,i,k,a){{m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};m[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){{if(document.scripts[j].src===r){{return;}}}}k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}})(window,document,'script','https://mc.yandex.ru/metrika/tag.js?id=107136069','ym');
ym(107136069,'init',{{defer:true,webvisor:true,clickmap:true,accurateTrackBounce:true,trackLinks:true}});
(function(){{var TRACKING={tracking_json};var search=window.location.search;if(search&&search.length>1){{var params=new URLSearchParams(search);var changed=false;for(var i=0;i<TRACKING.length;i++){{if(params.has(TRACKING[i])){{params.delete(TRACKING[i]);changed=true;}}}}if(changed){{var rest=params.toString();search=rest?'?'+rest:'';}}}}var cleanUrl=window.location.pathname+search+window.location.hash;ym(107136069,'hit',cleanUrl,{{title:document.title,referer:document.referrer}});}})();
</script>"""


async def build_document(
    *,
    title: str,
    description: str,
    canonical_path: str,
    body: str,
    json_ld: list[dict] | None = None,
) -> str:
    assets = await get_app_assets()
    url = _absolute(canonical_path)
    safe_title = escape(title)
    safe_desc = escape(clean_text(description)[:300])
    structured = "\n".join(_json_script(item) for item in (json_ld or []))
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{_metrika_script()}
<title>{safe_title}</title>
<meta name="description" content="{safe_desc}">
<meta name="author" content="Forecast Economy">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">
<meta name="theme-color" content="#F8F9FC">
<meta name="yandex-verification" content="02b4966d46881470">
<link rel="canonical" href="{escape(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Forecast Economy">
<meta property="og:url" content="{escape(url)}">
<meta property="og:title" content="{safe_title}">
<meta property="og:description" content="{safe_desc}">
<meta property="og:locale" content="ru_RU">
<meta property="og:image" content="{OG_IMAGE}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{safe_title}">
<meta name="twitter:description" content="{safe_desc}">
<meta name="twitter:image" content="{OG_IMAGE}">
{assets.head_links}
{structured}
</head>
<body>
<noscript><div><img src="https://mc.yandex.ru/watch/107136069" style="position:absolute; left:-9999px;" alt=""></div></noscript>
<div id="root">{body}</div>
{assets.body_scripts}
</body>
</html>"""


def _blocks_html(blocks: Iterable[SeoBlock]) -> str:
    return "".join(
        f'<section class="seo-section"><h2>{escape(block.title)}</h2><p>{escape(block.body)}</p></section>'
        for block in blocks
    )


def _page_body(page: PageSeo) -> str:
    return f"""<main class="seo-page">
<nav aria-label="Хлебные крошки">{_link("/", "Главная")}</nav>
<h1>{escape(page.h1)}</h1>
<p>{escape(page.intro)}</p>
{_blocks_html(page.blocks)}
<section><h2>Связанные разделы</h2>{_links_list(page.links or tuple((f"/category/{slug}", meta.name) for slug, meta in CATEGORY_META.items()))}</section>
</main>"""


async def render_page_html(page_slug: str) -> tuple[int, str]:
    page = PAGE_META.get(page_slug)
    if not page:
        return 404, "Not found"
    json_ld = [
        _site_json_ld(),
        _breadcrumbs([("/", "Главная"), (page.path, page.h1)]),
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page.title,
            "description": page.description,
            "url": _absolute(page.path),
            "inLanguage": "ru-RU",
            "isPartOf": {"@id": f"{DOMAIN}/#website"},
        },
    ]
    html = await build_document(
        title=page.title,
        description=page.description,
        canonical_path=page.path,
        body=_page_body(page),
        json_ld=json_ld,
    )
    return 200, html


async def render_home_html(db: AsyncSession) -> str:
    indicators = await _active_indicators(db, limit=12)
    category_links = tuple((f"/category/{slug}", meta.name) for slug, meta in CATEGORY_META.items())
    indicator_links = tuple((f"/indicator/{ind.code}", ind.name) for ind in indicators[:8])
    page = PAGE_META["home"]
    body = f"""<main class="seo-page">
<h1>{escape(page.h1)}</h1>
<p>{escape(page.intro)}</p>
<section><h2>Категории</h2>{_links_list(category_links)}</section>
<section><h2>Популярные индикаторы</h2>{_links_list(indicator_links)}</section>
<section><h2>Инструменты</h2>{_links_list(page.links)}</section>
</main>"""
    html = await build_document(
        title=page.title,
        description=page.description,
        canonical_path="/",
        body=body,
        json_ld=[_site_json_ld(), _breadcrumbs([("/", "Главная")])],
    )
    return html


async def _active_indicators(db: AsyncSession, *, limit: int | None = None, category: str | None = None):
    stmt = select(Indicator).where(Indicator.is_active.is_(True)).order_by(Indicator.code)
    if category:
        stmt = stmt.where(Indicator.category == category)
    if limit:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def render_category_html(slug: str, db: AsyncSession) -> tuple[int, str]:
    category = CATEGORY_META.get(slug)
    if not category:
        return 404, "Not found"
    indicators = await _active_indicators(db, category=category.api_category)
    links = tuple((f"/indicator/{ind.code}", ind.name) for ind in indicators)
    body = f"""<main class="seo-page">
<nav aria-label="Хлебные крошки">{_link("/", "Главная")} / {escape(category.name)}</nav>
<h1>{escape(category.title)}</h1>
<p>{escape(category.intro)}</p>
{_blocks_html(category.blocks)}
<section><h2>Индикаторы раздела</h2>{_links_list(links)}</section>
<section><h2>Связанные разделы</h2>{_links_list(_related_categories(slug))}</section>
</main>"""
    json_ld = [
        _site_json_ld(),
        _breadcrumbs([("/", "Главная"), (f"/category/{slug}", category.name)]),
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"{category.title} — Forecast Economy",
            "description": category.description,
            "url": _absolute(f"/category/{slug}"),
            "mainEntity": [
                {"@type": "Dataset", "name": ind.name, "url": _absolute(f"/indicator/{ind.code}")}
                for ind in indicators[:12]
            ],
        },
    ]
    html = await build_document(
        title=f"{category.title} — Forecast Economy",
        description=category.description,
        canonical_path=f"/category/{slug}",
        body=body,
        json_ld=json_ld,
    )
    return 200, html


def _related_categories(current_slug: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (f"/category/{slug}", meta.name)
        for slug, meta in CATEGORY_META.items()
        if slug != current_slug
    )[:6]


async def render_indicator_html(code: str, db: AsyncSession) -> tuple[int, str]:
    q = await db.execute(select(Indicator).where(Indicator.code == code, Indicator.is_active.is_(True)))
    indicator = q.scalar_one_or_none()
    if not indicator:
        return 404, "Not found"
    category = _category_for_api(indicator.category)
    latest_rows = await _latest_rows(db, indicator.id, limit=8)
    count, first_dt, last_dt = await _indicator_stats(db, indicator.id)
    related = await _related_indicators(db, indicator)
    title = f"{indicator.name} — данные, график и прогноз"
    desc = clean_text(indicator.description, f"{indicator.name}: динамика, источник, методология и последние значения.")
    body = _indicator_body(indicator, category, latest_rows, related, count, first_dt, last_dt)
    json_ld = [
        _site_json_ld(),
        _breadcrumbs([
            ("/", "Главная"),
            (f"/category/{category.slug}", category.name) if category else ("/", "Индикаторы"),
            (f"/indicator/{indicator.code}", indicator.name),
        ]),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": indicator.name,
            "description": desc,
            "url": _absolute(f"/indicator/{indicator.code}"),
            "inLanguage": "ru-RU",
            "creator": {"@type": "Organization", "name": indicator.source},
            "temporalCoverage": f"{_format_date(first_dt)}/{_format_date(last_dt)}",
            "variableMeasured": indicator.name,
        },
    ]
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=f"/indicator/{indicator.code}",
        body=body,
        json_ld=json_ld,
    )
    return 200, html


def _category_for_api(api_category: str | None) -> CategorySeo | None:
    for category in CATEGORY_META.values():
        if category.api_category == api_category:
            return category
    return None


async def _latest_rows(db: AsyncSession, indicator_id: int, *, limit: int):
    result = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator_id)
        .order_by(desc(IndicatorData.date))
        .limit(limit)
    )
    return list(result.scalars().all())


async def _indicator_stats(db: AsyncSession, indicator_id: int):
    result = await db.execute(
        select(
            func.count(IndicatorData.id),
            func.min(IndicatorData.date),
            func.max(IndicatorData.date),
        ).where(IndicatorData.indicator_id == indicator_id)
    )
    return result.one()


async def _related_indicators(db: AsyncSession, indicator: Indicator):
    if not indicator.category:
        return []
    result = await db.execute(
        select(Indicator)
        .where(
            Indicator.is_active.is_(True),
            Indicator.category == indicator.category,
            Indicator.code != indicator.code,
        )
        .order_by(Indicator.code)
        .limit(8)
    )
    return list(result.scalars().all())


def _indicator_body(
    indicator: Indicator,
    category: CategorySeo | None,
    latest_rows,
    related,
    count: int,
    first_dt: date | None,
    last_dt: date | None,
) -> str:
    current = latest_rows[0] if latest_rows else None
    category_link = _link(f"/category/{category.slug}", category.name) if category else "Индикаторы"
    data_rows = "".join(
        f"<tr><td>{escape(_format_date(row.date))}</td><td>{escape(_format_number(row.value))}</td></tr>"
        for row in latest_rows
    )
    source_link = _link(indicator.source_url, indicator.source) if indicator.source_url else escape(indicator.source)
    related_links = tuple((f"/indicator/{ind.code}", ind.name) for ind in related)
    blocks = GLOBAL_INDICATOR_BLOCKS + INDICATOR_BLOCKS.get(indicator.code, tuple())
    return f"""<main class="seo-page">
<nav aria-label="Хлебные крошки">{_link("/", "Главная")} / {category_link} / {escape(indicator.name)}</nav>
<h1>{escape(indicator.name)}</h1>
<p>{escape(clean_text(indicator.description, f"{indicator.name}: официальный экономический индикатор с историей значений и графиком."))}</p>
<section><h2>Текущее значение</h2>
<ul>
<li>Последнее значение: {escape(_format_number(current.value if current else None))} {escape(indicator.unit)}</li>
<li>Дата последнего значения: {escape(_format_date(current.date if current else None))}</li>
<li>Периодичность: {escape(indicator.frequency)}</li>
<li>Источник: {source_link}</li>
<li>Количество точек: {int(count)}</li>
<li>Период данных: {escape(_format_date(first_dt))} — {escape(_format_date(last_dt))}</li>
</ul></section>
{_blocks_html(blocks)}
<section><h2>Методология</h2><p>{escape(clean_text(indicator.methodology, "Методология показателя указана по данным официального источника и используется для интерпретации ряда."))}</p></section>
<section><h2>Последние данные</h2><table><thead><tr><th>Дата</th><th>Значение</th></tr></thead><tbody>{data_rows}</tbody></table></section>
<section><h2>Связанные индикаторы</h2>{_links_list(related_links or ((f"/category/{category.slug}", category.name),) if category else tuple())}</section>
</main>"""
