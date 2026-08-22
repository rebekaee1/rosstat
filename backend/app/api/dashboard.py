from fastapi import APIRouter, Depends
from sqlalchemy import distinct, select, desc, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Indicator,
    IndicatorData,
    Region,
    RegionDataPoint,
    WorldCountry,
    WorldDataPoint,
    WorldIndicator,
)
from app.core.cache import cache_get, cache_set, versioned_key
from app.services.locale import get_locale
from app.services.seo_i18n import public_indicator_fields

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

FLAGSHIP_MAP: dict[str, dict] = {
    "prices":     {"code": "cpi",             "sentiment": "inverse"},
    "rates":      {"code": "key-rate",        "sentiment": "neutral"},
    "finance":    {"code": "usd-rub",         "sentiment": "inverse"},
    "labor":      {"code": "unemployment",    "sentiment": "inverse"},
    "gdp":        {"code": "gdp-nominal",     "sentiment": "positive"},
    "population": {"code": "population",      "sentiment": "positive"},
    "trade":      {"code": "current-account", "sentiment": "neutral"},
    "business":   {"code": "ipi",             "sentiment": "positive"},
    "science":    {"code": "rd-personnel",    "sentiment": "positive"},
}

POINTS_LIMIT = 12
CACHE_TTL = 1800
COVERAGE_TTL = 21600


@router.get("/coverage")
async def dashboard_coverage(db: AsyncSession = Depends(get_db)):
    """Сколько данных на платформе: страны, публичные ряды, период наблюдений.

    Числа считаются по фактическому содержимому базы, а не задаются вручную:
    иначе витрина расходится с данными при первом же обновлении каталога.
    Россия учитывается отдельным слагаемым — в мировом каталоге её нет.
    """
    cache_key = await versioned_key("dashboard", "coverage:v1")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    world_countries = int(
        (
            await db.execute(
                select(func.count(distinct(WorldIndicator.country_id)))
                .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
                .where(
                    WorldIndicator.is_listed.is_(True),
                    WorldCountry.is_active.is_(True),
                )
            )
        ).scalar()
        or 0
    )
    world_series = int(
        (
            await db.execute(
                select(func.count()).select_from(WorldIndicator)
                .where(WorldIndicator.is_listed.is_(True))
            )
        ).scalar()
        or 0
    )
    russia_series = int(
        (
            await db.execute(
                select(func.count()).select_from(Indicator)
                .where(Indicator.is_listed.is_(True))
            )
        ).scalar()
        or 0
    )
    # Региональный ряд = показатель × субъект: пара, а не показатель.
    regional_series = int(
        (
            await db.execute(
                text(
                    "select count(*) from ("
                    " select distinct d.indicator_id, d.region_id from region_data d"
                    " join regions r on r.id = d.region_id and r.kind = 'region'"
                    ") pairs"
                )
            )
        ).scalar()
        or 0
    )
    # Только субъекты: федеральные округа, РФ целиком и остатки — служебные
    # строки артефакта, наружу их считать нельзя.
    regions = int(
        (
            await db.execute(
                select(func.count()).select_from(Region).where(Region.kind == "region")
            )
        ).scalar()
        or 0
    )

    years: list[int] = []
    for span_query in (
        select(func.min(IndicatorData.date), func.max(IndicatorData.date)),
        select(func.min(WorldDataPoint.date), func.max(WorldDataPoint.date)),
    ):
        span = (await db.execute(span_query)).first()
        if span:
            years.extend(int(v.year) for v in span if v is not None)
    region_span = (
        await db.execute(
            select(func.min(RegionDataPoint.year), func.max(RegionDataPoint.year))
        )
    ).first()
    if region_span:
        years.extend(int(v) for v in region_span if v is not None)

    payload = {
        "countries": world_countries + (1 if russia_series else 0),
        "series": world_series + russia_series + regional_series,
        "regions": regions,
        "year_from": min(years) if years else None,
        "year_to": max(years) if years else None,
    }
    await cache_set(cache_key, payload, COVERAGE_TTL)
    return payload


@router.get("/sparklines")
async def dashboard_sparklines(db: AsyncSession = Depends(get_db)):
    cache_key = await versioned_key("dashboard", f"sparklines:{get_locale()}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    codes = [v["code"] for v in FLAGSHIP_MAP.values()]

    ind_q = await db.execute(
        select(
            Indicator.id,
            Indicator.code,
            Indicator.name,
            Indicator.name_en,
            Indicator.unit,
        )
        .where(Indicator.code.in_(codes))
    )
    indicators = {row.code: row for row in ind_q.all()}

    if not indicators:
        return {}

    ind_ids = [row.id for row in indicators.values()]

    ranked = (
        select(
            IndicatorData.indicator_id,
            IndicatorData.date,
            IndicatorData.value,
            func.row_number()
            .over(
                partition_by=IndicatorData.indicator_id,
                order_by=desc(IndicatorData.date),
            )
            .label("rn"),
        )
        .where(IndicatorData.indicator_id.in_(ind_ids))
        .subquery()
    )

    data_q = await db.execute(
        select(
            ranked.c.indicator_id,
            ranked.c.date,
            ranked.c.value,
            ranked.c.rn,
        ).where(ranked.c.rn <= POINTS_LIMIT)
    )
    rows = data_q.all()

    by_ind_id: dict[int, list] = {}
    for row in rows:
        by_ind_id.setdefault(row.indicator_id, []).append(row)

    result = {}
    for cat_slug, cfg in FLAGSHIP_MAP.items():
        code = cfg["code"]
        ind = indicators.get(code)
        if not ind:
            continue

        pts = by_ind_id.get(ind.id, [])
        pts.sort(key=lambda r: r.rn, reverse=True)

        if not pts:
            continue

        points = [float(r.value) for r in pts]
        current_value = points[-1] if points else None
        previous_value = points[-2] if len(points) >= 2 else None

        change = None
        if current_value is not None and previous_value is not None:
            change = round(current_value - previous_value, 4)

        trend = "flat"
        if change is not None:
            if change > 0:
                trend = "up"
            elif change < 0:
                trend = "down"

        fields = public_indicator_fields(
            code,
            name_ru=ind.name,
            name_en=ind.name_en,
            unit_ru=ind.unit,
        )
        result[cat_slug] = {
            "code": code,
            "name": fields["name"] or ind.name,
            "unit": fields.get("unit") or ind.unit,
            "points": points,
            "current_value": current_value,
            "previous_value": previous_value,
            "change": change,
            "trend": trend,
            "sentiment": cfg["sentiment"],
            "point_count": len(points),
            "last_date": str(pts[-1].date) if pts else None,
        }

    await cache_set(cache_key, result, CACHE_TTL)
    return result
