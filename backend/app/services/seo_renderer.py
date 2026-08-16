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
    format_date_locale,
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
    GLOBAL_INDICATOR_BLOCKS,
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
    """Человекочитаемая дата («1 мая 2026» / «1 May 2026») — для видимого текста."""
    from app.services.display import format_date_locale

    return format_date_locale(value)


def _iso_date(value: date | None) -> str:
    """ISO-дата для машинных полей JSON-LD (temporalCoverage, dateModified)."""
    return value.isoformat() if value else ""


def _format_number(value) -> str:
    """Locale typography for visible SSR numbers (RU comma / EN period)."""
    from app.services.locale import get_locale

    return format_number_ru(value, locale=get_locale())


def _absolute(path: str) -> str:
    """Absolute URL on the request host (canonical / JSON-LD url)."""
    from app.services.locale import get_request_origin

    origin = get_request_origin()
    if path == "/":
        return origin
    return f"{origin}{path}"


def _link(path: str, label: str) -> str:
    return f'<a href="{escape(path)}">{escape(label)}</a>'


def _breadcrumbs_nav(items: list[tuple[str, str]]) -> str:
    """Видимые крошки: шеврон « / », последний узел без ссылки."""
    if not items:
        return ""
    from app.services.locale import get_locale

    parts: list[str] = []
    last = len(items) - 1
    for index, (path, name) in enumerate(items):
        if index:
            parts.append(" / ")
        if index == last:
            parts.append(escape(name))
        else:
            parts.append(_link(path, name))
    aria = "Breadcrumb" if get_locale() == "en" else "Хлебные крошки"
    return f'<nav aria-label="{aria}">{"".join(parts)}</nav>'


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
    from app.services.locale import get_locale

    en = get_locale() == "en"
    if not value:
        return "not specified" if en else "не указана"
    key = value.lower()
    if en:
        return FREQUENCY_LABELS_EN.get(key, value)
    return FREQUENCY_LABELS_RU.get(key, value)


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
    from app.services.locale import get_locale

    loc = get_locale()
    value_text = display_value_text(
        code, current.value, unit, frequency, locale=loc,
    )
    period = value_period_phrase(current.date, frequency, locale=loc)
    if loc == "en":
        snippet = f"Latest value — {value_text} {period}."
    else:
        snippet = f"Актуальное значение — {value_text} {period}."
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
    from app.services.locale import get_locale, get_request_origin

    en = get_locale() == "en"
    origin = get_request_origin()
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": f"{origin}/#website",
                "url": origin,
                "name": "Forecast Economy",
                "description": (
                    "Analytical platform for official economic data on Russia, "
                    "85 regions and available countries: charts, tables, comparisons and forecasts."
                    if en
                    else (
                        "Аналитическая платформа официальных экономических данных России, "
                        "85 регионов и доступных стран: графики, таблицы, сравнения и прогнозы."
                    )
                ),
                "inLanguage": "en" if en else "ru-RU",
                "publisher": {"@id": f"{origin}/#organization"},
            },
            {
                "@type": "Organization",
                "@id": f"{origin}/#organization",
                "name": "Forecast Economy",
                "url": origin,
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
# `_ssr_platform_deep_links()` внутри body (бот читает; React заменит #root).
#
# RU-константы ниже — эталон и для тестов структуры href. EN — через
# `_ssr_chrome_*()` / `_ssr_platform_deep_links()` по get_locale().
_SSR_CHROME_HEADER = f"""<header class="seo-topbar"><div class="seo-topbar-in">
<a class="seo-brand" href="/">Forecast<em>Economy</em></a>
<nav class="seo-topnav"><a href="/">Индикаторы</a><a href="{paths.today()}">Сегодня</a><a href="{paths.region_hub()}">Регионы</a><a href="{paths.world_hub()}">Страны</a><a href="{paths.world_rating("unemployment-rate")}">Рейтинг стран</a><a href="{paths.calendar()}">Календарь</a><a href="/compare">Сравнение</a><a href="/calculator">Калькуляторы</a><a href="/about">О проекте</a></nav>
</div></header>"""

_SSR_CHROME_HEADER_EN = f"""<header class="seo-topbar"><div class="seo-topbar-in">
<a class="seo-brand" href="/">Forecast<em>Economy</em></a>
<nav class="seo-topnav"><a href="/">Indicators</a><a href="{paths.today()}">Today</a><a href="{paths.region_hub()}">Regions</a><a href="{paths.world_hub()}">Countries</a><a href="{paths.world_rating("unemployment-rate")}">Country rankings</a><a href="{paths.calendar()}">Calendar</a><a href="/compare">Compare</a><a href="/calculator">Calculators</a><a href="/about">About</a></nav>
</div></header>"""

_SSR_CHROME_FOOTER = f"""<div class="seo-cta"><div class="seo-cta-in">
<p><strong>Интерактивные графики, сравнения и проверенные прогнозы</strong> — для показателей России, регионов и доступных стран. Просмотр открыт всем, скачивание — после бесплатной регистрации.</p>
<a class="seo-btn" href="/">Открыть платформу</a>
</div></div>
<footer class="seo-foot">Данные — только официальные первоисточники: государственные статистические ведомства, центральные банки и официальные биржи. Обновляются по мере публикации. © Forecast Economy — <a href="/">forecasteconomy.com</a></footer>
<script type="module" src="/assets/behavior-standalone.js" defer></script>"""

_SSR_CHROME_FOOTER_EN = f"""<div class="seo-cta"><div class="seo-cta-in">
<p><strong>Interactive charts, comparisons, and validated forecasts</strong> — for Russia, its regions, and available countries. Browsing is open to everyone; downloads require a free account.</p>
<a class="seo-btn" href="/">Open the platform</a>
</div></div>
<footer class="seo-foot">Data come only from official primary sources: national statistical offices, central banks, and official exchanges. Updated as publishers release. © Forecast Economy — <a href="/">forecasteconomy.com</a></footer>
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

_SSR_PLATFORM_DEEP_LINKS_EN = f"""
<section class="seo-section seo-platform-nav" aria-label="Platform sections">
<h2>Platform sections</h2>
<ul class="seo-pills">
<li><a href="/">Russia indicators</a></li>
<li><a href="{paths.today()}">Economy today</a></li>
<li><a href="{paths.region_hub()}">Regions of Russia</a></li>
<li><a href="{paths.world_hub()}">Country statistics</a></li>
<li><a href="{paths.calendar()}">Release calendar</a></li>
<li><a href="/compare">Compare indicators</a></li>
</ul>
</section>
"""


def _ssr_chrome_header() -> str:
    from app.services.locale import get_locale

    return _SSR_CHROME_HEADER_EN if get_locale() == "en" else _SSR_CHROME_HEADER


def _ssr_chrome_footer() -> str:
    from app.services.locale import get_locale

    return _SSR_CHROME_FOOTER_EN if get_locale() == "en" else _SSR_CHROME_FOOTER


def _ssr_platform_deep_links() -> str:
    from app.services.locale import get_locale

    return (
        _SSR_PLATFORM_DEEP_LINKS_EN
        if get_locale() == "en"
        else _SSR_PLATFORM_DEEP_LINKS
    )


FREQUENCY_LABELS_RU = {
    "daily": "ежедневно",
    "weekly": "еженедельно",
    "monthly": "ежемесячно",
    "quarterly": "ежеквартально",
    "annual": "ежегодно",
    "yearly": "ежегодно",
}

FREQUENCY_LABELS_EN = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
    "quarterly": "quarterly",
    "annual": "annual",
    "yearly": "annual",
}

FLAGSHIP_CODES = tuple(meta.flagship_code for meta in CATEGORY_META.values())
SSR_LATEST_ROWS = 12


def _hreflang_head(canonical_path: str) -> str:
    """Emit hreflang only after apex EN cutover and when an EN twin is catalogued.

    Until ``settings.apex_locale_en`` is True, apex is still Russian — do not
    advertise ``hreflang="en"`` → apex (would lie to crawlers).
    """
    from app.config import settings
    from app.data.i18n.en_catalog import has_en_path
    from app.services.locale import (
        en_public_origin,
        og_locale_alternate,
        ru_public_origin,
    )

    if not settings.apex_locale_en:
        return ""

    path = canonical_path if canonical_path.startswith("/") else f"/{canonical_path}"
    path = path.split("?", 1)[0]
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if not has_en_path(path):
        return ""

    path_href = "/" if path == "/" else path
    ru_href = escape(f"{ru_public_origin()}{path_href}")
    en_href = escape(f"{en_public_origin()}{path_href}")
    # x-default → apex (EN) when EN exists.
    return "\n".join(
        [
            f'<link rel="alternate" hreflang="ru" href="{ru_href}">',
            f'<link rel="alternate" hreflang="en" href="{en_href}">',
            f'<link rel="alternate" hreflang="x-default" href="{en_href}">',
            f'<meta property="og:locale:alternate" content="{og_locale_alternate()}">',
        ]
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
    og_image: str | None = None,
    include_app: bool = True,
) -> str:
    """Полный SSR HTML-документ.

    og_image — per-page превью (индикаторы получают /og/{code}.png);
    include_app=False — чистая HTML-страница без React-bundle (годовые
    landing'и: у SPA-роутера нет такого маршрута, гидратация показала бы 404).
    """
    from app.services.locale import get_locale, html_lang, og_locale

    assets = await get_app_assets()
    url = _absolute(canonical_path)
    safe_title = escape(title)
    safe_desc = escape(truncate_meta(clean_text(description), 300))
    safe_keywords = escape(clean_text(keywords or DEFAULT_KEYWORDS)[:400])
    structured = "\n".join(_json_script(item) for item in (json_ld or []))
    extras = extra_head or ""
    hreflang = _hreflang_head(canonical_path)
    css_preload = _css_preload(assets.head_links)
    og_url = escape(og_image or _absolute("/og-image-v2.png"))
    body_scripts = assets.body_scripts if include_app else ""
    lang = html_lang()
    locale_og = og_locale()
    rss_title = (
        "Forecast Economy — data updates"
        if get_locale() == "en"
        else "Forecast Economy — обновления данных"
    )
    head_links = assets.head_links if include_app else _strip_preloads(assets.head_links)
    if not include_app:
        # Чистые SSR-страницы получают брендовый хром: шапка-навигация + CTA на
        # платформу + футер об источниках. React-страницы — нет (гидратация
        # заменит #root своим layout'ом). Locale-aware: EN chrome на apex.
        body = f"{_ssr_chrome_header()}\n{body}\n{_ssr_chrome_footer()}"
    elif "seo-platform-nav" not in body:
        # SPA-SSR без chrome: бот видит только prerender в #root. Единый блок
        # выхода в хабы — иначе тонкие семейства (/today/*, /calendar/*) —
        # тупики с одними крошками. React при гидратации заменит #root.
        body = f"{body.rstrip()}\n{_ssr_platform_deep_links()}"
    return f"""<!DOCTYPE html>
<html lang="{lang}">
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
<link rel="alternate" type="application/rss+xml" title="{rss_title}" href="{escape(_absolute("/feed.xml"))}">
{hreflang}
{extras}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Forecast Economy">
<meta property="og:url" content="{escape(url)}">
<meta property="og:title" content="{safe_title}">
<meta property="og:description" content="{safe_desc}">
<meta property="og:locale" content="{locale_og}">
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


def render_not_found_html(message: str | None = None) -> str:
    """Брендовая 404 для SSR-роутов и nginx catch-all.

    Самодостаточный документ (без asset-fetch и БД): critical CSS + хром +
    навигация по основным разделам. noindex — чтобы поисковики не тащили
    404-страницы в выдачу. Не тупик: ведём в каталог, сегодня, регионы,
    страны, сравнение и поиск на главной.
    """
    from app.services.locale import get_locale, html_lang
    from app.services.seo_i18n import get_category_seo

    en = get_locale() == "en"
    if message is None:
        message = "Page not found" if en else "Страница не найдена"
    safe = escape(message)
    cats = []
    for slug, meta in list(CATEGORY_META.items())[:6]:
        disp = get_category_seo(slug) or meta
        cats.append(
            f'<li><a href="{escape(paths.russia_category(slug))}">{escape(disp.name)}</a></li>'
        )
    category_links = "".join(cats)
    if en:
        lead = "This page does not exist or has moved. Continue from here:"
        links = f"""<li><a href="/">All Russia economic indicators</a></li>
<li><a href="{paths.today()}">Key indicators for today</a></li>
<li><a href="{paths.region_hub()}">Statistics by Russian regions</a></li>
<li><a href="{paths.world_hub()}">Country statistics</a></li>
<li><a href="/compare">Compare indicators</a></li>
<li><a href="{paths.calendar()}">Statistical release calendar</a></li>
<li><a href="/">Search the platform</a> — open the home page and use search in the header</li>"""
        catalog_h2 = "Catalogue sections"
    else:
        lead = "Такой страницы нет или она переехала. Вот с чего можно продолжить:"
        links = f"""<li><a href="/">Все экономические индикаторы России</a></li>
<li><a href="{paths.today()}">Ключевые показатели на сегодня</a></li>
<li><a href="{paths.region_hub()}">Статистика по регионам России</a></li>
<li><a href="{paths.world_hub()}">Статистика по странам</a></li>
<li><a href="/compare">Сравнение показателей</a></li>
<li><a href="{paths.calendar()}">Календарь публикаций статистики</a></li>
<li><a href="/">Поиск по платформе</a> — откройте главную и воспользуйтесь поиском в шапке</li>"""
        catalog_h2 = "Разделы каталога"

    return f"""<!DOCTYPE html>
<html lang="{html_lang()}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{SEO_CRITICAL_CSS}
<title>{safe} — Forecast Economy</title>
<meta name="robots" content="noindex, follow">
</head>
<body>
{_ssr_chrome_header()}
<main class="seo-page">
<h1>{safe}</h1>
<p>{lead}</p>
<ul>
{links}
</ul>
<section><h2>{catalog_h2}</h2>
<ul>
{category_links}
</ul></section>
</main>
{_ssr_chrome_footer()}
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
    from app.services.locale import in_language
    from app.services.seo_i18n import get_page_seo

    page = get_page_seo(page_slug)
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
            "inLanguage": in_language(),
            "isPartOf": {"@id": f"{_absolute("/")}/#website"},
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
    from app.services.locale import in_language
    from app.services.seo_i18n import get_page_seo

    flagships = await _indicators_by_codes(db, FLAGSHIP_CODES)
    from app.services.i18n_display import public_name

    flagship_links = tuple(
        (paths.russia_indicator(ind.code), public_name(ind.name, ind.name_en))
        for ind in flagships
    )
    page = get_page_seo("home")
    if page is None:
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
        _breadcrumbs([crumbs.home()]),
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page.title,
            "description": page.description,
            "url": _absolute("/"),
            "inLanguage": in_language(),
            "isPartOf": {"@id": f"{_absolute("/")}/#website"},
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
                    "name": public_name(ind.name, ind.name_en),
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
    from app.services.locale import in_language
    from app.services.seo_i18n import get_category_seo, get_page_seo

    page = get_page_seo("russia-categories")
    if not page:
        return 404, "Not found"
    trail = crumbs.russia_categories_trail()
    categories = {
        slug: get_category_seo(slug) or meta
        for slug, meta in CATEGORY_META.items()
    }
    links = tuple(
        (paths.russia_category(slug), meta.name)
        for slug, meta in categories.items()
    )
    body = f"""<main class="seo-page">
{_breadcrumbs_nav(trail)}
<h1>{escape(page.h1)}</h1>
<p>{escape(page.intro)}</p>
{_blocks_html(page.blocks)}
<section><h2>Категории</h2>{_category_rich_list(categories)}</section>
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
            "inLanguage": in_language(),
            "mainEntity": [
                {
                    "@type": "Thing",
                    "name": meta.name,
                    "url": _absolute(paths.russia_category(slug)),
                }
                for slug, meta in categories.items()
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
    from app.services.i18n_display import public_name
    from app.services.locale import in_language
    from app.services.seo_i18n import get_category_seo

    category = get_category_seo(slug)
    if not category:
        return 404, "Not found"
    indicators = await _active_indicators(
        db, category=category.api_category, listed_only=True
    )
    indicators = _sort_indicators_for_seo(indicators, category)
    links = tuple(
        (paths.russia_indicator(ind.code), public_name(ind.name, ind.name_en))
        for ind in indicators
    )
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
            "inLanguage": in_language(),
            "mainEntity": [
                {
                    "@type": "Dataset",
                    "name": public_name(ind.name, ind.name_en),
                    "url": _absolute(paths.russia_indicator(ind.code)),
                }
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
        resolve_view_mode,
    )
    from app.services.locale import get_locale, in_language
    from app.services.seo_i18n import (
        indicator_template,
        localize_mode_display_suffix,
        public_indicator_seo,
        translate_source,
    )
    from app.services.display import localize_unit

    q = await db.execute(select(Indicator).where(Indicator.code == code, Indicator.is_active.is_(True)))
    indicator = q.scalar_one_or_none()
    if not indicator:
        return 404, "Not found"

    loc = get_locale()
    overlay = public_indicator_seo(
        indicator.code,
        name_ru=indicator.name,
        name_en=indicator.name_en,
        description_ru=indicator.description,
        methodology_ru=indicator.methodology,
        unit_ru=indicator.unit,
        source_ru=indicator.source,
        seo_title_ru=indicator.seo_title,
        seo_description_ru=indicator.seo_description,
        seo_blocks_ru=indicator.seo_blocks,
        frequency=indicator.frequency,
        locale=loc,
    )
    base_name = overlay["name"] or indicator.name
    source_label = overlay.get("source") or translate_source(indicator.source, loc) or indicator.source

    family = FAMILY_BY_BASE.get(code)
    resolved_mode = resolve_view_mode(code, mode) if family else None
    data_code = data_indicator_code(code, mode) if family else code
    data_indicator = indicator
    if data_code != code:
        dq = await db.execute(
            select(Indicator).where(Indicator.code == data_code, Indicator.is_active.is_(True))
        )
        data_indicator = dq.scalar_one_or_none() or indicator

    display_name = base_name
    display_unit = overlay.get("unit") or indicator.unit
    display_frequency = indicator.frequency
    if family and resolved_mode:
        suffix = localize_mode_display_suffix(family, resolved_mode, locale=loc)
        if suffix:
            display_name = f"{base_name} — {suffix}"
        # Mode unit is storage RU; overlay unit wins when mode keeps the base unit.
        display_unit = localize_unit(
            resolved_mode.unit or display_unit, locale=loc
        )
        display_frequency = resolved_mode.frequency or display_frequency
    else:
        display_unit = localize_unit(display_unit, locale=loc)

    category = _category_for_api(indicator.category)
    latest_rows = await _latest_rows(db, data_indicator.id, limit=SSR_LATEST_ROWS)
    count, first_dt, last_dt = await _indicator_stats(db, data_indicator.id)
    related = await _related_indicators(db, indicator)
    # А-4: внутренняя перелинковка «по годам» — год-запросы («X в 2019»)
    # должны ранжировать годовые landing'и, а не карточку со сниппетом «сегодня».
    data_years = await indicator_data_years(db, indicator.id)
    if loc == "en":
        # Always from display_name (includes mode suffix), never RU seo_title from DB.
        title = (
            indicator_template("title", loc) or "{name} — data and chart"
        ).format(name=display_name)
    else:
        title = indicator.seo_title or f"{display_name} — данные и график"
    desc = (
        overlay.get("seo_description")
        or clean_text(
            overlay.get("description") or indicator.description,
            (
                indicator_template("description_fallback", loc)
                or "{name}: динамика, источник, методология и последние значения."
            ).format(name=display_name),
        )
    )
    forecast_ssr = _forecast_ssr_enabled(indicator)
    # V2: хвост meta description (без дубля, если «прогноз» уже в тексте).
    if forecast_ssr:
        if loc == "en":
            tail = indicator_template("forecast_desc_tail", loc) or ""
            if tail and "forecast" not in desc.lower():
                desc = f"{desc.rstrip('.')}." if desc else ""
                desc = f"{desc} {tail}".strip() if desc else tail
        else:
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
        description=overlay.get("description"),
        methodology=overlay.get("methodology"),
        source_label=source_label,
        seo_blocks=overlay.get("seo_blocks"),
        locale=loc,
    )
    canonical_path = paths.russia_indicator(indicator.code)
    if resolved_mode and resolved_mode.mode != family.default_mode:
        canonical_path = f"{canonical_path}?mode={resolved_mode.mode}"
    # OG-картинка и видимый график — код карточки (URL), не sibling-режима:
    # /og/{base}.png всегда существует; /og/{base}-yoy.png на проде часто 404
    # (unlisted derived ещё без превью). Смысл режима остаётся в title/Dataset.
    og_path = _absolute(paths.og_indicator(paths.RUSSIA, indicator.code))
    if forecast_ssr:
        image_name = (
            indicator_template("forecast_image_name", loc)
            or forecast_ssr_image_name(display_name)
        ).format(name=display_name) if loc == "en" else forecast_ssr_image_name(display_name)
    else:
        image_name = (
            indicator_template("image_name", loc)
            or "{name} — график динамики ({source})"
        ).format(name=display_name, source=source_label)
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
            "inLanguage": in_language(),
            "creator": {"@type": "Organization", "name": source_label},
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
            "caption": image_name,
            "description": desc,
            "width": 1200,
            "height": 630,
            "representativeOfPage": True,
            "creditText": "Forecast Economy",
            "author": {"@type": "Organization", "name": "Forecast Economy"},
        },
    ]
    faq_blocks = overlay.get("seo_blocks") if loc == "en" else None
    if faq_blocks:
        from app.services.seo_content import SeoBlock
        faq_ld = _faq_json_ld(
            tuple(SeoBlock(title=b["title"], body=b["body"]) for b in faq_blocks
                  if b.get("title") and b.get("body"))
        )
    else:
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
    from app.services.seo_i18n import year_template

    cpi_mode = is_cpi_index(code)
    shown = display_value(code, value)
    unit_suffix = f" {unit}" if unit and not cpi_mode else (" %" if cpi_mode else "")
    yt = year_template
    lines = [
        (yt("change_value") or "Значение: {value}").format(
            value=f"{format_number_ru(shown, signed=cpi_mode)}{unit_suffix}"
        ),
    ]
    if prev_value is None or prev_year is None:
        lines.append(
            yt("change_no_prev")
            or "Изменение к предыдущему году: нет сопоставимого значения"
        )
        return lines
    prev_shown = display_value(code, prev_value)
    if shown is None or prev_shown is None:
        lines.append(
            (yt("change_no_data") or "Изменение к {prev_year} году: нет данных").format(
                prev_year=prev_year
            )
        )
        return lines
    delta = shown - prev_shown
    abs_text = format_number_ru(delta, signed=True)
    if prev_shown == 0:
        pct_text = yt("change_zero_base") or "не рассчитывается (база равна нулю)"
    else:
        pct = round((delta / abs(prev_shown)) * 100.0, 2)
        pct_text = f"{format_number_ru(pct, signed=True)} %"
    lines.append(
        (yt("change_vs") or "Изменение к {prev_year} году: {abs}{unit} ({pct})").format(
            prev_year=prev_year,
            abs=abs_text,
            unit=unit_suffix,
            pct=pct_text,
        )
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
    from app.services.seo_i18n import year_template

    yt = year_template
    if len(series) < 2:
        return [
            yt("hist_insufficient")
            or "Положение в истории: недостаточно соседних лет для сравнения"
        ]
    cpi_mode = is_cpi_index(code)
    unit_suffix = f" {unit}" if unit and not cpi_mode else (" %" if cpi_mode else "")
    shown_pairs = [
        (y, display_value(code, v))
        for y, v, _d in series
        if display_value(code, v) is not None
    ]
    if not shown_pairs:
        return [yt("hist_no_data") or "Положение в истории: нет данных"]
    shown_map = {y: s for y, s in shown_pairs}
    current = shown_map.get(year)
    if current is None:
        current = display_value(code, value)
    if current is None:
        return [yt("hist_no_data") or "Положение в истории: нет данных"]
    values = [s for _y, s in shown_pairs]
    mean = sum(values) / len(values)
    n_years = len(shown_pairs)
    if current > mean:
        vs_mean = (yt("hist_above") or "выше среднего за {n} лет").format(n=n_years)
    elif current < mean:
        vs_mean = (yt("hist_below") or "ниже среднего за {n} лет").format(n=n_years)
    else:
        vs_mean = (yt("hist_at") or "на уровне среднего за {n} лет").format(n=n_years)
    lines = [
        (
            yt("hist_position")
            or "Положение в истории: {vs_mean} (среднее — {mean})"
        ).format(
            vs_mean=vs_mean,
            mean=f"{format_number_ru(mean, signed=cpi_mode)}{unit_suffix}",
        ),
    ]
    vmax = max(values)
    vmin = min(values)
    max_years = sorted(y for y, s in shown_pairs if s == vmax)
    min_years = sorted(y for y, s in shown_pairs if s == vmin)

    def _gap_ago(gap: int) -> str:
        if gap <= 0:
            return ""
        en = yt("gap_ago")
        if en:
            return en.format(n=gap)
        gap_text = (
            f"{gap} год назад" if gap == 1
            else f"{gap} года назад" if 2 <= gap % 10 <= 4 and not 12 <= gap % 100 <= 14
            else f"{gap} лет назад"
        )
        return f" ({gap_text})"

    if current == vmax and year in max_years:
        if len(max_years) == 1:
            lines.append(
                (
                    yt("hist_max_sole")
                    or "Это максимум за всю доступную историю ряда ({n} лет)"
                ).format(n=n_years)
            )
        else:
            lines.append(
                (
                    yt("hist_max_tie")
                    or "Это один из максимумов истории ряда ({value})"
                ).format(
                    value=f"{format_number_ru(vmax, signed=cpi_mode)}{unit_suffix}"
                )
            )
    else:
        peak_year = max_years[-1]
        gap = year - peak_year
        lines.append(
            (
                yt("hist_max_other")
                or "Максимум истории — {value} в {peak_year} году{gap}"
            ).format(
                value=f"{format_number_ru(vmax, signed=cpi_mode)}{unit_suffix}",
                peak_year=peak_year,
                gap=_gap_ago(gap) if gap > 0 else "",
            )
        )
    if current == vmin and year in min_years:
        if len(min_years) == 1:
            lines.append(
                (
                    yt("hist_min_sole")
                    or "Это минимум за всю доступную историю ряда ({n} лет)"
                ).format(n=n_years)
            )
        else:
            lines.append(
                (
                    yt("hist_min_tie")
                    or "Это один из минимумов истории ряда ({value})"
                ).format(
                    value=f"{format_number_ru(vmin, signed=cpi_mode)}{unit_suffix}"
                )
            )
    else:
        floor_year = min_years[-1]
        gap = year - floor_year
        lines.append(
            (
                yt("hist_min_other")
                or "Минимум истории — {value} в {floor_year} году{gap}"
            ).format(
                value=f"{format_number_ru(vmin, signed=cpi_mode)}{unit_suffix}",
                floor_year=floor_year,
                gap=_gap_ago(gap) if gap > 0 else "",
            )
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
    from app.services.seo_i18n import year_template

    yt = year_template
    freq = (frequency or "").lower()
    summary_bit = summary_text.rstrip(".")
    # EN keeps natural title case on summary labels; RU lowercases mid-sentence.
    summary_label_out = summary_label if yt("title_annual") else summary_label.lower()

    if yt("title_annual"):
        if freq == "annual":
            title_key = "title_annual_current" if current_year else "title_annual"
        elif current_year:
            title_key = "title_ytd"
        elif n_rows == 1:
            title_key = "title_single"
        elif freq == "quarterly":
            title_key = "title_quarterly"
        elif freq == "weekly":
            title_key = "title_weekly"
        elif freq == "daily":
            title_key = "title_daily"
        else:
            title_key = "title_monthly"
        title = yt(title_key).format(name=name, year=year)
        desc_key = "desc_single" if (n_rows == 1 or freq == "annual") else "desc_multi"
        desc = yt(desc_key).format(
            name=name,
            year=year,
            period_note=period_note,
            summary_label=summary_label_out,
            summary_bit=summary_bit,
            source=source,
            n=n_rows,
        )
        return title, desc

    if freq == "annual":
        title = (
            f"{name} в {year} году — актуальное годовое значение"
            if current_year
            else f"{name} в {year} году — значение и динамика"
        )
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
    category = _category_for_api(indicator.category)

    from app.services.locale import in_language
    from app.services.seo_i18n import (
        get_category_seo,
        public_indicator_fields,
        translate_source,
        year_template,
    )

    yt = year_template
    fields = public_indicator_fields(
        code,
        name_ru=indicator.name,
        name_en=indicator.name_en,
        unit_ru=indicator.unit,
    )
    name = fields["name"] or indicator.name
    unit = fields["unit"] or (indicator.unit or "")
    source = translate_source(indicator.source) or indicator.source or (
        "official source" if yt("title_annual") else "официальный источник"
    )
    cat_name = None
    if category is not None:
        en_cat = get_category_seo(category.slug)
        cat_name = (en_cat.name if en_cat else None) or category.name
    # Семантика значений и итога — через display-adapter: CPI-индекс людям
    # показывается изменением цен, годовой итог сворачивается по природе ряда
    # (сумма для потоков, конец года для запасов, цепной рост для CPI) — а не
    # «среднее за год» для всего подряд (В-25).
    cpi_mode = is_cpi_index(code)
    shown_values = [display_value(code, v) for v in values]
    vmin, vmax = min(shown_values), max(shown_values)
    summary_label, summary_text = annual_summary(code, values, unit)
    if yt("summary_avg"):
        kind = {
            "Рост цен за год": "summary_chain",
            "Итог за год (сумма)": "summary_sum",
            "Значение на конец года": "summary_last",
            "Среднее за год": "summary_avg",
            "Итог за год": "summary_avg",
        }.get(summary_label)
        if kind and yt(kind):
            summary_label = yt(kind)
    # Незавершённый год не выдаём за «итоги года» (В-26): честная рамка
    # «с начала года», итог — «на дату последнего значения».
    current_year = today_msk().year == year
    if current_year:
        period_note = (
            yt("period_note_ytd") or " (данные с начала года по {date})"
        ).format(date=_format_date(last.date))
    else:
        period_note = ""
    # Годовой ряд / одна точка: «среднее за год» звучит неестественно.
    freq = (indicator.frequency or "").lower()
    if len(rows) == 1 and not is_cpi_index(code):
        if yt("summary_annual_value"):
            summary_label = (
                yt("summary_annual_value") if freq == "annual" else yt("summary_value")
            )
        else:
            summary_label = "Годовое значение" if freq == "annual" else "Значение"
        summary_text = display_value_text(code, last.value, unit, indicator.frequency)
    if current_year:
        summary_label = (
            yt("summary_as_of") or "{label} (на {date})"
        ).format(label=summary_label, date=_format_date(last.date))
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
        source=source,
    )

    series = await yearly_last_points(db, indicator.id)
    series_by_year = {y: (v, d) for y, v, d in series}
    prev_year = year - 1 if (year - 1) in series_by_year else None
    prev_value = series_by_year[prev_year][0] if prev_year is not None else None
    neighbors = neighbor_year_window(series, year, size=10)
    if cpi_mode:
        value_head = yt("th_cpi_change") or "Изменение цен, %"
    elif unit:
        value_head = (yt("th_value_unit") or "Значение, {unit}").format(unit=escape(unit))
    else:
        value_head = yt("th_value") or "Значение"

    single_point = len(rows) == 1
    if single_point:
        if current_year:
            totals_head = (
                yt("h2_single_as_of") or "{name} в {year} году: данные на {date}"
            ).format(name=name, year=year, date=_format_date(last.date))
        else:
            totals_head = (yt("h2_single") or "{name} в {year} году").format(
                name=name, year=year
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
            f"<li>{escape((yt('li_value_date') or 'Дата значения: {date}').format(date=_format_date(last.date)))}</li>"
            f"<li>{escape((yt('li_source') or 'Источник: {source}').format(source=source))}</li>"
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
        neighbors_h2 = yt("h2_neighbors") or "Динамика соседних лет"
        th_year = yt("th_year") or "Год"
        data_section = f"""<section><h2>{escape(totals_head)}</h2>
<ul>
{context_items}
</ul></section>
<section><h2>{escape(neighbors_h2)}</h2>
<table><thead><tr><th>{escape(th_year)}</th><th>{value_head}</th></tr></thead>
<tbody>{neighbor_rows}</tbody></table></section>"""
        chart_caption = (
            yt("chart_caption_single")
            or "{name} в {year} году — значение в контексте соседних лет. Источник: {source}. forecasteconomy.com"
        ).format(name=name, year=year, source=source)
        chart_alt = (
            yt("chart_alt_single")
            or "{name} в {year} году — график соседних лет, {summary_label} {summary_text}, источник {source}"
        ).format(
            name=name,
            year=year,
            summary_label=summary_label if yt("chart_alt_single") else summary_label.lower(),
            summary_text=summary_text,
            source=source,
        )
        image_caption = (
            yt("image_caption_single") or "{name} в {year} году — значение и динамика"
        ).format(name=name, year=year)
    else:
        if current_year:
            totals_head = (yt("h2_ytd") or "{name} в {year} году: данные с начала года").format(
                name=name, year=year
            )
        else:
            totals_head = (yt("h2_totals") or "Итоги {year} года").format(year=year)
        range_label = (
            (yt("range_cpi") or "Минимальное и максимальное изменение за период")
            if cpi_mode
            else (yt("range_minmax") or "Минимум и максимум")
        )
        data_rows = "".join(
            f"<tr><td>{escape(_format_date(r.date))}</td>"
            f"<td>{escape(format_number_ru(display_value(code, r.value), signed=cpi_mode))}</td></tr>"
            for r in rows
        )
        li_start = (yt("li_year_start") or "Значение на начало года: {value} ({date})").format(
            value=f"{format_number_ru(display_value(code, first.value), signed=cpi_mode)}{unit_suffix}",
            date=_format_date(first.date),
        )
        end_tpl = yt("li_latest") if current_year else yt("li_year_end")
        end_fallback = (
            "Последнее значение: {value} ({date})"
            if current_year
            else "Значение на конец года: {value} ({date})"
        )
        li_end = (end_tpl or end_fallback).format(
            value=f"{format_number_ru(display_value(code, last.value), signed=cpi_mode)}{unit_suffix}",
            date=_format_date(last.date),
        )
        all_h2 = (yt("h2_all_values") or "Все значения за {year} год").format(year=year)
        th_date = yt("th_date") or "Дата"
        data_section = f"""<section><h2>{escape(totals_head)}</h2>
<ul>
<li>{escape(summary_label)}: {escape(summary_text)}</li>
<li>{li_start}</li>
<li>{li_end}</li>
<li>{escape(range_label)}: {escape(format_number_ru(vmin, signed=cpi_mode))} … {escape(format_number_ru(vmax, signed=cpi_mode))}{unit_suffix}</li>
<li>{escape((yt('li_obs') or 'Количество наблюдений: {n}').format(n=len(rows)))}</li>
<li>{escape((yt('li_source') or 'Источник: {source}').format(source=source))}</li>
</ul></section>
<section><h2>{escape(all_h2)}</h2><table><thead><tr><th>{escape(th_date)}</th><th>{value_head}</th></tr></thead><tbody>{data_rows}</tbody></table></section>"""
        chart_caption = (
            yt("chart_caption_multi")
            or "{name} в {year} году — график динамики. Источник: {source}. forecasteconomy.com"
        ).format(name=name, year=year, source=source)
        chart_alt = (
            yt("chart_alt_multi")
            or "{name} в {year} году — график, {summary_label} {summary_text}, источник {source}"
        ).format(
            name=name,
            year=year,
            summary_label=summary_label if yt("chart_alt_multi") else summary_label.lower(),
            summary_text=summary_text,
            source=source,
        )
        image_caption = (
            yt("image_caption_multi") or "{name} в {year} году — график и итоги"
        ).format(name=name, year=year)

    year_link_tpl = yt("year_link") or "{name} в {year} году"
    year_links = _links_list(
        tuple(
            (paths.russia_indicator_year(code, y), year_link_tpl.format(name=name, year=y))
            for y in years
            if y != year
        )[-12:]
    )
    canonical_path = paths.russia_indicator_year(code, year)
    year_trail = crumbs.russia_indicator_year_trail(
        cat_name,
        paths.russia_category(category.slug) if category else None,
        name,
        paths.russia_indicator(code),
        year,
        canonical_path,
    )
    chart_h2 = yt("h2_chart") or "График и прогноз"
    other_h2 = yt("h2_other_years") or "Другие годы"
    chart_p_tpl = yt("chart_p") or "Полная история, интерактивный график и прогноз — на странице {_link}."
    chart_p = chart_p_tpl.format(_link=_link(paths.russia_indicator(code), name))
    h1_text = title.split(" — ")[0]
    body = f"""<main class="seo-page">
{_breadcrumbs_nav(year_trail)}
<h1>{escape(h1_text)}</h1>
<p>{escape(desc)}</p>
<figure class="seo-chart"><img src="{escape(_absolute(paths.og_indicator(paths.RUSSIA, code, year)))}" width="1200" height="630" alt="{escape(chart_alt)}" loading="lazy"><figcaption>{escape(chart_caption)}</figcaption></figure>
{data_section}
<section><h2>{escape(chart_h2)}</h2><p>{chart_p}</p></section>
<section><h2>{escape(other_h2)}</h2>{year_links}</section>
</main>"""
    # temporalCoverage — по факту, не «до 31 декабря» для незакрытого года (В-26).
    # Для годового ряда с одной точкой покрытие — дата этой точки.
    if single_point:
        coverage_end = _iso_date(last.date)
    else:
        coverage_end = _iso_date(last.date) if current_year else f"{year}-12-31"
    jsonld_name = (yt("jsonld_name") or "{name} — {year} год").format(name=name, year=year)
    json_ld = [
        _site_json_ld(),
        _breadcrumbs(year_trail),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": jsonld_name,
            "description": desc,
            "url": _absolute(canonical_path),
            "inLanguage": in_language(),
            "creator": {"@type": "Organization", "name": source},
            "temporalCoverage": f"{_iso_date(first.date)}/{coverage_end}",
            "variableMeasured": name,
            "image": _absolute(paths.og_indicator(paths.RUSSIA, code, year)),
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": _absolute(paths.og_indicator(paths.RUSSIA, code, year)),
            "url": _absolute(paths.og_indicator(paths.RUSSIA, code, year)),
            "caption": image_caption,
            "width": 1200,
            "height": 630,
            "representativeOfPage": True,
        },
    ]
    if yt("keywords"):
        keywords = yt("keywords").format(
            name=name,
            year=year,
            seo_keywords=name,
        )
    else:
        keywords = (
            f"{name} {year}, {name} {year} год, {indicator.seo_keywords or name}"
        )
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical_path,
        body=body,
        json_ld=json_ld,
        keywords=keywords,
        og_image=_absolute(paths.og_indicator(paths.RUSSIA, code, year)),
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
    from app.services.seo_i18n import get_category_seo

    if not api_category:
        return None
    for slug, category in CATEGORY_META.items():
        if category.api_category == api_category:
            return get_category_seo(slug) or category
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
    description: str | None = None,
    methodology: str | None = None,
    source_label: str | None = None,
    seo_blocks: list | None = None,
    locale: str | None = None,
) -> str:
    from app.services.i18n_display import public_name
    from app.services.locale import get_locale
    from app.services.seo_content import SeoBlock
    from app.services.seo_i18n import frequency_label_en, indicator_template
    from app.services.display import localize_unit

    loc = locale or get_locale()
    en = loc == "en"
    name = display_name or indicator.name
    unit = localize_unit(display_unit or indicator.unit, locale=loc)
    frequency = display_frequency or indicator.frequency
    src = source_label or indicator.source
    # Prefer caller overlay (INDICATOR_COPY_EN via public_indicator_seo); never prefer
    # empty string over fallback intro on EN.
    if description is not None and str(description).strip():
        desc_text = description
    elif en:
        desc_text = None  # intro_fb below
    else:
        desc_text = indicator.description
    if methodology is not None and str(methodology).strip():
        method_text = methodology
    elif en:
        method_text = None
    else:
        method_text = indicator.methodology
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
    if en:
        if cpi_mode:
            value_head = indicator_template("th_cpi_change", loc) or "Price change, %"
        elif unit:
            value_head = (indicator_template("th_value_unit", loc) or "Value, {unit}").format(unit=unit)
        else:
            value_head = indicator_template("th_value", loc) or "Value"
        freq_text = frequency_label_en(frequency)
        th_date = indicator_template("th_date", loc) or "Date"
        section_current = indicator_template("section_current", loc) or "Latest value"
        section_method = indicator_template("section_methodology", loc) or "Methodology"
        section_latest = indicator_template("section_latest", loc) or "Latest data"
        section_related = indicator_template("section_related", loc) or "Related indicators"
        intro_fb = (
            indicator_template("intro_fallback", loc)
            or "{name}: official economic indicator with historical values and a chart."
        ).format(name=name)
        method_fb = (
            indicator_template("methodology_fallback", loc)
            or "Methodology follows the official publisher."
        )
        chart_caption_tpl = (
            indicator_template("chart_caption", loc)
            or "{name} — dynamics chart from {source}. Source: forecasteconomy.com"
        )
        chart_alt_tpl = (
            indicator_template("chart_alt", loc)
            or "{name} — dynamics chart, latest value {value}, source {source}"
        )
        forecast_note_prefix = indicator_template("forecast_chart_note", loc) or FORECAST_SSR_CHART_NOTE
        forecast_link_label = indicator_template("forecast_link", loc) or "how the forecast is calculated"
        years_h2_tpl = indicator_template("section_years", loc) or "{name} by year"
        year_link_tpl = indicator_template("year_link", loc) or "{name} in {year}"
        li_latest_tpl = indicator_template("li_latest", loc) or "Latest value: {value}"
        li_date_tpl = indicator_template("li_date", loc) or "Date of latest value: {date}"
        li_freq_tpl = indicator_template("li_frequency", loc) or "Frequency: {frequency}"
        li_source_tpl = indicator_template("li_source", loc) or "Source: {source}"
        li_points_tpl = indicator_template("li_points", loc) or "Number of observations: {count}"
        li_period_tpl = indicator_template("li_period", loc) or "Data period: {first} — {last}"
    else:
        value_head = "Изменение цен, %" if cpi_mode else (f"Значение, {unit}" if unit else "Значение")
        freq_text = _format_frequency(frequency)
        th_date = "Дата"
        section_current = "Текущее значение"
        section_method = "Методология"
        section_latest = "Последние данные"
        section_related = "Связанные индикаторы"
        intro_fb = f"{name}: официальный экономический индикатор с историей значений и графиком."
        method_fb = "Методология показателя указана по данным официального источника и используется для интерпретации ряда."
        chart_caption_tpl = "{name} — график динамики по данным {source}. Источник: forecasteconomy.com"
        chart_alt_tpl = "{name} — график динамики, последнее значение {value}, источник {source}"
        forecast_note_prefix = FORECAST_SSR_CHART_NOTE
        forecast_link_label = "как считается прогноз"
        years_h2_tpl = "{name} по годам"
        year_link_tpl = "{name} в {year} году"
        li_latest_tpl = "Последнее значение: {value}"
        li_date_tpl = "Дата последнего значения: {date}"
        li_freq_tpl = "Периодичность: {frequency}"
        li_source_tpl = "Источник: {source}"
        li_points_tpl = "Количество точек: {count}"
        li_period_tpl = "Период данных: {first} — {last}"

    data_rows = "".join(
        f"<tr><td>{escape(_format_date(row.date))}</td>"
        f"<td>{escape(format_number_ru(display_value(value_code, row.value), signed=cpi_mode))}</td></tr>"
        for row in latest_rows
    )
    source_link = _link(indicator.source_url, src) if indicator.source_url else escape(src)
    related_links = tuple(
        (
            paths.russia_indicator(ind.code),
            public_name(ind.name, ind.name_en, locale=loc),
        )
        for ind in related
    )
    if en and seo_blocks:
        custom_blocks = tuple(
            SeoBlock(title=b["title"], body=b["body"])
            for b in seo_blocks
            if isinstance(b, dict) and b.get("title") and b.get("body")
        )
    else:
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
        if forecast_ssr and not en
        else (
            (indicator_template("forecast_image_name", loc) or forecast_ssr_image_name(name)).format(name=name)
            if forecast_ssr and en
            else chart_alt_tpl.format(name=name, value=current_text, source=src)
        )
    )
    og_code = indicator.code
    # V4: видимый абзац под графиком (только пилот с реальным прогнозом).
    forecast_note = ""
    if forecast_ssr:
        forecast_note = (
            f'<p class="seo-forecast-note">{escape(forecast_note_prefix)}'
            f'{_link("/methodology", forecast_link_label)}.</p>\n'
        )
    # А-4: блок «по годам» — ссылки на годовые landing'и (последние 12 лет).
    years_section = ""
    if data_years:
        year_links = _links_list(tuple(
            (
                paths.russia_indicator_year(indicator.code, y),
                year_link_tpl.format(name=name, year=y),
            )
            for y in sorted(data_years, reverse=True)[:12]
        ))
        years_section = (
            f"<section><h2>{escape(years_h2_tpl.format(name=name))}</h2>"
            f"{year_links}</section>\n"
        )
    chart_caption = chart_caption_tpl.format(name=name, source=src)
    return f"""<main class="seo-page">
{_breadcrumbs_nav(crumb_trail)}
<h1>{escape(name)}</h1>
<p>{escape(clean_text(desc_text, intro_fb))}</p>
<figure class="seo-chart"><img src="{escape(_absolute(paths.og_indicator(paths.RUSSIA, og_code)))}" width="1200" height="630" alt="{escape(chart_alt)}" loading="lazy"><figcaption>{escape(chart_caption)}</figcaption></figure>
{forecast_note}<section><h2>{escape(section_current)}</h2>
<ul>
<li>{escape(li_latest_tpl.format(value=current_text))}</li>
<li>{escape(li_date_tpl.format(date=_format_date(current.date if current else None)))}</li>
<li>{escape(li_freq_tpl.format(frequency=freq_text))}</li>
<li>{li_source_tpl.format(source=source_link)}</li>
<li>{escape(li_points_tpl.format(count=int(count)))}</li>
<li>{escape(li_period_tpl.format(first=_format_date(first_dt), last=_format_date(last_dt)))}</li>
</ul></section>
{_blocks_html(blocks, current_code=indicator.code)}
<section><h2>{escape(section_method)}</h2><p>{escape(clean_text(method_text, method_fb))}</p></section>
<section><h2>{escape(section_latest)}</h2><table><thead><tr><th>{escape(th_date)}</th><th>{escape(value_head)}</th></tr></thead><tbody>{data_rows}</tbody></table></section>
{years_section}<section><h2>{escape(section_related)}</h2>{_links_list(related_links or ((paths.russia_category(category.slug), category.name),) if category else tuple())}</section>
</main>"""
