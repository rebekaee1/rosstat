"""Локальный backfill всех quality-gated прогнозов world bounded context."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.world_forecast_pipeline import world_forecast_job


async def main() -> None:
    summary = await world_forecast_job()
    print(json.dumps(summary.__dict__, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
