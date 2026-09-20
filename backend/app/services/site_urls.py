"""Единый реестр публичных URL сайта.

Одна точка истины для трёх потребителей:
  1. sitemap-контура (`/sitemap.xml` → `/sitemap-{section}.xml`) — `app/api/sitemap.py`;
  2. IndexNow-очередь приоритетных секций (`indexnow.ping_sections`);
  3. приоритетная очередь переобхода Вебмастера (`webmaster_recrawl.py`).

Секции возвращаются в порядке приоритета обхода: чем раньше секция и чем
раньше URL внутри секции, тем важнее страница. Этот порядок используется
очередью переобхода (150 URL/день) как приоритет.

Реестр описан словарём `GROUP_BUILDERS` (имя группы → async builder, полный
список группы) + `_CHUNKED_GROUPS` (чанкируемые группы). `collect_url_sections`
сохраняет прежнюю сигнатуру и собирается из билдеров. `/sitemap-{section}.xml`
строит ТОЛЬКО группу запрошенной секции (не монолит из ~2 млн URL) — холодный
miss группы стоит одну группу, а не весь реестр (П-13: 40+ секунд и 504).
Тяжёлые группы (regional-years, world-years) режутся на страницы на стороне
БД: границы чанков считаются одним оконным запросом (`_chunk_bounds`) и
кэшируются, страница чанка — один keyset-запрос от границы (сотни мс на любой
глубине вместо O(N/chunk) последовательных проходов).

Инвариант индексации: в реестр не попадают URL, которые SSR отвечает 301
(unlisted view-mode siblings → `/russia/indicator/{base}?mode=…`, легаси-коды,
вторичные частоты мировых карточек). Иначе Вебмастер тратит квоту переобхода
(~150/день) на NOT_CANONICAL.

Пути строятся только через `app.services.site_paths` (ADR-0013 path-cut).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Awaitable, Callable

from app.services.index_policy import (
    RUSSIA_YEAR_MIN_POINTS,
    TIER1_PRIORITY,
    TIER2_PRIORITY,
)
from app.services.display import today_msk

from sqlalchemy import Integer, func, select, tuple_, union_all
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.models import (
    EconomicEvent,
    Indicator,
    IndicatorData,
    Region,
    RegionDataPoint,
    RegionMonthlyPoint,
    RegionIndicator,
    WorldCountry,
    WorldDataPoint,
    WorldIndicator,
    SubnationalDataPoint,
    SubnationalIndicator,
    SubnationalRegion,
)
from app.services import site_paths as paths
from app.services.seo_content import CATEGORIES, STATIC_PAGES

# Лимит протокола sitemap — 50 000 URL на файл; держим с запасом.
REGIONAL_CHUNK = 10_000
WORLD_CHUNK = 10_000

# Годовая посадочная `/russia/indicator/{code}/{year}`: минимум точек за календарный год.
YEAR_LANDING_MIN_POINTS = RUSSIA_YEAR_MIN_POINTS
# То же для мировых годовых лендингов /{country}/indicator/{code}/{year}.
WORLD_YEAR_LANDING_MIN_POINTS = 1
# Те же виды территорий, для которых существуют публичные SSR-страницы.
_PUBLIC_REGION_KINDS = ("region", "district", "country")


def _world_year_filters():
    """Все существующие мировые годы публичных рядов, как у SSR."""
    return [
        WorldCountry.is_active.is_(True),
        WorldIndicator.is_listed.is_(True),
        WorldDataPoint.date >= date(1900, 1, 1),
        WorldDataPoint.date < date(2100, 1, 1),
    ]


@dataclass(frozen=True, slots=True)
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
    """Код, у которого карточка — только 301 на канон (не индексировать)."""
    from app.data.legacy_redirects import (
        resolve_legacy_indicator,
        resolve_unlisted_indicator,
    )

    return bool(resolve_legacy_indicator(code) or resolve_unlisted_indicator(code))


def is_recrawl_eligible(path: str) -> bool:
    """Путь можно подавать в переобход Вебмастера (остаётся в поиске)."""
    if "?" in path:
        return False
    if path.startswith("/__honeypot__") or path.endswith("/links-exchange"):
        return False
    for prefix in (f"/{paths.RUSSIA}/indicator/", "/indicator/"):
        if path.startswith(prefix):
            rest = path[len(prefix):]
            code = rest.split("/", 1)[0]
            if code and is_redirect_only_indicator(code):
                return False
    return True


async def _core_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    urls = [
        _u(path, today.isoformat(), freq, priority)
        for path, freq, priority in STATIC_PAGES
    ]
    urls.append(_u(paths.russia_home(), today.isoformat(), "daily", "0.95"))
    urls.append(_u(paths.russia_categories(), today.isoformat(), "weekly", "0.85"))
    urls.append(_u(paths.region_rating_hub(), today.isoformat(), "weekly", "0.7"))
    urls.extend(
        _u(paths.russia_category(slug), today.isoformat(), "weekly", "0.8")
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
        if is_redirect_only_indicator(code):
            continue
        urls.append(_u(
            paths.russia_indicator(code),
            (last_data or today).isoformat(),
            "daily",
            _sitemap_priority(listed=listed),
        ))
    # Ханипот в карту не кладём: Яндекс ходит по sitemap вопреки
    # robots Disallow. Ловушка живёт только в скрытой ссылке футера
    # (/russia/util/links-exchange). /__honeypot__/trap остаётся 403
    # в nginx, но без рекламы в XML.
    return urls


async def _year_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    year_expr = func.extract("year", IndicatorData.date)
    stmt = (
        select(Indicator.code, year_expr.label("y"), func.max(IndicatorData.date))
        .join(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(Indicator.is_active.is_(True),
               IndicatorData.date >= date(1990, 1, 1),
               IndicatorData.date < date(2101, 1, 1))
        .group_by(Indicator.code, year_expr)
        .order_by(year_expr.desc(), Indicator.code)
    )
    urls = []
    for code, year, last_data in (await db.execute(stmt)).all():
        if is_redirect_only_indicator(code):
            continue
        year = int(year)
        freq = "weekly" if year == today.year else "yearly"
        urls.append(_u(
            paths.russia_indicator_year(code, year),
            (last_data or today).isoformat(),
            freq,
            TIER2_PRIORITY if year < today.year else TIER1_PRIORITY,
        ))
    return urls


async def _region_hub_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    urls = [_u(paths.region_hub(), today.isoformat(), "weekly", "0.9")]
    region_rows = (await db.execute(
        select(Region.slug, func.max(RegionDataPoint.year))
        .outerjoin(RegionDataPoint, RegionDataPoint.region_id == Region.id)
        .where(Region.kind.in_(_PUBLIC_REGION_KINDS))
        .group_by(Region.id, Region.slug, Region.sort_order)
        .order_by(Region.sort_order)
    )).all()
    urls.extend(
        _u(
            paths.region(slug),
            f"{int(last_year)}-12-31" if last_year else today.isoformat(),
            "monthly",
            "0.8",
        )
        for slug, last_year in region_rows
    )
    return urls


# Годовые и месячные ряды используют одну публичную карточку. UNION ALL
# допускает оба источника, GROUP BY ниже не даёт дублировать URL пары.
_REGIONAL_PAIR_DATA = union_all(
    select(RegionDataPoint.indicator_id, RegionDataPoint.region_id,
           (RegionDataPoint.year * 10000 + 1231).label("last_day")),
    select(RegionMonthlyPoint.indicator_id, RegionMonthlyPoint.region_id,
           (RegionMonthlyPoint.month * 100 + 1).label("last_day")),
).subquery()


def _regional_pairs_stmt():
    return (
        select(RegionIndicator.id, Region.slug, func.max(_REGIONAL_PAIR_DATA.c.last_day))
        .select_from(_REGIONAL_PAIR_DATA)
        .join(RegionIndicator, RegionIndicator.id == _REGIONAL_PAIR_DATA.c.indicator_id)
        .join(Region, Region.id == _REGIONAL_PAIR_DATA.c.region_id)
        .where(Region.kind.in_(_PUBLIC_REGION_KINDS))
        .group_by(RegionIndicator.id, Region.slug)
    )


def _regional_pair_lastmod(day: int | None, today: date) -> str:
    if day is None:
        return today.isoformat()
    stamp = str(int(day))
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}"


async def _regional_pair_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    rows = (await db.execute(_regional_pairs_stmt().order_by(RegionIndicator.id, Region.slug))).all()
    code_by_id = await _region_indicator_codes(db, {int(r[0]) for r in rows})
    return [
        _u(paths.region_indicator(slug, code_by_id[int(iid)]),
           _regional_pair_lastmod(day, today), "monthly", "0.5")
        for iid, slug, day in rows
    ]


async def _rating_eligible_codes(db: AsyncSession) -> list[tuple[str, int]]:
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
    return [
        _u(paths.region_rating(code), f"{y}-12-31", "monthly", "0.7")
        for code, y in await _rating_eligible_codes(db)
    ]


async def _map_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    from app.services.seo_regional import MAP_OVERVIEW_CODE

    return [_u(paths.region_map(MAP_OVERVIEW_CODE), today.isoformat(), "monthly", "0.65")] + [
        _u(paths.region_map(code), f"{y}-12-31", "monthly", "0.65")
        for code, y in await _rating_eligible_codes(db)
    ]


async def _today_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    from app.services.seo_today import TODAY_CODES

    codes = (await db.execute(
        select(Indicator.code).where(
            Indicator.code.in_(list(TODAY_CODES)), Indicator.is_active.is_(True)
        )
    )).scalars().all()
    urls = [_u(paths.today(), today.isoformat(), "daily", "0.9")]
    urls.extend(
        _u(paths.today(code), today.isoformat(), "daily", "0.8")
        for code in sorted(codes, key=list(TODAY_CODES).index)
    )
    return urls


async def _calendar_month_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
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
            paths.calendar(y, m),
            today.isoformat() if is_current else f"{y}-{m:02d}-28",
            "daily" if is_current else "monthly",
            "0.6" if is_current else "0.4",
        ))
    return urls


async def _region_vs_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    from app.services.region_compare_data import _KEY_TABLE_CODES

    rows = (await db.execute(
        select(RegionDataPoint.indicator_id, RegionDataPoint.year, Region.slug)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .join(RegionIndicator, RegionIndicator.id == RegionDataPoint.indicator_id)
        .where(Region.kind == "region", RegionIndicator.table_code.in_(_KEY_TABLE_CODES))
    )).all()
    coverage: dict[tuple[int, int], set[str]] = {}
    for iid, year, slug in rows:
        coverage.setdefault((int(iid), int(year)), set()).add(slug)
    pair_years: dict[tuple[str, str], int] = {}
    for (_iid, year), slugs in coverage.items():
        for pair in combinations(sorted(slugs), 2):
            pair_years[pair] = max(pair_years.get(pair, year), year)
    return [
        _u(paths.region_vs(a, b), f"{year}-12-31", "monthly", "0.6")
        for (a, b), year in sorted(pair_years.items())
    ]


async def _regional_year_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    """Годовые лендинги регионов: /russia/region/{slug}/{code}/{year}.

    GROUP BY (slug, code, year) уже гарантирует уникальность строк; для годовых
    страниц точная дата внутри года не нужна — lastmod = 31 декабря года
    (регионы обновляются раз в год), поэтому дополнительная агрегация max(id)
    избыточна. Материализуются только плоские кортежи, без ORM-объектов.
    """
    stmt = (
        select(Region.slug, RegionIndicator.code, RegionDataPoint.year)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .join(RegionIndicator, RegionIndicator.id == RegionDataPoint.indicator_id)
        .where(
            Region.kind.in_(_PUBLIC_REGION_KINDS),
            RegionDataPoint.year.between(1900, 2099),
        )
        .group_by(Region.slug, RegionIndicator.code, RegionDataPoint.year)
        .order_by(Region.slug, RegionIndicator.code, RegionDataPoint.year)
    )
    return [
        _u(
            paths.region_indicator_year(rslug, icode, int(year)),
            f"{int(year)}-12-31",
            "yearly",
            TIER2_PRIORITY,
        )
        for rslug, icode, year in (await db.execute(stmt)).all()
    ]


async def _world_rating_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    """Рейтинги стран: базовые /world/rating/{concept} + годовые path-URL лет.

    Годовые лендинги — отдельные индексируемые страницы (Фаза 6): канон года
    теперь path-URL, поэтому все существующие годы концепта идут в sitemap
    с lastmod = максимальной дате точек этого года.
    """
    from app.data.world_concepts import WORLD_CONCEPTS
    from app.services.seo_world import build_world_rating_payload

    urls: list[SiteUrl] = []
    for concept in WORLD_CONCEPTS:
        if "rating" not in concept.enabled_surfaces:
            continue
        payload = await build_world_rating_payload(concept.slug, db)
        if not payload or not payload["items"]:
            continue
        lastmod = payload["last_date"] or today.isoformat()
        urls.append(_u(paths.world_rating(concept.slug), lastmod, "weekly", "0.7"))
        # База — self-canonical дефолтного года (path-URL дефолта 301 на неё),
        # поэтому дефолтный год в карту не идёт: один URL — одна страница.
        # Любой непустой год рейтинга уже имеет публичную SSR-страницу.
        default_year = payload.get("active_year")
        year_dates: dict[int, str] = {}
        for year_key, bucket in (payload.get("values_by_year") or {}).items():
            try:
                y = int(year_key)
            except (TypeError, ValueError):
                continue
            if y == default_year or not 1900 <= y <= 2099:
                continue
            dates = [item.get("date") for item in bucket.values() if item.get("date")]
            if dates:
                year_dates[y] = max(dates)
        for y in sorted(year_dates):
            urls.append(_u(
                paths.world_rating_year(concept.slug, y),
                year_dates[y],
                "yearly" if y < today.year else "weekly",
                "0.5",
            ))
    return urls


async def _world_hub_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    """Карточки стран /{slug}. Хаба /world нет — витрина мира живёт на главной."""
    urls: list[SiteUrl] = []
    last_sub = (
        select(
            WorldIndicator.country_id.label("cid"),
            func.max(WorldDataPoint.date).label("last_data"),
        )
        .join(WorldDataPoint, WorldDataPoint.indicator_id == WorldIndicator.id)
        .where(WorldIndicator.is_listed.is_(True))
        .group_by(WorldIndicator.country_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(WorldCountry.slug, last_sub.c.last_data)
            .join(last_sub, last_sub.c.cid == WorldCountry.id)
            .where(WorldCountry.is_active.is_(True))
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru)
        )
    ).all()
    for slug, last_data in rows:
        urls.append(_u(
            paths.country(slug),
            (last_data or today).isoformat(),
            "weekly",
            "0.8",
        ))
    return urls


async def _world_regions_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    """Субнациональные хабы / профили / карточки (только is_listed)."""
    urls: list[SiteUrl] = []
    last_by_country = (
        select(
            SubnationalIndicator.country_code.label("cc"),
            func.max(SubnationalDataPoint.period).label("last_data"),
        )
        .join(SubnationalDataPoint, SubnationalDataPoint.indicator_id == SubnationalIndicator.id)
        .where(SubnationalIndicator.is_listed.is_(True))
        .group_by(SubnationalIndicator.country_code)
        .subquery()
    )
    hubs = (
        await db.execute(
            select(WorldCountry.slug, WorldCountry.code, last_by_country.c.last_data)
            .join(last_by_country, last_by_country.c.cc == WorldCountry.code)
            .where(WorldCountry.is_active.is_(True))
        )
    ).all()
    for slug, code, last_data in hubs:
        lastmod = (last_data or today).isoformat()
        urls.append(_u(paths.country_regions(slug), lastmod, "weekly", "0.7"))
        regions = (
            await db.execute(
                select(SubnationalRegion.slug)
                .where(SubnationalRegion.country_code == code)
                .order_by(SubnationalRegion.sort_order)
            )
        ).scalars().all()
        indicators = (
            await db.execute(
                select(SubnationalIndicator.code)
                .where(
                    SubnationalIndicator.country_code == code,
                    SubnationalIndicator.is_listed.is_(True),
                )
                .order_by(SubnationalIndicator.code)
            )
        ).scalars().all()
        last_pair = (
            select(
                SubnationalRegion.slug.label("rslug"),
                SubnationalIndicator.code.label("icode"),
                func.max(SubnationalDataPoint.period).label("last_data"),
            )
            .select_from(SubnationalDataPoint)
            .join(SubnationalRegion, SubnationalRegion.id == SubnationalDataPoint.region_id)
            .join(SubnationalIndicator, SubnationalIndicator.id == SubnationalDataPoint.indicator_id)
            .where(
                SubnationalRegion.country_code == code,
                SubnationalIndicator.is_listed.is_(True),
            )
            .group_by(SubnationalRegion.slug, SubnationalIndicator.code)
            .subquery()
        )
        pair_last = {
            (rslug, icode): last
            for rslug, icode, last in (
                await db.execute(select(last_pair.c.rslug, last_pair.c.icode, last_pair.c.last_data))
            ).all()
        }
        for region_slug in regions:
            urls.append(_u(
                paths.country_region(slug, region_slug), lastmod, "weekly", "0.6",
            ))
            for icode in indicators:
                pair_mod = pair_last.get((region_slug, icode))
                if pair_mod is None:
                    continue
                urls.append(_u(
                    paths.country_region_indicator(slug, region_slug, icode),
                    pair_mod.isoformat(),
                    "weekly",
                    "0.5",
                ))
    return urls


class _RankProbe:
    """Строчка-прокси для world_card_primary_rank без ORM-объекта."""

    __slots__ = ("frequency", "points_count", "code")

    def __init__(self, frequency: str | None, points_count: int, code: str):
        self.frequency = frequency
        self.points_count = points_count
        self.code = code


def _world_merge_primary_rank(
    unit: str | None,
    unit_ru: str | None,
    freq: str | None,
    pts: int,
    code: str,
) -> tuple:
    """Ранг ряда для sitemap-дедупа по merge-ключу.

    Сначала предпочтение меры (уровень-индекс > %-изменение > прочее —
    синхронно с measure_preference_rank), затем штатный ранг частоты
    карточки. Ряд-победитель = primary-мера слитой карточки, на которую
    в sitemap ведёт одна страница.
    """
    from app.data.eurostat_listing import _measure_preference_rank
    from app.data.legacy_redirects import world_card_primary_rank

    return (
        _measure_preference_rank(unit, unit_ru),
        world_card_primary_rank(_RankProbe(freq, pts, code)),
    )


def _world_primary_codes(rows) -> tuple[dict[tuple[int, tuple], str], dict[int, set[str]]]:
    """Дедуп карточек: catalog_merge_key → primary-код (инвариант анти-301).

    Меры одного смысла (уровень/темп/среднегодовой) схлопываются в один
    ключ — в sitemap попадает одна страница слитой карточки; вторичные
    ряды остаются доступны по прямому коду и VariantGroupPicker'у.
    Ранг считается по полям строки через `_RankProbe`, без загрузки
    ORM-объектов. Строки — 9 колонок (id, country_id, code, dataset_id,
    unit, unit_ru, slice_json, frequency, points_count): id пробрасывается,
    чтобы вызывающий код мог собрать множество primary-id без второго
    прохода. Возвращает (primary_id_by_key, codes_by_country).
    """
    from app.data.eurostat_listing import catalog_merge_key

    primary_id: dict[tuple[int, tuple], int] = {}
    primary_rank: dict[tuple[int, tuple], tuple] = {}
    for iid, cid, code, dsid, unit, unit_ru, slice_json, freq, pts in rows:
        key = (
            int(cid),
            catalog_merge_key(
                country_id=int(cid),
                provider="eurostat",
                dataset_id=dsid,
                unit=unit,
                unit_ru=unit_ru,
                slice_json=slice_json,
            ),
        )
        rank = _world_merge_primary_rank(unit, unit_ru, freq, int(pts or 0), code)
        prev_rank = primary_rank.get(key)
        if prev_rank is None or rank < prev_rank:
            primary_id[key] = int(iid)
            primary_rank[key] = rank

    codes_by_country: dict[int, set[str]] = {}
    return primary_id, codes_by_country


async def _world_primary_ids(db: AsyncSession) -> set[int]:
    """Глобальный дедуп мировых карточек: id primary-рядов (anti-301).

    Card_key → primary-код считается по ВСЕМ listed-рядам (не по странице):
    вторичная частота отдаёт 301 на primary, даже если пагинация положила их
    в разные чанки. Один проход по лёгким колонкам (~36k строк, сотни мс),
    кэш на `_CHUNK_BOUNDS_TTL` — все чанки карточек и годовых лендингов мира
    переиспользуют одно значение.
    """
    from app.core.cache import cache_get, cache_set

    cached = await cache_get(_WORLD_PRIMARY_IDS_KEY)
    if isinstance(cached, list) and cached:
        return {int(i) for i in cached}

    meta_rows = (
        await db.execute(
            select(
                WorldIndicator.id,
                WorldIndicator.country_id,
                WorldIndicator.code,
                WorldIndicator.dataset_id,
                WorldIndicator.unit,
                WorldIndicator.unit_ru,
                WorldIndicator.slice_json,
                WorldIndicator.frequency,
                WorldIndicator.points_count,
            ).where(WorldIndicator.is_listed.is_(True))
        )
    ).all()
    primary_id_by_key, _ = _world_primary_codes(meta_rows)
    ids = set(primary_id_by_key.values())
    await cache_set(_WORLD_PRIMARY_IDS_KEY, sorted(ids), _CHUNK_BOUNDS_TTL)
    return ids


async def _world_cards_page(
    db: AsyncSession, today: date, after: tuple | None, limit: int
) -> tuple[list[SiteUrl], tuple | None]:
    """Страница карточек listed-индикаторов: /{slug}/indicator/{code}.

    Курсор (id) — id-led план по первичному ключу. Дедуп карточек ГЛОБАЛЬНЫЙ
    (`_world_primary_ids`): вторичная частота карточки отдаёт 301 на primary,
    поэтому в sitemap не попадает независимо от того, в какой чанк её
    положила пагинация (anti-301-инвариант).
    """

    stmt = (
        select(
            WorldIndicator.id,
            WorldIndicator.country_id,
            WorldIndicator.code,
            func.max(WorldDataPoint.date).label("last_data"),
        )
        .join(WorldDataPoint, WorldDataPoint.indicator_id == WorldIndicator.id)
        .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
        .where(WorldCountry.is_active.is_(True), WorldIndicator.is_listed.is_(True))
        .group_by(WorldIndicator.id)
    )
    if after:
        stmt = stmt.having(WorldIndicator.id > int(after[0]))
    stmt = stmt.order_by(WorldIndicator.id).limit(limit)
    rows = (await db.execute(stmt)).all()
    if not rows:
        return [], None

    primary_ids = await _world_primary_ids(db)
    slugs = dict(
        (await db.execute(select(WorldCountry.id, WorldCountry.slug))).all()
    )

    urls: list[SiteUrl] = []
    for iid, cid, code, last_data in rows:
        if int(iid) not in primary_ids or is_redirect_only_indicator(code):
            continue
        cslug = slugs.get(int(cid))
        if cslug is None:
            continue
        urls.append(_u(
            paths.indicator(cslug, code),
            (last_data or today).isoformat(),
            "weekly",
            "0.5",
        ))
    last = rows[-1]
    return urls, (int(last[0]),)


async def _world_year_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    """Годовые лендинги мира: /{country}/indicator/{code}/{year}.

    Дедуп карточек — тот же глобальный primary-id set, что у чанковой
    страницы (`_world_primary_ids`): у полных билдеров и чанков группы
    обязано быть одно множество URL. Страница группируется по году внутри
    страны, без ORM-материализации всех точек.
    """
    primary_ids = await _world_primary_ids(db)

    urls: list[SiteUrl] = []
    slug_by_id = dict(
        (await db.execute(
            select(WorldCountry.id, WorldCountry.slug).where(
                WorldCountry.is_active.is_(True)
            )
        )).all()
    )
    year_expr = func.extract("year", WorldDataPoint.date)
    year_rows = (
        await db.execute(
            select(
                WorldDataPoint.indicator_id,
                WorldIndicator.country_id,
                WorldIndicator.code,
                year_expr,
                func.max(WorldDataPoint.date),
            )
            .join(WorldIndicator, WorldIndicator.id == WorldDataPoint.indicator_id)
            .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
            .where(*_world_year_filters())
            .group_by(
                WorldDataPoint.indicator_id,
                WorldIndicator.country_id,
                WorldIndicator.code,
                year_expr,
            )
        )
    ).all()
    for iid, cid, code, year, last_in_year in year_rows:
        if int(iid) not in primary_ids:
            continue
        if is_redirect_only_indicator(code):
            continue
        cslug = slug_by_id.get(int(cid))
        if cslug is None:
            continue
        urls.append(_u(
            paths.indicator_year(cslug, code, int(year)),
            (last_in_year or today).isoformat(),
            "weekly" if int(year) == today.year else "yearly",
            "0.4",
        ))
    urls.sort(key=lambda u: u.path)
    return urls


def _months_stmt():
    """Только существующие месяцы активных listed-рядов месячной частоты."""
    year_expr = func.extract("year", IndicatorData.date)
    month_expr = func.extract("month", IndicatorData.date)
    return (
        select(
            Indicator.code,
            year_expr.label("y"),
            month_expr.label("m"),
            func.max(IndicatorData.date).label("last_data"),
        )
        .join(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(
            Indicator.is_active.is_(True),
            Indicator.is_listed.is_(True),
            func.lower(Indicator.frequency).like("month%"),
            IndicatorData.date >= date(1900, 1, 1),
            IndicatorData.date < date(2100, 1, 1),
        )
        .group_by(Indicator.code, year_expr, month_expr)
    )


def _month_rows_urls(rows, today: date) -> list[SiteUrl]:
    urls = []
    for code, year, month, _last in rows:
        if is_redirect_only_indicator(code):
            continue
        year, month = int(year), int(month)
        is_current = (year, month) >= (today.year, today.month)
        urls.append(_u(
            paths.indicator_month(paths.RUSSIA, code, year, month),
            today.isoformat() if is_current else f"{year}-{month:02d}-01",
            "monthly",
            "0.5",
        ))
    return urls


async def _month_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    rows = (await db.execute(_months_stmt().order_by(Indicator.code, "y", "m"))).all()
    return _month_rows_urls(rows, today)


async def _months_page(
    db: AsyncSession, today: date, after: tuple | None, limit: int
) -> tuple[list[SiteUrl], tuple | None]:
    year = func.extract("year", IndicatorData.date).cast(Integer)
    month = func.extract("month", IndicatorData.date).cast(Integer)
    stmt = _months_stmt()
    if after:
        stmt = stmt.having(
            tuple_(Indicator.code, year, month)
            > tuple_(str(after[0]), int(after[1]), int(after[2]))
        )
    rows = (await db.execute(stmt.order_by(Indicator.code, year, month).limit(limit))).all()
    last = rows[-1] if rows else None
    return _month_rows_urls(rows, today), ((last[0], int(last[1]), int(last[2])) if last else None)


async def _world_vs_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    """Все канонические пары с данными, которые принимает SSR сравнения.

    Выбор основного ряда и преобразование level/yoy — общие с SSR helpers.
    Лёгкие метаданные и точки выбранных рядов читаются двумя батчами;
    материализация ORM-каталога и SQL-запрос на каждую пару не нужны.
    """
    from types import SimpleNamespace

    from app.data.world_concept_national import national_codes_for_concept
    from app.data.world_concepts import WORLD_CONCEPTS
    from app.services.seo_world import _concept_allowed_datasets
    from app.services.seo_world_compare import _match_concept_pair, world_vs_path
    from app.services.world_rank_values import apply_rank_series, ranking_value_mode

    concepts = [c for c in WORLD_CONCEPTS if "compare" in c.enabled_surfaces]
    allowed = set().union(*(_concept_allowed_datasets(c) for c in concepts))
    national = set().union(*(set(national_codes_for_concept(c.slug)) for c in concepts))
    rows = (await db.execute(
        select(WorldCountry.slug, WorldIndicator.id, WorldIndicator.country_id,
               WorldIndicator.code, WorldIndicator.dataset_id, WorldIndicator.unit,
               WorldIndicator.unit_ru, WorldIndicator.provider, WorldIndicator.slice_json,
               WorldIndicator.frequency)
        .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
        .where(WorldCountry.is_active.is_(True), WorldIndicator.is_listed.is_(True),
               func.lower(WorldIndicator.dataset_id).in_(sorted(allowed)) |
               WorldIndicator.code.in_(sorted(national)))
        .order_by(WorldIndicator.country_id, WorldIndicator.code)
    )).all()
    countries = {}
    candidates: dict[int, list] = {}
    for row in rows:
        slug, iid, cid, code, dsid, unit, unit_ru, provider, slice_json, frequency = row
        countries[cid] = SimpleNamespace(id=cid, slug=slug)
        candidates.setdefault(cid, []).append(SimpleNamespace(
            id=iid, country_id=cid, code=code, dataset_id=dsid, unit=unit,
            unit_ru=unit_ru, provider=provider, slice_json=slice_json, frequency=frequency,
        ))
    members = {}
    selected_ids = set()
    for concept in concepts:
        selected = []
        for cid, country in countries.items():
            indicator, _ = _match_concept_pair(candidates[cid], concept, country, country)
            if indicator is not None:
                selected.append((country, indicator))
                selected_ids.add(indicator.id)
        members[concept.slug] = sorted(selected, key=lambda item: item[0].slug)
    if not selected_ids:
        return []
    raw_by_id: dict[int, list] = {iid: [] for iid in selected_ids}
    for iid, point_date, value in (await db.execute(
        select(WorldDataPoint.indicator_id, WorldDataPoint.date, WorldDataPoint.value)
        .where(WorldDataPoint.indicator_id.in_(selected_ids))
        .order_by(WorldDataPoint.indicator_id, WorldDataPoint.date)
    )).all():
        raw_by_id[iid].append((point_date, float(value)))
    transformed: dict[tuple[int, str], list] = {}
    urls = []
    for concept in concepts:
        for member_a, member_b in combinations(members[concept.slug], 2):
            country_a, ind_a = member_a
            country_b, ind_b = member_b
            mode = ranking_value_mode(concept.slug, (member_a, member_b))
            for ind in (ind_a, ind_b):
                key = (ind.id, mode)
                if key not in transformed:
                    transformed[key] = apply_rank_series(raw_by_id[ind.id], mode)
            a, b = transformed[(ind_a.id, mode)], transformed[(ind_b.id, mode)]
            if len(a) < 2 or len(b) < 2 or (mode == "level" and (a[-1][1] == 0 or b[-1][1] == 0)):
                continue
            urls.append(_u(
                world_vs_path(country_a.slug, country_b.slug, concept.slug),
                max(a[-1][0], b[-1][0]).isoformat(), "weekly", "0.4",
            ))
    return urls


async def _world_cards_urls(db: AsyncSession, today: date) -> list[SiteUrl]:
    """Карточки listed-индикаторов: /{slug}/indicator/{code}.

    Дедуп карточек ГЛОБАЛЬНЫЙ (catalog_merge_key → primary-мера страны),
    не постраничный: вторичные частоты и вторичные меры слитой карточки
    отдают 301 на primary и в sitemap не попадают (инвариант анти-301) —
    у границы чанков им «утечь» некуда.
    """
    from app.data.eurostat_listing import catalog_merge_key

    rows = (
        await db.execute(
            select(
                WorldIndicator.country_id,
                WorldIndicator.code,
                WorldIndicator.dataset_id,
                WorldIndicator.unit,
                WorldIndicator.unit_ru,
                WorldIndicator.slice_json,
                WorldIndicator.frequency,
                WorldIndicator.points_count,
                func.max(WorldDataPoint.date).label("last_data"),
            )
            .join(WorldDataPoint, WorldDataPoint.indicator_id == WorldIndicator.id)
            .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
            .where(WorldCountry.is_active.is_(True), WorldIndicator.is_listed.is_(True))
            .group_by(WorldIndicator.id)
            .order_by(WorldIndicator.id)
        )
    ).all()

    best: dict[tuple, tuple] = {}
    for cid, code, dsid, unit, unit_ru, slice_json, freq, pts, last_data in rows:
        key = (
            int(cid),
            catalog_merge_key(
                country_id=int(cid),
                provider="eurostat",
                dataset_id=dsid,
                unit=unit,
                unit_ru=unit_ru,
                slice_json=slice_json,
            ),
        )
        rank = _world_merge_primary_rank(unit, unit_ru, freq, int(pts or 0), code)
        prev = best.get(key)
        if prev is None or rank < prev[0]:
            best[key] = (rank, code, int(cid), last_data)

    slugs = dict(
        (await db.execute(select(WorldCountry.id, WorldCountry.slug))).all()
    )
    cards: list[tuple[str, str, date | None]] = []
    for _key, (_rank, code, cid, last_data) in best.items():
        cslug = slugs.get(cid)
        if cslug is None or is_redirect_only_indicator(code):
            continue
        cards.append((cslug, code, last_data))
    cards.sort(key=lambda t: (t[0], t[1]))
    return [
        _u(
            paths.indicator(cslug, code),
            (last_data or today).isoformat(),
            "weekly",
            "0.5",
        )
        for cslug, code, last_data in cards
    ]


# --- Чанковая машинерия: границы одним оконным запросом -----------------------
#
# Массовые группы (десятки–сотни тысяч URL) нельзя материализовать целиком на
# каждый запрос секции: монолитная сборка и была причиной 40-секундных холодных
# ответов (П-13). Секция собирает ТОЛЬКО СВОЮ группу: групповой билдер
# (`_SIMPLE_SECTION_BUILDERS` / chunked-билдеры ниже) выгружает список группы
# целиком, сборка режет его на чанки. Для двух самых тяжёлых групп
# (regional-years ~850 тыс, world-years ~700 тыс) полный список — сотни мегабайт
# строк, поэтому там страницы режутся на стороне БД: `_chunk_bounds` одним
# оконным запросом (row_number() по сортировке группы) находит ключи границ
# чанков и кэширует их; страница чанка — ОДИН keyset-запрос «row(sort) > ключ
# границы, LIMIT chunk» — сотни мс на любой глубине, вместо O(N/chunk)
# последовательных проходов по страницам.

_CodeDict = dict[int, str]


async def _region_indicator_codes(
    db: AsyncSession, ids: set[int]
) -> _CodeDict:
    """Код показателя по id (первичный ключ — миллисекунды)."""
    flat = {int(i) for i in ids}
    if not flat:
        return {}
    rows = (
        await db.execute(
            select(RegionIndicator.id, RegionIndicator.code).where(
                RegionIndicator.id.in_(flat)
            )
        )
    ).all()
    return {int(i): c for i, c in rows}


async def _regional_pairs_page(
    db: AsyncSession, today: date, after: tuple | None, limit: int
) -> tuple[list[SiteUrl], tuple | None]:
    """Страница пар регион×показатель: /russia/region/{slug}/{code}.

    Курсор (indicator_id, slug) — id-led план (первичный ключ, стабильные
    сотни мс на страницу); код показателя добирается отдельным запросом по
    первичным ключам страницы.
    """
    stmt = _regional_pairs_stmt()
    if after:
        stmt = stmt.having(
            tuple_(RegionIndicator.id, Region.slug)
            > tuple_(int(after[0]), str(after[1]))
        )
    stmt = stmt.order_by(RegionIndicator.id, Region.slug).limit(limit)
    rows = (await db.execute(stmt)).all()
    code_by_id = await _region_indicator_codes(db, {int(r[0]) for r in rows})
    urls = [
        _u(
            paths.region_indicator(rslug, code_by_id[int(iid)]),
            _regional_pair_lastmod(last_year, today),
            "monthly",
            "0.5",
        )
        for iid, rslug, last_year in rows
        if int(iid) in code_by_id
    ]
    last = rows[-1] if rows else None
    return urls, ((int(last[0]), last[1]) if last else None)


async def _chunk_bounds(
    db: AsyncSession,
    key: str,
    stmt_builder: Callable[[], object],
    sort_cols: tuple,
    chunk_size: int,
) -> list[tuple | None]:
    """Ключи границ чанков группы: [None, end_1, end_2, …, end_last-1, None].

    Первый элемент — None (чанк 1 читается с начала группы), дальше — ключи
    ПОСЛЕДНЕЙ строки каждого не-последнего чанка (rn = chunk, 2 * chunk, …):
    страница читается «row(sort) > ключ, LIMIT chunk», поэтому ключ границы
    принадлежит предыдущему чанку и сам в следующий не попадает. Последний
    элемент — None: последний чанк читается до конца группы. Число чанков =
    len(bounds) - 1. Кэш на `_CHUNK_BOUNDS_TTL` — бот обегает чанки подряд,
    границы платятся один раз на окно.

    `sort_cols` — SQL-выражения (те же, что в keyset-странице группы), а не
    имена: оконный ORDER BY внутри подзапроса не видит алиасы выходных
    колонок (extract-«year» и т.п.).
    """
    from sqlalchemy import Integer, bindparam, literal_column

    from app.core.cache import cache_get, cache_set

    cache_key = f"fe:sitemap:chunk-bounds:public-v3:{key}"
    raw = await cache_get(cache_key)
    if isinstance(raw, list) and raw:
        return [tuple(b) if b is not None else None for b in raw]

    rn = func.row_number().over(order_by=list(sort_cols)).label("rn")
    sub = stmt_builder().add_columns(rn).subquery()
    s = sub.alias("s")
    # Выходные колонки подзапроса = курсор фетчера (порядок совпадает с
    # sort_cols по построению); «rn» — служебная.
    out_cols = [literal_column(f"s.{k}") for k in sub.c.keys() if k != "rn"]
    # `s.rn % chunk == 0` — ключи последних строк не-последних чанков.
    chunk_param = bindparam("chunk", value=chunk_size, type_=Integer)
    mod_expr = (literal_column("s.rn") % chunk_param) == 0
    stmt = (
        select(*out_cols)
        .select_from(s)
        .where(mod_expr)
        .order_by(*out_cols)
    )
    rows = (await db.execute(stmt)).all()
    bounds: list[tuple | None] = [None] + [tuple(r) for r in rows]
    bounds.append(None)
    await cache_set(
        cache_key,
        [list(b) if b is not None else None for b in bounds],
        _CHUNK_BOUNDS_TTL,
    )
    return bounds


async def _regional_years_page(
    db: AsyncSession, today: date, after: tuple | None, limit: int
) -> tuple[list[SiteUrl], tuple | None]:
    """Страница годовых лендингов регионов: /russia/region/{slug}/{code}/{year}.

    Курсор (indicator_id, slug, year) — id-led план. lastmod = 31 декабря
    СВОЕГО года (регионы обновляются раз в год).
    """
    stmt = (
        select(RegionIndicator.id, Region.slug, RegionDataPoint.year)
        .join(RegionIndicator, RegionIndicator.id == RegionDataPoint.indicator_id)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(
            Region.kind.in_(_PUBLIC_REGION_KINDS),
            RegionDataPoint.year.between(1900, 2099),
        )
        .group_by(RegionIndicator.id, Region.slug, RegionDataPoint.year)
    )
    if after:
        stmt = stmt.having(
            tuple_(RegionIndicator.id, Region.slug, RegionDataPoint.year)
            > tuple_(int(after[0]), str(after[1]), int(after[2]))
        )
    stmt = stmt.order_by(RegionIndicator.id, Region.slug, RegionDataPoint.year).limit(limit)
    rows = (await db.execute(stmt)).all()
    code_by_id = await _region_indicator_codes(db, {int(r[0]) for r in rows})
    urls = [
        _u(
            paths.region_indicator_year(rslug, code_by_id[int(iid)], int(year)),
            f"{int(year)}-12-31",
            "yearly",
            TIER2_PRIORITY,
        )
        for iid, rslug, year in rows
        if int(iid) in code_by_id
    ]
    last = rows[-1] if rows else None
    return urls, ((int(last[0]), last[1], int(last[2])) if last else None)


async def _world_years_page(
    db: AsyncSession, today: date, after: tuple | None, limit: int
) -> tuple[list[SiteUrl], tuple | None]:
    """Страница годовых лендингов мира (один чанк реестра).

    Курсор (indicator_id, year) — id-led план (50–120 мс на страницу);
    дедуп карточек — тот же глобальный primary-id set, что у карточек
    (`_world_primary_ids`), у полных билдеров и чанков группы одно
    множество URL. Год из JSON-кэша границ приходит строкой — приводится
    к int (extract отдаёт numeric).
    """
    year_expr = func.extract("year", WorldDataPoint.date)
    stmt = (
        select(
            WorldDataPoint.indicator_id,
            year_expr,
            func.max(WorldDataPoint.date),
        )
        .join(WorldIndicator, WorldIndicator.id == WorldDataPoint.indicator_id)
        .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
        .where(*_world_year_filters())
        .group_by(WorldDataPoint.indicator_id, year_expr)
    )
    if after:
        stmt = stmt.having(
            tuple_(
                WorldDataPoint.indicator_id,
                year_expr.cast(Integer),
            )
            > tuple_(int(after[0]), int(after[1]))
        )
    stmt = stmt.order_by(WorldDataPoint.indicator_id, year_expr).limit(limit)
    rows = (await db.execute(stmt)).all()
    if not rows:
        return [], None

    primary_ids = await _world_primary_ids(db)
    meta_rows = (
        await db.execute(
            select(WorldIndicator.id, WorldIndicator.country_id, WorldIndicator.code)
            .where(WorldIndicator.id.in_({int(r[0]) for r in rows}))
        )
    ).all()
    meta_by_id = {int(r[0]): r for r in meta_rows}
    slugs = dict(
        (await db.execute(select(WorldCountry.id, WorldCountry.slug))).all()
    )

    urls: list[SiteUrl] = []
    for iid, year, last_in_year in rows:
        if int(iid) not in primary_ids:
            continue
        meta = meta_by_id.get(int(iid))
        if meta is None:
            continue
        code = meta[2]
        if is_redirect_only_indicator(code):
            continue
        cslug = slugs.get(int(meta[1]))
        if cslug is None:
            continue
        urls.append(_u(
            paths.indicator_year(cslug, code, int(year)),
            (last_in_year or today).isoformat(),
            "weekly" if int(year) == today.year else "yearly",
            "0.4",
        ))
    last = rows[-1]
    return urls, ((int(last[0]), int(last[1])))


# --- Счётчики чанков: один count(*) по каждой группе --------------------------
#
# Дешёвые запросы (без выгрузки строк): считают ровно те группы, что режутся
# на чанки. Замеры на проде-объёмах (локально 2026-08-28): months < 0,1 с,
# regional-pairs ~0,12 с, regional-years ~0,8 с, world-indicators ~0,7 с,
# world-years ~2,4 с (GROUP BY по 787k групп год×ряд — самый тяжёлый).
# Кэшируются на `_CHUNK_COUNTS_TTL` (бот обегает ~200 чанков подряд — count
# платится один раз на окно, а число чанков меняется только при росте данных).

_CHUNK_COUNTS_TTL = 6 * 3600

_CHUNK_COUNTS_KEY = "fe:sitemap:chunk-counts:public-v3"

_CHUNK_BOUNDS_TTL = 3600

# Кэш глобального дедупа мировых карточек (см. `_world_primary_ids`).
_WORLD_PRIMARY_IDS_KEY = "fe:sitemap:world-primary-ids"

_REG_PAIRS_COUNT = select(func.count()).select_from(_regional_pairs_stmt().subquery())

_REG_YEARS_COUNT = select(func.count()).select_from(
    select(Region.slug, RegionIndicator.code, RegionDataPoint.year)
    .join(Region, Region.id == RegionDataPoint.region_id)
    .join(RegionIndicator, RegionIndicator.id == RegionDataPoint.indicator_id)
    .where(
        Region.kind.in_(_PUBLIC_REGION_KINDS),
        RegionDataPoint.year.between(1900, 2099),
    )
    .group_by(Region.slug, RegionIndicator.code, RegionDataPoint.year)
    .subquery()
)

_WORLD_CARDS_COUNT = select(func.count()).select_from(
    select(WorldIndicator.id)
    .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
    .join(WorldDataPoint, WorldDataPoint.indicator_id == WorldIndicator.id)
    .where(WorldCountry.is_active.is_(True), WorldIndicator.is_listed.is_(True))
    .group_by(WorldIndicator.id)
    .subquery()
)

_WORLD_YEARS_COUNT = select(func.count()).select_from(
    select(WorldIndicator.code.label("c"), func.extract("year", WorldDataPoint.date).label("y"))
    .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
    .join(WorldDataPoint, WorldDataPoint.indicator_id == WorldIndicator.id)
    .where(*_world_year_filters())
    .group_by(WorldIndicator.id, "c", "y")
    .subquery()
)

# Порядок секций = приоритет очереди переобхода (AGENTS.md::site_urls).
_SIMPLE_SECTION_ORDER = [
    "core",
    "today",
    "ratings",
    "maps",
    "regions",
    "region-vs",
    "world-ratings",
    "world",
    "world-regions",
    "calendar",
    "world-vs",
    "years",
    "months-",
    "world-indicators-",
    "regional-",
    "regional-years-",
    "world-years-",
]

@dataclass(frozen=True, slots=True)
class _ChunkSource:
    fetch: Callable
    size: int
    bounds: Callable[[], object]
    sort: tuple
    count: object


# Базовые выборки границ чанков: колонки = курсор страницы (тот же порядок,
# что в `sort` группы), сами границы строит `_chunk_bounds`.
def _world_cards_bounds_stmt() -> object:
    return (
        select(
            WorldIndicator.id.label("id"),
        )
        .join(WorldDataPoint, WorldDataPoint.indicator_id == WorldIndicator.id)
        .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
        .where(WorldCountry.is_active.is_(True), WorldIndicator.is_listed.is_(True))
        .group_by(WorldIndicator.id)
    )


def _regional_pairs_bounds_stmt() -> object:
    return _regional_pairs_stmt().with_only_columns(
        RegionIndicator.id.label("id"), Region.slug.label("slug"),
    )


def _regional_years_bounds_stmt() -> object:
    return (
        select(
            RegionIndicator.id.label("id"),
            Region.slug.label("slug"),
            RegionDataPoint.year.label("year"),
        )
        .join(RegionIndicator, RegionIndicator.id == RegionDataPoint.indicator_id)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(
            Region.kind.in_(_PUBLIC_REGION_KINDS),
            RegionDataPoint.year.between(1900, 2099),
        )
        .group_by(RegionIndicator.id, Region.slug, RegionDataPoint.year)
    )


def _world_years_bounds_stmt() -> object:
    year_expr = func.extract("year", WorldDataPoint.date).label("year")
    return (
        select(WorldDataPoint.indicator_id.label("indicator_id"), year_expr)
        .join(WorldIndicator, WorldIndicator.id == WorldDataPoint.indicator_id)
        .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
        .where(*_world_year_filters())
        .group_by(WorldDataPoint.indicator_id, year_expr)
    )


def _months_bounds_stmt():
    return _months_stmt().with_only_columns(
        Indicator.code.label("code"),
        func.extract("year", IndicatorData.date).cast(Integer).label("year"),
        func.extract("month", IndicatorData.date).cast(Integer).label("month"),
    )


# Чанковые группы: имя-префикс → источник (страничный keyset-fetcher, размер
# чанка, базовая выборка для границ). Секции-чанки собираются через
# build_chunk; простые секции — мимо этой таблицы, напрямую через
# _SIMPLE_SECTION_BUILDERS.
_CHUNKED_SOURCES: dict[str, _ChunkSource] = {
    "months-": _ChunkSource(
        fetch=_months_page, size=REGIONAL_CHUNK,
        bounds=_months_bounds_stmt,
        sort=(Indicator.code, func.extract("year", IndicatorData.date).cast(Integer),
              func.extract("month", IndicatorData.date).cast(Integer)),
        count=select(func.count()).select_from(_months_bounds_stmt().subquery()),
    ),
    "world-indicators-": _ChunkSource(
        fetch=_world_cards_page, size=WORLD_CHUNK,
        bounds=_world_cards_bounds_stmt,
        sort=(WorldIndicator.id,),
        count=_WORLD_CARDS_COUNT,
    ),
    "regional-": _ChunkSource(
        fetch=_regional_pairs_page, size=REGIONAL_CHUNK,
        bounds=_regional_pairs_bounds_stmt,
        sort=(RegionIndicator.id, Region.slug),
        count=_REG_PAIRS_COUNT,
    ),
    "regional-years-": _ChunkSource(
        fetch=_regional_years_page, size=REGIONAL_CHUNK,
        bounds=_regional_years_bounds_stmt,
        sort=(RegionIndicator.id, Region.slug, RegionDataPoint.year),
        count=_REG_YEARS_COUNT,
    ),
    "world-years-": _ChunkSource(
        fetch=_world_years_page, size=WORLD_CHUNK,
        bounds=_world_years_bounds_stmt,
        sort=(WorldDataPoint.indicator_id, func.extract("year", WorldDataPoint.date)),
        count=_WORLD_YEARS_COUNT,
    ),
}

_SIMPLE_SECTION_BUILDERS: dict[str, Callable[[AsyncSession, date], Awaitable[list[SiteUrl]]]] = {
    "core": _core_urls,
    "today": _today_urls,
    "ratings": _rating_urls,
    "maps": _map_urls,
    "regions": _region_hub_urls,
    "region-vs": _region_vs_urls,
    "world-ratings": _world_rating_urls,
    "world": _world_hub_urls,
    "world-regions": _world_regions_urls,
    "calendar": _calendar_month_urls,
    "world-vs": _world_vs_urls,
    "years": _year_urls,
}


def _chunked_prefix_for(name: str) -> tuple[str, int] | None:
    """`regional-years-42` → (`regional-years-`, 42); None — не чанковая секция."""
    for prefix in _CHUNKED_SOURCES:
        if prefix.endswith("-") and name.startswith(prefix) and name[len(prefix):].isdigit():
            return prefix, int(name[len(prefix):])
    return None


def section_names_static() -> list[str]:
    """Имена простых секций (чанковые группы не разворачиваются)."""
    return [n for n in _SIMPLE_SECTION_ORDER if n in _SIMPLE_SECTION_BUILDERS]


async def section_names(db: AsyncSession) -> list[str]:
    """Полный список имён существующих секций в порядке приоритета обхода.

    Простые секции + развёрнутые чанки групп (число чанков — из
    `chunk_counts`, count-запросы с кэшем). Единая точка для sitemap-индекса
    и known-sections: новая группа появляется в индексе автоматически.
    """
    counts = await chunk_counts(db)
    names: list[str] = []
    for name in _SIMPLE_SECTION_ORDER:
        if name in _SIMPLE_SECTION_BUILDERS:
            names.append(name)
        else:
            prefix = name if name.endswith("-") else f"{name}-"
            names.extend(f"{prefix}{i + 1}" for i in range(counts.get(prefix, 0)))
    return names


SECTION_BUILDERS: dict[str, Callable[[AsyncSession, date], Awaitable[dict | list]]] = {}


async def chunk_counts(db: AsyncSession) -> dict[str, int]:
    """Число чанков по каждой чанковой группе — дешёвым count-запросом.

    Каждая группа считает СВОИ группы строк (то, что режется на чанки) одним
    count(*) — сотни мс на проде (regional-years ~0,12 с, world-years ~0,3 с,
    прочие быстрее). Кэшируется на `_CHUNK_COUNTS_TTL`: бот обегает ~200
    чанков подряд — count платится один раз на окно, число чанков меняется
    только при росте данных.
    """
    from app.core.cache import cache_get, cache_set

    cached = await cache_get(_CHUNK_COUNTS_KEY)
    if isinstance(cached, dict) and cached:
        return {k: int(v) for k, v in cached.items()}

    counts: dict[str, int] = {}
    for prefix, source in _CHUNKED_SOURCES.items():
        n = (await db.execute(source.count)).scalar_one()
        counts[prefix] = max(1, -(-max(int(n), 0) // source.size))
    await cache_set(_CHUNK_COUNTS_KEY, counts, _CHUNK_COUNTS_TTL)
    return counts


async def _fill_section_builders(db: AsyncSession) -> None:
    """Заполнить SECTION_BUILDERS именами всех существующих секций.

    Для чанковых групп число чанков берётся из `chunk_counts` (count-запросы),
    сами URL при этом НЕ собираются — индекс строится мгновенно.
    """
    counts = await chunk_counts(db)
    SECTION_BUILDERS.clear()
    for name in _SIMPLE_SECTION_ORDER:
        if name in _SIMPLE_SECTION_BUILDERS:
            SECTION_BUILDERS[name] = _simple_builder(name)
        else:
            prefix = name if name.endswith("-") else name
            for i in range(counts.get(prefix, 0)):
                SECTION_BUILDERS[f"{prefix}{i + 1}"] = _chunk_builder(prefix, i + 1)


def _simple_builder(name: str):
    async def _build(db: AsyncSession) -> list[SiteUrl]:
        return await _SIMPLE_SECTION_BUILDERS[name](db, today_msk())

    return _build


def _chunk_builder(prefix: str, chunk_no: int):
    async def _build(db: AsyncSession) -> list[SiteUrl]:
        return await build_chunk(db, prefix, chunk_no)

    return _build


async def build_chunk(db: AsyncSession, prefix: str, chunk_no: int) -> list[SiteUrl]:
    """Собрать один чанк чанковой группы (страница keyset-пагинации).

    Чанк читается ОДНИМ keyset-запросом от ключа границы — сотни мс на любой
    глубине (границы кэшируются, см. `_chunk_bounds`). Пустая страница
    (`chunk_no` за концом данных, данные опустели с прошлого прогона) —
    пустой список: секция отдаёт 404 и выпадает из индекса.
    """
    source = _CHUNKED_SOURCES[prefix]
    if chunk_no <= 0:
        return []
    today = today_msk()

    bounds = await _chunk_bounds(
        db, prefix, source.bounds, source.sort, source.size
    )
    if chunk_no > len(bounds) - 1:
        return []
    after = bounds[chunk_no - 1]
    page, _cursor = await source.fetch(db, today, after, source.size)
    return page


async def resolve_section(db: AsyncSession, section: str) -> list[dict | list] | list[SiteUrl] | None:
    """Builder секции по имени (чанки резолвятся по префиксу без count-запросов).

    Возвращает список URL или None, если секция не существует. Для чанков
    `chunk_no` может превысить фактическое число чанков (данные опустели) —
    вернётся пустой список, секция отдаст 404/выпадет из индекса.
    """
    if section == "months":
        # Старый sitemap URL остаётся ограниченным первым чанком;
        # актуальный индекс перечисляет все months-N.
        return await build_chunk(db, "months-", 1)
    if section in _SIMPLE_SECTION_BUILDERS:
        return await _SIMPLE_SECTION_BUILDERS[section](db, today_msk())
    parsed = _chunked_prefix_for(section)
    if parsed is None:
        return None
    prefix, chunk_no = parsed
    return await build_chunk(db, prefix, chunk_no)


async def iter_url_sections(db: AsyncSession):
    """Свежая последовательная сборка без TTL-границ и накопления всего реестра.

    Статическая генерация не должна потерять хвост истории из-за устаревшего
    числа чанков или перескочить строки при истечении кэша в середине сборки.
    """
    today = today_msk()
    for name in _SIMPLE_SECTION_ORDER:
        if name in _SIMPLE_SECTION_BUILDERS:
            yield name, await _SIMPLE_SECTION_BUILDERS[name](db, today)
            continue
        source = _CHUNKED_SOURCES[name]
        after = None
        chunk = 1
        while True:
            page, cursor = await source.fetch(db, today, after, source.size)
            if cursor is None:
                break
            if cursor == after:
                raise ValueError(f"Sitemap cursor did not advance: {name}")
            yield f"{name}{chunk}", page
            after = cursor
            chunk += 1


async def collect_url_sections(db: AsyncSession) -> dict[str, list[SiteUrl]]:
    """Полный реестр (совместимость: IndexNow/recrawl/скрипты).

    Возвращаемый словарь накапливает весь реестр в памяти. Для публикации
    использовать iter_url_sections, который отдаёт по одному чанку.
    """
    await _fill_section_builders(db)
    sections: dict[str, list[SiteUrl]] = {}
    for name, builder in SECTION_BUILDERS.items():
        sections[name] = await builder(db)
    return sections


async def collect_all_paths(db: AsyncSession, sections: list[str] | None = None) -> list[str]:
    grouped = await collect_url_sections(db)
    result: list[str] = []
    for name, urls in grouped.items():
        if sections is not None and name not in sections and not (
            (name.startswith("regional-") and "regional" in sections)
            or (name.startswith("world-") and "world" in sections)
        ):
            continue
        result.extend(u.path for u in urls)
    return result


def filter_recrawl_paths(paths_list: list[str]) -> tuple[list[str], list[str]]:
    eligible: list[str] = []
    skipped: list[str] = []
    for path in paths_list:
        if is_recrawl_eligible(path):
            eligible.append(path)
        else:
            skipped.append(path)
    return eligible, skipped

