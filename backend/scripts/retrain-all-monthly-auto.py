#!/usr/bin/env python3
"""Пересчёт monthly_auto прогнозов и каскад в derived siblings (sum-quarter/year и др.).

Запуск:
    docker compose exec backend python /app/scripts/retrain-all-monthly-auto.py
    docker compose exec backend python /app/scripts/retrain-all-monthly-auto.py --codes budget-revenue retail-trade
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent, Path("/app")):
    if (_candidate / "app" / "database.py").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from sqlalchemy import select

from app.database import async_session
from app.models import Indicator
from app.services.forecast_pipeline import retrain_indicator_forecast
from seed_data import MONTHLY_AUTO_FORECAST_CODES

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(codes: list[str]) -> int:
    failed: list[str] = []
    async with async_session() as db:
        for code in codes:
            ind = (
                await db.execute(select(Indicator).where(Indicator.code == code))
            ).scalar_one_or_none()
            if ind is None:
                logger.error("Indicator %s not found", code)
                failed.append(code)
                continue
            try:
                logger.info("Retrain %s …", code)
                await retrain_indicator_forecast(db, ind)
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("Retrain failed for %s", code)
                failed.append(code)

    if failed:
        logger.error("Failed (%d): %s", len(failed), ", ".join(failed))
        return 1
    logger.info("Done: %d source indicator(s)", len(codes))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codes",
        nargs="*",
        default=sorted(MONTHLY_AUTO_FORECAST_CODES),
        help="Source codes (default: all MONTHLY_AUTO_FORECAST_CODES)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.codes)))
