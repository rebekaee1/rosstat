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
from app.models import Indicator, Region, RegionDataPoint, RegionIndicator, WorldCountry, WorldIndicator
from app.services import site_paths as paths
from app.services.locale import get_locale

logger = logging.getLogger(__name__)

CATEGORY_RU = "Туризм"
CODE_PREFIX = "tour-"
CACHE_REST = "tourism-overview:v2"

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

FEATURED_REGIONAL = 6   # сколько групп получают карточку с тремя лидерами (по одной на группу)
LEADERS = 3
WORLD_SERIES_PER_COUNTRY = 2
RATING_MIN_REGIONS = 10  # как у серверных страниц рейтинга и карты (seo_regional): меньше — страницы нет

# Первые карточки России: потоки людей и деньги, затем ёмкость. Остальные ряды категории — после них
# в прежнем порядке. Список — порядок витрины, а не отбор: ряд вне списка всё равно показывается.
RUSSIA_LEAD_CODES = (
    "tour-outbound-trips", "tour-inbound-trips", "tour-hotel-nights-monthly", "tour-travel-imports",
    "tour-travel-exports", "tour-gva-share", "tour-hotel-guests", "tour-travel-balance",
)

# Группы региональных рядов по смыслу. Порядок проверки важен: транспорт и цены раньше денег,
# деньги раньше потоков («траты … в поездках»), потоки раньше турфирм («туристы, отправленные турфирмами»).
REGION_GROUPS: tuple[tuple[str, re.Pattern], ...] = (
    ("transport", re.compile(r"пассажир|проезд", re.I)),
    ("prices", re.compile(r"индекс[а-я ]*цен|средняя цена|цена дня", re.I)),
    ("money", re.compile(r"доля туристской|доход|трат|затрат|услуг|оборот|налог|сбор|инвестиц|прибыль", re.I)),
    ("flows", re.compile(r"турпоток|поездк|туристы|туристов|отдыхающ|гости |россияне|иностран|граждане|ночёв|ночев|"
                         r"школьник|размещённ|размещенн", re.I)),
    ("business", re.compile(r"турфирм|туристск[а-я]* фирм|туропер|турагент|экскурсион|ресторан|столов|питани|турпакет", re.I)),
)
REGION_GROUP_ORDER = ("flows", "stay", "money", "prices", "transport", "business")


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


def region_group(name: str) -> str:
    """Группа регионального ряда по названию; всё, что не поток, деньги, цены, транспорт или турфирмы, — размещение."""
    for key, pattern in REGION_GROUPS:
        if pattern.search(name or ""):
            return key
    return "stay"


def _is_breakdown(name: str) -> bool:
    # «Туристы, отправленные турфирмами: Германия» — разбивка; итог без двоеточия идёт первым.
    return ":" in (name or "") and not re.match(r"(?i)средняя цена|индекс", name or "")


def _region_sort_key(row: dict) -> tuple:
    # Внутри группы: итоги раньше разбивок, свежие раньше старых, ряды tour-* раньше прежних.
    # В ценах первыми — средние цены в рублях: «лидер» по индексу цен (рост к прошлому году) ничего не говорит.
    index_price = row["group"] == "prices" and not row["name"].lower().startswith("средняя цена")
    return (REGION_GROUP_ORDER.index(row["group"]), 1 if index_price else 0, 1 if _is_breakdown(row["name"]) else 0,
            -(row.get("year") or 0), 0 if row["code"].startswith(CODE_PREFIX) else 1, row["name"])


