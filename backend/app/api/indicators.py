import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData
from app.schemas import IndicatorSummary, IndicatorDetail, IndicatorStats, DataPointOut, DataResponse
from app.core.cache import cache_get, cache_set
from app.config import settings

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("", response_model=list[IndicatorSummary])
async def list_indicators(
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None, description="Точное совпадение с полем category в БД"),
    include_inactive: bool = Query(False, description="Показать неактивные индикаторы"),
):
    cache_key = f"fe:indicators:list:{category or 'all'}:{'all' if include_inactive else 'active'}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    stmt = select(Indicator).order_by(Indicator.code)
    if not include_inactive:
        stmt = stmt.where(Indicator.is_active.is_(True))
    if category:
        stmt = stmt.where(Indicator.category == category)
    result = await db.execute(stmt)
    indicators = result.scalars().all()
    if not indicators:
        return []

    ind_ids = [ind.id for ind in indicators]

    ranked = (
        select(
            IndicatorData.indicator_id,
            IndicatorData.date,
            IndicatorData.value,
            func.row_number()
            .over(partition_by=IndicatorData.indicator_id, order_by=desc(IndicatorData.date))
            .label("rn"),
        )
        .where(IndicatorData.indicator_id.in_(ind_ids))
        .subquery()
    )
    latest_q = await db.execute(
        select(ranked.c.indicator_id, ranked.c.date, ranked.c.value, ranked.c.rn)
        .where(ranked.c.rn <= 2)
    )
    latest_rows = latest_q.all()

    by_ind: dict[int, list] = {}
    for row in latest_rows:
        by_ind.setdefault(row.indicator_id, []).append(row)
    for v in by_ind.values():
        v.sort(key=lambda r: r.rn)

    out = []
    for ind in indicators:
        rows = by_ind.get(ind.id, [])
        current_val = rows[0].value if rows else None
        current_dt = rows[0].date if rows else None
        prev_val = rows[1].value if len(rows) > 1 else None
        change = round(float(current_val - prev_val), 4) if current_val is not None and prev_val is not None else None

        out.append(IndicatorSummary(
            code=ind.code, name=ind.name, name_en=ind.name_en,
            unit=ind.unit, category=ind.category, is_active=ind.is_active,
            current_value=float(current_val) if current_val is not None else None,
            current_date=current_dt, previous_value=float(prev_val) if prev_val is not None else None,
            change=change,
        ))

    serialized = [s.model_dump(mode="json") for s in out]
    await cache_set(cache_key, serialized, settings.cache_ttl_meta)
    return out


_CODE_RE = re.compile(r'^[a-z0-9-]+$')


def _validate_code(code: str) -> None:
    if not _CODE_RE.match(code):
        raise HTTPException(status_code=400, detail="Invalid indicator code format")


@router.get("/{code}", response_model=IndicatorDetail)
async def get_indicator(code: str, db: AsyncSession = Depends(get_db)):
    _validate_code(code)
    cached = await cache_get(f"fe:{code}:detail")
    if cached:
        return cached

    ind = await db.execute(select(Indicator).where(Indicator.code == code))
    indicator = ind.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    stats = await db.execute(
        select(
            func.count(IndicatorData.id),
            func.min(IndicatorData.date),
            func.max(IndicatorData.date),
        ).where(IndicatorData.indicator_id == indicator.id)
    )
    count, first_dt, last_dt = stats.one()

    latest = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(desc(IndicatorData.date))
        .limit(2)
    )
    recent = latest.scalars().all()
    current_val = recent[0].value if recent else None
    current_dt = recent[0].date if recent else None
    prev_val = recent[1].value if len(recent) > 1 else None
    change = round(float(current_val - prev_val), 4) if current_val is not None and prev_val is not None else None

    detail = IndicatorDetail(
        code=indicator.code, name=indicator.name, name_en=indicator.name_en,
        unit=indicator.unit, category=indicator.category, is_active=indicator.is_active,
        frequency=indicator.frequency, source=indicator.source,
        source_url=indicator.source_url, description=indicator.description,
        methodology=indicator.methodology,
        current_value=float(current_val) if current_val is not None else None,
        current_date=current_dt, previous_value=float(prev_val) if prev_val is not None else None,
        change=change, data_count=count, first_date=first_dt, last_date=last_dt,
        updated_at=indicator.updated_at,
    )

    await cache_set(f"fe:{code}:detail", detail.model_dump(mode="json"), settings.cache_ttl_meta)
    return detail


@router.get("/{code}/data", response_model=DataResponse)
async def get_indicator_data(
    code: str,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    limit: int = Query(10000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    _validate_code(code)
    cache_key = f"fe:{code}:data:{from_date}:{to_date}:{limit}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    ind = await db.execute(select(Indicator).where(Indicator.code == code))
    indicator = ind.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    stmt = (
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
    )
    if from_date:
        stmt = stmt.where(IndicatorData.date >= from_date)
    if to_date:
        stmt = stmt.where(IndicatorData.date <= to_date)

    if not from_date and not to_date:
        stmt = stmt.order_by(desc(IndicatorData.date)).limit(limit)
        result = await db.execute(stmt)
        rows = list(reversed(result.scalars().all()))
    else:
        stmt = stmt.order_by(IndicatorData.date).limit(limit)
        result = await db.execute(stmt)
        rows = result.scalars().all()

    response = DataResponse(
        indicator=code,
        count=len(rows),
        data=[DataPointOut(date=r.date, value=float(r.value)) for r in rows],
    )

    await cache_set(cache_key, response.model_dump(mode="json"), settings.cache_ttl_data)
    return response


@router.get("/{code}/stats", response_model=IndicatorStats)
async def get_indicator_stats(code: str, db: AsyncSession = Depends(get_db)):
    _validate_code(code)
    ind = await db.execute(select(Indicator).where(Indicator.code == code))
    indicator = ind.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    stats_q = await db.execute(
        select(
            func.count(IndicatorData.id),
            func.avg(IndicatorData.value),
            func.stddev(IndicatorData.value),
        ).where(IndicatorData.indicator_id == indicator.id)
    )
    count, avg_val, std_val = stats_q.one()

    highest_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(desc(IndicatorData.value))
        .limit(1)
    )
    highest = highest_q.scalar_one_or_none()

    lowest_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(IndicatorData.value)
        .limit(1)
    )
    lowest = lowest_q.scalar_one_or_none()

    return IndicatorStats(
        code=code,
        highest={"value": float(highest.value), "date": str(highest.date)} if highest else None,
        lowest={"value": float(lowest.value), "date": str(lowest.date)} if lowest else None,
        average=round(float(avg_val), 2) if avg_val is not None else None,
        std_dev=round(float(std_val), 2) if std_val is not None else None,
        data_count=count or 0,
    )
