"""Bulk reads for large subnational indicator catalogs."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SubnationalDataPoint


async def latest_region_points(
    db: AsyncSession,
    region_id: int,
    indicator_ids: list[int],
    *,
    limit: int = 2,
) -> dict[int, list[tuple[date, float]]]:
    """Read the last N observations for every requested indicator in one query."""
    if not indicator_ids:
        return {}
    rank = func.row_number().over(
        partition_by=SubnationalDataPoint.indicator_id,
        order_by=SubnationalDataPoint.period.desc(),
    ).label("rn")
    ranked = (
        select(
            SubnationalDataPoint.indicator_id,
            SubnationalDataPoint.period,
            SubnationalDataPoint.value,
            rank,
        )
        .where(
            SubnationalDataPoint.region_id == region_id,
            SubnationalDataPoint.indicator_id.in_(indicator_ids),
        )
        .subquery()
    )
    rows = (
        await db.execute(
            select(ranked.c.indicator_id, ranked.c.period, ranked.c.value)
            .where(ranked.c.rn <= limit)
            .order_by(ranked.c.indicator_id, ranked.c.period.desc())
        )
    ).all()
    grouped: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for indicator_id, period, value in rows:
        grouped[indicator_id].append((period, float(value)))
    return dict(grouped)
