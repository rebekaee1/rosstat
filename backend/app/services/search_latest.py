"""Additive presentation fields for the first search rows: latest stored value and a short trend.

Runs after retrieval and ranking, so it can never reorder, drop or add a candidate.
Only rows that stand for one stored series of their own (federal `Indicator` and
world `WorldIndicator`) are enriched; regional and territory rows are left as is.
The numbers are the series' own last stored points (no derived values, no
forecast), read in at most two bounded queries for the first few rows.
"""

from __future__ import annotations

from sqlalchemy import and_, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator, IndicatorData, WorldDataPoint

# Rows that get a value and a mini chart: what a person sees without pressing "more".
ENRICHED_ROWS = 8
# Points per mini chart: about a year of monthly data, enough to show a direction.
SPARK_POINTS = 12
_MIN_SPARK_POINTS = 3


def _finite(column):
    """Same bounds as the search fact gates: excludes PG NaN/Infinity."""
    return and_(column.is_not(None), column > literal_column("-1e30"), column < literal_column("1e30"))


async def _recent_points(db: AsyncSession, model, ids: list[int], points: int) -> dict[int, list[tuple]]:
    """Last `points` finite observations per series id, oldest first."""
    if not ids:
        return {}
    ranked = select(
        model.indicator_id.label("indicator_id"), model.date.label("date"), model.value.label("value"),
        func.row_number().over(partition_by=model.indicator_id, order_by=model.date.desc()).label("rn"),
    ).where(model.indicator_id.in_(ids), _finite(model.value)).subquery()
    rows = (await db.execute(
        select(ranked.c.indicator_id, ranked.c.date, ranked.c.value)
        .where(ranked.c.rn <= points).order_by(ranked.c.indicator_id, ranked.c.date)
    )).all()
    grouped: dict[int, list[tuple]] = {}
    for indicator_id, day, value in rows:
        grouped.setdefault(indicator_id, []).append((day, float(value)))
    return grouped


def _apply(item: dict, series: list[tuple] | None) -> None:
    if not series:
        return
    day, value = series[-1]
    item["latest"] = {"value": round(value, 4), "date": day.isoformat()}
    if len(series) >= _MIN_SPARK_POINTS:
        item["spark"] = [round(point, 4) for _day, point in series]


async def attach_latest(db: AsyncSession, results: list[dict], *, rows: int = ENRICHED_ROWS, points: int = SPARK_POINTS) -> None:
    """Add `latest` ({value, date}) and `spark` (oldest to newest) to the first `rows` series rows, in place."""
    head = [item for item in results[:rows] if item.get("code") and item.get("kind") in ("russia", "world")]
    if not head:
        return
    world_rows = db.info.get("fe_search_world_rows", {})
    world_ids: dict[tuple, int] = {}
    federal_codes: list[str] = []
    for item in head:
        if item["kind"] == "world":
            row = world_rows.get((item.get("country_slug"), item["code"]))
            if row is not None:
                world_ids[(item["country_slug"], item["code"])] = row.id
        else:
            federal_codes.append(item["code"])
    federal_ids: dict[str, int] = {}
    if federal_codes:
        federal_ids = {code: pk for pk, code in (await db.execute(
            select(Indicator.id, Indicator.code).where(Indicator.code.in_(federal_codes)))).all()}
    world_series = await _recent_points(db, WorldDataPoint, list(world_ids.values()), points)
    federal_series = await _recent_points(db, IndicatorData, list(federal_ids.values()), points)
    for item in head:
        if item["kind"] == "world":
            pk = world_ids.get((item.get("country_slug"), item["code"]))
            _apply(item, world_series.get(pk))
        else:
            pk = federal_ids.get(item["code"])
            _apply(item, federal_series.get(pk))
