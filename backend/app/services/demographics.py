"""One observed age-structure dataset shared by API, HTML and image rendering."""
import math
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Indicator, IndicatorData
from app.core.cache import cache_get, cache_set, versioned_key
from app.config import settings

AGE_GROUP_CODES = [
    "pop-under-working-age",
    "working-age-population",
    "pop-over-working-age",
]


async def age_structure(db: AsyncSession):
    """All 3 age groups merged by year for stacked visualization."""
    cache_key = await versioned_key("indicators", "demographics:structure:v2")
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
            meta[code] = {"name": ind.name, "name_en": ind.name_en, "unit": ind.unit, "source": ind.source, "source_url": ind.source_url}

    result = {"series": merged, "meta": meta}
    await cache_set(cache_key, result, settings.cache_ttl_data)
    return result


def complete_snapshot(data: dict, year: int | None = None) -> dict | None:
    """The latest complete comparable year; never treat an absent group as zero."""
    units = [data.get("meta", {}).get(code, {}).get("unit") for code in AGE_GROUP_CODES]
    if not all(units) or len(set(units)) != 1:
        return None
    for row in reversed(data.get("series", [])):
        if year is not None and row["year"] != year:
            continue
        values = [row.get(code) for code in AGE_GROUP_CODES]
        if all(v is not None and math.isfinite(float(v)) and float(v) >= 0 for v in values) and sum(values) > 0:
            return row
    return None

def snapshot_groups(row: dict, locale: str) -> list[tuple[str, float]]:
    labels = ("Below working age", "Working age", "Above working age") if locale == "en" else ("Моложе трудоспособного", "Трудоспособный возраст", "Старше трудоспособного")
    return [(label, row[code]) for label, code in zip(labels, AGE_GROUP_CODES)]
