import logging
from datetime import timezone, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData
from app.core.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

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
CACHE_KEY = "fe:dashboard:sparklines"
CACHE_TTL = 1800


@router.get("/sparklines")
async def dashboard_sparklines(db: AsyncSession = Depends(get_db)):
    cached = await cache_get(CACHE_KEY)
    if cached:
        return cached

    codes = [v["code"] for v in FLAGSHIP_MAP.values()]

    ind_q = await db.execute(
        select(Indicator.id, Indicator.code, Indicator.name, Indicator.unit)
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

    id_to_code = {row.id: row.code for row in indicators.values()}

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

        result[cat_slug] = {
            "code": code,
            "name": ind.name,
            "unit": ind.unit,
            "points": points,
            "current_value": current_value,
            "previous_value": previous_value,
            "change": change,
            "trend": trend,
            "sentiment": cfg["sentiment"],
            "point_count": len(points),
            "last_date": str(pts[-1].date) if pts else None,
        }

    await cache_set(CACHE_KEY, result, CACHE_TTL)
    return result
