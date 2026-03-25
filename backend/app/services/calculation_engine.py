"""
Движок расчёта производных индикаторов.

Регистрирует функции-калькуляторы (Callable[[AsyncSession], Awaitable[int]])
и вызывается после ETL для пересчёта рядов, зависящих от обновлённых источников.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator, IndicatorData
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

DerivedFn = Callable[[AsyncSession], Awaitable[int]]


class CalculationEngine:
    """Реестр производных рядов и запуск пересчёта."""

    def __init__(self) -> None:
        self._derived: dict[str, tuple[list[str], DerivedFn]] = {}

    def register(self, code: str, sources: list[str], fn: DerivedFn) -> None:
        self._derived[code] = (sources, fn)

    async def run_for_updated_sources(self, db: AsyncSession, source_codes: list[str]) -> list[str]:
        """Пересчитать производные, зависящие от обновлённых источников. Возвращает коды обновлённых."""
        if not source_codes:
            return []
        updated: list[str] = []
        for code, (sources, fn) in self._derived.items():
            if any(s in source_codes for s in sources):
                try:
                    n = await fn(db)
                    if n > 0:
                        await cache_invalidate_indicator(code)
                        updated.append(code)
                    logger.info("CalculationEngine: %s → %d new points", code, n)
                except Exception:
                    logger.exception("CalculationEngine: failed to compute '%s'", code)
        return updated


calculation_engine = CalculationEngine()


async def _compute_quarterly_inflation(db: AsyncSession) -> int:
    """ИПЦ квартальный = произведение 3 месячных ИПЦ индексов → % к предыдущему кварталу."""
    src_q = await db.execute(select(Indicator).where(Indicator.code == "cpi"))
    src = src_q.scalar_one_or_none()
    if not src:
        return 0
    dst_q = await db.execute(select(Indicator).where(Indicator.code == "inflation-quarterly"))
    dst = dst_q.scalar_one_or_none()
    if not dst:
        return 0

    data_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == src.id)
        .order_by(IndicatorData.date)
    )
    rows = data_q.scalars().all()
    if len(rows) < 3:
        return 0

    by_ym: dict[tuple[int, int], float] = {}
    for r in rows:
        by_ym[(r.date.year, r.date.month)] = float(r.value)

    points: list[tuple[date, float]] = []
    quarter_ends = [3, 6, 9, 12]
    years = sorted({y for y, _ in by_ym})
    for y in years:
        for qe in quarter_ends:
            m1, m2, m3 = qe - 2, qe - 1, qe
            v1 = by_ym.get((y, m1))
            v2 = by_ym.get((y, m2))
            v3 = by_ym.get((y, m3))
            if v1 is not None and v2 is not None and v3 is not None:
                quarterly = (v1 / 100) * (v2 / 100) * (v3 / 100) * 100
                d = date(y, qe, 1)
                points.append((d, round(quarterly, 4)))

    added = 0
    for d, v in points:
        stmt = (
            pg_insert(IndicatorData)
            .values(indicator_id=dst.id, date=d, value=v)
            .on_conflict_do_nothing(constraint="uq_indicator_date")
        )
        result = await db.execute(stmt)
        if result.rowcount:
            added += 1
    if added:
        await db.flush()
    return added


async def _compute_annual_inflation(db: AsyncSession) -> int:
    """Годовая инфляция = произведение 12 месячных ИПЦ → % к аналогичному месяцу прошлого года."""
    src_q = await db.execute(select(Indicator).where(Indicator.code == "cpi"))
    src = src_q.scalar_one_or_none()
    if not src:
        return 0
    dst_q = await db.execute(select(Indicator).where(Indicator.code == "inflation-annual"))
    dst = dst_q.scalar_one_or_none()
    if not dst:
        return 0

    data_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == src.id)
        .order_by(IndicatorData.date)
    )
    rows = data_q.scalars().all()
    if len(rows) < 12:
        return 0

    by_ym: dict[tuple[int, int], float] = {}
    for r in rows:
        by_ym[(r.date.year, r.date.month)] = float(r.value)

    sorted_keys = sorted(by_ym.keys())
    points: list[tuple[date, float]] = []
    for y, m in sorted_keys:
        trailing = []
        for offset in range(12):
            mo = m - offset
            yr = y
            if mo <= 0:
                mo += 12
                yr -= 1
            val = by_ym.get((yr, mo))
            if val is not None:
                trailing.append(val)
        if len(trailing) == 12:
            product = 1.0
            for v in trailing:
                product *= v / 100
            annual = round(product * 100 - 100, 4)
            points.append((date(y, m, 1), annual))

    added = 0
    for d, v in points:
        stmt = (
            pg_insert(IndicatorData)
            .values(indicator_id=dst.id, date=d, value=v)
            .on_conflict_do_nothing(constraint="uq_indicator_date")
        )
        result = await db.execute(stmt)
        if result.rowcount:
            added += 1
    if added:
        await db.flush()
    return added


calculation_engine.register("inflation-quarterly", ["cpi"], _compute_quarterly_inflation)
calculation_engine.register("inflation-annual", ["cpi"], _compute_annual_inflation)
