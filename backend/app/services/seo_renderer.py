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
            '<link href="/fonts/fonts.css" rel="stylesheet">\n'
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
        head_links = _sort_head_links(head_links)
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


def _category_rich_list(categories: dict[str, CategorySeo]) -> str:
    """Категории с кратким описанием — для SSR главной и индексации."""
    items = []
    for slug, meta in categories.items():
        desc = escape(clean_text(meta.description))
        items.append(
            f'<li>{_link(f"/category/{slug}", meta.name)}'
            f'<span class="seo-cat-desc"> — {desc}</span></li>'
        )
    return "<ul>" + "".join(items) + "</ul>"


def _sort_head_links(links: list[str]) -> list[str]:
    """Stylesheets первыми — меньше FOUC до загрузки Tailwind bundle."""
    stylesheets: list[str] = []
    icons: list[str] = []
    preloads: list[str] = []
    for link in links:
        lowered = link.lower()
        if "stylesheet" in lowered:
            stylesheets.append(link)
        elif "modulepreload" in lowered:
            preloads.append(link)
        else:
            icons.append(link)
    return stylesheets + icons + preloads


def _css_preload(head_links: str) -> str:
    match = re.search(r'href="(/assets/[^"]+\.css)"', head_links)
    if not match:
        return ""
    href = escape(match.group(1))
    return f'<link rel="preload" href="{href}" as="style">'


def _format_frequency(value: str | None) -> str:
    if not value:
        return "не указана"
    return FREQUENCY_LABELS_RU.get(value.lower(), value)


def _sort_indicators_for_seo(
    indicators: list[Indicator],
    category: CategorySeo | None,
) -> list[Indicator]:
    """Flagship категории первым — для SSR-листингов и internal linking."""
    flagship = category.flagship_code if category else None

    def sort_key(ind: Indicator) -> tuple[int, str]:
        if flagship and ind.code == flagship:
            return (0, ind.name)
        return (1, ind.name)

    return sorted(indicators, key=sort_key)


def _enrich_description(desc: str, current, unit: str) -> str:
    """Добавляет актуальное значение в meta description (CTR в выдаче)."""
    if not current:
        return desc
    unit_suffix = f" {unit.strip()}" if unit and unit.strip() else ""
    snippet = (
        f"Актуальное значение — {_format_number(current.value)}{unit_suffix} "
        f"на {_format_date(current.date)}."
    )
    if snippet.lower()[:20] in desc.lower():
        return desc
    return f"{snippet} {desc}"


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
                "description": (
                    "Бесплатная аналитическая платформа макроэкономических данных России: "
                    "ИПЦ, ключевая ставка, курсы валют, ВВП, безработица и 100+ показателей."
                ),
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

# Inline critical CSS для SSR-контента (.seo-page): без него при hard refresh
# виден «голый» HTML до гидратации React — Tailwind bundle не стилизует .seo-page.
SEO_CRITICAL_CSS = """<style id="seo-critical">
body{margin:0;background:#F8F9FC;color:#1A1A2E;font-family:"DM Sans",system-ui,sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased}
.seo-page{max-width:56rem;margin:0 auto;padding:5rem 1rem 3rem}
.seo-eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:.3em;color:#B8942F;font-weight:600;margin:0 0 .75rem}
.seo-page h1{font-size:1.25rem;font-weight:600;line-height:1.375;margin:0 0 1rem;max-width:48rem;color:#1A1A2E}
@media(min-width:768px){.seo-page h1{font-size:1.5rem}}
.seo-page h2{font-size:.75rem;text-transform:uppercase;letter-spacing:.2em;color:rgba(26,26,46,.65);font-weight:600;margin:2rem 0 .75rem;padding-top:.5rem;border-top:1px solid rgba(0,0,0,.08)}
.seo-page p,.seo-cat-desc{margin:0 0 1rem;color:rgba(26,26,46,.65)}
.seo-page ul{margin:0 0 1rem;padding-left:1.25rem}
.seo-page li{margin:.35rem 0}
.seo-page a{color:#1A1A2E;text-decoration:underline;text-underline-offset:2px}
.seo-page a:hover{color:#B8942F}
.seo-section{margin:1.5rem 0}
.seo-page nav{font-size:.875rem;margin-bottom:1.5rem;color:rgba(26,26,46,.65)}
.seo-page table{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.875rem}
.seo-page th,.seo-page td{border:1px solid rgba(0,0,0,.08);padding:.5rem .75rem;text-align:left}
.seo-page th{background:#F0F1F5;font-weight:600;color:#1A1A2E}
.seo-page tbody tr:nth-child(even){background:rgba(255,255,255,.6)}
</style>"""

