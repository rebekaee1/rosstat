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


async def _compute_wages_real(db: AsyncSession) -> int:
    """Реальная зарплата = (wages_t / wages_base) / (cpi_t / cpi_base) * 100.

    Берём первый доступный месяц за базу. Результат — индекс в % (100 = базовый уровень).
    """
    wages_q = await db.execute(select(Indicator).where(Indicator.code == "wages-nominal"))
    wages_ind = wages_q.scalar_one_or_none()
    cpi_q = await db.execute(select(Indicator).where(Indicator.code == "cpi"))
    cpi_ind = cpi_q.scalar_one_or_none()
    dst_q = await db.execute(select(Indicator).where(Indicator.code == "wages-real"))
    dst = dst_q.scalar_one_or_none()
    if not wages_ind or not cpi_ind or not dst:
        return 0

    w_data = (await db.execute(
        select(IndicatorData).where(IndicatorData.indicator_id == wages_ind.id).order_by(IndicatorData.date)
    )).scalars().all()
    c_data = (await db.execute(
        select(IndicatorData).where(IndicatorData.indicator_id == cpi_ind.id).order_by(IndicatorData.date)
    )).scalars().all()

    if len(w_data) < 2 or len(c_data) < 12:
        return 0

    wages_by_ym = {(r.date.year, r.date.month): float(r.value) for r in w_data}
    cpi_by_ym = {(r.date.year, r.date.month): float(r.value) for r in c_data}

    cpi_index: dict[tuple[int, int], float] = {}
    cumulative = 1.0
    sorted_cpi = sorted(cpi_by_ym.items())
    for (y, m), v in sorted_cpi:
        cumulative *= v / 100.0
        cpi_index[(y, m)] = cumulative

    sorted_wages = sorted(wages_by_ym.items())
    base_wage = sorted_wages[0][1]
    base_ym = sorted_wages[0][0]
    base_cpi = cpi_index.get(base_ym, 1.0)

    points: list[tuple[date, float]] = []
    for (y, m), wage in sorted_wages:
        ci = cpi_index.get((y, m))
        if ci is None:
            continue
        real_idx = round((wage / base_wage) / (ci / base_cpi) * 100, 2)
        points.append((date(y, m, 1), real_idx))

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


async def _compute_gdp_yoy(db: AsyncSession) -> int:
    """Рост ВВП year-over-year: (GDP_q / GDP_{q-4} - 1) * 100."""
    src_q = await db.execute(select(Indicator).where(Indicator.code == "gdp-nominal"))
    src = src_q.scalar_one_or_none()
    dst_q = await db.execute(select(Indicator).where(Indicator.code == "gdp-yoy"))
    dst = dst_q.scalar_one_or_none()
    if not src or not dst:
        return 0

    data = (await db.execute(
        select(IndicatorData).where(IndicatorData.indicator_id == src.id).order_by(IndicatorData.date)
    )).scalars().all()
    if len(data) < 5:
        return 0

    by_date: dict[date, float] = {r.date: float(r.value) for r in data}
    sorted_dates = sorted(by_date.keys())

    date_to_prev: dict[date, date] = {}
    for d in sorted_dates:
        prev_y = d.year - 1
        prev_d = date(prev_y, d.month, d.day)
        if prev_d in by_date:
            date_to_prev[d] = prev_d

    points: list[tuple[date, float]] = []
    for d, prev_d in sorted(date_to_prev.items()):
        growth = round((by_date[d] / by_date[prev_d] - 1) * 100, 2)
        points.append((d, growth))

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


async def _compute_gdp_qoq(db: AsyncSession) -> int:
    """Рост ВВП quarter-over-quarter: (GDP_q / GDP_{q-1} - 1) * 100."""
    src_q = await db.execute(select(Indicator).where(Indicator.code == "gdp-nominal"))
    src = src_q.scalar_one_or_none()
    dst_q = await db.execute(select(Indicator).where(Indicator.code == "gdp-qoq"))
    dst = dst_q.scalar_one_or_none()
    if not src or not dst:
        return 0

    data = (await db.execute(
        select(IndicatorData).where(IndicatorData.indicator_id == src.id).order_by(IndicatorData.date)
    )).scalars().all()
    if len(data) < 2:
        return 0

    sorted_data = sorted(data, key=lambda r: r.date)

    points: list[tuple[date, float]] = []
    for i in range(1, len(sorted_data)):
        cur = float(sorted_data[i].value)
        prev = float(sorted_data[i - 1].value)
        if prev > 0:
            growth = round((cur / prev - 1) * 100, 2)
            points.append((sorted_data[i].date, growth))

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


