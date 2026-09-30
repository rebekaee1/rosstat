"""SQL-only metadata for the surviving annual/monthly regional history.

Call inside the writer's transaction, after point writes. The caller commits
and publishes cache generations; this module never commits or touches Redis.
"""

from collections.abc import Iterable

from sqlalchemy import func, or_, select, text, union_all, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RegionDataPoint, RegionIndicator, RegionMonthlyPoint

_REGIONAL_WRITE_LOCK_ID = 7063003


async def acquire_regional_write_lock(db: AsyncSession) -> None:
    """Serialize seed/EMISS SQL units before either acquires row locks.

    Both writers update metadata and points in different orders. A shared
    transaction advisory lock prevents that row-lock inversion, and releases
    automatically on commit/rollback. Fetch first; never hold it during HTTP.
    Non-PostgreSQL hermetic fixtures need no PostgreSQL advisory-lock syntax.
    """
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                         {"key": _REGIONAL_WRITE_LOCK_ID})


async def update_regional_year_bounds(
    db: AsyncSession, indicator_ids: Iterable[int] | None = None,
) -> int:
    """Refresh catalogue bounds from actual stored periods, including extras.

    Monthly YYYYMM uses integer SQL division. An explicit empty id set is a
    no-op; a monthly writer restricts aggregation to its changed indicators.
    A seed passes None to reconcile every indicator, including empty ones.
    """
    ids = None if indicator_ids is None else sorted(set(indicator_ids))
    if ids == []:
        return 0
    annual = select(RegionDataPoint.indicator_id, RegionDataPoint.year.label("year"))
    monthly = select(
        RegionMonthlyPoint.indicator_id,
        RegionMonthlyPoint.month.op("/")(100).label("year"),
    )
    indicators = select(RegionIndicator.id)
    if ids is not None:
        annual = annual.where(RegionDataPoint.indicator_id.in_(ids))
        monthly = monthly.where(RegionMonthlyPoint.indicator_id.in_(ids))
        indicators = indicators.where(RegionIndicator.id.in_(ids))
    periods = union_all(annual, monthly).subquery()
    selected = indicators.subquery()
    bounds = (
        select(selected.c.id, func.min(periods.c.year).label("lo"),
               func.max(periods.c.year).label("hi"))
        .outerjoin(periods, periods.c.indicator_id == selected.c.id)
        .group_by(selected.c.id).subquery()
    )
    result = await db.execute(
        update(RegionIndicator)
        .where(
            RegionIndicator.id == bounds.c.id,
            or_(RegionIndicator.year_min.is_distinct_from(bounds.c.lo),
                RegionIndicator.year_max.is_distinct_from(bounds.c.hi)),
        )
        .values(year_min=bounds.c.lo, year_max=bounds.c.hi)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount
