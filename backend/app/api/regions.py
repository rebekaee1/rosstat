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
from app.core.cache import cache_get, cache_set, versioned_key
from app.data.region_indicator_polarity import (
    region_rating_meta,
    region_rating_order_by,
)
from app.data.emiss_price_goods import (
    HEADLINE_PRICE_CODES,
    PRICE_GROUPS,
    PRICE_GROUPS_EN,
    price_meta,
)
from app.database import get_db
from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint
from app.services.locale import get_locale
from app.services.seo_i18n import region_display_name, region_indicator_copy
from app.services.seo_regional import MACRO_BY_TABLE

router = APIRouter(prefix="/regions", tags=["regions"])

# Ключевые показатели карточек/профиля: table_code -> короткая подпись.
HEADLINE_TABLES = {
    "1.1": "Население",
    "3.4": "Средняя зарплата",
    "2.10.1": "Безработица",
    "8.1": "Объём экономики",
    "8.2": "Экономика на человека",
    "10.1": "Инвестиции",
    "20.1": "Инфляция",
    "3.12": "Бедность",
}

HEADLINE_TABLES_EN = {
    "1.1": "Population",
    "3.4": "Average wage",
    "2.10.1": "Unemployment",
    "8.1": "Regional output",
    "8.2": "Output per person",
    "10.1": "Investment",
    "20.1": "Inflation",
    "3.12": "Poverty",
}

# Ряды, где источник публикует индекс к предыдущему году (100 = цены не
# изменились), а карточка обязана показать прирост: «Инфляция — 110,1 %»
# читается как рост цен в 2,1 раза. Ключ — table_code, значение — единица
# результата и уточнение периода сравнения.
HEADLINE_INDEX_TO_GROWTH = {
    "20.1": ("%", "декабрь к декабрю предыдущего года"),
}

HEADLINE_INDEX_TO_GROWTH_EN = {
    "20.1": ("%", "December to December of the previous year"),
}

# На лендинге у каждой карточки региона — эти три числа.
LANDING_TABLES = ("1.1", "3.4", "2.10.1")


def _fmt(v: float) -> float:
    return round(v, 4)


def _rname(slug: str, name_ru: str) -> str:
    return region_display_name(slug, name_ru)


def _icopy(ind: RegionIndicator) -> dict[str, str | None]:
    return region_indicator_copy(
        ind.code,
        name_ru=ind.name,
        unit_ru=ind.unit or "",
        note_ru=ind.note,
        section_ru=ind.section_name,
    )


def _indicator_search_fields(ind: RegionIndicator) -> dict[str, str | None]:
    """Add both source languages without replacing locale-facing display copy."""
    english = region_indicator_copy(
        ind.code, name_ru=ind.name, unit_ru=ind.unit or "",
        section_ru=ind.section_name, locale="en",
    )
    return {
        "name_ru": ind.name,
        "name_en": english["name"],
        "unit_ru": ind.unit or "",
        "unit_en": english["unit"],
        "section_ru": ind.section_name,
        "section_en": english["section"],
    }


def _region_search_fields(region: Region) -> dict[str, str]:
    return {
        "name_ru": region.name,
        "name_en": region_display_name(region.slug, region.name, locale="en"),
    }


