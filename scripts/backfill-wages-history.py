#!/usr/bin/env python3
"""One-shot backfill исторических годовых точек 1991-2014 для `wages-nominal`.

Источник: `app.data.wages_historical.ANNUAL_NOMINAL_WAGES_RUB` — снимок
Росстатовского архивного ряда «Среднемесячная номинальная начисленная
заработная плата работников по полному кругу организаций». Значения
1991-1997 уже деноминированы (поделены на 1000 в seed-файле), 1998-2014 —
в нынешних рублях.

Что делает:
- Берёт `SPEC.annual_table` (24 годовые точки 1991-2014).
- Каждую точку записывает в БД на 1 января соответствующего года.
- Через `bulk_upsert` (идемпотентно по ADR-0002): повторный запуск — no-op.
- Каскадно ретрейнит `wages-yoy` и `wages-index` (derived_from_source),
  чтобы derived'ы тоже увидели исторические точки.

Запуск:
    docker exec rosstat-backend-1 sh -c \
        "cd /app && PYTHONPATH=/app python3 /app/scripts/backfill-wages-history.py"

После запуска `wages-nominal` будет иметь:
- 24 годовых точки 1991-2014 (1 января каждого года).
- ~133 monthly точки 2015-01..2026-02 (текущий ряд).

Frontend chart автоматически растянет шкалу. Frequency пометки для
исторических точек не отдельной колонкой, а через `data_source='Росстат архив'`
(стандарт для historical-seed данных в `housing_historical`).
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

from app.data.wages_historical import SPEC  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models import Indicator  # noqa: E402
from app.services.forecast_pipeline import retrain_indicator_forecast  # noqa: E402
from app.services.upsert import bulk_upsert  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_wages")

DERIVED_TO_RETRAIN = ("wages-yoy", "wages-index", "wages-real")


async def main() -> None:
    async with async_session() as session:
        ind = (
            await session.execute(
                select(Indicator).where(Indicator.code == SPEC.indicator_code)
            )
        ).scalar_one_or_none()
        if ind is None:
            log.error("Indicator %s not found in DB", SPEC.indicator_code)
            return

        rows = [
            (date(year, 1, 1), float(value))
            for year, value in sorted(SPEC.annual_table.items())
        ]
        log.info(
            "%s: prepared %d historical annual points (%s..%s)",
            SPEC.indicator_code, len(rows), rows[0][0], rows[-1][0],
        )

        stats = await bulk_upsert(session, ind.id, rows)
        await session.commit()
        log.info(
            "%s: bulk_upsert (new, updated)=%s",
            SPEC.indicator_code, stats,
        )

        for derived_code in DERIVED_TO_RETRAIN:
            derived_ind = (
                await session.execute(
                    select(Indicator).where(Indicator.code == derived_code)
                )
            ).scalar_one_or_none()
            if derived_ind is not None:
                log.info(
                    "%s: retrain %s (derived cascade)",
                    SPEC.indicator_code, derived_code,
                )
                await retrain_indicator_forecast(session, derived_ind)
                await session.commit()

        log.info(
            "DONE: backfilled %d historical points for %s",
            len(rows), SPEC.indicator_code,
        )


if __name__ == "__main__":
    asyncio.run(main())
