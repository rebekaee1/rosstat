"""Universal server-rendered SEO HTML for public pages.

This is the implementation of ADR-0003 (SEO single-source-of-truth):
- Backend renders full HTML with `<title>`, `<meta>`, OG, JSON-LD, visible content.
- Vite asset hashes are discovered at runtime via `__spa-index.html` (TTL 5 min).
- Nginx ALWAYS proxies indexable routes (`/`, `/category/*`, `/indicator/*`,
  `/about|privacy|...`) to backend `/seo/*` — for all User-Agents, not just bots.

Single source of truth for texts: `app/services/seo_content.py`
(`PAGE_META`, `CATEGORY_META`, `GLOBAL_INDICATOR_BLOCKS`) +
`Indicator.seo_blocks` JSONB for per-indicator overrides.

`frontend/src/lib/categories.js` duplicates category texts for in-app UI cards
and MUST stay in sync — see the warning comment in that file and ADR-0003
"Consequences" section.

See `docs/adr/0003-seo-single-source-server-rendered.md`.
"""

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
    OG_IMAGE,
    PAGE_META,
    CategorySeo,
    PageSeo,
    SeoBlock,
)

logger = logging.getLogger(__name__)

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
                "legalName": "ООО «ИИМПАКТ ПЛЮС»",
                "taxID": "9705243471",
                "url": DOMAIN,
                "email": "contact@forecasteconomy.com",
            },
        ],
    }


def _consent_bootstrap() -> str:
    """Consent-bootstrap (152-ФЗ, opt-in) — единая точка загрузки трекеров.

    Яндекс.Метрика и РСЯ загружаются ТОЛЬКО после согласия пользователя.
    Логика (включая очистку URL от tracking-меток) живёт в одном файле
    `frontend/public/consent.js`, который nginx раздаёт как /consent.js
    с no-cache. SPA shell (frontend/index.html) подключает его так же.
    Управление согласием — frontend/src/components/CookieConsent.jsx.
    """
    return '<script src="/consent.js" defer></script>'


DEFAULT_KEYWORDS = (
    "экономика России, макроэкономические данные, Росстат, Банк России, "
    "ВВП, инфляция, ставки, валюты"
)


