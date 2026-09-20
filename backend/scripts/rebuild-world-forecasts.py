"""Локальный backfill quality-gated прогнозов world bounded context.

Прогресс пишется в stdout без буфера (python -u / logging.basicConfig force).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUNBUFFERED", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.world_forecast_pipeline import (  # noqa: E402
    WorldForecastCandidate,
    load_world_forecast_plan,
    parse_country_slugs,
    world_forecast_job,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rebuild quality-gated world forecasts (incremental by default).",
    )
    parser.add_argument(
        "--country",
        default=None,
        help="Comma-separated world_countries.slug filter (e.g. austria,germany).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max series after priority sort.")
    parser.add_argument("--force", action="store_true", help="Ignore fingerprint and retrain.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan (total / unchanged / to_train and first 20 rows), do not train.",
    )
    return parser


def _print_plan(
    candidates: list[WorldForecastCandidate],
    unchanged_ids: set[int],
) -> None:
    total = len(candidates)
    unchanged = sum(1 for row in candidates if row.id in unchanged_ids)
    to_train = total - unchanged
    print(
        f"PLAN total={total} unchanged={unchanged} to_train={to_train}",
        flush=True,
    )
    seen: list[str] = []
    for row in candidates:
        if row.country_slug not in seen:
            seen.append(row.country_slug)
    print("COUNTRY_ORDER " + ", ".join(seen[:24]), flush=True)
    print("FIRST_20", flush=True)
    for index, row in enumerate(candidates[:20], 1):
        action = "unchanged" if row.id in unchanged_ids else "train"
        print(
            f"{index:2d}. {row.country_slug} {row.code} {row.provider} "
            f"{row.frequency} {action}",
            flush=True,
        )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    args = _build_parser().parse_args()
    slugs = parse_country_slugs(args.country)
    if args.dry_run:
        candidates, unchanged_ids = await load_world_forecast_plan(
            country_slugs=slugs or None,
            limit=args.limit,
            force=args.force,
        )
        _print_plan(candidates, unchanged_ids)
        payload = {
            "advisory": 0,
            "errors": 0,
            "failed": 0,
            "lock_busy": False,
            "passed": 0,
            "selected": len(candidates),
            "skipped": 0,
            "to_train": len(candidates) - len(unchanged_ids),
            "unchanged": len(unchanged_ids),
        }
    else:
        summary = await world_forecast_job(
            country_slugs=slugs or None,
            limit=args.limit,
            force=args.force,
        )
        payload = summary.__dict__
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
