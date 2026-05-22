#!/usr/bin/env python3
"""Backfill полного годового ряда `wages-nominal-annual` (1991 — последний полный год).

Источник 1991-2014 (immutable, ручной):
  `app.data.wages_historical.ANNUAL_NOMINAL_WAGES_RUB` — снимок Росстатовского
  архивного ряда «Среднемесячная номинальная начисленная заработная плата
  работников по полному кругу организаций». 1991-1997 деноминированы
  (поделены на 1000 в seed-файле), 1998-2014 в нынешних рублях.

Источник 2015 — настоящее (автоматический):
  Месячные точки `wages-nominal` из БД (parser `rosstat_labor`). Скрипт
  агрегирует их в годовые средние (mean из 12 значений) и аппендит к
  историческим точкам. Год считается полным только если в БД есть все
  12 месяцев — неполный 2026 пропускается до закрытия декабря.

Что делает:
- Берёт `SPEC.annual_table` (24 годовые точки 1991-2014).
- Подтягивает все monthly точки `wages-nominal` из БД, группирует по году,
  для каждого полного года (12 месяцев) считает среднее → одна точка
  на 1 января соответствующего года.
- Записывает оба набора одним `bulk_upsert` в `wages-nominal-annual`
  (идемпотентно по ADR-0002): повторный запуск с тем же набором точек —
  no-op; запуск после закрытия нового года добавляет одну точку.

Запуск:
    docker exec rosstat-backend-1 sh -c \\
        "cd /app && PYTHONPATH=/app python3 /app/scripts/backfill-wages-history.py"

После запуска `wages-nominal-annual` будет иметь годовой ряд с 1991-01 до
последнего закрытого года (например 1991..2025 = 35 точек на 2026-05).
`wages-nominal` (monthly) остаётся неизменным.

Trap «annual continuation требует ручного re-run» (CONTEXT.md): этот скрипт
не подключён к ETL — после закрытия нового года (например, январь 2027
после декабря 2026) надо прогнать вручную либо завести derived spec
`annual_mean` для автоматического продолжения. См. backlog → backlog «B2».
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "backend", Path("/app")):
    if (_candidate / "app" / "database.py").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from sqlalchemy import select  # noqa: E402

from app.data.wages_historical import ANCHOR_YEAR, SPEC  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models import Indicator, IndicatorData  # noqa: E402
from app.services.upsert import bulk_upsert  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_wages")

TARGET_CODE = "wages-nominal-annual"
SOURCE_CODE = "wages-nominal"


async def _load_monthly_by_year(session, source_indicator_id: int) -> dict[int, list[float]]:
    """Returns {year: [values per month]} from `wages-nominal` monthly series."""
    rows = (
        await session.execute(
            select(IndicatorData.date, IndicatorData.value).where(
                IndicatorData.indicator_id == source_indicator_id
            )
        )
    ).all()
    by_year: dict[int, list[float]] = defaultdict(list)
    for d, v in rows:
        by_year[d.year].append(float(v))
    return by_year


async def main() -> None:
    async with async_session() as session:
        ind = (
            await session.execute(
                select(Indicator).where(Indicator.code == TARGET_CODE)
            )
        ).scalar_one_or_none()
        if ind is None:
            log.error(
                "Indicator %s not found in DB — ensure seed_data has the annual sibling",
                TARGET_CODE,
            )
            return

        source = (
            await session.execute(
                select(Indicator).where(Indicator.code == SOURCE_CODE)
            )
        ).scalar_one_or_none()
        if source is None:
            log.error("Source indicator %s not found in DB", SOURCE_CODE)
            return

        # 1) Исторический хвост 1991-2014 из immutable seed.
        historical_rows = [
            (date(year, 1, 1), float(value))
            for year, value in sorted(SPEC.annual_table.items())
        ]
        log.info(
            "Historical 1991-2014: %d points (%s..%s)",
            len(historical_rows), historical_rows[0][0], historical_rows[-1][0],
        )

        # 2) Continuation 2015+: annual mean из monthly. Только полные годы
        #    (12 точек), неполный текущий год отбрасывается.
        monthly_by_year = await _load_monthly_by_year(session, source.id)
        continuation_rows: list[tuple[date, float]] = []
        skipped: list[tuple[int, int]] = []
        for year in sorted(y for y in monthly_by_year if y >= ANCHOR_YEAR):
            values = monthly_by_year[year]
            if len(values) < 12:
                skipped.append((year, len(values)))
                continue
            mean_value = round(sum(values) / len(values), 2)
            continuation_rows.append((date(year, 1, 1), mean_value))

        if continuation_rows:
            log.info(
                "Continuation %d-...: %d points (%s..%s) from %s monthly",
                ANCHOR_YEAR, len(continuation_rows),
                continuation_rows[0][0], continuation_rows[-1][0], SOURCE_CODE,
            )
        if skipped:
            log.info("Skipped incomplete years (need 12 monthly): %s", skipped)

        all_rows = historical_rows + continuation_rows
        if not all_rows:
            log.warning("No rows to upsert — aborting.")
            return

        stats = await bulk_upsert(session, ind.id, all_rows)
        await session.commit()
        log.info(
            "%s: bulk_upsert (new, updated)=%s | total prepared=%d",
            TARGET_CODE, stats, len(all_rows),
        )

        log.info(
            "DONE: %s annual range %s..%s (%d total points)",
            TARGET_CODE, all_rows[0][0], all_rows[-1][0], len(all_rows),
        )


if __name__ == "__main__":
    asyncio.run(main())
