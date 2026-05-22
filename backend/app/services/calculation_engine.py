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

Architectural decisions:
- `docs/adr/0001-derived-indicators-engine-shape.md` — declarative DSL +
  pure ops as the engine shape (28 specs, 9 ops as of 2026-05-07).
- `docs/adr/0002-derived-always-reflects-source.md` — invariant that derived
  always reflects current source state.
- See also `CONTEXT.md::Derived indicator` for the domain glossary.
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
    # CPI family — quarterly inflation (chained 3 monthly indices) and
    # December-to-December annual inflation (one point per calendar year,
    # matching ЦБ/Росстат convention). Annual is NOT rolling 12M anymore —
    # rolling produced a 12-point-per-year series with a U-shape under
    # forecasting and confused users; the new single-point-per-year series
    # is the standard «inflation Y». See ADR-0003.
    DerivedSpec("inflation-quarterly", ("cpi",), ops.quarterly_index),
    DerivedSpec("inflation-annual", ("cpi",), ops.december_to_december),
    DerivedSpec("cpi-food-quarterly", ("cpi-food",), ops.quarterly_index),
    DerivedSpec("cpi-food-annual", ("cpi-food",), ops.december_to_december),
    DerivedSpec("cpi-nonfood-quarterly", ("cpi-nonfood",), ops.quarterly_index),
    DerivedSpec("cpi-nonfood-annual", ("cpi-nonfood",), ops.december_to_december),
    DerivedSpec("cpi-services-quarterly", ("cpi-services",), ops.quarterly_index),
    DerivedSpec("cpi-services-annual", ("cpi-services",), ops.december_to_december),

    # PPI annual: same December-to-December logic on the producer price index.
    DerivedSpec("ppi-annual", ("ppi",), ops.december_to_december),

    # Wages: nominal × CPI → real wage index.
    DerivedSpec("wages-real", ("wages-nominal", "cpi"), ops.wages_real),

    # GDP year-over-year and quarter-over-quarter growth (две раздельные
    # семьи: nominal — в текущих ценах, real — в постоянных ценах 2021 г.).
    DerivedSpec("gdp-yoy", ("gdp-nominal",), ops.yoy),
    DerivedSpec("gdp-qoq", ("gdp-nominal",), ops.qoq),
    DerivedSpec("gdp-real-yoy", ("gdp-real",), ops.yoy),
    DerivedSpec("gdp-real-qoq", ("gdp-real",), ops.qoq),

    # Annual GDP (one point per complete calendar year):
    #   - nominal: sum of 4 quarterly values in current prices.
    #   - real:    sum of 4 quarterly values in constant 2021 prices.
    DerivedSpec("gdp-nominal-annual", ("gdp-nominal",), ops.annual_sum),
    DerivedSpec("gdp-real-annual", ("gdp-real",), ops.annual_sum),

    # Unemployment monthly → quarterly mean and 12-month rolling mean.
    DerivedSpec("unemployment-quarterly", ("unemployment",), ops.quarterly_avg),
    DerivedSpec("unemployment-annual", ("unemployment",), partial(ops.rolling_avg, window=12)),

    # YoY-only derivations (one per source).
    DerivedSpec("ipi-yoy", ("ipi",), ops.yoy),
    DerivedSpec("exports-yoy", ("exports",), ops.yoy),
    DerivedSpec("imports-yoy", ("imports",), ops.yoy),
    DerivedSpec("ppi-yoy", ("ppi",), ops.yoy),
    DerivedSpec("housing-yoy-primary", ("housing-price-primary",), ops.yoy),
    DerivedSpec("housing-yoy-secondary", ("housing-price-secondary",), ops.yoy),
    DerivedSpec("wages-yoy", ("wages-nominal",), ops.yoy),

    # YoY-абсолют (звонок 2026-05-22): для balances со знаком процент YoY
    # бессмыслен (база может быть нулём или отрицательной). Считаем разницу
    # в единицах источника — пользователь видит «сальдо выросло на N млн $».
    # Заменяет старый current-account-yoy %, который оставлен депрекейтнутым
    # в seed_data (is_active=false), но НЕ числится в DERIVED_SPECS — поэтому
    # CalculationEngine его больше не пересчитывает.
    DerivedSpec("current-account-yoy-abs", ("current-account",), ops.yoy_abs),
    DerivedSpec("trade-balance-yoy-abs", ("trade-balance",), ops.yoy_abs),

    # QoQ-only derivations.
    DerivedSpec("exports-qoq", ("exports",), ops.qoq),
    DerivedSpec("imports-qoq", ("imports",), ops.qoq),

    # C2 (звонок 2026-05-21): зарплата в индексной форме, среднее значение 2015 года = 100.
    # Сопоставимый формат с housing-price-primary/secondary (тоже индекс). База 2015,
    # потому что Росстат публикует помесячный ряд `wages-nominal` именно с 2015-01-01;
    # для базы 2010 годовых данных в БД пока нет.
    DerivedSpec("wages-index", ("wages-nominal",), partial(ops.rebase_to_index, base_year=2015)),

    # C1 (звонок 2026-05-21): индекс доступности жилья = wages-index / housing-price-secondary × 100.
    # Значения >100 — за период с 2010 года зарплаты росли быстрее цен на жильё (доступность ↑),
    # <100 — цены на жильё обогнали зарплаты (доступность ↓). Берём вторичный рынок
    # как более широкий и менее зависимый от госипотечных программ.
    DerivedSpec(
        "housing-affordability",
        ("housing-price-secondary", "wages-index"),
        ops.affordability_index,
    ),
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
        """Recompute every derived series end-to-end after an ETL batch.

        Semantic (ADR-0002, since 2026-05-05): derived[t] always reflects the
        current state of source[t]. Whenever any source updated in this ETL
        batch, every derived is recomputed across its full history — not just
        the ones whose source code appears in `source_codes`. This matters
        because parsers detect "new" by `records_added > 0` (incremental rows),
        but Rosstat revises historical points in place (`records_updated > 0`).
        Old code only touched derived whose source raised `records_added`,
        leaving stale derived values for years after a silent revision.

        `source_codes` is kept for short-circuit only: if the ETL batch did
        nothing (`source_codes == []`), there's no point spending CPU to
        re-derive identical numbers. Otherwise we recompute all 23 derived;
        `bulk_upsert` is no-op for unchanged values, so cost is bounded.

        Returns the list of derived codes whose stored values actually changed
        (and thus whose Redis cache was invalidated).
        """
        if not source_codes:
            return []
        updated: list[str] = []
        for code, (_sources, fn) in self._derived.items():
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
