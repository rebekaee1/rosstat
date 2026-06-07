"""Shared upsert helper for IndicatorData — on_conflict_do_update ensures revisions are captured.

This is the seam that enforces the ADR-0002 invariant: any source revision
(value change for an existing date) is automatically picked up at the next ETL.
The `where=(value != excluded.value)` guard makes repeated upserts of unchanged
points a no-op — `records_added`/`records_updated` only increment on real change.

See `docs/adr/0002-derived-always-reflects-source.md` for the full invariant
and its boundaries (pure-revision day limitation). The same idempotency holds
for every concrete parser (CBR / Минфин / Rosstat) — see parser docstrings
in `backend/app/services/*_parser.py`.
"""

from datetime import date as _date

from sqlalchemy import delete, select, func
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


async def prune_indicator_dates_not_in(
    db: AsyncSession,
    indicator_id: int,
    points: list,
) -> int:
    """Удалить точки индикатора, которых нет в свежем parse-output.

    Для источников с полным снимком ряда (Минфин OpenData CSV) — убирает
    устаревшие preliminary-точки из пресс-релизов, если парсер их больше
    не отдаёт.
    """
    parsed_dates = {_split_point(p)[0] for p in points}
    if not parsed_dates:
        return 0
    result = await db.execute(
        delete(IndicatorData).where(
            IndicatorData.indicator_id == indicator_id,
            IndicatorData.date.not_in(parsed_dates),
        )
    )
    deleted = result.rowcount or 0
    if deleted:
        await db.flush()
    return deleted


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
        # ADR-0002 boundary: never overwrite an existing value with NULL/None.
        # An empty/None payload from a parser (e.g. source page changed shape, got 502)
        # must NOT silently wipe what's already in the DB. Skip such points entirely.
        if val is None:
            continue
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