async def _compute_unemployment_quarterly(db: AsyncSession) -> int:
    """Безработица квартальная = среднее 3 месячных значений."""
    src_q = await db.execute(select(Indicator).where(Indicator.code == "unemployment"))
    src = src_q.scalar_one_or_none()
    dst_q = await db.execute(select(Indicator).where(Indicator.code == "unemployment-quarterly"))
    dst = dst_q.scalar_one_or_none()
    if not src or not dst:
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
                avg = round((v1 + v2 + v3) / 3, 2)
                points.append((date(y, qe, 1), avg))

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


async def _compute_unemployment_annual(db: AsyncSession) -> int:
    """Безработица среднегодовая = скользящее среднее 12 месяцев."""
    src_q = await db.execute(select(Indicator).where(Indicator.code == "unemployment"))
    src = src_q.scalar_one_or_none()
    dst_q = await db.execute(select(Indicator).where(Indicator.code == "unemployment-annual"))
    dst = dst_q.scalar_one_or_none()
    if not src or not dst:
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
            avg = round(sum(trailing) / 12, 2)
            points.append((date(y, m, 1), avg))

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


async def _compute_yoy_generic(db: AsyncSession, src_code: str, dst_code: str) -> int:
    """Year-over-year: (val_t / val_{t-4quarters or t-12months} - 1) * 100."""
    src_q = await db.execute(select(Indicator).where(Indicator.code == src_code))
    src = src_q.scalar_one_or_none()
    dst_q = await db.execute(select(Indicator).where(Indicator.code == dst_code))
    dst = dst_q.scalar_one_or_none()
    if not src or not dst:
        return 0

    data = (await db.execute(
        select(IndicatorData).where(IndicatorData.indicator_id == src.id).order_by(IndicatorData.date)
    )).scalars().all()
    if len(data) < 5:
        return 0

    by_date: dict[date, float] = {r.date: float(r.value) for r in data}
    sorted_dates = sorted(by_date.keys())

    points: list[tuple[date, float]] = []
    for d in sorted_dates:
        prev_d = date(d.year - 1, d.month, d.day)
        if prev_d in by_date and by_date[prev_d] > 0:
            growth = round((by_date[d] / by_date[prev_d] - 1) * 100, 2)
            points.append((d, growth))

    added = 0
    for d, v in points:
        stmt = pg_insert(IndicatorData).values(
            indicator_id=dst.id, date=d, value=v
        ).on_conflict_do_nothing(constraint="uq_indicator_date")
        result = await db.execute(stmt)
        if result.rowcount:
            added += 1
    if added:
        await db.flush()
    return added


async def _compute_current_account_yoy(db: AsyncSession) -> int:
    return await _compute_yoy_generic(db, "current-account", "current-account-yoy")


async def _compute_ipi_yoy(db: AsyncSession) -> int:
    return await _compute_yoy_generic(db, "ipi", "ipi-yoy")


calculation_engine.register("inflation-quarterly", ["cpi"], _compute_quarterly_inflation)
calculation_engine.register("inflation-annual", ["cpi"], _compute_annual_inflation)
calculation_engine.register("wages-real", ["wages-nominal", "cpi"], _compute_wages_real)
calculation_engine.register("gdp-yoy", ["gdp-nominal"], _compute_gdp_yoy)
calculation_engine.register("gdp-qoq", ["gdp-nominal"], _compute_gdp_qoq)
calculation_engine.register("unemployment-quarterly", ["unemployment"], _compute_unemployment_quarterly)
calculation_engine.register("unemployment-annual", ["unemployment"], _compute_unemployment_annual)
calculation_engine.register("current-account-yoy", ["current-account"], _compute_current_account_yoy)
calculation_engine.register("ipi-yoy", ["ipi"], _compute_ipi_yoy)