FREQUENCY_LABELS_RU = {
    "daily": "ежедневно",
    "weekly": "еженедельно",
    "monthly": "ежемесячно",
    "quarterly": "ежеквартально",
    "annual": "ежегодно",
    "yearly": "ежегодно",
}

FLAGSHIP_CODES = tuple(meta.flagship_code for meta in CATEGORY_META.values())
SSR_LATEST_ROWS = 12


async def build_document(
    *,
    title: str,
    description: str,
    canonical_path: str,
    body: str,
    json_ld: list[dict] | None = None,
    keywords: str | None = None,
    extra_head: str | None = None,
    og_image: str | None = None,
    include_app: bool = True,
) -> str:
    """Полный SSR HTML-документ.

    og_image — per-page превью (индикаторы получают /og/{code}.png);
    include_app=False — чистая HTML-страница без React-bundle (годовые
    landing'и: у SPA-роутера нет такого маршрута, гидратация показала бы 404).
    """
    assets = await get_app_assets()
    url = _absolute(canonical_path)
    safe_title = escape(title)
    safe_desc = escape(clean_text(description)[:300])
    safe_keywords = escape(clean_text(keywords or DEFAULT_KEYWORDS)[:400])
    structured = "\n".join(_json_script(item) for item in (json_ld or []))
    extras = extra_head or ""
    css_preload = _css_preload(assets.head_links)
    og_url = escape(og_image or OG_IMAGE)
    body_scripts = assets.body_scripts if include_app else ""
    head_links = assets.head_links if include_app else _strip_preloads(assets.head_links)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{SEO_CRITICAL_CSS}
{css_preload}
{_consent_bootstrap()}
<title>{safe_title}</title>
<meta name="description" content="{safe_desc}">
<meta name="keywords" content="{safe_keywords}">
<meta name="author" content="Forecast Economy">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">
<meta name="theme-color" content="#F8F9FC">
<meta name="yandex-verification" content="02b4966d46881470">
<link rel="canonical" href="{escape(url)}">
<link rel="alternate" type="application/rss+xml" title="Forecast Economy — обновления данных" href="{DOMAIN}/feed.xml">
{extras}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Forecast Economy">
<meta property="og:url" content="{escape(url)}">
<meta property="og:title" content="{safe_title}">
<meta property="og:description" content="{safe_desc}">
<meta property="og:locale" content="ru_RU">
<meta property="og:image" content="{og_url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{safe_title}">
<meta name="twitter:description" content="{safe_desc}">
<meta name="twitter:image" content="{og_url}">
{head_links}
{structured}
</head>
<body>
<div id="root">{body}</div>
{body_scripts}
</body>
</html>"""


def _strip_preloads(head_links: str) -> str:
    """Для страниц без React-bundle modulepreload'ы — мёртвый вес."""
    return "\n".join(
        line for line in head_links.splitlines() if "modulepreload" not in line
    )


# Перелинковка терминов в seo-блоках (SSR): консервативный curated-список,
# только однозначные термины. Морфология — через стемы в regex. Первое
# вхождение на блок, self-ссылки пропускаются.
AUTOLINK_TERMS: tuple[tuple[str, str], ...] = (
    (r"ключев(?:ая|ой|ую) ставк[а-яё]+", "key-rate"),
    (r"RUONIA", "ruonia"),
    (r"ИПЦ", "cpi"),
    (r"индекс[а-яё]* потребительских цен", "cpi"),
    (r"денежн(?:ая|ой|ую) масс[а-яё]+", "m2"),
    (r"курс[а-яё]* доллара", "usd-rub"),
    (r"курс[а-яё]* евро", "eur-rub"),
    (r"уров(?:ень|ня|ню) безработицы", "unemployment"),
    (r"ВВП", "gdp-nominal"),
)


def _autolink(text_escaped: str, *, current_code: str | None = None) -> str:
    """Превращает первое вхождение известного термина в ссылку на индикатор."""
    linked_codes: set[str] = set()
    for pattern, code in AUTOLINK_TERMS:
        if code == current_code or code in linked_codes:
            continue

        def _wrap(match: re.Match) -> str:
            linked_codes.add(code)
            return f'<a href="/indicator/{code}">{match.group(0)}</a>'

        new_text, n = re.subn(pattern, _wrap, text_escaped, count=1)
        if n:
            text_escaped = new_text
    return text_escaped


