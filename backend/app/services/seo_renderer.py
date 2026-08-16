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
from app.data.indicator_seo import (
    FORECAST_SSR_CHART_NOTE,
    FORECAST_SSR_PILOT_CODES,
    append_forecast_ssr_desc_tail,
    forecast_ssr_image_name,
)
from app.models import Indicator, IndicatorData
from app.services.display import (
    today_msk,
    annual_summary,
    display_value,
    display_value_text,
    format_date_ru,
    format_number_ru,
    is_cpi_index,
    value_period_phrase,
)
from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths
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
from app.services.site_urls import YEAR_LANDING_MIN_POINTS

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


def truncate_meta(value: str, limit: int) -> str:
    """Обрезка meta по границе слова: посетитель видит текст в выдаче, и
    оборванное посередине слово выглядит как сбой сайта."""
    if len(value) <= limit:
        return value
    head = value[:limit].rstrip()
    cut = max(head.rfind(" "), head.rfind("—"), head.rfind(","))
    if cut > limit * 0.6:
        head = head[:cut]
    return head.rstrip(" ,;:—-") + "…"


def _format_date(value: date | None) -> str:
    """Человекочитаемая русская дата («1 мая 2026») — для видимого текста."""
    return format_date_ru(value)


def _iso_date(value: date | None) -> str:
    """ISO-дата для машинных полей JSON-LD (temporalCoverage, dateModified)."""
    return value.isoformat() if value else ""


def _format_number(value) -> str:
    """Русская типографика чисел (запятая в дроби) — для видимого текста."""
    return format_number_ru(value)


def _absolute(path: str) -> str:
    if path == "/":
        return DOMAIN
    return f"{DOMAIN}{path}"


def _link(path: str, label: str) -> str:
    return f'<a href="{escape(path)}">{escape(label)}</a>'


def _breadcrumbs_nav(items: list[tuple[str, str]]) -> str:
    """Видимые крошки: шеврон « / », последний узел без ссылки."""
    if not items:
        return ""
    parts: list[str] = []
    last = len(items) - 1
    for index, (path, name) in enumerate(items):
        if index:
            parts.append(" / ")
        if index == last:
            parts.append(escape(name))
        else:
            parts.append(_link(path, name))
    return f'<nav aria-label="Хлебные крошки">{"".join(parts)}</nav>'


def _links_list(links: Iterable[tuple[str, str]]) -> str:
    items = [f"<li>{_link(path, label)}</li>" for path, label in links]
    return "<ul>" + "".join(items) + "</ul>" if items else ""


