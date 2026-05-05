"""
Derived-indicator engine.

Each derived indicator is described once as a `DerivedSpec` (destination code,
source codes, pure operation from `derived_ops`). A generic executor loads the
source series, calls the operation, and upserts the result via
`bulk_upsert`. After ETL the engine dispatches recomputation only for derived
indicators whose source list intersects the freshly-updated indicators, and
invalidates their Redis cache when a value actually changed.

This module owns the seam between **the formula** (pure, in `derived_ops`) and
**the storage** (this file). To add a derived indicator:
  1. add (or reuse) a pure op in `derived_ops.py`,
  2. append a `DerivedSpec(...)` entry to `DERIVED_SPECS` below,
  3. ensure both source and destination indicators are seeded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from functools import partial
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_invalidate_indicator
from app.models import Indicator, IndicatorData
from app.services import derived_ops as ops
from app.services.upsert import bulk_upsert

logger = logging.getLogger(__name__)

DerivedFn = Callable[[AsyncSession], Awaitable[int]]
DerivedOp = Callable[..., list[tuple[date, float]]]


@dataclass(frozen=True)
class DerivedSpec:
    """Declarative description of one derived indicator.

    `op` receives `len(src_codes)` lists of `(date, value)` tuples (each ordered
    by date) and returns a list of `(date, value)` tuples to upsert into the
    destination indicator.
    """

    dst_code: str
    src_codes: tuple[str, ...]
    op: DerivedOp


DERIVED_SPECS: list[DerivedSpec] = [
    # CPI family — quarterly and annual aggregates of monthly indices.
    DerivedSpec("inflation-quarterly", ("cpi",), ops.quarterly_index),
    DerivedSpec("inflation-annual", ("cpi",), ops.annual_inflation),
    DerivedSpec("cpi-food-quarterly", ("cpi-food",), ops.quarterly_index),
    DerivedSpec("cpi-food-annual", ("cpi-food",), ops.annual_inflation),
    DerivedSpec("cpi-nonfood-quarterly", ("cpi-nonfood",), ops.quarterly_index),
    DerivedSpec("cpi-nonfood-annual", ("cpi-nonfood",), ops.annual_inflation),
    DerivedSpec("cpi-services-quarterly", ("cpi-services",), ops.quarterly_index),
    DerivedSpec("cpi-services-annual", ("cpi-services",), ops.annual_inflation),

    # Wages: nominal × CPI → real wage index.
    DerivedSpec("wages-real", ("wages-nominal", "cpi"), ops.wages_real),

    # GDP year-over-year and quarter-over-quarter growth.
    DerivedSpec("gdp-yoy", ("gdp-nominal",), ops.yoy),
    DerivedSpec("gdp-qoq", ("gdp-nominal",), ops.qoq),

    # Unemployment monthly → quarterly mean and 12-month rolling mean.
    DerivedSpec("unemployment-quarterly", ("unemployment",), ops.quarterly_avg),
    DerivedSpec("unemployment-annual", ("unemployment",), partial(ops.rolling_avg, window=12)),

    # YoY-only derivations (one per source).
    DerivedSpec("current-account-yoy", ("current-account",), ops.yoy),
    DerivedSpec("ipi-yoy", ("ipi",), ops.yoy),
    DerivedSpec("exports-yoy", ("exports",), ops.yoy),
    DerivedSpec("imports-yoy", ("imports",), ops.yoy),
    DerivedSpec("ppi-yoy", ("ppi",), ops.yoy),
    DerivedSpec("housing-yoy-primary", ("housing-price-primary",), ops.yoy),
    DerivedSpec("housing-yoy-secondary", ("housing-price-secondary",), ops.yoy),
    DerivedSpec("wages-yoy", ("wages-nominal",), ops.yoy),

    # QoQ-only derivations.
    DerivedSpec("exports-qoq", ("exports",), ops.qoq),
    DerivedSpec("imports-qoq", ("imports",), ops.qoq),
]


async def _load_series(db: AsyncSession, code: str) -> tuple[int | None, list[tuple[date, float]]]:
    """Return (indicator_id, ordered series) for `code`, or (None, []) if missing."""
    ind = (await db.execute(select(Indicator).where(Indicator.code == code))).scalar_one_or_none()
    if not ind:
        return None, []
    rows = (await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == ind.id)
        .order_by(IndicatorData.date)
    )).scalars().all()
    return ind.id, [(r.date, float(r.value)) for r in rows]


async def _execute(db: AsyncSession, spec: DerivedSpec) -> int:
    """Compute one derived series and upsert it. Returns # of rows actually changed."""
    dst_id, _ = await _load_series(db, spec.dst_code)
    if dst_id is None:
        return 0

    inputs: list[list[tuple[date, float]]] = []
    for code in spec.src_codes:
        src_id, series = await _load_series(db, code)
        if src_id is None:
            return 0
        inputs.append(series)

    points = spec.op(*inputs)
    if not points:
        return 0

    added, updated = await bulk_upsert(db, dst_id, points)
    return added + updated


class CalculationEngine:
    """Registry of derived series + post-ETL dispatcher."""

    def __init__(self) -> None:
        self._derived: dict[str, tuple[list[str], DerivedFn]] = {}

    def register_spec(self, spec: DerivedSpec) -> None:
        """Register a declarative spec; the executor is generated automatically."""
        async def fn(db: AsyncSession) -> int:
            return await _execute(db, spec)
        self._derived[spec.dst_code] = (list(spec.src_codes), fn)

    def register(self, code: str, sources: list[str], fn: DerivedFn) -> None:
        """Escape hatch for ad-hoc derivations that don't fit a `DerivedSpec`."""
        self._derived[code] = (sources, fn)

    async def run_for_updated_sources(self, db: AsyncSession, source_codes: list[str]) -> list[str]:
        """Recompute every derived whose source list intersects `source_codes`.

        Returns the list of derived codes whose stored values changed (and thus
        whose Redis cache was invalidated).
        """
        if not source_codes:
            return []
        updated: list[str] = []
        for code, (sources, fn) in self._derived.items():
            if not any(s in source_codes for s in sources):
                continue
            try:
                n = await fn(db)
                if n > 0:
                    await cache_invalidate_indicator(code)
                    updated.append(code)
                logger.info("CalculationEngine: %s → %d changes", code, n)
            except Exception:
                logger.exception("CalculationEngine: failed to compute '%s'", code)
        return updated


calculation_engine = CalculationEngine()
for _spec in DERIVED_SPECS:
    calculation_engine.register_spec(_spec)