async def build_document(
    *,
    title: str,
    description: str,
    canonical_path: str,
    body: str,
    json_ld: list[dict] | None = None,
    keywords: str | None = None,
    extra_head: str | None = None,
) -> str:
    assets = await get_app_assets()
    url = _absolute(canonical_path)
    safe_title = escape(title)
    safe_desc = escape(clean_text(description)[:300])
    safe_keywords = escape(clean_text(keywords or DEFAULT_KEYWORDS)[:400])
    structured = "\n".join(_json_script(item) for item in (json_ld or []))
    extras = extra_head or ""
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{_consent_bootstrap()}
<title>{safe_title}</title>
<meta name="description" content="{safe_desc}">
<meta name="keywords" content="{safe_keywords}">
<meta name="author" content="Forecast Economy">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">
<meta name="theme-color" content="#F8F9FC">
<meta name="yandex-verification" content="02b4966d46881470">
<link rel="canonical" href="{escape(url)}">
{extras}
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
<div id="root">{body}</div>
{assets.body_scripts}
</body>
</html>"""


def _blocks_html(blocks: Iterable[SeoBlock]) -> str:
    return "".join(
        f'<section class="seo-section"><h2>{escape(block.title)}</h2><p>{escape(block.body)}</p></section>'
        for block in blocks
    )


def _faq_json_ld(blocks: Iterable[SeoBlock]) -> dict | None:
    """FAQPage structured data из seo-блоков индикатора.

    Заголовок блока трактуется как вопрос, тело — как ответ. Позволяет
    поисковикам распознать Q&A-секцию «О показателе» как структурированные
    вопросы-ответы (rich result), а не просто текст.
    """
    entities = [
        {
            "@type": "Question",
            "name": block.title,
            "acceptedAnswer": {"@type": "Answer", "text": block.body},
        }
        for block in blocks
        if block.title and block.body
    ]
    if len(entities) < 2:
        return None
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities,
    }


def _indicator_blocks_from_db(indicator: Indicator) -> tuple[SeoBlock, ...]:
    """Convert Indicator.seo_blocks (JSON list of dicts) → tuple[SeoBlock]."""
    raw = indicator.seo_blocks
    if not raw or not isinstance(raw, list):
        return tuple()
    out: list[SeoBlock] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or ""
        body = item.get("body") or ""
        if title and body:
            out.append(SeoBlock(title=title, body=body))
    return tuple(out)


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
        keywords=page.keywords or None,
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
        keywords=page.keywords or None,
    )
    return html


async def _active_indicators(
    db: AsyncSession,
    *,
    limit: int | None = None,
    category: str | None = None,
    listed_only: bool = False,
):
    """Active indicators for SEO output.

    listed_only=True фильтрует «скрытые» derived (inflation-quarterly,
    cpi-food-annual, …): они доступны по прямому URL и есть в sitemap, но
    не попадают в листинги категорий — там же, что и UI.
    """
    stmt = select(Indicator).where(Indicator.is_active.is_(True)).order_by(Indicator.code)
    if listed_only:
        stmt = stmt.where(Indicator.is_listed.is_(True))
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
    indicators = await _active_indicators(
        db, category=category.api_category, listed_only=True
    )
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
            "name": category.title,
            "description": category.description,
            "url": _absolute(f"/category/{slug}"),
            "mainEntity": [
                {"@type": "Dataset", "name": ind.name, "url": _absolute(f"/indicator/{ind.code}")}
                for ind in indicators[:12]
            ],
        },
    ]
    html = await build_document(
        title=category.title,
        description=category.description,
        canonical_path=f"/category/{slug}",
        body=body,
        json_ld=json_ld,
        keywords=category.keywords or None,
    )
    return 200, html


def _related_categories(current_slug: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (f"/category/{slug}", meta.name)
        for slug, meta in CATEGORY_META.items()
        if slug != current_slug
    )[:6]


async def render_indicator_html(
    code: str,
    db: AsyncSession,
    *,
    mode: str | None = None,
) -> tuple[int, str]:
    from app.data.view_model_families import (
        FAMILY_BY_BASE,
        data_indicator_code,
        mode_display_suffix,
        resolve_view_mode,
    )

    q = await db.execute(select(Indicator).where(Indicator.code == code, Indicator.is_active.is_(True)))
    indicator = q.scalar_one_or_none()
    if not indicator:
        return 404, "Not found"

    family = FAMILY_BY_BASE.get(code)
    resolved_mode = resolve_view_mode(code, mode) if family else None
    data_code = data_indicator_code(code, mode) if family else code
    data_indicator = indicator
    if data_code != code:
        dq = await db.execute(
            select(Indicator).where(Indicator.code == data_code, Indicator.is_active.is_(True))
        )
        data_indicator = dq.scalar_one_or_none() or indicator

    display_name = indicator.name
    display_unit = indicator.unit
    display_frequency = indicator.frequency
    if family and resolved_mode:
        suffix = mode_display_suffix(family, resolved_mode)
        if suffix:
            display_name = f"{indicator.name} — {suffix}"
        display_unit = resolved_mode.unit or display_unit
        display_frequency = resolved_mode.frequency or display_frequency

    category = _category_for_api(indicator.category)
    latest_rows = await _latest_rows(db, data_indicator.id, limit=8)
    count, first_dt, last_dt = await _indicator_stats(db, data_indicator.id)
    related = await _related_indicators(db, indicator)
    title = indicator.seo_title or f"{display_name} — данные и график"
    desc = (
        indicator.seo_description
        or clean_text(
            indicator.description,
            f"{display_name}: динамика, источник, методология и последние значения.",
        )
    )
    body = _indicator_body(
        indicator,
        category,
        latest_rows,
        related,
        count,
        first_dt,
        last_dt,
        display_name=display_name,
        display_unit=display_unit,
        display_frequency=display_frequency,
    )
    canonical_path = f"/indicator/{indicator.code}"
    if resolved_mode and resolved_mode.mode != family.default_mode:
        canonical_path = f"{canonical_path}?mode={resolved_mode.mode}"
    json_ld = [
        _site_json_ld(),
        _breadcrumbs([
            ("/", "Главная"),
            (f"/category/{category.slug}", category.name) if category else ("/", "Индикаторы"),
            (canonical_path, display_name),
        ]),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": display_name,
            "description": desc,
            "url": _absolute(canonical_path),
            "inLanguage": "ru-RU",
            "creator": {"@type": "Organization", "name": indicator.source},
            "temporalCoverage": f"{_format_date(first_dt)}/{_format_date(last_dt)}",
            "variableMeasured": display_name,
        },
    ]
    faq_ld = _faq_json_ld(_indicator_blocks_from_db(indicator))
    if faq_ld:
        json_ld.append(faq_ld)
    extra_head = _indicator_alt_freq_links(indicator)
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical_path,
        body=body,
        json_ld=json_ld,
        keywords=indicator.seo_keywords or None,
        extra_head=extra_head or None,
    )
    return 200, html


def _indicator_alt_freq_links(indicator: Indicator) -> str:
    """Render `<link rel="alternate">` для frequency-counterpart индикатора.

    Источник — `indicator.model_config.alternate_frequencies` или
    `primary_indicator_code` (см. T3 plan, FrequencySwitcher на frontend).
    Поисковики таким образом понимают семантическую связь между парой URLs
    (`/indicator/exports` ↔ `/indicator/exports-monthly`).
    """
    cfg = indicator.model_config_json or {}
    links: list[str] = []
    alt_freqs = cfg.get("alternate_frequencies")
    if isinstance(alt_freqs, dict):
        for _freq_key, alt_code in alt_freqs.items():
            if not alt_code:
                continue
            href = escape(_absolute(f"/indicator/{alt_code}"))
            links.append(f'<link rel="alternate" hreflang="ru-RU" href="{href}">')
    primary_code = cfg.get("primary_indicator_code")
    if primary_code:
        href = escape(_absolute(f"/indicator/{primary_code}"))
        links.append(f'<link rel="alternate" hreflang="ru-RU" href="{href}">')
    return "\n".join(links)


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
    *,
    display_name: str | None = None,
    display_unit: str | None = None,
    display_frequency: str | None = None,
) -> str:
    name = display_name or indicator.name
    unit = display_unit or indicator.unit
    frequency = display_frequency or indicator.frequency
    current = latest_rows[0] if latest_rows else None
    category_link = _link(f"/category/{category.slug}", category.name) if category else "Индикаторы"
    data_rows = "".join(
        f"<tr><td>{escape(_format_date(row.date))}</td><td>{escape(_format_number(row.value))}</td></tr>"
        for row in latest_rows
    )
    source_link = _link(indicator.source_url, indicator.source) if indicator.source_url else escape(indicator.source)
    related_links = tuple((f"/indicator/{ind.code}", ind.name) for ind in related)
    custom_blocks = _indicator_blocks_from_db(indicator)
    # Индикаторы с собственными seo_blocks — без GLOBAL (иначе два блока
    # «Источник и обновление» в SSR: generic + предметный).
    blocks = custom_blocks if custom_blocks else GLOBAL_INDICATOR_BLOCKS
    return f"""<main class="seo-page">
