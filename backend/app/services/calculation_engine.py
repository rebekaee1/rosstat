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
  pure ops as the engine shape (31 specs, 12 ops as of 2026-05-22 — one op,
  `annual_inflation`, retained but unused; 11 active).
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
from app.data.view_model_families import iter_derived_specs as _iter_vmf_specs
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

    # CPI «К прошлому периоду»: г/г и к/к на накопленном уровне (с 2000-01).
    DerivedSpec("cpi-yoy", ("cpi",), ops.cpi_mom_yoy),
    DerivedSpec("cpi-food-yoy", ("cpi-food",), ops.cpi_mom_yoy),
    DerivedSpec("cpi-nonfood-yoy", ("cpi-nonfood",), ops.cpi_mom_yoy),
    DerivedSpec("cpi-services-yoy", ("cpi-services",), ops.cpi_mom_yoy),
    DerivedSpec("cpi-qoq", ("cpi",), ops.cpi_mom_qoq),
    DerivedSpec("cpi-food-qoq", ("cpi-food",), ops.cpi_mom_qoq),
    DerivedSpec("cpi-nonfood-qoq", ("cpi-nonfood",), ops.cpi_mom_qoq),
    DerivedSpec("cpi-services-qoq", ("cpi-services",), ops.cpi_mom_qoq),

    # CPI «Рост за период / Недельная»: накопление с 1-й недели месяца по текущую.
    DerivedSpec("cpi-period-weekly", ("inflation-weekly",), ops.weekly_mtd_in_calendar_month),
    DerivedSpec(
        "cpi-food-period-weekly",
        ("inflation-weekly-food",),
        ops.weekly_mtd_in_calendar_month,
    ),
    DerivedSpec(
        "cpi-nonfood-period-weekly",
        ("inflation-weekly-nonfood",),
        ops.weekly_mtd_in_calendar_month,
    ),
    DerivedSpec(
        "cpi-services-period-weekly",
        ("inflation-weekly-services",),
        ops.weekly_mtd_in_calendar_month,
    ),

    # CPI «Рост за период / Месячная»: произведение недель внутри календарного месяца.
    DerivedSpec("cpi-period-monthly", ("inflation-weekly",), ops.weekly_inflation_by_calendar_month),
    DerivedSpec(
        "cpi-food-period-monthly",
        ("inflation-weekly-food",),
        ops.weekly_inflation_by_calendar_month,
    ),
    DerivedSpec(
        "cpi-nonfood-period-monthly",
        ("inflation-weekly-nonfood",),
        ops.weekly_inflation_by_calendar_month,
    ),
    DerivedSpec(
        "cpi-services-period-monthly",
        ("inflation-weekly-services",),
        ops.weekly_inflation_by_calendar_month,
    ),

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
    # PPI quarter-over-quarter: индекс сводим к концу квартала, затем % к
    # предыдущему кварталу (группа «К прошлому периоду» на карточке ИЦП).
    DerivedSpec(
        "ppi-qoq", ("ppi",),
        partial(ops.period_over_period, granularity="quarter", method="last"),
    ),
    DerivedSpec("housing-yoy-primary", ("housing-price-primary",), ops.yoy),
    DerivedSpec("housing-yoy-secondary", ("housing-price-secondary",), ops.yoy),
    DerivedSpec("housing-qoq-primary", ("housing-price-primary",), ops.qoq),
    DerivedSpec("housing-qoq-secondary", ("housing-price-secondary",), ops.qoq),
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

    # C2 (звонок 2026-05-21): зарплата в индексной форме, базовый год = 2010 (= 100).
    # Сопоставимый формат с индексами цен на жильё (их база тоже ≈2010), что нужно
    # для корректного индекса доступности: оба индекса в одной базе → паритет в
    # окрестности 2010 ≈ 100. Базовое среднее берём из годового ряда зарплаты
    # (`wages-nominal-annual`, 2010 присутствует), потому что помесячный ряд
    # `wages-nominal` начинается позже базового года.
    DerivedSpec(
        "wages-index", ("wages-nominal", "wages-nominal-annual"),
        partial(ops.rebase_to_index_with_base, base_year=2010),
    ),

    # C1 (звонок 2026-05-21, уточнено v7): индекс доступности жилья =
    # wages-index / housing-price-secondary × 100, ПОМЕСЯЧНО. Цена квартальная →
    # forward-fill квартального индекса на месяцы внутри квартала. Значения >100 —
    # с базового года (2010) зарплаты росли быстрее цен на жильё (доступность ↑),
    # <100 — наоборот. Вторичный рынок (более широкий, менее зависим от госипотеки).
    DerivedSpec(
        "housing-affordability",
        ("housing-price-secondary", "wages-index"),
        ops.affordability_index_monthly,
    ),
    # Первичный рынок — та же формула, второй вариант карточки (variant-picker).
    DerivedSpec(
        "housing-affordability-primary",
        ("housing-price-primary", "wages-index"),
        ops.affordability_index_monthly,
    ),
]


# --- Config-driven derived specs (canonical view-mode families) --------------
#
# Каждый НЕ-нативный режим карточки из `app.data.view_model_families` становится
# derived sibling-рядом. Op'ы заданы пайплайном (op_name, kwargs); композиция
# единообразно выражает «кв/кв на суммах» и «г/г на месячных уровнях недельного
# ряда». Коды, уже объявленные выше вручную (легаси gdp-*/wages-yoy), оставляем
# как есть и здесь пропускаем — чтобы не регистрировать дважды. См. ADR-0001.


def _make_pipeline_op(pipeline: tuple[tuple[str, dict], ...]) -> DerivedOp:
    """Скомпоновать пайплайн (op_name, kwargs) в одну чистую Series->Series fn."""
    steps = [(getattr(ops, name), dict(kwargs)) for name, kwargs in pipeline]

    def _run(series: list[tuple[date, float]]) -> list[tuple[date, float]]:
        out = series
        for fn, kwargs in steps:
            out = fn(out, **kwargs)
        return out

    return _run


_existing_dst = {s.dst_code for s in DERIVED_SPECS}
for _dst, _src, _pipeline in _iter_vmf_specs():
    if _dst in _existing_dst:
        continue
    DERIVED_SPECS.append(DerivedSpec(_dst, (_src,), _make_pipeline_op(_pipeline)))
    _existing_dst.add(_dst)


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
