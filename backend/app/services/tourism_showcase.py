"""Раздел «Туризм» (20.11.2026): Россия, регионы и страны мира на одной странице.

Страница `/russia/category/tourism` показывает российские ряды категории «Туризм» обычным списком
категории. Этот модуль собирает два других её этажа — регионы России и страны мира — без списка кодов:

- регионы: показатель с кодом `tour-*`, раздел «Туризм» или туристическое название в разделе, где есть
  слово «туризм» («Культура, отдых и туризм»), плюс туристическое название в любом разделе
  (цена проживания в гостинице); зарплаты отрасли «гостиницы и общепит» — не туризм для этой витрины;
- мир: публичные ряды стран с категорией «Туризм» (`world_indicators.category_ru`) и понятия рейтинга
  стран, наборы которых совпадают с наборами этих рядов.

Ответ общий для API (`GET /api/v1/tourism/overview`) и серверной страницы (seo_renderer): одна сборка,
один кэш на язык.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import cache_get, cache_set, versioned_key
from app.models import Indicator, RegionIndicator, WorldCountry, WorldIndicator
from app.services import site_paths as paths
from app.services.locale import get_locale

logger = logging.getLogger(__name__)

CATEGORY_RU = "Туризм"
CODE_PREFIX = "tour-"
CACHE_REST = "tourism-overview:v1"

# Туристическое название регионального ряда. Слова — предметы туризма, а не коды рядов.
_TOURISM_NAME = re.compile(
    r"турист|туризм|турпо|турпак|туропер|турфирм|турагент|путёвк|путевк|гостиниц|\bотел[ьеия]|"
    r"средств[а-я]* размещени|ночёв|ночев|санатор|курорт",
    re.I,
)
# Зарплата «гостиниц и общепита» и прочие отраслевые сводки — не про поездки.
_NOT_TOURISM_NAME = re.compile(r"зарплат|заработн|оборот общественного питания", re.I)

# Грубый отбор в базе; точное правило — is_tourism_region_indicator.
_SQL_STEMS = ("урист", "уризм", "урпо", "уропер", "урфирм", "утёвк", "утевк", "остиниц", "Отел", "отел", "азмещени",
              "очёв", "очев", "анатор", "урорт")

FEATURED_REGIONAL = 6   # сколько региональных показателей получают трёх лидеров
LEADERS = 3
WORLD_SERIES_PER_COUNTRY = 3


def is_tourism_region_indicator(code: str, section_name: str | None, name: str | None) -> bool:
    """Относится ли региональный показатель к разделу «Туризм» (правило без списка кодов)."""
    code = (code or "").lower()
    section = (section_name or "").strip()
    title = name or ""
    if code.startswith(CODE_PREFIX) or section.lower() == CATEGORY_RU.lower():
        return True
    if _NOT_TOURISM_NAME.search(title):
        return False
    return bool(_TOURISM_NAME.search(title))


def _region_sort_key(row: dict) -> tuple:
    # Свежие и с долгой историей — выше; новые ряды tour-* — первыми при равной свежести.
    return (-(row.get("year") or 0), 0 if row["code"].startswith(CODE_PREFIX) else 1, row["name"])


async def _regional_block(db: AsyncSession) -> dict:
    from app.api.regions import _icopy, regions_heatmap  # локальный импорт: api.regions тянет весь роутер

    candidates = (await db.execute(
        select(RegionIndicator).where(RegionIndicator.is_listed.is_(True)).where(or_(
            RegionIndicator.code.like(f"{CODE_PREFIX}%"),
            RegionIndicator.section_name.like("%уризм%"),
            # Без первой буквы: регистр кириллицы LIKE различает не во всех базах.
            *(RegionIndicator.name.like(f"%{stem}%") for stem in _SQL_STEMS),
        ))
    )).scalars().all()
    items: list[dict] = []
    for ind in candidates:
        if not is_tourism_region_indicator(ind.code, ind.section_name, ind.name):
            continue
        copy = _icopy(ind)
        items.append({
            "code": ind.code,
            "name": copy["name"],
            "unit": copy["unit"],
            "year": ind.year_max,
            "rating_path": paths.region_rating(ind.code),
            "map_path": paths.region_map(ind.code),
        })
    items.sort(key=_region_sort_key)
    for item in items[:FEATURED_REGIONAL]:
        try:
            heat = await regions_heatmap(item["code"], db)
        except Exception:  # нет точек у субъектов — показатель остаётся без лидеров
            logger.debug("tourism: no heatmap for %s", item["code"], exc_info=True)
            continue
        values = sorted(heat.get("values") or [], key=lambda v: v.get("raw", 0), reverse=True)
        item["period"] = heat.get("period_label") or heat.get("year")
        item["leaders"] = [
            {"slug": v["slug"], "name": v["name"], "value": v["value"],
             "path": paths.region_indicator(v["slug"], item["code"])}
            for v in values[:LEADERS]
        ]
    return {"count": len(items), "items": items}


def _world_name(ind: WorldIndicator, en: bool) -> str:
    if en:
        return (ind.name_en or "").strip() or ind.name_ru
    return ind.name_ru


async def _world_block(db: AsyncSession) -> dict:
    from app.data.world_concepts import WORLD_CONCEPTS, concept_public_name

    en = get_locale() == "en"
    rows = (await db.execute(
        select(WorldIndicator, WorldCountry)
        .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
        .where(WorldIndicator.category_ru == CATEGORY_RU, WorldIndicator.is_listed.is_(True),
               WorldCountry.is_active.is_(True))
        .order_by(WorldCountry.sort_order, WorldCountry.slug, WorldIndicator.points_count.desc(),
                  WorldIndicator.code)
    )).all()
    countries: dict[str, dict] = {}
    datasets: set[str] = set()
    for ind, country in rows:
        datasets.add(ind.dataset_id)
        entry = countries.setdefault(country.slug, {
            "slug": country.slug,
            "name": (country.name_en if en and (country.name_en or "").strip() else country.name_ru),
            "path": paths.country(country.slug),
            "count": 0,
            "series": [],
        })
        entry["count"] += 1
        if len(entry["series"]) < WORLD_SERIES_PER_COUNTRY:
            entry["series"].append({
                "code": ind.code,
                "name": _world_name(ind, en),
                "path": paths.indicator(country.slug, ind.code),
            })
    concepts = []
    for concept in WORLD_CONCEPTS:
        if "rating" not in concept.enabled_surfaces:
            continue
        ids = set(concept.dataset_ids)
        for extra in (concept.provider_dataset_ids or {}).values():
            ids |= set(extra)
        if ids & datasets:
            concepts.append({
                "slug": concept.slug,
                "name": concept_public_name(concept, locale="en" if en else "ru"),
                "path": paths.world_rating(concept.slug),
            })
    ordered = sorted(countries.values(), key=lambda c: (-c["count"], c["name"]))
    return {"count": len(rows), "countries": ordered, "concepts": concepts}


async def _russia_count(db: AsyncSession) -> int:
    return int((await db.execute(
        select(func.count()).select_from(Indicator).where(
            Indicator.category == CATEGORY_RU, Indicator.is_active.is_(True), Indicator.is_listed.is_(True),
        )
    )).scalar() or 0)


async def build_overview(db: AsyncSession) -> dict:
    """Этажи страницы «Туризм» на языке запроса. Пустой этаж — пустой список, не ошибка."""
    return {
        "russia": {"count": await _russia_count(db), "path": paths.russia_category("tourism")},
        "regions": await _regional_block(db),
        "world": await _world_block(db),
    }


async def tourism_overview(db: AsyncSession) -> dict:
    """Сборка из Redis или с нуля. Ключ меняется при загрузке любого из трёх контуров данных."""
    loc = get_locale()
    key = "|".join((
        await versioned_key("indicators", f"{CACHE_REST}:{loc}"),
        await versioned_key("regions", "t"),
        await versioned_key("world", "t"),
    ))
    cached = await cache_get(key)
    if isinstance(cached, dict) and "regions" in cached:
        return cached
    payload = await build_overview(db)
    empty = not (payload["russia"]["count"] or payload["regions"]["count"] or payload["world"]["count"])
    await cache_set(key, payload, 120 if empty else settings.cache_ttl_data)
    return payload
