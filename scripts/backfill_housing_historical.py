#!/usr/bin/env python3
"""One-shot backfill исторических Q4-точек 1998-2014 для housing-price-*.

Источник YoY%-таблицы: `app.data.housing_historical` (snapshot Росстатовских
архивных таблиц tab8.htm и tab9.htm, заморожены 10.02.2020). Backward chain
делается от anchor 2015-Q4 (известная точка в БД).

Что делает:
- Для каждой записи в `housing_historical.SPECS`:
  - Достаёт из БД точку 2015-Q4 как anchor.
  - Через `build_historical_levels()` строит словарь {year: Q4_level} для
    1998..2014.
  - Вставляет/обновляет через `bulk_upsert` (идемпотентно по ADR-0002).
- Каскадно ретрейнит `housing-yoy-{primary,secondary}` (derived_from_source),
  чтобы derived seria тоже отразила исторические Q4-YoY-точки.

Запуск:
    docker exec rosstat-backend-1 sh -c \
        "cd /app && PYTHONPATH=/app python3 /app/scripts/backfill_housing_historical.py"

Идемпотентно: повторный запуск без изменения seed-таблицы или anchor — no-op.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "backend", Path("/app")):
    if (_candidate / "app" / "database.py").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from sqlalchemy import select  # noqa: E402

from app.data.housing_historical import (  # noqa: E402
    ANCHOR_YEAR,
    SPECS,
    build_historical_levels,
)
from app.database import async_session  # noqa: E402
from app.models import Indicator, IndicatorData  # noqa: E402
from app.services.forecast_pipeline import retrain_indicator_forecast  # noqa: E402
from app.services.upsert import bulk_upsert  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_housing")


async def _backfill_one(session, spec) -> int:
    ind = (
        await session.execute(
            select(Indicator).where(Indicator.code == spec.indicator_code)
        )
    ).scalar_one()

    anchor_date = date(ANCHOR_YEAR, 12, 1)
    anchor_row = (
        await session.execute(
            select(IndicatorData).where(
                IndicatorData.indicator_id == ind.id,
                IndicatorData.date == anchor_date,
            )
        )
    ).scalar_one_or_none()
    if anchor_row is None:
        log.error("%s: anchor %s missing — skip", spec.indicator_code, anchor_date)
        return 0
    anchor_value = float(anchor_row.value)
    log.info("%s: anchor %s = %s", spec.indicator_code, anchor_date, anchor_value)

    levels = build_historical_levels(anchor_value, spec.yoy_table)
    rows = [(date(year, 12, 1), value) for year, value in levels.items()]
    log.info("%s: prepared %d historical Q4 points (%s..%s)",
             spec.indicator_code, len(rows), rows[0][0], rows[-1][0])

    stats = await bulk_upsert(session, ind.id, rows)
    await session.commit()
    log.info("%s: bulk_upsert (new, updated)=%s", spec.indicator_code, stats)

    # Cascade retrain derived (housing-yoy-*) — derived_from_source.
    derived_code = f"housing-yoy-{spec.indicator_code.split('-')[-1]}"
    derived_ind = (
        await session.execute(select(Indicator).where(Indicator.code == derived_code))
    ).scalar_one_or_none()
    if derived_ind is not None:
        log.info("%s: retrain %s (derived cascade)", spec.indicator_code, derived_code)
        await retrain_indicator_forecast(session, derived_ind)
        await session.commit()

    return len(rows)


async def main() -> None:
    async with async_session() as session:
        total = 0
        for spec in SPECS:
            n = await _backfill_one(session, spec)
            total += n
        log.info("DONE: backfilled %d historical points across %d indicators",
                 total, len(SPECS))


if __name__ == "__main__":
    asyncio.run(main())