<nav aria-label="Хлебные крошки">{_link("/", "Главная")} / {category_link} / {escape(name)}</nav>
<h1>{escape(name)}</h1>
<p>{escape(clean_text(indicator.description, f"{name}: официальный экономический индикатор с историей значений и графиком."))}</p>
<section><h2>Текущее значение</h2>
<ul>
<li>Последнее значение: {escape(_format_number(current.value if current else None))} {escape(unit)}</li>
<li>Дата последнего значения: {escape(_format_date(current.date if current else None))}</li>
<li>Периодичность: {escape(frequency)}</li>
<li>Источник: {source_link}</li>
<li>Количество точек: {int(count)}</li>
<li>Период данных: {escape(_format_date(first_dt))} — {escape(_format_date(last_dt))}</li>
</ul></section>
{_blocks_html(blocks)}
<section><h2>Методология</h2><p>{escape(clean_text(indicator.methodology, "Методология показателя указана по данным официального источника и используется для интерпретации ряда."))}</p></section>
<section><h2>Последние данные</h2><table><thead><tr><th>Дата</th><th>Значение</th></tr></thead><tbody>{data_rows}</tbody></table></section>
<section><h2>Связанные индикаторы</h2>{_links_list(related_links or ((f"/category/{category.slug}", category.name),) if category else tuple())}</section>
</main>"""
