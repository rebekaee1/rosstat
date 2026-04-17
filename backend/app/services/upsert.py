"""Shared upsert helper for IndicatorData — on_conflict_do_update ensures revisions are captured."""

from datetime import date as _date

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IndicatorData


def upsert_indicator_data(indicator_id: int, dt: _date, val: float):
    """INSERT … ON CONFLICT (indicator_id, date) DO UPDATE SET value = excluded.value
    only when value actually changed. Returns affected row via RETURNING."""
    stmt = pg_insert(IndicatorData).values(
        indicator_id=indicator_id, date=dt, value=val,
    )
    return stmt.on_conflict_do_update(
        constraint="uq_indicator_date",
        set_={"value": stmt.excluded.value},
        where=(IndicatorData.__table__.c.value != stmt.excluded.value),
    ).returning(IndicatorData.id)


def _split_point(point):
    """Accept either dataclass/NamedTuple with .date/.value or plain (date, value) tuple."""
    if hasattr(point, "date") and hasattr(point, "value"):
        return point.date, point.value
    if isinstance(point, (tuple, list)) and len(point) >= 2:
        return point[0], point[1]
    raise TypeError(f"Unsupported point shape for bulk_upsert: {type(point).__name__}")


async def bulk_upsert(db: AsyncSession, indicator_id: int, points: list) -> tuple[int, int]:
    """Upsert a list of points. Accepts objects with .date/.value OR (date, value) tuples.
    Returns (new_records, updated_records)."""
    count_before = (await db.execute(
        select(func.count(IndicatorData.id))
        .where(IndicatorData.indicator_id == indicator_id)
    )).scalar() or 0

    changed = 0
    for point in points:
        dt, val = _split_point(point)
        result = await db.execute(upsert_indicator_data(indicator_id, dt, val))
        if result.fetchone() is not None:
            changed += 1

    await db.flush()
    count_after = (await db.execute(
        select(func.count(IndicatorData.id))
        .where(IndicatorData.indicator_id == indicator_id)
    )).scalar() or 0

    records_added = count_after - count_before
    records_updated = changed - records_added
    return records_added, records_updated