def _blocks_html(blocks: Iterable[SeoBlock], *, current_code: str | None = None) -> str:
    return "".join(
        f'<section class="seo-section"><h2>{escape(block.title)}</h2>'
        f"<p>{_autolink(escape(block.body), current_code=current_code)}</p></section>"
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
    flagships = await _indicators_by_codes(db, FLAGSHIP_CODES)
    flagship_links = tuple((f"/indicator/{ind.code}", ind.name) for ind in flagships)
    page = PAGE_META["home"]
    body = f"""<main class="seo-page">
<p class="seo-eyebrow">Бесплатная аналитическая платформа экономических данных России</p>
<h1>{escape(page.h1)}</h1>
<p>{escape(page.intro)}</p>
{_blocks_html(page.blocks)}
<section><h2>Категории показателей</h2>{_category_rich_list(CATEGORY_META)}</section>
<section><h2>Ключевые индикаторы</h2>{_links_list(flagship_links)}</section>
<section><h2>Инструменты и разделы</h2>{_links_list(page.links)}</section>
</main>"""
    category_items = [
        {
            "@type": "ListItem",
            "position": index + 1,
            "name": meta.name,
            "url": _absolute(f"/category/{slug}"),
        }
        for index, (slug, meta) in enumerate(CATEGORY_META.items())
    ]
    json_ld = [
        _site_json_ld(),
        _breadcrumbs([("/", "Главная")]),
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page.title,
            "description": page.description,
            "url": _absolute("/"),
            "inLanguage": "ru-RU",
            "isPartOf": {"@id": f"{DOMAIN}/#website"},
        },
        {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": "Категории макроэкономических показателей России",
            "itemListElement": category_items,
        },
        {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": "Ключевые макроэкономические индикаторы",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": ind.name,
                    "url": _absolute(f"/indicator/{ind.code}"),
                }
                for index, ind in enumerate(flagships)
            ],
        },
    ]
    html = await build_document(
        title=page.title,
        description=page.description,
        canonical_path="/",
        body=body,
        json_ld=json_ld,
        keywords=page.keywords or None,
    )
    return html


async def _indicators_by_codes(
    db: AsyncSession,
    codes: tuple[str, ...],
) -> list[Indicator]:
    """Индикаторы в заданном порядке (flagship-ряды для главной и JSON-LD)."""
    if not codes:
        return []
    stmt = select(Indicator).where(
        Indicator.code.in_(codes),
        Indicator.is_active.is_(True),
    )
    result = await db.execute(stmt)
    by_code = {ind.code: ind for ind in result.scalars().all()}
    return [by_code[code] for code in codes if code in by_code]


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
    indicators = _sort_indicators_for_seo(indicators, category)
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
    latest_rows = await _latest_rows(db, data_indicator.id, limit=SSR_LATEST_ROWS)
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
    current = latest_rows[0] if latest_rows else None
    desc = _enrich_description(desc, current, display_unit or indicator.unit)
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
            "dateModified": _format_date(last_dt),
            "keywords": clean_text(indicator.seo_keywords or "", display_name),
            "isAccessibleForFree": True,
            "license": "https://creativecommons.org/publicdomain/zero/1.0/",
            "distribution": [
                {
                    "@type": "DataDownload",
                    "encodingFormat": "application/json",
                    "contentUrl": _absolute(f"/api/v1/indicators/{data_indicator.code}/data"),
                }
            ],
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
        og_image=f"{DOMAIN}/og/{indicator.code}.png",
    )
    return 200, html


async def indicator_data_years(db: AsyncSession, indicator_id: int) -> list[int]:
    """Годы, за которые у индикатора есть >= 2 точек (для landing-страниц)."""
    year_expr = func.extract("year", IndicatorData.date)
    result = await db.execute(
        select(year_expr.label("y"), func.count(IndicatorData.id))
        .where(IndicatorData.indicator_id == indicator_id)
        .group_by(year_expr)
        .having(func.count(IndicatorData.id) >= 2)
        .order_by(year_expr)
    )
    return [int(y) for y, _cnt in result.all()]