def _category_rich_list(categories: dict[str, CategorySeo]) -> str:
    """Категории с кратким описанием — для SSR главной и индексации."""
    items = []
    for slug, meta in categories.items():
        desc = escape(clean_text(meta.description))
        items.append(
            f'<li>{_link(paths.russia_category(slug), meta.name)}'
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


def _enrich_description(desc: str, current, unit: str,
                        code: str | None = None, frequency: str | None = None) -> str:
    """Добавляет актуальное значение в meta description (CTR в выдаче).

    Значение идёт через display-adapter: CPI-индекс показывается как изменение
    цен («+0,17 % за месяц»), а не сырые «100,17 %» (инцидент «инфляция 100,2%»).
    """
    if not current:
        return desc
    snippet = (
        f"Актуальное значение — {display_value_text(code, current.value, unit, frequency)} "
        f"{value_period_phrase(current.date, frequency)}."
    )
    if snippet.lower()[:20] in desc.lower():
        return desc
    return f"{snippet} {desc}"


def _forecast_ssr_enabled(indicator: Indicator) -> bool:
    """B1/B2 пилот V2+V4+V5: whitelist ∩ реальный модельный прогноз."""
    if indicator.code not in FORECAST_SSR_PILOT_CODES:
        return False
    cfg = indicator.model_config_json or {}
    try:
        steps = int(cfg.get("forecast_steps") or 0)
    except (TypeError, ValueError):
        steps = 0
    return steps > 0


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
                    "Аналитическая платформа официальных экономических данных России, "
                    "85 регионов и доступных стран: графики, таблицы, сравнения и прогнозы."
                ),
                "inLanguage": "ru-RU",
                "publisher": {"@id": f"{DOMAIN}/#organization"},
            },
            {
                "@type": "Organization",
                "@id": f"{DOMAIN}/#organization",
                "name": "Forecast Economy",
                "url": DOMAIN,
                "email": "rebeka.ee@yandex.ru",
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
.seo-page{max-width:56rem;margin:0 auto;padding:2rem 1rem 3rem}
.seo-eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:.3em;color:#B8942F;font-weight:600;margin:0 0 .75rem}
.seo-note{font-size:13px;color:#8a6d1f;background:#fdf6e3;border:1px solid #ecd9a0;border-radius:8px;padding:.5rem .75rem;margin:.5rem 0}
.seo-page h1{font-size:1.5rem;font-weight:700;line-height:1.3;letter-spacing:-.01em;margin:0 0 .75rem;max-width:48rem;color:#1A1A2E}
@media(min-width:768px){.seo-page h1{font-size:2rem}}
.seo-page h2{font-size:.75rem;text-transform:uppercase;letter-spacing:.2em;color:rgba(26,26,46,.65);font-weight:600;margin:2rem 0 .75rem}
.seo-page h3{font-size:.9375rem;font-weight:600;margin:1rem 0 .25rem;color:#1A1A2E}
.seo-page p,.seo-cat-desc{margin:0 0 1rem;color:rgba(26,26,46,.65)}
.seo-page ul{margin:0 0 1rem;padding-left:1.25rem}
.seo-page li{margin:.35rem 0}
.seo-page a{color:#1A1A2E;text-decoration:underline;text-underline-offset:2px}
.seo-page a:hover{color:#B8942F}
.seo-section{margin:1.5rem 0}
.seo-page nav{font-size:.8125rem;margin-bottom:1.25rem;color:rgba(26,26,46,.55)}
.seo-page nav a{text-decoration:none;color:inherit}
.seo-page nav a:hover{color:#B8942F;text-decoration:underline}
.seo-page table{width:100%;border-collapse:separate;border-spacing:0;margin:1rem 0;font-size:.875rem;background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:.9rem;overflow:hidden}
.seo-page th,.seo-page td{padding:.55rem .9rem;text-align:left;border-bottom:1px solid rgba(0,0,0,.06)}
.seo-page th{background:#F4F5F9;font-weight:600;color:rgba(26,26,46,.75);font-size:.75rem;text-transform:uppercase;letter-spacing:.08em}
.seo-page tbody tr:last-child td{border-bottom:none}
.seo-page tbody tr:hover{background:rgba(184,148,47,.05)}
.seo-page td:last-child,.seo-page th:last-child{text-align:right;font-variant-numeric:tabular-nums}
.seo-chart{margin:1.25rem 0 .75rem;border:1px solid rgba(0,0,0,.08);border-radius:1rem;overflow:hidden;background:#fff;box-shadow:0 1px 3px rgba(26,26,46,.04)}
.seo-chart img{display:block;width:100%;height:auto}
.seo-chart figcaption{font-size:.8125rem;color:rgba(26,26,46,.6);padding:.5rem .75rem;border-top:1px solid rgba(0,0,0,.06)}
.seo-forecast-note{margin:0 0 1.5rem;font-size:.9375rem;line-height:1.55;color:rgba(26,26,46,.72)}
.seo-topbar{position:sticky;top:0;z-index:10;background:rgba(248,249,252,.92);backdrop-filter:blur(8px);border-bottom:1px solid rgba(0,0,0,.07)}
.seo-topbar-in{max-width:56rem;margin:0 auto;padding:.8rem 1rem;display:flex;align-items:center;gap:1.25rem;flex-wrap:wrap}
.seo-brand{font-weight:700;font-size:1rem;letter-spacing:-.01em;text-decoration:none!important;color:#1A1A2E}
.seo-brand em{font-style:normal;color:#B8942F}
.seo-topnav{display:flex;gap:1rem;font-size:.875rem;overflow-x:auto;white-space:nowrap;scrollbar-width:none}
.seo-topnav a{text-decoration:none!important;color:rgba(26,26,46,.7)}
.seo-topnav a:hover{color:#B8942F}
.seo-hero{background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:1rem;padding:1.25rem 1.5rem;margin:0 0 1.25rem;box-shadow:0 1px 3px rgba(26,26,46,.04)}
.seo-hero-value{font-size:2.4rem;font-weight:700;letter-spacing:-.02em;line-height:1.1;color:#1A1A2E;font-variant-numeric:tabular-nums}
@media(min-width:768px){.seo-hero-value{font-size:3rem}}
.seo-hero-value small{font-size:1.05rem;font-weight:500;color:rgba(26,26,46,.55);margin-left:.35rem;letter-spacing:0}
.seo-hero-meta{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin-top:.55rem;font-size:.875rem;color:rgba(26,26,46,.6)}
.seo-badge{display:inline-block;padding:.15rem .6rem;border-radius:999px;font-size:.8125rem;font-weight:600;white-space:nowrap}
.seo-badge.up{background:rgba(22,121,76,.1);color:#16794C}
.seo-badge.down{background:rgba(180,35,24,.08);color:#B42318}
.seo-badge.flat{background:rgba(26,26,46,.06);color:rgba(26,26,46,.65)}
.seo-tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:.75rem;margin:1.25rem 0}
@media(min-width:640px){.seo-tiles{grid-template-columns:repeat(4,1fr)}}
.seo-tile{background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:.9rem;padding:.8rem 1rem}
.seo-tile b{display:block;font-size:1.05rem;font-weight:700;color:#1A1A2E;font-variant-numeric:tabular-nums;line-height:1.3}
.seo-tile span{display:block;font-size:.65rem;text-transform:uppercase;letter-spacing:.12em;color:rgba(26,26,46,.5);font-weight:600;margin-bottom:.2rem}
.seo-grid{display:grid;grid-template-columns:1fr;gap:.75rem;margin:1rem 0;padding:0;list-style:none}
@media(min-width:640px){.seo-grid{grid-template-columns:repeat(2,1fr)}}
.seo-grid li{margin:0}
.seo-grid a.seo-item{display:block;background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:.9rem;padding:.9rem 1.1rem;text-decoration:none!important;transition:border-color .15s}
.seo-grid a.seo-item:hover{border-color:#B8942F}
.seo-item-name{font-size:.8125rem;color:rgba(26,26,46,.6);margin-bottom:.15rem}
.seo-item-value{font-size:1.35rem;font-weight:700;color:#1A1A2E;font-variant-numeric:tabular-nums}
.seo-item-value small{font-size:.85rem;font-weight:500;color:rgba(26,26,46,.5);margin-left:.25rem}
.seo-item-meta{font-size:.75rem;color:rgba(26,26,46,.5);margin-top:.25rem;display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
.seo-linkbtn{display:inline-block;background:#1A1A2E;color:#fff!important;text-decoration:none!important;padding:.55rem 1.1rem;border-radius:.6rem;font-weight:600;font-size:.875rem}
.seo-linkbtn:hover{background:#B8942F}
.seo-pills{display:flex;flex-wrap:wrap;gap:.5rem;margin:.75rem 0;padding:0;list-style:none}
.seo-pills li{margin:0}
.seo-pills a{display:inline-block;background:#fff;border:1px solid rgba(0,0,0,.1);border-radius:999px;padding:.35rem .9rem;font-size:.8125rem;text-decoration:none!important;color:rgba(26,26,46,.75)}
.seo-pills a:hover{border-color:#B8942F;color:#B8942F}
.seo-faq{background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:.9rem;padding:.35rem 1.1rem .6rem;margin:.75rem 0}
.seo-cta{max-width:56rem;margin:2.5rem auto 0;padding:0 1rem}
.seo-cta-in{background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:1rem;padding:1.5rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}
.seo-cta p{margin:0;color:rgba(26,26,46,.75);max-width:34rem}
.seo-cta a.seo-btn{display:inline-block;background:#1A1A2E;color:#fff;text-decoration:none!important;padding:.7rem 1.4rem;border-radius:.6rem;font-weight:600;font-size:.9375rem;white-space:nowrap}
.seo-cta a.seo-btn:hover{background:#B8942F;color:#fff}
.seo-foot{max-width:56rem;margin:1.25rem auto 0;padding:0 1rem 2.5rem;font-size:.8125rem;color:rgba(26,26,46,.55)}
.seo-foot a{color:inherit}
.seo-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.seo-scroll table{min-width:26rem}
</style>"""

# Брендовый «хром» чистых SSR-страниц (include_app=False): единая шапка с
# навигацией и CTA-футер на главную. Одна точка правки для всех программатик-
# семейств без React-bundle (годовые landing'и + брендовая 404).
#
# Состав seo-topnav ≠ клиентская Navbar: здесь перелинковка для робота.
# Обязательны хабы /russia/today, /russia/region, /world, /russia/calendar.
# Клиентскую шапку «пункт в пункт» не синхронизировать.
#
# Масштаб (site_urls, 2026-08): chrome видят только ~2,5k годовых landing'ов;
# ~77k URL — SPA-SSR (include_app=True) без chrome. Для них — блок
# `_SSR_PLATFORM_DEEP_LINKS` внутри body (бот читает; React заменит #root).
_SSR_CHROME_HEADER = f"""<header class="seo-topbar"><div class="seo-topbar-in">
<a class="seo-brand" href="/">Forecast<em>Economy</em></a>
<nav class="seo-topnav"><a href="/">Индикаторы</a><a href="{paths.today()}">Сегодня</a><a href="{paths.region_hub()}">Регионы</a><a href="{paths.world_hub()}">Страны</a><a href="{paths.world_rating("unemployment-rate")}">Рейтинг стран</a><a href="{paths.calendar()}">Календарь</a><a href="/compare">Сравнение</a><a href="/calculator">Калькуляторы</a></nav>
</div></header>"""

_SSR_CHROME_FOOTER = f"""<div class="seo-cta"><div class="seo-cta-in">
<p><strong>Интерактивные графики, сравнения и проверенные прогнозы</strong> — для показателей России, регионов и доступных стран. Просмотр открыт всем, скачивание — после бесплатной регистрации.</p>
<a class="seo-btn" href="/">Открыть платформу</a>
</div></div>
<footer class="seo-foot">Данные — только официальные первоисточники: государственные статистические ведомства, центральные банки и официальные биржи. Обновляются по мере публикации. © Forecast Economy — <a href="{DOMAIN}">forecasteconomy.com</a></footer>
<script type="module" src="/assets/behavior-standalone.js" defer></script>"""

# Единый выход вглубь платформы для SPA-SSR (include_app=True): без chrome
# тонкие страницы (/today/*, /calendar/*) оставляли боту только крошки.
# Класс seo-platform-nav — маркер «блок уже есть», чтобы не дублировать.
_SSR_PLATFORM_DEEP_LINKS = f"""
<section class="seo-section seo-platform-nav" aria-label="Разделы платформы">
<h2>Разделы платформы</h2>
<ul class="seo-pills">
<li><a href="/">Индикаторы России</a></li>
<li><a href="{paths.today()}">Экономика сегодня</a></li>
<li><a href="{paths.region_hub()}">Регионы России</a></li>
<li><a href="{paths.world_hub()}">Статистика по странам</a></li>
<li><a href="{paths.calendar()}">Календарь публикаций</a></li>
<li><a href="/compare">Сравнение показателей</a></li>
</ul>
</section>
"""

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
    safe_desc = escape(truncate_meta(clean_text(description), 300))
    safe_keywords = escape(clean_text(keywords or DEFAULT_KEYWORDS)[:400])
    structured = "\n".join(_json_script(item) for item in (json_ld or []))
    extras = extra_head or ""
    css_preload = _css_preload(assets.head_links)
    og_url = escape(og_image or OG_IMAGE)
    body_scripts = assets.body_scripts if include_app else ""
    head_links = assets.head_links if include_app else _strip_preloads(assets.head_links)
    if not include_app:
        # Чистые SSR-страницы получают брендовый хром: шапка-навигация + CTA на
        # платформу + футер об источниках. React-страницы — нет (гидратация
        # заменит #root своим layout'ом).
        body = f"{_SSR_CHROME_HEADER}\n{body}\n{_SSR_CHROME_FOOTER}"
    elif "seo-platform-nav" not in body:
        # SPA-SSR без chrome: бот видит только prerender в #root. Единый блок
        # выхода в хабы — иначе тонкие семейства (/today/*, /calendar/*) —
        # тупики с одними крошками. React при гидратации заменит #root.
        body = f"{body.rstrip()}\n{_SSR_PLATFORM_DEEP_LINKS}"
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


def render_not_found_html(message: str = "Страница не найдена") -> str:
    """Брендовая 404 для SSR-роутов и nginx catch-all.

    Самодостаточный документ (без asset-fetch и БД): critical CSS + хром +
    навигация по основным разделам. noindex — чтобы поисковики не тащили
    404-страницы в выдачу. Не тупик: ведём в каталог, сегодня, регионы,
    страны, сравнение и поиск на главной.
    """
    safe = escape(message)
    category_links = "".join(
        f'<li><a href="{escape(paths.russia_category(slug))}">{escape(meta.name)}</a></li>'
        for slug, meta in list(CATEGORY_META.items())[:6]
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{SEO_CRITICAL_CSS}
<title>{safe} — Forecast Economy</title>
<meta name="robots" content="noindex, follow">
</head>
<body>
{_SSR_CHROME_HEADER}
<main class="seo-page">
<h1>{safe}</h1>
<p>Такой страницы нет или она переехала. Вот с чего можно продолжить:</p>
<ul>
<li><a href="/">Все экономические индикаторы России</a></li>
<li><a href="{paths.today()}">Ключевые показатели на сегодня</a></li>
<li><a href="{paths.region_hub()}">Статистика по регионам России</a></li>
<li><a href="{paths.world_hub()}">Статистика по странам</a></li>
<li><a href="/compare">Сравнение показателей</a></li>
<li><a href="{paths.calendar()}">Календарь публикаций статистики</a></li>
<li><a href="/">Поиск по платформе</a> — откройте главную и воспользуйтесь поиском в шапке</li>
</ul>
<section><h2>Разделы каталога</h2>
<ul>
{category_links}
</ul></section>
</main>
{_SSR_CHROME_FOOTER}
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
            return f'<a href="{paths.russia_indicator(code)}">{match.group(0)}</a>'

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


def _page_trail(page_slug: str, page: PageSeo) -> list[tuple[str, str]]:
    if page_slug == "russia":
        return crumbs.russia_home_trail()
    if page_slug == "russia-categories":
        return crumbs.russia_categories_trail()
    if page_slug == "calendar":
        return crumbs.calendar_trail()
    if page_slug == "demographics":
        return crumbs.demographics_trail()
    if page_slug in {
        "compare",
        "calculator",
        "calculator-mortgage",
        "calculator-compound",
        "widgets",
        "about",
        "methodology",
        "privacy",
        "terms",
    }:
        return crumbs.tool_trail(page.h1, page.path)
    return crumbs.trail(crumbs.home(), (page.path, page.h1))


def _page_body(page: PageSeo, trail: list[tuple[str, str]]) -> str:
    return f"""<main class="seo-page">
{_breadcrumbs_nav(trail)}
<h1>{escape(page.h1)}</h1>
<p>{escape(page.intro)}</p>
{_blocks_html(page.blocks)}
<section><h2>Связанные разделы</h2>{_links_list(page.links or tuple((paths.russia_category(slug), meta.name) for slug, meta in CATEGORY_META.items()))}</section>
</main>"""


async def render_page_html(page_slug: str) -> tuple[int, str]:
    page = PAGE_META.get(page_slug)
    if not page:
        return 404, "Not found"
    trail = _page_trail(page_slug, page)
    json_ld = [
        _site_json_ld(),
        _breadcrumbs(trail),
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
        body=_page_body(page, trail),
        json_ld=json_ld,
        keywords=page.keywords or None,
    )
    return 200, html


async def render_home_html(db: AsyncSession) -> str:
    flagships = await _indicators_by_codes(db, FLAGSHIP_CODES)
    flagship_links = tuple((paths.russia_indicator(ind.code), ind.name) for ind in flagships)
    page = PAGE_META["home"]
    body = f"""<main class="seo-page">
<p class="seo-eyebrow">Официальные данные России, регионов и стран</p>
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
            "url": _absolute(paths.russia_category(slug)),
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
                    "url": _absolute(paths.russia_indicator(ind.code)),
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


async def render_categories_hub_html(db: AsyncSession) -> tuple[int, str]:
    """Хаб /russia/category — список категорий России."""
    page = PAGE_META.get("russia-categories")
    if not page:
        return 404, "Not found"
    trail = crumbs.russia_categories_trail()
    links = tuple(
        (paths.russia_category(slug), meta.name)
        for slug, meta in CATEGORY_META.items()
    )
    body = f"""<main class="seo-page">
{_breadcrumbs_nav(trail)}
<h1>{escape(page.h1)}</h1>
<p>{escape(page.intro)}</p>
{_blocks_html(page.blocks)}
<section><h2>Категории</h2>{_category_rich_list(CATEGORY_META)}</section>
<section><h2>Связанные разделы</h2>{_links_list(page.links or links[:6])}</section>
</main>"""
    json_ld = [
        _site_json_ld(),
        _breadcrumbs(trail),
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": page.title,
            "description": page.description,
            "url": _absolute(paths.russia_categories()),
            "mainEntity": [
                {
                    "@type": "Thing",
                    "name": meta.name,
                    "url": _absolute(paths.russia_category(slug)),
                }
                for slug, meta in list(CATEGORY_META.items())[:12]
            ],
        },
    ]
    html = await build_document(
        title=page.title,
        description=page.description,
        canonical_path=paths.russia_categories(),
        body=body,
        json_ld=json_ld,
        keywords=page.keywords or None,
    )
    return 200, html


async def render_category_html(slug: str, db: AsyncSession) -> tuple[int, str]:
    category = CATEGORY_META.get(slug)
    if not category:
        return 404, "Not found"
    indicators = await _active_indicators(
        db, category=category.api_category, listed_only=True
    )
    indicators = _sort_indicators_for_seo(indicators, category)
    links = tuple((paths.russia_indicator(ind.code), ind.name) for ind in indicators)
    trail = crumbs.russia_category_trail(category.name, paths.russia_category(slug))
    body = f"""<main class="seo-page">
{_breadcrumbs_nav(trail)}
<h1>{escape(category.title)}</h1>
<p>{escape(category.intro)}</p>
{_blocks_html(category.blocks)}
<section><h2>Индикаторы раздела</h2>{_links_list(links)}</section>
<section><h2>Связанные разделы</h2>{_links_list(_related_categories(slug))}</section>
</main>"""
    json_ld = [
        _site_json_ld(),
        _breadcrumbs(trail),
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": category.title,
            "description": category.description,
            "url": _absolute(paths.russia_category(slug)),
            "mainEntity": [
                {"@type": "Dataset", "name": ind.name, "url": _absolute(paths.russia_indicator(ind.code))}
                for ind in indicators[:12]
            ],
        },
    ]
    html = await build_document(
        title=category.title,
        description=category.description,
        canonical_path=paths.russia_category(slug),
        body=body,
        json_ld=json_ld,
        keywords=category.keywords or None,
    )
    return 200, html


def _related_categories(current_slug: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (paths.russia_category(slug), meta.name)
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
    # А-4: внутренняя перелинковка «по годам» — год-запросы («X в 2019»)
    # должны ранжировать годовые landing'и, а не карточку со сниппетом «сегодня».
    data_years = await indicator_data_years(db, indicator.id)
    title = indicator.seo_title or f"{display_name} — данные и график"
    desc = (
        indicator.seo_description
        or clean_text(
            indicator.description,
            f"{display_name}: динамика, источник, методология и последние значения.",
        )
    )
    forecast_ssr = _forecast_ssr_enabled(indicator)
    # V2: хвост meta description (без дубля, если «прогноз» уже в тексте).
    if forecast_ssr:
        desc = append_forecast_ssr_desc_tail(desc)
    current = latest_rows[0] if latest_rows else None
    desc = _enrich_description(
        desc, current, display_unit or indicator.unit,
        code=data_indicator.code, frequency=display_frequency,
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
        data_code=data_indicator.code,
        data_years=data_years,
        forecast_ssr=forecast_ssr,
    )
    canonical_path = paths.russia_indicator(indicator.code)
    if resolved_mode and resolved_mode.mode != family.default_mode:
        canonical_path = f"{canonical_path}?mode={resolved_mode.mode}"
    # OG-картинка и видимый график — код карточки (URL), не sibling-режима:
    # /og/{base}.png всегда существует; /og/{base}-yoy.png на проде часто 404
    # (unlisted derived ещё без превью). Смысл режима остаётся в title/Dataset.
    og_path = f"{DOMAIN}{paths.og_indicator(paths.RUSSIA, indicator.code)}"
    image_name = (
        forecast_ssr_image_name(display_name)
        if forecast_ssr
        else f"{display_name} — график динамики ({indicator.source})"
    )
    crumb_trail = crumbs.russia_indicator_trail(
        category.name if category else None,
        paths.russia_category(category.slug) if category else None,
        display_name,
        canonical_path.split("?")[0],
    )
    json_ld = [
        _site_json_ld(),
        _breadcrumbs(crumb_trail),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": display_name,
            "description": desc,
            "url": _absolute(canonical_path),
            "inLanguage": "ru-RU",
            "creator": {"@type": "Organization", "name": indicator.source},
            "temporalCoverage": f"{_iso_date(first_dt)}/{_iso_date(last_dt)}",
            "variableMeasured": display_name,
            "dateModified": _iso_date(last_dt),
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
            "image": og_path,
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": og_path,
            "url": og_path,
            "name": image_name,
            "caption": image_name if forecast_ssr else f"{display_name} — график динамики ({indicator.source})",
            "description": desc,
            "width": 1200,
            "height": 630,
            "representativeOfPage": True,
            "creditText": "Forecast Economy",
            "author": {"@type": "Organization", "name": "Forecast Economy"},
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
        og_image=og_path,
    )
    return 200, html


async def indicator_data_years(db: AsyncSession, indicator_id: int) -> list[int]:
    """Годы с достаточным числом точек для годовой landing-страницы."""
    year_expr = func.extract("year", IndicatorData.date)
    result = await db.execute(
        select(year_expr.label("y"), func.count(IndicatorData.id))
        .where(IndicatorData.indicator_id == indicator_id)
        .group_by(year_expr)
        .having(func.count(IndicatorData.id) >= YEAR_LANDING_MIN_POINTS)
        .order_by(year_expr)
    )
    return [int(y) for y, _cnt in result.all()]


async def yearly_last_points(
    db: AsyncSession, indicator_id: int,
) -> list[tuple[int, float, date]]:
    """Последняя точка каждого календарного года (для годовых рядов — единственная)."""
    result = await db.execute(
        select(IndicatorData.date, IndicatorData.value)
        .where(IndicatorData.indicator_id == indicator_id)
        .order_by(IndicatorData.date)
    )
    by_year: dict[int, tuple[int, float, date]] = {}
    for dt, raw in result.all():
        if dt is None or raw is None:
            continue
        by_year[int(dt.year)] = (int(dt.year), float(raw), dt)
    return [by_year[y] for y in sorted(by_year)]


def neighbor_year_window(
    series: list[tuple[int, float, date]],
    year: int,
    *,
    size: int = 10,
) -> list[tuple[int, float, date]]:
    """Окно соседних лет вокруг выбранного (до `size` точек)."""
    if not series:
        return []
    years = [y for y, _v, _d in series]
    if year in years:
        idx = years.index(year)
    else:
        idx = min(range(len(years)), key=lambda i: abs(years[i] - year))
    half = size // 2
    start = max(0, idx - half)
    end = min(len(series), start + size)
    start = max(0, end - size)
    return series[start:end]


def year_change_lines(
    *,
    year: int,
    value: float,
    prev_value: float | None,
    prev_year: int | None,
    code: str,
    unit: str,
) -> list[str]:
    """Строки «значение» и «изменение к прошлому году» для одноточечной страницы."""
    cpi_mode = is_cpi_index(code)
    shown = display_value(code, value)
    unit_suffix = f" {unit}" if unit and not cpi_mode else (" %" if cpi_mode else "")
    lines = [
        f"Значение: {format_number_ru(shown, signed=cpi_mode)}{unit_suffix}",
    ]
    if prev_value is None or prev_year is None:
        lines.append("Изменение к предыдущему году: нет сопоставимого значения")
        return lines
    prev_shown = display_value(code, prev_value)
    if shown is None or prev_shown is None:
        lines.append(f"Изменение к {prev_year} году: нет данных")
        return lines
    delta = shown - prev_shown
    abs_text = format_number_ru(delta, signed=True)
    if prev_shown == 0:
        pct_text = "не рассчитывается (база равна нулю)"
        lines.append(
            f"Изменение к {prev_year} году: {abs_text}{unit_suffix} "
            f"({pct_text})"
        )
    else:
        pct = round((delta / abs(prev_shown)) * 100.0, 2)
        lines.append(
            f"Изменение к {prev_year} году: {abs_text}{unit_suffix} "
            f"({format_number_ru(pct, signed=True)} %)"
        )
    return lines


def year_history_position_lines(
    *,
    year: int,
    value: float,
    series: list[tuple[int, float, date]],
    code: str,
    unit: str,
) -> list[str]:
    """Положение значения в истории ряда: среднее, рекорд, давность экстремума."""
    if len(series) < 2:
        return ["Положение в истории: недостаточно соседних лет для сравнения"]
    cpi_mode = is_cpi_index(code)
    unit_suffix = f" {unit}" if unit and not cpi_mode else (" %" if cpi_mode else "")
    shown_pairs = [
        (y, display_value(code, v))
        for y, v, _d in series
        if display_value(code, v) is not None
    ]
    if not shown_pairs:
        return ["Положение в истории: нет данных"]
    shown_map = {y: s for y, s in shown_pairs}
    current = shown_map.get(year)
    if current is None:
        current = display_value(code, value)
    if current is None:
        return ["Положение в истории: нет данных"]
    values = [s for _y, s in shown_pairs]
    mean = sum(values) / len(values)
    n_years = len(shown_pairs)
    if current > mean:
        vs_mean = f"выше среднего за {n_years} лет"
    elif current < mean:
        vs_mean = f"ниже среднего за {n_years} лет"
    else:
        vs_mean = f"на уровне среднего за {n_years} лет"
    lines = [
        f"Положение в истории: {vs_mean} "
        f"(среднее — {format_number_ru(mean, signed=cpi_mode)}{unit_suffix})",
    ]
    vmax = max(values)
    vmin = min(values)
    max_years = sorted(y for y, s in shown_pairs if s == vmax)
    min_years = sorted(y for y, s in shown_pairs if s == vmin)
    if current == vmax and year in max_years:
        if len(max_years) == 1:
            lines.append(f"Это максимум за всю доступную историю ряда ({n_years} лет)")
        else:
            lines.append(
                f"Это один из максимумов истории ряда "
                f"({format_number_ru(vmax, signed=cpi_mode)}{unit_suffix})"
            )
    else:
        peak_year = max_years[-1]
        gap = year - peak_year
        gap_text = (
            f"{gap} год назад" if gap == 1
            else f"{gap} года назад" if 2 <= gap % 10 <= 4 and not 12 <= gap % 100 <= 14
            else f"{gap} лет назад"
        )
        lines.append(
            f"Максимум истории — {format_number_ru(vmax, signed=cpi_mode)}"
            f"{unit_suffix} в {peak_year} году"
            + (f" ({gap_text})" if gap > 0 else "")
        )
    if current == vmin and year in min_years:
        if len(min_years) == 1:
            lines.append(f"Это минимум за всю доступную историю ряда ({n_years} лет)")
        else:
            lines.append(
                f"Это один из минимумов истории ряда "
                f"({format_number_ru(vmin, signed=cpi_mode)}{unit_suffix})"
            )
    else:
        floor_year = min_years[-1]
        gap = year - floor_year
        if gap > 0:
            gap_text = (
                f"{gap} год назад" if gap == 1
                else f"{gap} года назад" if 2 <= gap % 10 <= 4 and not 12 <= gap % 100 <= 14
                else f"{gap} лет назад"
            )
            lines.append(
                f"Минимум истории — {format_number_ru(vmin, signed=cpi_mode)}"
                f"{unit_suffix} в {floor_year} году ({gap_text})"
            )
        else:
            lines.append(
                f"Минимум истории — {format_number_ru(vmin, signed=cpi_mode)}"
                f"{unit_suffix} в {floor_year} году"
            )
    return lines


def _year_page_title_desc(
    *,
    name: str,
    year: int,
    frequency: str | None,
    n_rows: int,
    current_year: bool,
    period_note: str,
    summary_label: str,
    summary_text: str,
    source: str,
) -> tuple[str, str]:
    """Заголовок и description с учётом частоты и числа точек за год."""
    freq = (frequency or "").lower()
    if freq == "annual":
        title = (
            f"{name} в {year} году — актуальное годовое значение"
            if current_year
            else f"{name} в {year} году — значение и динамика"
        )
        summary_bit = summary_text.rstrip(".")
        desc = (
            f"{name} в {year} году{period_note}: {summary_label.lower()} — {summary_bit}. "
            f"Сравнение с прошлым годом и положение в истории ряда. "
            f"Официальные данные — {source}."
        )
        return title, desc
    if current_year:
        title = f"{name} в {year} году — данные с начала года"
    elif n_rows == 1:
        title = f"{name} в {year} году — значение и динамика"
    elif freq == "quarterly":
        title = f"{name} в {year} году — данные по кварталам и итоги"
    elif freq == "weekly":
        title = f"{name} в {year} году — данные по неделям и итоги"
    elif freq == "daily":
        title = f"{name} в {year} году — дневные данные и итоги"
    else:
        title = f"{name} в {year} году — данные по месяцам и итоги"
    summary_bit = summary_text.rstrip(".")
    if n_rows == 1:
        desc = (
            f"{name} в {year} году{period_note}: {summary_label.lower()} — {summary_bit}. "
            f"Сравнение с прошлым годом и положение в истории ряда. "
            f"Официальные данные — {source}."
        )
    else:
        desc = (
            f"{name} в {year} году{period_note}: {n_rows} значений, "
            f"{summary_label.lower()} — {summary_bit}. Официальные данные — {source}."
        )
    return title, desc


async def render_indicator_year_html(code: str, year: int, db: AsyncSession) -> tuple[int, str]:
    """Годовая landing-страница `/russia/indicator/{code}/{year}`.

    Чистый SSR без React-bundle (include_app=False): у SPA-роутера нет такого
    маршрута. Контент полностью data-driven: точки за год, итоги, навигация
    по соседним годам, ссылка на живую карточку. Под long-tail запросы вида
    «инфляция в 2024 году», «население России 2025».

    Порог — YEAR_LANDING_MIN_POINTS (согласован с sitemap). При одной точке
    за год страница обогащается YoY, положением в истории и таблицей соседних лет.
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
    if len(rows) < YEAR_LANDING_MIN_POINTS:
        return 404, "Not found"

    years = await indicator_data_years(db, indicator.id)
    values = [float(r.value) for r in rows]
    first, last = rows[0], rows[-1]
    unit = indicator.unit or ""
    category = _category_for_api(indicator.category)

    name = indicator.name
    # Семантика значений и итога — через display-adapter: CPI-индекс людям
    # показывается изменением цен, годовой итог сворачивается по природе ряда
    # (сумма для потоков, конец года для запасов, цепной рост для CPI) — а не
    # «среднее за год» для всего подряд (В-25).
    cpi_mode = is_cpi_index(code)
    shown_values = [display_value(code, v) for v in values]
    vmin, vmax = min(shown_values), max(shown_values)
    summary_label, summary_text = annual_summary(code, values, unit)
    # Незавершённый год не выдаём за «итоги года» (В-26): честная рамка
    # «с начала года», итог — «на дату последнего значения».
    current_year = today_msk().year == year
    period_note = f" (данные с начала года по {_format_date(last.date)})" if current_year else ""
    # Годовой ряд / одна точка: «среднее за год» звучит неестественно.
    freq = (indicator.frequency or "").lower()
    if len(rows) == 1 and not is_cpi_index(code):
        summary_label = "Годовое значение" if freq == "annual" else "Значение"
        summary_text = display_value_text(code, last.value, unit, indicator.frequency)
    if current_year:
        summary_label = f"{summary_label} (на {_format_date(last.date)})"
    unit_suffix = f" {escape(unit)}" if unit and not cpi_mode else (" %" if cpi_mode else "")
    title, desc = _year_page_title_desc(
        name=name,
        year=year,
        frequency=indicator.frequency,
        n_rows=len(rows),
        current_year=current_year,
        period_note=period_note,
        summary_label=summary_label,
        summary_text=summary_text,
        source=indicator.source or "официальный источник",
    )

    series = await yearly_last_points(db, indicator.id)
    series_by_year = {y: (v, d) for y, v, d in series}
    prev_year = year - 1 if (year - 1) in series_by_year else None
    prev_value = series_by_year[prev_year][0] if prev_year is not None else None
    neighbors = neighbor_year_window(series, year, size=10)
    value_head = "Изменение цен, %" if cpi_mode else (f"Значение, {escape(unit)}" if unit else "Значение")

    single_point = len(rows) == 1
    if single_point:
        totals_head = (
            f"{name} в {year} году"
            if not current_year
            else f"{name} в {year} году: данные на {_format_date(last.date)}"
        )
        change_lines = year_change_lines(
            year=year,
            value=float(last.value),
            prev_value=prev_value,
            prev_year=prev_year,
            code=code,
            unit=unit,
        )
        history_lines = year_history_position_lines(
            year=year,
            value=float(last.value),
            series=series,
            code=code,
            unit=unit,
        )
        context_items = "".join(
            f"<li>{escape(line)}</li>" for line in (change_lines + history_lines)
        )
        context_items += (
            f"<li>Дата значения: {escape(_format_date(last.date))}</li>"
            f"<li>Источник: {escape(indicator.source)}</li>"
        )
        neighbor_rows = "".join(
            (
                f"<tr><td><strong>{y}</strong></td>"
                f"<td><strong>{escape(format_number_ru(display_value(code, v), signed=cpi_mode))}</strong></td></tr>"
                if y == year
                else (
                    f"<tr><td>{y}</td>"
                    f"<td>{escape(format_number_ru(display_value(code, v), signed=cpi_mode))}</td></tr>"
                )
            )
            for y, v, _d in neighbors
        )
        data_section = f"""<section><h2>{escape(totals_head)}</h2>
<ul>
{context_items}
</ul></section>
<section><h2>Динамика соседних лет</h2>
<table><thead><tr><th>Год</th><th>{value_head}</th></tr></thead>
<tbody>{neighbor_rows}</tbody></table></section>"""
        chart_caption = (
            f"{name} в {year} году — значение в контексте соседних лет. "
            f"Источник: {indicator.source}. forecasteconomy.com"
        )
        chart_alt = (
            f"{name} в {year} году — график соседних лет, "
            f"{summary_label.lower()} {summary_text}, источник {indicator.source}"
        )
        image_caption = f"{name} в {year} году — значение и динамика"
    else:
        totals_head = (
            f"{name} в {year} году: данные с начала года"
            if current_year else f"Итоги {year} года"
        )
        range_label = (
            "Минимальное и максимальное изменение за период"
            if cpi_mode else "Минимум и максимум"
        )
        data_rows = "".join(
            f"<tr><td>{escape(_format_date(r.date))}</td>"
            f"<td>{escape(format_number_ru(display_value(code, r.value), signed=cpi_mode))}</td></tr>"
            for r in rows
        )
        data_section = f"""<section><h2>{escape(totals_head)}</h2>
<ul>
<li>{escape(summary_label)}: {escape(summary_text)}</li>
<li>Значение на начало года: {escape(format_number_ru(display_value(code, first.value), signed=cpi_mode))}{unit_suffix} ({escape(_format_date(first.date))})</li>
<li>{'Последнее значение' if current_year else 'Значение на конец года'}: {escape(format_number_ru(display_value(code, last.value), signed=cpi_mode))}{unit_suffix} ({escape(_format_date(last.date))})</li>
<li>{escape(range_label)}: {escape(format_number_ru(vmin, signed=cpi_mode))} … {escape(format_number_ru(vmax, signed=cpi_mode))}{unit_suffix}</li>
<li>Количество наблюдений: {len(rows)}</li>
<li>Источник: {escape(indicator.source)}</li>
</ul></section>
<section><h2>Все значения за {year} год</h2><table><thead><tr><th>Дата</th><th>{value_head}</th></tr></thead><tbody>{data_rows}</tbody></table></section>"""
        chart_caption = (
            f"{name} в {year} году — график динамики. "
            f"Источник: {indicator.source}. forecasteconomy.com"
        )
        chart_alt = (
            f"{name} в {year} году — график, "
            f"{summary_label.lower()} {summary_text}, источник {indicator.source}"
        )
        image_caption = f"{name} в {year} году — график и итоги"

    year_links = _links_list(
        tuple(
            (paths.russia_indicator_year(code, y), f"{name} в {y} году")
            for y in years
            if y != year
        )[-12:]
    )
    canonical_path = paths.russia_indicator_year(code, year)
    year_trail = crumbs.russia_indicator_year_trail(
        category.name if category else None,
        paths.russia_category(category.slug) if category else None,
        name,
        paths.russia_indicator(code),
        year,
        canonical_path,
    )
    body = f"""<main class="seo-page">
{_breadcrumbs_nav(year_trail)}
<h1>{escape(title.split(" — ")[0])}</h1>
<p>{escape(desc)}</p>
<figure class="seo-chart"><img src="{DOMAIN}{escape(paths.og_indicator(paths.RUSSIA, code, year))}" width="1200" height="630" alt="{escape(chart_alt)}" loading="lazy"><figcaption>{escape(chart_caption)}</figcaption></figure>
{data_section}
<section><h2>График и прогноз</h2><p>Полная история, интерактивный график и прогноз — на странице {_link(paths.russia_indicator(code), name)}.</p></section>
<section><h2>Другие годы</h2>{year_links}</section>
</main>"""
    # temporalCoverage — по факту, не «до 31 декабря» для незакрытого года (В-26).
    # Для годового ряда с одной точкой покрытие — дата этой точки.
    if single_point:
        coverage_end = _iso_date(last.date)
    else:
        coverage_end = _iso_date(last.date) if current_year else f"{year}-12-31"
    json_ld = [
        _site_json_ld(),
        _breadcrumbs(year_trail),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"{name} — {year} год",
            "description": desc,
            "url": _absolute(canonical_path),
            "inLanguage": "ru-RU",
            "creator": {"@type": "Organization", "name": indicator.source},
            "temporalCoverage": f"{_iso_date(first.date)}/{coverage_end}",
            "variableMeasured": name,
            "image": f"{DOMAIN}{paths.og_indicator(paths.RUSSIA, code, year)}",
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": f"{DOMAIN}{paths.og_indicator(paths.RUSSIA, code, year)}",
            "url": f"{DOMAIN}{paths.og_indicator(paths.RUSSIA, code, year)}",
            "caption": image_caption,
            "width": 1200,
            "height": 630,
            "representativeOfPage": True,
        },
    ]
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical_path,
        body=body,
        json_ld=json_ld,
        keywords=f"{name} {year}, {name} {year} год, {indicator.seo_keywords or name}",
        og_image=f"{DOMAIN}{paths.og_indicator(paths.RUSSIA, code, year)}",
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
            href = escape(_absolute(paths.russia_indicator(alt_code)))
            links.append(f'<link rel="alternate" hreflang="ru-RU" href="{href}">')
    primary_code = cfg.get("primary_indicator_code")
    if primary_code:
        href = escape(_absolute(paths.russia_indicator(primary_code)))
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
    data_code: str | None = None,
    data_years: list[int] | None = None,
    forecast_ssr: bool = False,
) -> str:
    name = display_name or indicator.name
    unit = display_unit or indicator.unit
    frequency = display_frequency or indicator.frequency
    # Семантика значений определяется рядом, который реально показан
    # (data_code режима), а не базовой карточкой.
    value_code = data_code or indicator.code
    current = latest_rows[0] if latest_rows else None
    crumb_trail = crumbs.russia_indicator_trail(
        category.name if category else None,
        paths.russia_category(category.slug) if category else None,
        name,
        paths.russia_indicator(indicator.code),
    )
    # CPI-индекс (~100.xx) людям показывается как изменение цен в % — как в
    # React-слое; сырой индекс в SSR был воспроизведённым инцидентом «100,2%».
    cpi_mode = is_cpi_index(value_code)
    value_head = "Изменение цен, %" if cpi_mode else (f"Значение, {unit}" if unit else "Значение")
    data_rows = "".join(
        f"<tr><td>{escape(_format_date(row.date))}</td>"
        f"<td>{escape(format_number_ru(display_value(value_code, row.value), signed=cpi_mode))}</td></tr>"
        for row in latest_rows
    )
    source_link = _link(indicator.source_url, indicator.source) if indicator.source_url else escape(indicator.source)
    related_links = tuple((paths.russia_indicator(ind.code), ind.name) for ind in related)
    custom_blocks = _indicator_blocks_from_db(indicator)
    # Индикаторы с собственными seo_blocks — без GLOBAL (иначе два блока
    # «Источник и обновление» в SSR: generic + предметный).
    blocks = custom_blocks if custom_blocks else GLOBAL_INDICATOR_BLOCKS
    current_text = display_value_text(
        value_code, current.value if current else None, unit, frequency,
    )
    # V5: alt с «прогноз» на пилотных карточках; иначе — факт + последнее значение.
    chart_alt = (
        forecast_ssr_image_name(name)
        if forecast_ssr
        else (
            f"{name} — график динамики, последнее значение "
            f"{current_text}, источник {indicator.source}"
        )
    )
    og_code = indicator.code
    # V4: видимый абзац под графиком (только пилот с реальным прогнозом).
    forecast_note = ""
    if forecast_ssr:
        forecast_note = (
            f'<p class="seo-forecast-note">{escape(FORECAST_SSR_CHART_NOTE)}'
            f'{_link("/methodology", "как считается прогноз")}.</p>\n'
        )
    # А-4: блок «по годам» — ссылки на годовые landing'и (последние 12 лет).
    years_section = ""
    if data_years:
        year_links = _links_list(tuple(
            (paths.russia_indicator_year(indicator.code, y), f"{name} в {y} году")
            for y in sorted(data_years, reverse=True)[:12]
        ))
        years_section = f"<section><h2>{escape(name)} по годам</h2>{year_links}</section>\n"
    return f"""<main class="seo-page">
{_breadcrumbs_nav(crumb_trail)}
<h1>{escape(name)}</h1>
<p>{escape(clean_text(indicator.description, f"{name}: официальный экономический индикатор с историей значений и графиком."))}</p>
<figure class="seo-chart"><img src="{DOMAIN}{escape(paths.og_indicator(paths.RUSSIA, og_code))}" width="1200" height="630" alt="{escape(chart_alt)}" loading="lazy"><figcaption>{escape(name)} — график динамики по данным {escape(indicator.source)}. Источник: forecasteconomy.com</figcaption></figure>
{forecast_note}<section><h2>Текущее значение</h2>
<ul>
<li>Последнее значение: {escape(current_text)}</li>
<li>Дата последнего значения: {escape(_format_date(current.date if current else None))}</li>
<li>Периодичность: {escape(_format_frequency(frequency))}</li>
<li>Источник: {source_link}</li>
<li>Количество точек: {int(count)}</li>
<li>Период данных: {escape(_format_date(first_dt))} — {escape(_format_date(last_dt))}</li>
</ul></section>
{_blocks_html(blocks, current_code=indicator.code)}
<section><h2>Методология</h2><p>{escape(clean_text(indicator.methodology, "Методология показателя указана по данным официального источника и используется для интерпретации ряда."))}</p></section>
<section><h2>Последние данные</h2><table><thead><tr><th>Дата</th><th>{escape(value_head)}</th></tr></thead><tbody>{data_rows}</tbody></table></section>
{years_section}<section><h2>Связанные индикаторы</h2>{_links_list(related_links or ((paths.russia_category(category.slug), category.name),) if category else tuple())}</section>
</main>"""
