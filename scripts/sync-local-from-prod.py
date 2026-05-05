"""
One-shot utility: pull all data points from production /api into local DB.

Why: local Postgres bootstrapped from an outdated pg_dump and is missing
data that prod has been collecting since (12k+ points across 95
indicators as of 2026-05-05).

What it does:
1. Lists indicators from prod and local.
2. For each common code, fetches the full point series from prod via
   `GET /api/v1/indicators/{code}/data?limit=10000`.
3. Bulk-upserts into local DB (ON CONFLICT DO NOTHING — keeps any
   existing local points, only fills gaps).
4. Reports how many points were added per indicator.

Safe to re-run: idempotent. Does not delete anything. Does not touch
prod (read-only). Does not trigger any forecast retrain — caller can
optionally run scripts/rebuild-all-derived.py afterwards to refresh
derived series.
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parents[1] / "backend",
    Path("/app"),
]
for _p in _CANDIDATES:
    if (_p / "app" / "database.py").exists():
        sys.path.insert(0, str(_p))
        break

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session
from app.models import Indicator, IndicatorData


PROD_API = "https://forecasteconomy.com/api/v1"


def fetch_json(url: str, timeout: int = 30) -> dict | list:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def fetch_prod_indicators() -> list[dict]:
    return fetch_json(f"{PROD_API}/indicators?include_inactive=true")


def fetch_prod_series(code: str) -> list[dict]:
    payload = fetch_json(f"{PROD_API}/indicators/{code}/data?limit=10000")
    return payload.get("data", [])


async def upsert_series(code: str, points: list[dict]) -> tuple[int, int, str | None]:
    """Returns (added, total_in_payload, error_or_none)."""
    if not points:
        return 0, 0, None
    try:
        async with async_session() as db:
            ind_q = await db.execute(select(Indicator).where(Indicator.code == code))
            ind = ind_q.scalar_one_or_none()
            if not ind:
                return 0, len(points), f"local indicator '{code}' not found"

            rows = [
                {
                    "indicator_id": ind.id,
                    "date": date.fromisoformat(p["date"]),
                    "value": float(p["value"]),
                }
                for p in points
            ]
            stmt = pg_insert(IndicatorData).values(rows).on_conflict_do_nothing(
                constraint="uq_indicator_date"
            )
            result = await db.execute(stmt)
            await db.commit()
            return result.rowcount or 0, len(rows), None
    except Exception as e:
        return 0, len(points), f"{type(e).__name__}: {e}"


async def main() -> None:
    prod = fetch_prod_indicators()
    print(f"prod indicators: {len(prod)}")

    codes = sorted(i["code"] for i in prod)

    # Fetch all series in parallel (HTTP-bound)
    print("Fetching prod series in parallel (max_workers=12)…")
    with ThreadPoolExecutor(max_workers=12) as ex:
        series_by_code = dict(zip(codes, ex.map(fetch_prod_series, codes)))

    total_added = 0
    total_processed = 0
    failures: list[tuple[str, str]] = []

    print(f"\n{'CODE':<32} {'POINTS':>7} {'ADDED':>7}")
    print("-" * 50)
    for code in codes:
        points = series_by_code[code]
        added, n, err = await upsert_series(code, points)
        total_added += added
        total_processed += n
        if err:
            failures.append((code, err))
            print(f"  {code:<30} {n:>7} {'ERR':>7}  ({err})")
        elif added > 0:
            print(f"  {code:<30} {n:>7} {added:>7}")

    print(f"\n=== DONE ===")
    print(f"Indicators processed: {len(codes)}")
    print(f"Total points fetched from prod: {total_processed}")
    print(f"Total points inserted locally: {total_added}")
    if failures:
        print(f"\nFailures: {len(failures)}")
        for code, err in failures:
            print(f"  {code}: {err}")


if __name__ == "__main__":
    asyncio.run(main())
