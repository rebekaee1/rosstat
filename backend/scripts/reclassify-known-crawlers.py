"""Repair known crawler flags only; default dry-run. Dates are MSK, until exclusive.

python scripts/reclassify-known-crawlers.py --since 2026-09-01 --until 2026-09-10
Add --apply only after reviewing counts. Does not send alerts or rebuild sessions.
"""
import argparse
import asyncio
from datetime import date, timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import analytics_session  # noqa: E402
from app.services.analytics_repair import reclassify_known_crawlers_day  # noqa: E402


async def main(args):
    if not 0 < (args.until - args.since).days <= 62:
        raise ValueError("request 1–62 MSK days; until is exclusive")
    day = args.since
    while day < args.until:
        async with analytics_session() as db:
            print(json.dumps(await reclassify_known_crawlers_day(db, day, apply=args.apply)), flush=True)
        day += timedelta(days=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True, type=date.fromisoformat)
    parser.add_argument("--until", required=True, type=date.fromisoformat)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args()))
