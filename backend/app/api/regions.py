"""API регионального блока: субъекты РФ × показатели «Регионы России» (Росстат).

Отдельный bounded context (ADR-0008): свои таблицы regions / region_indicators /
region_data, годовая частота, без forecast/derived-контуров макроблока.

Эндпоинты:
  GET /regions                      — лендинг: округа, регионы с ключевыми цифрами
  GET /regions/catalog              — каталог показателей по разделам (общий)
  GET /regions/{slug}               — профиль региона: ключевые цифры + все показатели
  GET /regions/{slug}/i/{code}      — ряд показателя в регионе + рейтинг + сравнение с РФ
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import cache_get, cache_set
from app.data.region_indicator_polarity import (
    region_rating_meta,
    region_rating_order_by,
)
from app.database import get_db
from app.models import Region, RegionDataPoint, RegionIndicator
from app.services.seo_regional import MACRO_BY_TABLE

router = APIRouter(prefix="/regions", tags=["regions"])

# Ключевые показатели карточек/профиля: table_code -> короткая подпись.
HEADLINE_TABLES = {
    "1.1": "Население",
    "3.4": "Средняя зарплата",
    "2.10.1": "Безработица",
    "8.1": "ВРП",
    "8.2": "ВРП на душу",
    "10.1": "Инвестиции",
    "20.1": "Инфляция",
    "3.12": "Бедность",
}

# Ряды, где источник публикует индекс к предыдущему году (100 = цены не
# изменились), а карточка обязана показать прирост: «Инфляция — 110,1 %»
# читается как рост цен в 2,1 раза. Ключ — table_code, значение — единица
# результата и уточнение периода сравнения.
HEADLINE_INDEX_TO_GROWTH = {
    "20.1": ("%", "декабрь к декабрю предыдущего года"),
}

# На лендинге у каждой карточки региона — эти три числа.
LANDING_TABLES = ("1.1", "3.4", "2.10.1")


def _fmt(v: float) -> float:
    return round(v, 4)


async def _region_or_404(slug: str, db: AsyncSession) -> Region:
    region = (await db.execute(select(Region).where(Region.slug == slug))).scalar_one_or_none()
    if region is None or region.kind not in ("region", "district", "country"):
        raise HTTPException(404, "Регион не найден")
    return region


async def _latest_values(db: AsyncSession, indicator_ids: list[int],
                         region_ids: list[int] | None = None) -> dict:
    """(indicator_id, region_id) -> (year, value) для последнего года ряда."""
    sub = (
        select(
            RegionDataPoint.indicator_id,
            RegionDataPoint.region_id,
            func.max(RegionDataPoint.year).label("y"),
        )
        .where(RegionDataPoint.indicator_id.in_(indicator_ids))
        .group_by(RegionDataPoint.indicator_id, RegionDataPoint.region_id)
        .subquery()
    )
    q = select(
        RegionDataPoint.indicator_id, RegionDataPoint.region_id,
        RegionDataPoint.year, RegionDataPoint.value,
    ).join(
        sub,
        (RegionDataPoint.indicator_id == sub.c.indicator_id)
        & (RegionDataPoint.region_id == sub.c.region_id)
        & (RegionDataPoint.year == sub.c.y),
    )
    if region_ids is not None:
        q = q.where(RegionDataPoint.region_id.in_(region_ids))
    out = {}
    for iid, rid, year, value in (await db.execute(q)).all():
        out[(iid, rid)] = (year, float(value))
    return out


@router.get("")
async def regions_landing(db: AsyncSession = Depends(get_db)):
    cache_key = "fe:regions:landing"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    regions = (await db.execute(
        select(Region).order_by(Region.sort_order)
    )).scalars().all()
    inds = (await db.execute(
        select(RegionIndicator).where(RegionIndicator.table_code.in_(LANDING_TABLES))
    )).scalars().all()
    ind_by_table = {i.table_code: i for i in inds}
    latest = await _latest_values(db, [i.id for i in inds])

    n_indicators = (await db.execute(
        select(func.count()).select_from(RegionIndicator)
    )).scalar()
    n_points = (await db.execute(
        select(func.count()).select_from(RegionDataPoint)
    )).scalar()

    districts = []
    district_map = {}
    for r in regions:
        if r.kind == "district":
            entry = {"slug": r.slug, "name": r.name, "regions": []}
            districts.append(entry)
            district_map[r.slug] = entry

    def stats_for(r: Region) -> dict:
        out = {}
        for tc in LANDING_TABLES:
            ind = ind_by_table.get(tc)
            if not ind:
                continue
            got = latest.get((ind.id, r.id))
            if got:
                out[tc] = {"year": got[0], "value": _fmt(got[1]), "unit": ind.unit}
        return out

    for r in regions:
        if r.kind != "region":
            continue
        entry = district_map.get(r.district_slug)
        if entry is None:
            continue
        entry["regions"].append({
            "slug": r.slug, "name": r.name, "stats": stats_for(r),
        })

    country = next((r for r in regions if r.kind == "country"), None)
    result = {
        "districts": districts,
        "russia": {"slug": "russia", "name": "Российская Федерация",
                   "stats": stats_for(country)} if country else None,
        "totals": {
            "regions": sum(len(d["regions"]) for d in districts),
            "indicators": n_indicators,
            "points": n_points,
        },
    }
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result


@router.get("/catalog")
async def regions_catalog(db: AsyncSession = Depends(get_db)):
    """Каталог показателей по разделам — одинаков для всех регионов."""
    cache_key = "fe:regions:catalog"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    inds = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.section_num, RegionIndicator.code)
    )).scalars().all()

    sections: dict[int, dict] = {}
    for i in inds:
        sec = sections.setdefault(i.section_num, {
            "num": i.section_num, "name": i.section_name, "indicators": [],
        })
        sec["indicators"].append({
            "code": i.code, "name": i.name, "unit": i.unit,
            "year_min": i.year_min, "year_max": i.year_max,
            # мост в макроблок: код общероссийского индикатора-аналога
            "macro_code": MACRO_BY_TABLE.get(i.table_code or ""),
        })
    # сортировка внутри раздела по табличному коду источника
    def _tc_key(code_entry):
        return code_entry["code"]
    result = {"sections": [sections[k] for k in sorted(sections)]}
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result


@router.get("/heatmap/{code}")
async def regions_heatmap(code: str, db: AsyncSession = Depends(get_db)):
    """Значения показателя по всем субъектам за последний год — для карты.

    Роут объявлен до `/{slug}` — иначе «heatmap» перехватится как slug региона.
    """
    cache_key = f"fe:regions:heatmap:v2:{code}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    indicator = (await db.execute(
        select(RegionIndicator).where(RegionIndicator.code == code)
    )).scalar_one_or_none()
    if indicator is None:
        raise HTTPException(404, "Показатель не найден")

    last_year = (await db.execute(
        select(func.max(RegionDataPoint.year))
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id,
               Region.kind == "region")
    )).scalar()
    if last_year is None:
        raise HTTPException(404, "Нет данных по этому показателю")

    rows = (await db.execute(
        select(Region.slug, Region.name, RegionDataPoint.value)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.year == last_year,
               Region.kind == "region")
    )).all()

    polarity = region_rating_meta(indicator.code, indicator.table_code)
    result = {
        "indicator": {"code": indicator.code, "name": indicator.name,
                      "unit": indicator.unit},
        "year": last_year,
        **polarity,
        "values": [
            {"slug": s, "name": n, "value": _fmt(float(v)), "raw": float(v)}
            for s, n, v in rows
        ],
    }
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result


@router.get("/heatmap-series/{code}")
async def regions_heatmap_series(code: str, db: AsyncSession = Depends(get_db)):
    """Значения показателя по всем субъектам за ВСЕ доступные годы — для карты
    с ползунком времени (плавная анимация choropleth по годам).

    Структура компактная: `values_by_year` — {год: {slug: raw}}. Раскраска на
    фронте считается по КАЖДОМУ году отдельно (квантили внутри года) — карта
    показывает относительную позицию региона в этом году, а не абсолютный рост
    во времени. Роут — до `/{slug}`, иначе перехватится как slug региона.
    """
    cache_key = f"fe:regions:heatmap-series:{code}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    indicator = (await db.execute(
        select(RegionIndicator).where(RegionIndicator.code == code)
    )).scalar_one_or_none()
    if indicator is None:
        raise HTTPException(404, "Показатель не найден")

    rows = (await db.execute(
        select(Region.slug, RegionDataPoint.year, RegionDataPoint.value)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id,
               Region.kind == "region")
        .order_by(RegionDataPoint.year)
    )).all()
    if not rows:
        raise HTTPException(404, "Нет данных по этому показателю")

    values_by_year: dict[str, dict[str, float]] = {}
    for slug, year, value in rows:
        values_by_year.setdefault(str(year), {})[slug] = _fmt(float(value))

    years = sorted(int(y) for y in values_by_year)
    result = {
        "indicator": {"code": indicator.code, "name": indicator.name,
                      "unit": indicator.unit},
        "years": years,
        "first_year": years[0],
        "last_year": years[-1],
        # Раскраска считается по каждому году отдельно (позиция региона ВНУТРИ
        # года), поэтому пул для общей шкалы не нужен — экономит ~⅓ payload.
        "values_by_year": values_by_year,
    }
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result


@router.get("/vs/{slug_a}/{slug_b}")
async def regions_compare(slug_a: str, slug_b: str, db: AsyncSession = Depends(get_db)):
    """Сравнение двух регионов по ключевым показателям — JSON для SPA /region-vs/*."""
    from app.services.region_compare_data import build_region_compare_payload

    cache_key = f"fe:regions:vs:{slug_a}:{slug_b}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    payload = await build_region_compare_payload(slug_a, slug_b, db)
    if payload is None:
        raise HTTPException(404, "Нет данных для сравнения")

    await cache_set(cache_key, payload, settings.cache_ttl_data)
    return payload


@router.get("/{slug}")
async def region_profile(slug: str, db: AsyncSession = Depends(get_db)):
    cache_key = f"fe:regions:profile:{slug}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    region = await _region_or_404(slug, db)

    district_name = None
    if region.district_slug:
        district_name = (await db.execute(
            select(Region.name).where(Region.slug == region.district_slug)
        )).scalar_one_or_none()

    inds = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.section_num, RegionIndicator.code)
    )).scalars().all()

    # последние + предыдущие значения всех показателей одним запросом:
    # два верхних года на (indicator, region) через оконный rank
    rn = func.row_number().over(
        partition_by=RegionDataPoint.indicator_id,
        order_by=RegionDataPoint.year.desc(),
    ).label("rn")
    sub = (
        select(RegionDataPoint.indicator_id, RegionDataPoint.year,
               RegionDataPoint.value, rn)
        .where(RegionDataPoint.region_id == region.id)
        .subquery()
    )
    rows = (await db.execute(
        select(sub.c.indicator_id, sub.c.year, sub.c.value, sub.c.rn)
        .where(sub.c.rn <= 2)
    )).all()
    latest: dict[int, tuple] = {}
    prev: dict[int, tuple] = {}
    for iid, year, value, r_n in rows:
        if r_n == 1:
            latest[iid] = (year, float(value))
        else:
            prev[iid] = (year, float(value))

    sections: dict[int, dict] = {}
    headline = {}
    for i in inds:
        got = latest.get(i.id)
        if got is None:
            continue
        year, value = got
        p = prev.get(i.id)
        item = {
            "code": i.code, "name": i.name, "unit": i.unit,
            "year": year, "value": _fmt(value),
            "prev_year": p[0] if p else None,
            "prev_value": _fmt(p[1]) if p else None,
        }
        sec = sections.setdefault(i.section_num, {
            "num": i.section_num, "name": i.section_name, "indicators": [],
        })
        sec["indicators"].append(item)
        if i.table_code in HEADLINE_TABLES:
            card = {**item, "label": HEADLINE_TABLES[i.table_code]}
            growth = HEADLINE_INDEX_TO_GROWTH.get(i.table_code)
            if growth is not None:
                unit_out, period = growth
                card["value"] = _fmt(card["value"] - 100)
                if card["prev_value"] is not None:
                    card["prev_value"] = _fmt(card["prev_value"] - 100)
                card["unit"] = unit_out
                card["note"] = period
            headline[i.table_code] = card

    result = {
        "region": {
            "slug": region.slug, "name": region.name, "kind": region.kind,
            "district_slug": region.district_slug, "district_name": district_name,
        },
        "headline": headline,
        "sections": [sections[k] for k in sorted(sections)],
        # Полный каталог (489) vs показатели с фактическими точками по региону (≈471 у Москвы).
        "catalog_total": len(inds),
        "available_total": sum(len(s["indicators"]) for s in sections.values()),
    }
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result


@router.get("/{slug}/i/{code}")
async def region_indicator_detail(slug: str, code: str, db: AsyncSession = Depends(get_db)):
    cache_key = f"fe:regions:detail:v2:{slug}:{code}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    region = await _region_or_404(slug, db)
    indicator = (await db.execute(
        select(RegionIndicator).where(RegionIndicator.code == code)
    )).scalar_one_or_none()
    if indicator is None:
        raise HTTPException(404, "Показатель не найден")

    series_rows = (await db.execute(
        select(RegionDataPoint.year, RegionDataPoint.value)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.region_id == region.id)
        .order_by(RegionDataPoint.year)
    )).all()
    series = [{"year": y, "value": _fmt(float(v))} for y, v in series_rows]
    if not series:
        raise HTTPException(404, "Нет данных по этому показателю для региона")

    # ряд РФ для сравнения
    russia_series = []
    if region.slug != "russia":
        rf = (await db.execute(select(Region).where(Region.slug == "russia"))).scalar_one_or_none()
        if rf:
            rf_rows = (await db.execute(
                select(RegionDataPoint.year, RegionDataPoint.value)
                .where(RegionDataPoint.indicator_id == indicator.id,
                       RegionDataPoint.region_id == rf.id)
                .order_by(RegionDataPoint.year)
            )).all()
            russia_series = [{"year": y, "value": _fmt(float(v))} for y, v in rf_rows]

    # рейтинг среди субъектов по последнему году ряда данного региона
    last_year = series[-1]["year"]
    polarity = region_rating_meta(indicator.code, indicator.table_code)
    rank_rows = (await db.execute(
        select(Region.slug, Region.name, RegionDataPoint.value)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.year == last_year,
               Region.kind == "region")
        .order_by(region_rating_order_by(
            RegionDataPoint.value, indicator.code, indicator.table_code
        ))
    )).all()
    rank = None
    total_ranked = len(rank_rows)
    top = [{"slug": s, "name": n, "value": _fmt(float(v))} for s, n, v in rank_rows[:5]]
    bottom = [{"slug": s, "name": n, "value": _fmt(float(v))} for s, n, v in rank_rows[-3:]]
    for pos, (s, _n, _v) in enumerate(rank_rows, 1):
        if s == region.slug:
            rank = pos
            break

    # соседние показатели раздела (для блока «В этом разделе»)
    siblings = (await db.execute(
        select(RegionIndicator.code, RegionIndicator.name, RegionIndicator.unit)
        .where(RegionIndicator.section_num == indicator.section_num,
               RegionIndicator.code != indicator.code,
               RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.code)
        .limit(12)
    )).all()

    result = {
        "region": {"slug": region.slug, "name": region.name, "kind": region.kind},
        "indicator": {
            "code": indicator.code, "name": indicator.name, "unit": indicator.unit,
            "note": indicator.note, "section_num": indicator.section_num,
            "section_name": indicator.section_name, "table_code": indicator.table_code,
            "macro_code": MACRO_BY_TABLE.get(indicator.table_code or ""),
        },
        "series": series,
        "russia_series": russia_series,
        "rank": {
            "position": rank, "total": total_ranked, "year": last_year,
            "top": top, "bottom": bottom, **polarity,
        } if rank else None,
        "siblings": [{"code": c, "name": n, "unit": u} for c, n, u in siblings],
    }
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result