async def _rating_ready(db: AsyncSession, ids: list[int]) -> set[int]:
    """Ряды, у которых есть страницы рейтинга и карты: годовые точки ≥ 10 субъектов в последнем году."""
    if not ids:
        return set()
    counts = (await db.execute(
        select(RegionDataPoint.indicator_id, RegionDataPoint.year, func.count(func.distinct(RegionDataPoint.region_id)))
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id.in_(ids), Region.kind == "region")
        .group_by(RegionDataPoint.indicator_id, RegionDataPoint.year)
    )).all()
    latest: dict[int, tuple[int, int]] = {}
    for iid, year, n in counts:
        if iid not in latest or year > latest[iid][0]:
            latest[iid] = (year, n)
    return {iid for iid, (_y, n) in latest.items() if n >= RATING_MIN_REGIONS}


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
    chosen = [ind for ind in candidates if is_tourism_region_indicator(ind.code, ind.section_name, ind.name)]
    ready = await _rating_ready(db, [ind.id for ind in chosen])
    items: list[dict] = []
    for ind in chosen:
        copy = _icopy(ind)
        has_rating = ind.id in ready
        items.append({
            "code": ind.code,
            "name": copy["name"],
            "unit": copy["unit"],
            "year": ind.year_max,
            "group": region_group(ind.name),
            # Месячные и квартальные ряды страниц рейтинга и карты не имеют: ведём на страницу ряда по России
            # (на ней все субъекты), карту не предлагаем.
            "path": paths.region_rating(ind.code) if has_rating else paths.region_indicator("russia", ind.code),
            "rating_path": paths.region_rating(ind.code) if has_rating else None,
            "map_path": paths.region_map(ind.code) if has_rating else None,
        })
    items.sort(key=_region_sort_key)
    featured_groups: set[str] = set()
    for item in items:
        if len(featured_groups) >= FEATURED_REGIONAL or item["group"] in featured_groups:
            continue
        try:
            heat = await regions_heatmap(item["code"], db)
        except Exception:  # нет точек у субъектов — показатель остаётся без лидеров
            logger.debug("tourism: no heatmap for %s", item["code"], exc_info=True)
            continue
        values = sorted(heat.get("values") or [], key=lambda v: v.get("raw", 0), reverse=True)
        if len(values) < LEADERS:
            continue
        item["period"] = heat.get("period_label") or heat.get("year")
        item["leaders"] = [
            {"slug": v["slug"], "name": v["name"], "value": v["value"],
             "path": paths.region_indicator(v["slug"], item["code"])}
            for v in values[:LEADERS]
        ]
        featured_groups.add(item["group"])
    return {"count": len(items), "groups": list(REGION_GROUP_ORDER), "items": items}


def _world_name(name_ru: str, name_en: str | None, en: bool) -> str:
    if en:
        return (name_en or "").strip() or name_ru
    return name_ru


_RUSSIA_SERIES = re.compile(r"росси|russia", re.I)
_SIDE_SERIES = re.compile(r"занят|employ|индекс \(|index \(", re.I)


def _world_series_key(code: str, name: str, points: int) -> tuple:
    # «Из России» первым, потом итог (короткое имя без разбивки), побочные темы (занятость, индексы) — в конце.
    russia = bool(_RUSSIA_SERIES.search(name) or code.endswith("-russia") or "-russia-" in code)
    return (0 if russia else 1, 1 if _SIDE_SERIES.search(name) else 0, 1 if ":" in name else 0, len(name), -points)


async def _world_block(db: AsyncSession) -> dict:
    from app.data.world_concepts import WORLD_CONCEPTS, concept_public_name

    en = get_locale() == "en"
    rows = (await db.execute(
        select(WorldIndicator.code, WorldIndicator.name_ru, WorldIndicator.name_en, WorldIndicator.dataset_id,
               WorldIndicator.points_count, WorldCountry.slug, WorldCountry.name_ru, WorldCountry.name_en,
               WorldCountry.sort_order)
        .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
        .where(WorldIndicator.category_ru == CATEGORY_RU, WorldIndicator.is_listed.is_(True),
               WorldCountry.is_active.is_(True))
    )).all()
    countries: dict[str, dict] = {}
    series: dict[str, list] = {}
    datasets: set[str] = set()
    for code, n_ru, n_en, dataset_id, points, slug, c_ru, c_en, order in rows:
        datasets.add(dataset_id)
        entry = countries.setdefault(slug, {
            "slug": slug,
            "name": (c_en if en and (c_en or "").strip() else c_ru),
            "path": paths.country(slug),
            "count": 0,
            "order": order or 0,
        })
        entry["count"] += 1
        name = _world_name(n_ru, n_en, en)
        series.setdefault(slug, []).append((_world_series_key(code, n_ru, points or 0), code, name))
    for slug, entry in countries.items():
        best = sorted(series[slug])[:WORLD_SERIES_PER_COUNTRY]
        entry["series"] = [{"code": c, "name": n, "path": paths.indicator(slug, c)} for _k, c, n in best]
        entry["russia"] = bool(best and best[0][0][0] == 0)
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
    # Страны, где считают туристов из России, — первыми; дальше обычный порядок стран сайта.
    ordered = sorted(countries.values(), key=lambda c: (0 if c["russia"] else 1, c.pop("order"), c["name"]))
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
