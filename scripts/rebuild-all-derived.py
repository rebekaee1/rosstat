#!/usr/bin/env python3
"""One-shot full rebuild of every derived indicator.

When to run:
- Locally before deploying calc_engine semantic changes (ADR-0002), to preview
  exactly which derived values will change in production.
- After a manual SQL correction to a source series (per the sirot-friendly
  rule in CONTEXT.md, the engine doesn't auto-clean orphan derived points,
  but it WILL repopulate values for any (source, date) pair that still maps
  to a derived date).
- One-off catchup if you suspect historical drift between source and derived
  due to past silent revisions that the daily ETL never propagated.

What it does:
- Loads every DerivedSpec from `app.services.calculation_engine.DERIVED_SPECS`.
- For each spec, calls `_execute(db, spec)` directly (bypassing the
  source-codes filter that the live engine uses, which is irrelevant here:
  we explicitly want a full recompute).
- Reports `(added, updated, total)` per derived. `bulk_upsert` only writes
  values that actually differ, so a clean prod run prints all zeros.

Run from `backend/`:
    PYTHONPATH=. python ../scripts/rebuild-all-derived.py
or via Docker:
    docker compose exec backend python /app/scripts/rebuild-all-derived.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Allow running from project root: add backend/ to sys.path.
_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.cache import cache_invalidate_indicator  # noqa: E402
from app.database import async_session  # noqa: E402
from app.services.calculation_engine import DERIVED_SPECS, _execute  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("rebuild-all-derived")


async def main() -> int:
    total_changes = 0
    print(f"Rebuilding {len(DERIVED_SPECS)} derived series...\n")
    print(f"{'dst_code':<30} {'changes':>10}")
    print("-" * 42)
    changed_codes: list[str] = []
    async with async_session() as db:
        for spec in DERIVED_SPECS:
            try:
                n = await _execute(db, spec)
                total_changes += n
                if n > 0:
                    changed_codes.append(spec.dst_code)
                tag = "OK" if n == 0 else "CHANGED"
                print(f"{spec.dst_code:<30} {n:>10}  {tag}")
            except Exception as exc:
                print(f"{spec.dst_code:<30} {'ERROR':>10}  {exc}")
                logger.exception("Failed to rebuild %s", spec.dst_code)
        await db.commit()
    print("-" * 42)
    print(f"Total point changes across {len(DERIVED_SPECS)} derived: {total_changes}")

    if changed_codes:
        print(f"Invalidating Redis cache for {len(changed_codes)} changed series...")
        for code in changed_codes:
            await cache_invalidate_indicator(code)
        print("Cache invalidated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
