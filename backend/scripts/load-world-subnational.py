#!/usr/bin/env python3
"""Загрузчик субнационального паспорта → subnational_* таблицы (ADR-0014).

Читает ``app/data/world_subnational/<country>.yaml``, тянет официальные ряды
(FRED keyless CSV) и идемпотентно пишет регионы / показатели / точки.

Запуск::

    python scripts/load-world-subnational.py --country us
    python scripts/load-world-subnational.py --country us --only unemployment-rate
    python scripts/load-world-subnational.py --country us --dry-run

В контейнере backend: ``python /app/scripts/load-world-subnational.py --country us``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.environ.get("PYTHONPATH_ROOT", "/app"))

from app.core.cache import bump_namespaces  # noqa: E402
from app.services.world_subnational_ingest import (  # noqa: E402
    expand_series_template,
    ingest_country,
    load_subnational_passport,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("load-world-subnational")


async def run(args: argparse.Namespace) -> int:
    country = args.country.strip().lower()
    passport = load_subnational_passport(country)
    log.info(
        "passport country=%s slug=%s regions=%d indicators=%d path=%s",
        passport.country_code,
        passport.country_slug,
        len(passport.regions),
        len(passport.indicators),
        passport.path,
    )
    if args.dry_run:
        specs = passport.indicators
        if args.only:
            needle = args.only.strip().lower()
            specs = tuple(s for s in specs if s.code == needle)
        for spec in specs:
            sample = passport.regions[0]
            series_id = expand_series_template(
                spec.series_template, geo=sample.geo_code, fips=sample.fips,
            )
            log.info(
                "  %s freq=%s tmpl=%s sample=%s listed=%s",
                spec.code, spec.frequency, spec.series_template, series_id,
                spec.is_listed,
            )
        return 0

    reports = await ingest_country(country, only=args.only)
    loaded = [r for r in reports if r.status == "loaded"]
    skipped = [r for r in reports if r.status == "skipped"]
    errors = [r for r in reports if r.status == "error"]
    log.info("=" * 60)
    log.info(
        "DONE country=%s loaded=%d skipped=%d errors=%d",
        passport.country_code, len(loaded), len(skipped), len(errors),
    )
    by_code: dict[str, list] = {}
    for row in reports:
        by_code.setdefault(row.indicator, []).append(row)
    for code, rows in by_code.items():
        ok = sum(1 for r in rows if r.status == "loaded")
        skip = sum(1 for r in rows if r.status == "skipped")
        err = sum(1 for r in rows if r.status == "error")
        points = sum(r.points for r in rows)
        firsts = [r.first for r in rows if r.first]
        lasts = [r.last for r in rows if r.last]
        log.info(
            "  %s states=%d skipped=%d errors=%d points=%d history=%s..%s",
            code, ok, skip, err, points,
            min(firsts).isoformat() if firsts else "—",
            max(lasts).isoformat() if lasts else "—",
        )
    for row in errors[:20]:
        log.info("  FAIL %s/%s %s: %s", row.indicator, row.region, row.series_id, row.detail)
    try:
        await bump_namespaces("world", "ssr-world", "world-catalog")
    except Exception as exc:  # noqa: BLE001
        log.warning("cache bump failed: %s", exc)
    if errors and not loaded:
        return 1
    return 0 if not errors else 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", required=True, help="ISO / yaml stem (us)")
    parser.add_argument("--only", default=None, help="один код показателя")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
