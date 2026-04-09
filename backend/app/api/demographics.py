"""Batch endpoint for demographic age structure data (population pyramid)."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData
from app.core.cache import cache_get, cache_set
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demographics", tags=["demographics"])

AGE_GROUP_CODES = [
    "pop-under-working-age",
    "working-age-population",
    "pop-over-working-age",
]


@router.get("/structure")
async def age_structure(db: AsyncSession = Depends(get_db)):
    """All 3 age groups merged by year for stacked visualization."""
    cache_key = "fe:demographics:structure"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    q = await db.execute(
        select(Indicator)
        .where(Indicator.code.in_(AGE_GROUP_CODES))
        .where(Indicator.is_active.is_(True))
    )
    indicators = {ind.code: ind for ind in q.scalars().all()}

    series: dict[str, list[dict]] = {}
    for code in AGE_GROUP_CODES:
        ind = indicators.get(code)
        if not ind:
            series[code] = []
            continue
        data_q = await db.execute(
            select(IndicatorData.date, IndicatorData.value)
            .where(IndicatorData.indicator_id == ind.id)
            .order_by(IndicatorData.date)
        )
        series[code] = [
            {"date": str(row.date), "value": float(row.value)}
            for row in data_q.all()
        ]

    by_year: dict[str, dict] = {}
    for code, points in series.items():
        for pt in points:
            yr = pt["date"][:4]
            entry = by_year.setdefault(yr, {"year": int(yr)})
            entry[code] = pt["value"]

    merged = sorted(by_year.values(), key=lambda r: r["year"])

    meta = {}
    for code in AGE_GROUP_CODES:
        ind = indicators.get(code)
        if ind:
            meta[code] = {"name": ind.name, "name_en": ind.name_en, "unit": ind.unit}

    result = {"series": merged, "meta": meta}
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result
