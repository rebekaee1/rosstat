#!/usr/bin/env python3
"""Load reviewed BEA US/state catalog and complete official ZIP histories.

Examples::

    PYTHONPATH=. python scripts/load-world-bea-regional.py --archive SARPP --dry-run
    PYTHONPATH=. python scripts/load-world-bea-regional.py --archive SARPP
    PYTHONPATH=. python scripts/load-world-bea-regional.py --all
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("PYTHONPATH_ROOT", "/app"))

from app.services.world_bea_regional import (  # noqa: E402
    TABLES_BY_ARCHIVE, extract_catalog_points, fetch_archive_sync,
    ingest_bea_archive, load_catalog,
)
from app.services.world_subnational_ingest import load_subnational_passport  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def run(args: argparse.Namespace) -> int:
    archives = list(TABLES_BY_ARCHIVE) if args.all else [args.archive]
    catalog = load_catalog()
    state_fips = {f"{r.fips}000" for r in load_subnational_passport("us").regions}
    for archive in archives:
        source = args.archive_dir / f"fe-bea-{archive}.zip" if args.archive_dir else None
        payload = source.read_bytes() if source and source.is_file() else await asyncio.to_thread(fetch_archive_sync, archive)
        if args.dry_run:
            extracted = extract_catalog_points(archive, payload, catalog, state_fips)
            geos = sum(len(v) - 1 for v in extracted.values())
            points = sum(len(series) for v in extracted.values() for series in v.values())
            print(f"{archive}: series={len(extracted)} state_series={geos} points={points}")
            continue
        result = await ingest_bea_archive(archive, payload=payload, force=args.force)
        print(f"{archive}: {result}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    select = parser.add_mutually_exclusive_group(required=True)
    select.add_argument("--archive", choices=sorted(TABLES_BY_ARCHIVE))
    select.add_argument("--all", action="store_true")
    parser.add_argument("--archive-dir", type=Path, help="reuse official ZIPs from a local directory")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="replay even when ZIP hash is unchanged")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
