"""Bulk "latest observation" reads for large indicator catalogs.

Perf batch 2 (2026-09-26): the previous implementation ranked *every* point
of every requested series with ``row_number() OVER (PARTITION BY …)`` and
kept rn <= N. For a US state that is ~88k rows (1.9k series) and for a
Eurostat-heavy country page ~425k rows, only to keep one row per series.

Now each series is probed with ``LATERAL (… ORDER BY period DESC LIMIT N)``
over the ``(region_id, indicator_id, period)`` / ``(indicator_id, date)``
btree indexes: O(series × N) index reads instead of O(points).
Results are identical (same ordering: newest first per series).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import Integer, cast, func, select, true
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SubnationalDataPoint, WorldDataPoint


def _is_postgres(db) -> bool:
    """LATERAL + unnest(int[]) — PostgreSQL; тестовый SQLite идёт окном."""
    try:
        return db.get_bind().dialect.name == "postgresql"
    except Exception:  # noqa: BLE001 — заглушки сессий в тестах
        return True


def _ids_subquery(ids: list[int]):
    return select(
        func.unnest(cast(list(ids), ARRAY(Integer))).label("id")
    ).subquery("req_ids")


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
    if not _is_postgres(db):
        return await _latest_region_points_window(db, region_id, indicator_ids, limit=limit)
    ids = _ids_subquery(sorted(set(int(i) for i in indicator_ids)))
    pts = (
        select(SubnationalDataPoint.period, SubnationalDataPoint.value)
        .where(
            SubnationalDataPoint.region_id == region_id,
            SubnationalDataPoint.indicator_id == ids.c.id,
        )
        .order_by(SubnationalDataPoint.period.desc())
        .limit(limit)
        .lateral("pts")
    )
    rows = (
        await db.execute(
            select(ids.c.id, pts.c.period, pts.c.value)
            .select_from(ids.join(pts, true()))
            .order_by(ids.c.id, pts.c.period.desc())
        )
    ).all()
    grouped: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for indicator_id, period, value in rows:
        grouped[int(indicator_id)].append((period, float(value)))
    return dict(grouped)


async def latest_world_points(
    db: AsyncSession,
    indicator_ids: list[int],
) -> dict[int, tuple[date, float]]:
    """Latest (date, value) per world indicator: one LATERAL index probe each."""
    if not indicator_ids:
        return {}
    if not _is_postgres(db):
        return await _latest_world_points_window(db, indicator_ids)
    ids = _ids_subquery(sorted(set(int(i) for i in indicator_ids)))
    pts = (
        select(WorldDataPoint.date, WorldDataPoint.value)
        .where(WorldDataPoint.indicator_id == ids.c.id)
        .order_by(WorldDataPoint.date.desc())
        .limit(1)
        .lateral("pts")
    )
    rows = (
        await db.execute(
            select(ids.c.id, pts.c.date, pts.c.value).select_from(ids.join(pts, true()))
        )
    ).all()
    return {int(iid): (dt, float(value)) for iid, dt, value in rows}


# --- Портируемый фолбэк (SQLite в тестах): прежний window-запрос ------------


async def _latest_region_points_window(
    db: AsyncSession, region_id: int, indicator_ids: list[int], *, limit: int,
) -> dict[int, list[tuple[date, float]]]:
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


async def _latest_world_points_window(
    db: AsyncSession, indicator_ids: list[int],
) -> dict[int, tuple[date, float]]:
    rn = func.row_number().over(
        partition_by=WorldDataPoint.indicator_id,
        order_by=WorldDataPoint.date.desc(),
    ).label("rn")
    sub = (
        select(WorldDataPoint.indicator_id, WorldDataPoint.date, WorldDataPoint.value, rn)
        .where(WorldDataPoint.indicator_id.in_(indicator_ids))
        .subquery()
    )
    rows = (
        await db.execute(
            select(sub.c.indicator_id, sub.c.date, sub.c.value).where(sub.c.rn == 1)
        )
    ).all()
    return {iid: (dt, float(value)) for iid, dt, value in rows}