def _headline_label(table_code: str) -> str:
    if get_locale() == "en":
        return HEADLINE_TABLES_EN.get(table_code) or HEADLINE_TABLES[table_code]
    return HEADLINE_TABLES[table_code]


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
    cache_key = await versioned_key("regions", f"landing:search-v2:{get_locale()}")
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
            entry = {"slug": r.slug, "name": _rname(r.slug, r.name), **_region_search_fields(r), "regions": []}
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
                copy = _icopy(ind)
                out[tc] = {
                    "year": got[0],
                    "value": _fmt(got[1]),
                    "unit": copy["unit"],
                }
        return out

    for r in regions:
        if r.kind != "region":
            continue
        entry = district_map.get(r.district_slug)
        if entry is None:
            continue
        entry["regions"].append({
            "slug": r.slug, "name": _rname(r.slug, r.name), **_region_search_fields(r), "stats": stats_for(r),
        })

    country = next((r for r in regions if r.kind == "country"), None)
    result = {
        "districts": districts,
        "russia": {
            "slug": "russia",
            "name": _rname("russia", "Российская Федерация"),
            **_region_search_fields(country),
            "stats": stats_for(country),
        } if country else None,
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
    cache_key = await versioned_key("regions", f"catalog:search-v2:{get_locale()}")
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
        copy = _icopy(i)
        search_fields = _indicator_search_fields(i)
        sec = sections.setdefault(i.section_num, {
            "num": i.section_num,
            "name": copy["section"] or i.section_name,
            "name_ru": search_fields["section_ru"],
            "name_en": search_fields["section_en"],
            "indicators": [],
        })
        sec["indicators"].append({
            "code": i.code, "name": copy["name"], "unit": copy["unit"],
            **search_fields,
            "year_min": i.year_min, "year_max": i.year_max,
            # мост в макроблок: код общероссийского индикатора-аналога
            "macro_code": MACRO_BY_TABLE.get(i.table_code or ""),
        })
    result = {"sections": [sections[k] for k in sorted(sections)]}
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result


@router.get("/heatmap/{code}")
async def regions_heatmap(code: str, db: AsyncSession = Depends(get_db)):
    """Значения показателя по всем субъектам за последний год — для карты.

    Роут объявлен до `/{slug}` — иначе «heatmap» перехватится как slug региона.
    """
    cache_key = await versioned_key("regions", f"heatmap:v3:{code}:{get_locale()}")
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
    last_month = None
    if last_year is None:
        # Месячные ряды (цены ЕМИСС): рейтинг по последнему месяцу, где есть точки субъектов.
        last_month = (await db.execute(
            select(func.max(RegionMonthlyPoint.month))
            .join(Region, Region.id == RegionMonthlyPoint.region_id)
            .where(RegionMonthlyPoint.indicator_id == indicator.id,
                   Region.kind == "region")
        )).scalar()
        if last_month is None:
            raise HTTPException(404, "Нет данных по этому показателю")
        last_year = int(last_month) // 100
        rows = (await db.execute(
            select(Region.slug, Region.name, RegionMonthlyPoint.value)
            .join(Region, Region.id == RegionMonthlyPoint.region_id)
            .where(RegionMonthlyPoint.indicator_id == indicator.id,
                   RegionMonthlyPoint.month == last_month,
                   Region.kind == "region")
        )).all()
    else:
        rows = (await db.execute(
            select(Region.slug, Region.name, RegionDataPoint.value)
            .join(Region, Region.id == RegionDataPoint.region_id)
            .where(RegionDataPoint.indicator_id == indicator.id,
                   RegionDataPoint.year == last_year,
                   Region.kind == "region")
        )).all()

    polarity = region_rating_meta(indicator.code, indicator.table_code)
    copy = _icopy(indicator)
    result = {
        "indicator": {
            "code": indicator.code,
            "name": copy["name"],
            "unit": copy["unit"],
        },
        "year": last_year,
        **({"month": int(last_month), "period_label": _month_label(int(last_month))} if last_month else {}),
        **polarity,
        "values": [
            {"slug": s, "name": _rname(s, n), "value": _fmt(float(v)), "raw": float(v)}
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
    cache_key = await versioned_key("regions", f"heatmap-series:{code}:{get_locale()}")
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
    )).all()
    if not rows:
        raise HTTPException(404, "Нет данных по этому показателю")

    values_by_year: dict[str, dict[str, float]] = {}
    for slug, year, value in rows:
        values_by_year.setdefault(str(year), {})[slug] = _fmt(float(value))

    years = sorted(int(y) for y in values_by_year)
    copy = _icopy(indicator)
    result = {
        "indicator": {
            "code": indicator.code,
            "name": copy["name"],
            "unit": copy["unit"],
        },
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

    cache_key = await versioned_key("regions", f"vs:{slug_a}:{slug_b}:{get_locale()}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    payload = await build_region_compare_payload(slug_a, slug_b, db)
    if payload is None:
        raise HTTPException(404, "Нет данных для сравнения")

    await cache_set(cache_key, payload, settings.cache_ttl_data)
    return payload


@router.get("/vs/{slug_a}/{slug_b}/prices")
async def regions_compare_prices(slug_a: str, slug_b: str, db: AsyncSession = Depends(get_db)):
    """Цены двух регионов рядом, корзина и зарплата в корзинах (R4-A)."""
    from app.services.r4a_price_compare import build_price_compare_payload

    cache_key = await versioned_key("regions", f"vs-prices:v1:{slug_a}:{slug_b}:{get_locale()}")
    cached = await cache_get(cache_key)
    if cached:
        return cached
    payload = await build_price_compare_payload(slug_a, slug_b, db)
    if payload is None:
        raise HTTPException(404, "Нет цен для сравнения")
    await cache_set(cache_key, payload, settings.cache_ttl_data)
    return payload


_MONTHS_RU = ("январь", "февраль", "март", "апрель", "май", "июнь",
              "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь")
_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _price_fields(meta: dict) -> dict:
    """short_name / price_group / is_discontinued / last_month для ряда цен (контракт Z1)."""
    group = meta["price_group"]
    return {
        "short_name": (meta.get("short_name_en") or meta["short_name"]) if get_locale() == "en" else meta["short_name"],
        "price_group": group,
        "price_group_label": PRICE_GROUPS_EN.get(group, group) if get_locale() == "en" else group,
        "is_discontinued": bool(meta["is_discontinued"]),
        "last_month": meta["last_month"],
        "last_month_label": _month_label(meta["last_month"]) if meta["last_month"] else None,
    }


def _month_label(month: int) -> str:
    """YYYYMM → «сентябрь 2026» / «Sep 2026» по языку запроса."""
    names = _MONTHS_EN if get_locale() == "en" else _MONTHS_RU
    return f"{names[month % 100 - 1]} {month // 100}"


@router.get("/{slug}")
async def region_profile(slug: str, db: AsyncSession = Depends(get_db)):
    cache_key = await versioned_key("regions", f"profile:prices-v4:{slug}:{get_locale()}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    region = await _region_or_404(slug, db)

    district_name = None
    if region.district_slug:
        district_name_ru = (await db.execute(
            select(Region.name).where(Region.slug == region.district_slug)
        )).scalar_one_or_none()
        if district_name_ru is not None:
            district_name = _rname(region.district_slug, district_name_ru)

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

    # Месячный слой (цены ЕМИСС: топливо и товары, 08.11.2026): два последних
    # месяца по каждому ряду региона. Годовая точка у показателя приоритетнее.
    mrn = func.row_number().over(
        partition_by=RegionMonthlyPoint.indicator_id,
        order_by=RegionMonthlyPoint.month.desc(),
    ).label("rn")
    msub = (
        select(RegionMonthlyPoint.indicator_id, RegionMonthlyPoint.month,
               RegionMonthlyPoint.value, mrn)
        .where(RegionMonthlyPoint.region_id == region.id)
        .subquery()
    )
    month_of: dict[int, tuple[int, int | None]] = {}
    mlatest: dict[int, tuple] = {}
    mprev: dict[int, tuple] = {}
    for iid, month, value, r_n in (await db.execute(
        select(msub.c.indicator_id, msub.c.month, msub.c.value, msub.c.rn).where(msub.c.rn <= 2)
    )).all():
        (mlatest if r_n == 1 else mprev)[iid] = (int(month), float(value))
    for iid, (month, value) in mlatest.items():
        if iid in latest:
            continue
        latest[iid] = (month // 100, value)
        p_month = mprev.get(iid)
        if p_month:
            prev[iid] = (p_month[0] // 100, p_month[1])
        month_of[iid] = (month, p_month[0] if p_month else None)

    sections: dict[int, dict] = {}
    headline = {}
    growth_map = (
        HEADLINE_INDEX_TO_GROWTH_EN if get_locale() == "en" else HEADLINE_INDEX_TO_GROWTH
    )
    for i in inds:
        got = latest.get(i.id)
        if got is None:
            continue
        year, value = got
        p = prev.get(i.id)
        copy = _icopy(i)
        item = {
            "code": i.code, "name": copy["name"], "unit": copy["unit"],
            **_indicator_search_fields(i),
            "year": year, "value": _fmt(value),
            "prev_year": p[0] if p else None,
            "prev_value": _fmt(p[1]) if p else None,
        }
        if i.id in month_of:
            # YYYYMM последней и предыдущей точки: карточка месячного ряда.
            item["month"], item["prev_month"] = month_of[i.id]
            item["period_label"] = _month_label(item["month"])
            meta = price_meta(i.code)
            if meta:
                item.update(_price_fields(meta))
        sec = sections.setdefault(i.section_num, {
            "num": i.section_num,
            "name": copy["section"] or i.section_name,
            "name_ru": item["section_ru"],
            "name_en": item["section_en"],
            "indicators": [],
        })
        sec["indicators"].append(item)
        if i.table_code in HEADLINE_TABLES:
            card = {**item, "label": _headline_label(i.table_code)}
            growth = growth_map.get(i.table_code)
            if growth is not None:
                unit_out, period = growth
                card["value"] = _fmt(card["value"] - 100)
                if card["prev_value"] is not None:
                    card["prev_value"] = _fmt(card["prev_value"] - 100)
                card["unit"] = unit_out
                card["note"] = period
            headline[i.table_code] = card

    # Цены ЕМИСС (table_code 20.m{N}): после годовых рядов раздела, в порядке
    # справочника — сначала ходовые товары и услуги (яйца, хлеб, ЖКХ, проезд).
    price_order = {
        i.code: int(i.table_code[4:]) for i in inds
        if (i.table_code or "").startswith("20.m") and i.table_code[4:].isdigit()
    }
    for sec in sections.values():
        sec["indicators"].sort(key=lambda it: (it["code"] in price_order, price_order.get(it["code"], 0)))

    result = {
        "region": {
            "slug": region.slug,
            "name": _rname(region.slug, region.name),
            **_region_search_fields(region),
            "kind": region.kind,
            "district_slug": region.district_slug,
            "district_name": district_name,
        },
        "headline": headline,
        "sections": [sections[k] for k in sorted(sections)],
        # Полный каталог (все RegionIndicator) vs показатели с фактическими точками по региону (≈471 у Москвы).
        "price_headline_codes": list(HEADLINE_PRICE_CODES),
        "price_groups": list(PRICE_GROUPS),
        "catalog_total": len(inds),
        "available_total": sum(len(s["indicators"]) for s in sections.values()),
    }
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result


async def _section_siblings(db: AsyncSession, region, indicator) -> list[dict]:
    """Соседние показатели раздела для блока «Ещё в разделе» (годовой и месячный режим).

    У позиций цен — та же группа и живые первыми, со значением и месяцем региона.
    """
    all_sib = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.section_num == indicator.section_num,
               RegionIndicator.code != indicator.code,
               RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.table_code, RegionIndicator.code)
    )).scalars().all()
    own_meta = price_meta(indicator.code)
    if own_meta:
        # Соседи по цене: та же группа и живые позиции первыми, затем остальные.
        def _sib_rank(ind):
            m = price_meta(ind.code)
            return (0 if m and m["price_group"] == own_meta["price_group"] else 1,
                    1 if (m and m["is_discontinued"]) else 0)
        # Только позиции цен: годовые индексы раздела (тарифы, ИПЦ) — другой смысл и
        # частота, в списке «Ещё в разделе» у цены товара они путают (круг 5, R5-A).
        all_sib = sorted((x for x in all_sib if price_meta(x.code)), key=_sib_rank)
        siblings = all_sib[:24]
    else:
        siblings = sorted(all_sib, key=lambda x: x.code)[:12]
    sib_latest: dict[int, tuple[int, float]] = {}
    if siblings:
        for iid, m, v in (await db.execute(
            select(RegionMonthlyPoint.indicator_id, RegionMonthlyPoint.month, RegionMonthlyPoint.value)
            .where(RegionMonthlyPoint.region_id == region.id,
                   RegionMonthlyPoint.indicator_id.in_([x.id for x in siblings]))
            .order_by(RegionMonthlyPoint.month.desc())
        )).all():
            sib_latest.setdefault(iid, (int(m), float(v)))

    def _sibling(x):
        item = {"code": x.code, "name": _icopy(x)["name"], "unit": _icopy(x)["unit"]}
        got = sib_latest.get(x.id)
        if got:
            item["last_month"], item["month"], item["value"] = got[0], got[0], _fmt(got[1])
            item["period_label"] = _month_label(got[0])
        meta = price_meta(x.code)
        if meta:
            fields = _price_fields(meta)
            if got:
                fields.pop("last_month", None)
                fields.pop("last_month_label", None)
            item.update(fields)
        return item

    return [_sibling(x) for x in siblings]


@router.get("/{slug}/i/{code}")
async def region_indicator_detail(slug: str, code: str, db: AsyncSession = Depends(get_db)):
    cache_key = await versioned_key("regions", f"detail:v2:{slug}:{code}:{get_locale()}")
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
    top = [{"slug": s, "name": _rname(s, n), "value": _fmt(float(v))} for s, n, v in rank_rows[:5]]
    bottom = [{"slug": s, "name": _rname(s, n), "value": _fmt(float(v))} for s, n, v in rank_rows[-3:]]
    for pos, (s, _n, _v) in enumerate(rank_rows, 1):
        if s == region.slug:
            rank = pos
            break

    # соседние показатели раздела (для блока «В этом разделе»)
    sibling_items = await _section_siblings(db, region, indicator)

    copy = _icopy(indicator)
    result = {
        "region": {
            "slug": region.slug,
            "name": _rname(region.slug, region.name),
            "kind": region.kind,
        },
        "indicator": {
            "code": indicator.code,
            "name": copy["name"],
            "unit": copy["unit"],
            "note": copy["note"],
            "section_num": indicator.section_num,
            "section_name": copy["section"] or indicator.section_name,
            "table_code": indicator.table_code,
            "macro_code": MACRO_BY_TABLE.get(indicator.table_code or ""),
        },
        "series": series,
        "russia_series": russia_series,
        "rank": {
            "position": rank, "total": total_ranked, "year": last_year,
            "top": top, "bottom": bottom, **polarity,
        } if rank else None,
        "siblings": sibling_items,
    }
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result


MONTH_NAMES_RU = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)


def _monthly_price_fields(code: str, region_last: int) -> dict:
    meta = price_meta(code)
    if not meta:
        return {"short_name": None, "price_group": None, "is_discontinued": False, "last_month": region_last}
    return _price_fields(meta)


@router.get("/{slug}/i/{code}/monthly")
async def region_indicator_monthly(slug: str, code: str, db: AsyncSession = Depends(get_db)):
    """Помесячный ряд показателя в регионе (пока — цены на топливо, ЕМИСС).

    Точки {year, month, value, label}; label — «2026-08» для оси/тултипа.
    Сравнение с РФ строится, рейтинг — нет: цена зависит от структуры рынка
    и логистики региона, «место в рейтинге цен» вводило бы в заблуждение.
    """
    cache_key = await versioned_key("regions", f"monthly:v2:{slug}:{code}:{get_locale()}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    region = await _region_or_404(slug, db)
    indicator = (await db.execute(
        select(RegionIndicator).where(RegionIndicator.code == code)
    )).scalar_one_or_none()
    if indicator is None:
        raise HTTPException(404, "Показатель не найден")

    rows = (await db.execute(
        select(RegionMonthlyPoint.month, RegionMonthlyPoint.value)
        .where(RegionMonthlyPoint.indicator_id == indicator.id,
               RegionMonthlyPoint.region_id == region.id)
        .order_by(RegionMonthlyPoint.month)
    )).all()
    if not rows:
        raise HTTPException(404, "Нет месячных данных по этому показателю для региона")

    # YYYYMM → (year, month); месяц внутри года = остаток от деления на 100
    series = [
        {
            "year": m // 100,
            "month": m % 100,
            "value": _fmt(float(v)),
            "label": f"{m // 100}-{m % 100:02d}",
        }
        for m, v in rows
    ]

    # ряд РФ для сравнения (russia — «РФ без учёта новых субъектов» витрины)
    russia_series = []
    if region.slug != "russia":
        rf = (await db.execute(select(Region).where(Region.slug == "russia"))).scalar_one_or_none()
        if rf:
            rf_rows = (await db.execute(
                select(RegionMonthlyPoint.month, RegionMonthlyPoint.value)
                .where(RegionMonthlyPoint.indicator_id == indicator.id,
                       RegionMonthlyPoint.region_id == rf.id)
                .order_by(RegionMonthlyPoint.month)
            )).all()
            russia_series = [
                {"year": m // 100, "month": m % 100, "value": _fmt(float(v)), "label": f"{m // 100}-{m % 100:02d}"}
                for m, v in rf_rows
            ]

    # значения РФ и Москвы на последний месяц региона — «где ваша цена»
    last_m = rows[-1][0]
    compare = {"russia": None, "moskva": None}
    for key in ("russia", "moskva"):
        if region.slug == key:
            continue
        peer = (await db.execute(select(Region).where(Region.slug == key))).scalar_one_or_none()
        if peer is None:
            continue
        pv = (await db.execute(
            select(RegionMonthlyPoint.value)
            .where(RegionMonthlyPoint.indicator_id == indicator.id,
                   RegionMonthlyPoint.region_id == peer.id,
                   RegionMonthlyPoint.month == last_m)
        )).scalar_one_or_none()
        if pv is not None:
            compare[key] = {"value": _fmt(float(pv)), "month": int(last_m)}

    # соседние показатели раздела + мост в макроблок — та же семантика, что
    # у годового эндпоинта: карточка месяц-режима строит те же блоки.
    sibling_items = await _section_siblings(db, region, indicator)

    copy = _icopy(indicator)
    result = {
        "region": {
            "slug": region.slug,
            "name": _rname(region.slug, region.name),
            "kind": region.kind,
        },
        "indicator": {
            "code": indicator.code,
            "name": copy["name"],
            "unit": copy["unit"],
            "note": copy["note"],
            "section_num": indicator.section_num,
            "section_name": copy["section"] or indicator.section_name,
            "table_code": indicator.table_code,
            "macro_code": MACRO_BY_TABLE.get(indicator.table_code or ""),
            **_monthly_price_fields(indicator.code, int(last_m)),
        },
        "frequency": "monthly",
        "compare": compare,
        "series": series,
        "russia_series": russia_series,
        "siblings": sibling_items,
    }
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result