async def render_indicator_year_html(code: str, year: int, db: AsyncSession) -> tuple[int, str]:
    """Годовая landing-страница `/indicator/{code}/{year}`.

    Чистый SSR без React-bundle (include_app=False): у SPA-роутера нет такого
    маршрута. Контент полностью data-driven: точки за год, итоги, навигация
    по соседним годам, ссылка на живую карточку. Под long-tail запросы вида
    «инфляция в 2024 году», «курс доллара 2023».
    """
    q = await db.execute(
        select(Indicator).where(Indicator.code == code, Indicator.is_active.is_(True))
    )
    indicator = q.scalar_one_or_none()
    if not indicator:
        return 404, "Not found"

    rows_q = await db.execute(
        select(IndicatorData)
        .where(
            IndicatorData.indicator_id == indicator.id,
            func.extract("year", IndicatorData.date) == year,
        )
        .order_by(IndicatorData.date)
    )
    rows = list(rows_q.scalars().all())
    if len(rows) < 2:
        return 404, "Not found"

    years = await indicator_data_years(db, indicator.id)
    values = [float(r.value) for r in rows]
    first, last = rows[0], rows[-1]
    vmin, vmax = min(values), max(values)
    avg = sum(values) / len(values)
    unit = indicator.unit or ""
    category = _category_for_api(indicator.category)
    category_link = _link(f"/category/{category.slug}", category.name) if category else "Индикаторы"

    name = indicator.name
    title = f"{name} в {year} году — данные по месяцам и итоги"
    desc = (
        f"{name} в {year} году: {len(rows)} значений, "
        f"от {_format_number(vmin)} до {_format_number(vmax)} {unit}, "
        f"среднее {_format_number(avg)} {unit}. Официальные данные — {indicator.source}."
    )

    data_rows = "".join(
        f"<tr><td>{escape(_format_date(r.date))}</td><td>{escape(_format_number(r.value))}</td></tr>"
        for r in rows
    )
    year_links = _links_list(
        tuple(
            (f"/indicator/{code}/{y}", f"{name} в {y} году")
            for y in years
            if y != year
        )[-12:]
    )
    canonical_path = f"/indicator/{code}/{year}"
    body = f"""<main class="seo-page">
<nav aria-label="Хлебные крошки">{_link("/", "Главная")} / {category_link} / {_link(f"/indicator/{code}", name)} / {year}</nav>
<h1>{escape(title.split(" — ")[0])}</h1>
<p>{escape(desc)}</p>
<section><h2>Итоги {year} года</h2>
<ul>
<li>Значение на начало года: {escape(_format_number(first.value))} {escape(unit)} ({escape(_format_date(first.date))})</li>
<li>Значение на конец года: {escape(_format_number(last.value))} {escape(unit)} ({escape(_format_date(last.date))})</li>
<li>Минимум: {escape(_format_number(vmin))} {escape(unit)} · Максимум: {escape(_format_number(vmax))} {escape(unit)}</li>
<li>Среднее за год: {escape(_format_number(avg))} {escape(unit)}</li>
<li>Количество наблюдений: {len(rows)}</li>
<li>Источник: {escape(indicator.source)}</li>
</ul></section>
<section><h2>Все значения за {year} год</h2><table><thead><tr><th>Дата</th><th>Значение, {escape(unit)}</th></tr></thead><tbody>{data_rows}</tbody></table></section>
<section><h2>График и прогноз</h2><p>Полная история, интерактивный график и прогноз — на странице {_link(f"/indicator/{code}", name)}.</p></section>
<section><h2>Другие годы</h2>{year_links}</section>
</main>"""
    json_ld = [
        _site_json_ld(),
        _breadcrumbs([
            ("/", "Главная"),
            (f"/indicator/{code}", name),
            (canonical_path, f"{name} в {year} году"),
        ]),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"{name} — {year} год",
            "description": desc,
            "url": _absolute(canonical_path),
            "inLanguage": "ru-RU",
            "creator": {"@type": "Organization", "name": indicator.source},
            "temporalCoverage": f"{year}-01-01/{year}-12-31",
            "variableMeasured": name,
        },
    ]
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical_path,
        body=body,
        json_ld=json_ld,
        keywords=f"{name} {year}, {name} {year} год, {indicator.seo_keywords or name}",
        og_image=f"{DOMAIN}/og/{indicator.code}.png",
        include_app=False,
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
    category = _category_for_api(indicator.category)
    result = await db.execute(
        select(Indicator)
        .where(
            Indicator.is_active.is_(True),
            Indicator.is_listed.is_(True),
            Indicator.category == indicator.category,
            Indicator.code != indicator.code,
        )
    )
    return _sort_indicators_for_seo(list(result.scalars().all()), category)[:8]


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
<li>Периодичность: {escape(_format_frequency(frequency))}</li>
<li>Источник: {source_link}</li>
<li>Количество точек: {int(count)}</li>
<li>Период данных: {escape(_format_date(first_dt))} — {escape(_format_date(last_dt))}</li>
</ul></section>
{_blocks_html(blocks, current_code=indicator.code)}
<section><h2>Методология</h2><p>{escape(clean_text(indicator.methodology, "Методология показателя указана по данным официального источника и используется для интерпретации ряда."))}</p></section>
<section><h2>Последние данные</h2><table><thead><tr><th>Дата</th><th>Значение</th></tr></thead><tbody>{data_rows}</tbody></table></section>
<section><h2>Связанные индикаторы</h2>{_links_list(related_links or ((f"/category/{category.slug}", category.name),) if category else tuple())}</section>
</main>"""
