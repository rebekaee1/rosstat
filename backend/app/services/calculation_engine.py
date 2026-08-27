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
  pure ops as the engine shape (33 hand-written specs, 11 ops as of 2026-06-24
  — +housing-annual-{primary,secondary} via december_to_december, созвон
  «ПРАВКИ ПЕРЕДЕЛ-2»; orphaned ops annual_inflation / affordability_index /
  rebase_to_index удалены в чистке 2026-06-24, все ops активны).
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
from app.data.wages_historical import ANNUAL_NOMINAL_WAGES_RUB as _ANNUAL_NOMINAL_WAGES_RUB
from app.models import Indicator, IndicatorData
from app.services import derived_ops as ops
from app.services.upsert import bulk_upsert, prune_indicator_dates_not_in

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

    # Справочные кросс-курсы ЕЦБ: фунт/доллар и доллар/юань из двух ног vs евро.
    DerivedSpec("gbp-usd", ("eur-usd", "gbp-eur"), ops.series_ratio),
    DerivedSpec("usd-cny", ("cny-eur", "eur-usd"), ops.series_ratio),

    # Годовой ряд зарплаты 1991+ = immutable исторический хвост (1991-2014,
    # Росстат-архив в `wages_historical.py`) + annual mean месячного ряда
    # (2015+). Заменяет ручной one-shot backfill-скрипт: движок продолжает
    # ряд сам при закрытии каждого года. ВАЖНО: объявлен ДО `wages-index`,
    # который читает 2010-базу из `wages-nominal-annual` (derived→derived;
    # движок исполняет specs по порядку списка, без топосорта).
    DerivedSpec(
        "wages-nominal-annual", ("wages-nominal",),
        partial(ops.annual_mean_with_prefix, prefix=_ANNUAL_NOMINAL_WAGES_RUB),
    ),

    # Г/г «по годам» зарплаты (1992+): yoy() матчит по date(year-1, month, day),
    # поэтому применённый прямо к annual-ряду `wages-nominal-annual` (1 точка/год,
    # 1 января) корректно даёт год-к-году без промежуточной месячной агрегации —
    # первая точка 1992 (1991 не с чем сравнивать). До этого «yoy-year» режим
    # карточки считался через period_avg(year)+yoy ПОВЕРХ помесячного wages-nominal
    # (2015+) — глубина обрывалась на 2016. Тот же trap и то же решение, что у
    # `avg-year` (override на deep-ряд), созвон «На правки 13» 2026-07-08.
    DerivedSpec("wages-nominal-annual-yoy", ("wages-nominal-annual",), ops.yoy),

    # GDP year-over-year and quarter-over-quarter growth (две раздельные
    # семьи: nominal — в текущих ценах, real — в постоянных ценах 2021 г.).
    DerivedSpec("gdp-yoy", ("gdp-nominal",), ops.yoy),
    DerivedSpec("gdp-qoq", ("gdp-nominal",), ops.qoq_adjacent),  # В-6: только смежные кварталы
    DerivedSpec("gdp-real-yoy", ("gdp-real",), ops.yoy),
    DerivedSpec("gdp-real-qoq", ("gdp-real",), ops.qoq_adjacent),

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
    # PPI month-over-month: % к предыдущему календарному месяцу (режим
    # «К прошлому периоду → М/м» на карточке ИЦП; прогноз — та же op поверх
    # месячного прогноза базы, как у ppi-qoq).
    DerivedSpec("ppi-mom", ("ppi",), ops.mom),
    DerivedSpec("housing-yoy-primary", ("housing-price-primary",), ops.yoy),
    DerivedSpec("housing-yoy-secondary", ("housing-price-secondary",), ops.yoy),
    # QoQ жилья — cadence-aware: ранняя история индекса цен годовая (1998-2014),
    # с 2015 квартальная. Обычный qoq() выдал бы «кв/кв» между годовыми точками
    # (годовой прирост под видом квартального, обрыв в 2015). qoq_adjacent
    # считает % только между соседними кварталами (G2-аудит 2026-07).
    DerivedSpec("housing-qoq-primary", ("housing-price-primary",), ops.qoq_adjacent),
    DerivedSpec("housing-qoq-secondary", ("housing-price-secondary",), ops.qoq_adjacent),
    # Г/г «по годам» (декабрь-к-декабрю на квартальном индексе уровня): одна
    # точка/год, режим «К прошлому периоду → Г/г» жилья — как inflation-annual
    # у ИПЦ. Квартальный yoy (housing-yoy-*) остаётся отдельным режимом
    # «К соответствующему периоду предыдущего года».
    DerivedSpec("housing-annual-primary", ("housing-price-primary",), ops.december_to_december),
    DerivedSpec("housing-annual-secondary", ("housing-price-secondary",), ops.december_to_december),
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
    DerivedSpec("exports-qoq", ("exports",), ops.qoq_adjacent),  # В-6
    DerivedSpec("imports-qoq", ("imports",), ops.qoq_adjacent),

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

    pruned = await prune_indicator_dates_not_in(db, dst_id, points)
    added, updated = await bulk_upsert(db, dst_id, points)
    if pruned:
        logger.info(
            "CalculationEngine: pruned %d stale date(s) for '%s'",
            pruned, spec.dst_code,
        )
    return added + updated + pruned


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

    def dependents_closure_topo(self, source_codes: list[str]) -> list[str]:
        """Транзитивное замыкание derived, зависящих от `source_codes`,
        в топологическом порядке (П-2, риск Р-1).

        В реестре есть цепочки derived-от-derived глубиной до 4 уровней
        (`wages-nominal-annual → wages-index → housing-affordability →
        housing-affordability-yoy-year`) — зависимые обязаны считаться ПОСЛЕ
        своих derived-источников, иначе возьмут stale-вход. Порядок внутри
        одного уровня детерминирован порядком регистрации.
        """
        dependents: dict[str, list[str]] = {}
        for dst, (srcs, _fn) in self._derived.items():
            for s in srcs:
                dependents.setdefault(s, []).append(dst)

        affected: set[str] = set()
        stack = list(source_codes)
        while stack:
            s = stack.pop()
            for dst in dependents.get(s, ()):
                if dst not in affected:
                    affected.add(dst)
                    stack.append(dst)

        # Kahn на подграфе affected; heap по индексу регистрации = детерминизм.
        import heapq

        order_index = {code: i for i, code in enumerate(self._derived)}
        indegree = {
            v: sum(1 for u in self._derived[v][0] if u in affected)
            for v in affected
        }
        ready = [(order_index[v], v) for v, d in indegree.items() if d == 0]
        heapq.heapify(ready)
        out: list[str] = []
        while ready:
            _, u = heapq.heappop(ready)
            out.append(u)
            for w in dependents.get(u, ()):
                if w in indegree:
                    indegree[w] -= 1
                    if indegree[w] == 0:
                        heapq.heappush(ready, (order_index[w], w))
        if len(out) < len(affected):
            # Цикл в спеках — конфигурационная ошибка; не теряем ряды.
            leftover = sorted(affected - set(out), key=order_index.get)
            logger.error(
                "CalculationEngine: cycle detected in derived specs, appending "
                "in registry order: %s", leftover,
            )
            out.extend(leftover)
        return out

    async def run_for_direct_dependents(
        self, db: AsyncSession, source_codes: list[str],
    ) -> list[str]:
        """Пересчитать derived, зависящие от `source_codes` (включая
        транзитивные уровни).

        Используется после ETL одного source (напр. бюджет Минфина), когда
        source-ряд укоротился (`replace_series`) и sibling-режимы должны
        потерять устаревшие даты, не дожидаясь дневного батча. С П-2
        реализация совпадает с `run_for_updated_sources`.
        """
        return await self.run_for_updated_sources(db, source_codes)

    async def run_for_updated_sources(self, db: AsyncSession, source_codes: list[str]) -> list[str]:
        """Пересчитать замыкание зависимых derived после ETL-батча (П-2).

        Семантика ADR-0002 (derived[t] всегда отражает текущее source[t])
        сохраняется дешевле, чем «пересчитай все 799 при любом изменении»:

        - Парсеры считают изменением И добавления, И in-place ревизии
          (`bulk_upsert` c WHERE value <> excluded.value возвращает точные
          added/updated; `run_etl_for_indicator` включает ревизованный source
          в updated_codes — П-3). Незатронутый source не порождает изменений
          derived по определению чистых op'ов.
        - Пересчёт идёт по транзитивному замыканию зависимости в
          топологическом порядке (`dependents_closure_topo`) — цепочки
          derived-от-derived получают свежие входы.
        - Полный прогон всего реестра остаётся за `scripts/rebuild-all-derived.py`
          (escape hatch) и seed-refresh (там source_codes = все источники,
          замыкание совпадает с полным реестром).

        Returns the list of derived codes whose stored values actually changed
        (and thus whose Redis cache was invalidated).
        """
        if not source_codes:
            return []
        todo = self.dependents_closure_topo(source_codes)
        logger.info(
            "CalculationEngine: %d source(s) → recomputing %d dependent derived",
            len(source_codes), len(todo),
        )
        updated: list[str] = []
        for code in todo:
            fn = self._derived[code][1]
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
