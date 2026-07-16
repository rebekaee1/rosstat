"""Единый реестр публичных URL сайта.

Одна точка истины для трёх потребителей:
  1. sitemap-индекс (`/sitemap.xml` → `/sitemap-{section}.xml`) — `app/api/sitemap.py`;
  2. IndexNow-батч по всему сайту (`indexnow.ping_full_site`);
  3. приоритетная очередь переобхода Вебмастера (`webmaster_recrawl.py`).

Секции возвращаются в порядке приоритета обхода: чем раньше секция и чем
раньше URL внутри секции, тем важнее страница. Этот порядок используется
очередью переобхода (150 URL/день) как приоритет.

Инвариант индексации: в реестр не попадают URL, которые SSR отвечает 301
(unlisted view-mode siblings → `/indicator/{base}?mode=…`, легаси-коды).
Иначе Вебмастер тратит квоту переобхода (~150/день) на NOT_CANONICAL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.display import today_msk

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EconomicEvent,
    Indicator,
    IndicatorData,
    Region,
    RegionDataPoint,
    RegionIndicator,
)
from app.services.seo_content import CATEGORIES, STATIC_PAGES

# Лимит протокола sitemap — 50 000 URL на файл; держим с запасом.
REGIONAL_CHUNK = 10_000


@dataclass(frozen=True)
class SiteUrl:
    path: str
    lastmod: str
    changefreq: str
    priority: str


def _u(path: str, lastmod: str, changefreq: str, priority: str) -> SiteUrl:
    return SiteUrl(path=path, lastmod=lastmod, changefreq=changefreq, priority=priority)


def _sitemap_priority(*, listed: bool) -> str:
    return "0.8" if listed else "0.5"


def is_redirect_only_indicator(code: str) -> bool:
    """Код, у которого `/indicator/{code}` — только 301 на канон (не индексировать)."""
    from app.data.legacy_redirects import (
        resolve_legacy_indicator,
        resolve_unlisted_indicator,
    )

    return bool(resolve_legacy_indicator(code) or resolve_unlisted_indicator(code))


def is_recrawl_eligible(path: str) -> bool:
    """Путь можно подавать в переобход Вебмастера (остаётся в поиске).

    Отсекаем:
    - query-варианты (`/compare?*`, `?year=`, legacy `?view=map`…) — неканон;
    - bare `/indicator/{sibling}` / year-landing легаси-кодов, которые 301.
    Канонические карточки, регионы, рейтинги, карты, /today, годы listed — ок.
    """
    if "?" in path:
        return False
    if path.startswith("/indicator/"):
        rest = path[len("/indicator/"):]
        code = rest.split("/", 1)[0]
        if code and is_redirect_only_indicator(code):
            return False
    return True


async def _core_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    urls = [
        _u(path, today.isoformat(), freq, priority)
        for path, freq, priority in STATIC_PAGES
    ]
    urls.extend(
        _u(f"/category/{slug}", today.isoformat(), "weekly", "0.8")
        for slug in CATEGORIES
    )
    stmt = (
        select(
            Indicator.code,
            Indicator.is_listed,
            func.max(IndicatorData.date).label("last_data"),
        )
        .outerjoin(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(Indicator.is_active.is_(True))
        .group_by(Indicator.id, Indicator.code, Indicator.is_listed)
        .order_by(Indicator.is_listed.desc(), Indicator.code)
    )
    for code, listed, last_data in (await db.execute(stmt)).all():
        # Unlisted view-mode siblings и легаси-коды → 301; в sitemap/IndexNow
        # / recrawl не кладём (иначе NOT_CANONICAL жжёт квоту Вебмастера).
        if is_redirect_only_indicator(code):
            continue
        urls.append(_u(
            f"/indicator/{code}",
            (last_data or today).isoformat(),
            "daily",
            _sitemap_priority(listed=listed),
        ))
    return urls


async def _year_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    year_expr = func.extract("year", IndicatorData.date)
    stmt = (
        select(Indicator.code, year_expr.label("y"), func.max(IndicatorData.date))
        .join(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(Indicator.is_active.is_(True), Indicator.is_listed.is_(True))
        .group_by(Indicator.code, year_expr)
        .having(func.count(IndicatorData.id) >= 2)
        .order_by(year_expr.desc(), Indicator.code)
    )
    urls = []
    for code, year, last_data in (await db.execute(stmt)).all():
        if is_redirect_only_indicator(code):
            continue
        year = int(year)
        freq = "weekly" if year == today.year else "yearly"
        urls.append(_u(
            f"/indicator/{code}/{year}",
            (last_data or today).isoformat(),
            freq,
            "0.4",
        ))
    return urls


async def _region_hub_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    """Региональные данные годовые — lastmod «сегодня» обманывал краулера (В-32).

    Честный lastmod хаба региона — конец последнего года его данных.
    """
    urls = [_u("/regions", today.isoformat(), "weekly", "0.9")]
    region_rows = (await db.execute(
        select(Region.slug, func.max(RegionDataPoint.year))
        .outerjoin(RegionDataPoint, RegionDataPoint.region_id == Region.id)
        .where(Region.kind == "region")
        .group_by(Region.id, Region.slug, Region.sort_order)
        .order_by(Region.sort_order)
    )).all()
    urls.extend(
        _u(
            f"/region/{slug}",
            f"{int(last_year)}-12-31" if last_year else today.isoformat(),
            "monthly",
            "0.8",
        )
        for slug, last_year in region_rows
    )
    return urls


async def _regional_pair_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    stmt = (
        select(Region.slug, RegionIndicator.code, func.max(RegionDataPoint.year))
        .join(Region, Region.id == RegionDataPoint.region_id)
        .join(RegionIndicator, RegionIndicator.id == RegionDataPoint.indicator_id)
        .where(Region.kind == "region", RegionIndicator.is_listed.is_(True))
        .group_by(Region.slug, RegionIndicator.code)
        .order_by(Region.slug, RegionIndicator.code)
    )
    urls = []
    for rslug, icode, last_year in (await db.execute(stmt)).all():
        lastmod = f"{int(last_year)}-12-31" if last_year else today.isoformat()
        urls.append(_u(f"/region/{rslug}/{icode}", lastmod, "monthly", "0.5"))
    return urls


async def _rating_eligible_codes(db: AsyncSession) -> list[tuple[str, int]]:
    """Listed показатели с ≥ 10 регионами за max-год (рейтинг и карта)."""
    last_year_sub = (
        select(
            RegionDataPoint.indicator_id.label("iid"),
            func.max(RegionDataPoint.year).label("ly"),
        )
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(Region.kind == "region")
        .group_by(RegionDataPoint.indicator_id)
        .subquery()
    )
    stmt = (
        select(RegionIndicator.code, last_year_sub.c.ly)
        .join(last_year_sub, last_year_sub.c.iid == RegionIndicator.id)
        .join(RegionDataPoint, (RegionDataPoint.indicator_id == RegionIndicator.id)
              & (RegionDataPoint.year == last_year_sub.c.ly))
        .join(Region, (Region.id == RegionDataPoint.region_id) & (Region.kind == "region"))
        .where(RegionIndicator.is_listed.is_(True))
        .group_by(RegionIndicator.code, last_year_sub.c.ly)
        .having(func.count(func.distinct(RegionDataPoint.region_id)) >= 10)
        .order_by(RegionIndicator.code)
    )
    return [(code, int(y)) for code, y in (await db.execute(stmt)).all()]


async def _rating_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    """Рейтинги регионов: listed показатели с >= 10 регионами за последний год.

    Порог согласован с рендером `render_region_rating_html` (иначе URL из
    sitemap отдавал бы 404): считаем регионы именно за max-год показателя.
    """
    return [
        _u(f"/region-rating/{code}", f"{y}-12-31", "monthly", "0.7")
        for code, y in await _rating_eligible_codes(db)
    ]


async def _map_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    """Карта регионов по показателю: /regions/map/{code} (без year в sitemap).

    Тот же пул, что у рейтингов: map SSR требует ≥ 10 регионов на срезе.
    Год в query — только для shareable deep-link, в индекс не раздуваем.
    """
    return [
        _u(f"/regions/map/{code}", f"{y}-12-31", "monthly", "0.65")
        for code, y in await _rating_eligible_codes(db)
    ]


async def _today_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    from app.services.seo_today import TODAY_CODES

    codes = (await db.execute(
        select(Indicator.code).where(
            Indicator.code.in_(list(TODAY_CODES)), Indicator.is_active.is_(True)
        )
    )).scalars().all()
    urls = [_u("/today", today.isoformat(), "daily", "0.9")]
    urls.extend(
        _u(f"/today/{code}", today.isoformat(), "daily", "0.8")
        for code in sorted(codes, key=list(TODAY_CODES).index)
    )
    return urls


async def _calendar_month_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    # Считаем только события, которые SSR-страница реально покажет (тот же
    # provenance-фильтр, В-7) — иначе sitemap ссылался бы на 404-месяцы.
    from app.api.calendar import _public_calendar_conditions

    stmt = (
        select(
            func.extract("year", EconomicEvent.scheduled_date).label("y"),
            func.extract("month", EconomicEvent.scheduled_date).label("m"),
            func.count(),
        )
        .where(*_public_calendar_conditions())
        .group_by("y", "m")
        .having(func.count() >= 3)
        .order_by(func.extract("year", EconomicEvent.scheduled_date).desc(),
                  func.extract("month", EconomicEvent.scheduled_date).desc())
    )
    urls = []
    for y, m, _n in (await db.execute(stmt)).all():
        y, m = int(y), int(m)
        is_current = (y, m) >= (today.year, today.month)
        urls.append(_u(
            f"/calendar/{y}/{m:02d}",
            today.isoformat() if is_current else f"{y}-{m:02d}-28",
            "daily" if is_current else "monthly",
            "0.6" if is_current else "0.4",
        ))
    return urls


async def _region_vs_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    from app.services.seo_region_compare import top_region_pairs

    # В-32: данные пар годовые — честный lastmod общий по датасету, не «сегодня».
    last_year = (await db.execute(
        select(func.max(RegionDataPoint.year))
    )).scalar_one_or_none()
    lastmod = f"{int(last_year)}-12-31" if last_year else today.isoformat()
    pairs = await top_region_pairs(db)
    return [
        _u(f"/region-vs/{a}-vs-{b}", lastmod, "monthly", "0.6")
        for a, b in pairs
    ]


async def collect_url_sections(db: AsyncSession) -> dict[str, list[SiteUrl]]:
    """Все публичные URL сайта, сгруппированные по секциям sitemap-индекса.

    Порядок секций и URL внутри — приоритет обхода (используется очередью
    переобхода Вебмастера).
    """
    today = today_msk()
    sections: dict[str, list[SiteUrl]] = {
        "core": await _core_urls(db, today),
        "today": await _today_urls(db, today),
        "ratings": await _rating_urls(db, today),
        "maps": await _map_urls(db, today),
        "regions": await _region_hub_urls(db, today),
        "region-vs": await _region_vs_urls(db, today),
        "calendar": await _calendar_month_urls(db, today),
        "years": await _year_urls(db, today),
    }
    pairs = await _regional_pair_urls(db, today)
    for i in range(0, len(pairs), REGIONAL_CHUNK):
        sections[f"regional-{i // REGIONAL_CHUNK + 1}"] = pairs[i:i + REGIONAL_CHUNK]
    return sections


async def collect_all_paths(db: AsyncSession, sections: list[str] | None = None) -> list[str]:
    """Плоский список путей (для IndexNow и очереди переобхода), с сохранением приоритета."""
    grouped = await collect_url_sections(db)
    result: list[str] = []
    for name, urls in grouped.items():
        if sections is not None and name not in sections and not (
            name.startswith("regional-") and "regional" in sections
        ):
            continue
        result.extend(u.path for u in urls)
    return result


def filter_recrawl_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """Разделить реестр на eligible / skip (для skip-on-submit без траты квоты)."""
    eligible: list[str] = []
    skipped: list[str] = []
    for path in paths:
        if is_recrawl_eligible(path):
            eligible.append(path)
        else:
            skipped.append(path)
    return eligible, skipped
