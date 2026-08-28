#!/usr/bin/env python3
"""Загрузчик national-core паспорта страны → world_* таблицы.

Читает ``app/data/world_national_core/<country>.yaml``, для каждого ряда
вызывает WorldSourceAdapter.fetch_series и идемпотентно пишет
WorldIndicator / WorldDataPoint / WorldDatasetState. Eurostat-ряды той же
страны не удаляет и не переписывает (другой provider в identity).

Запуск (в контейнере backend, после синка файлов worktree в Europe-mount)::

    python /app/scripts/load-world-national.py --country ca
    python /app/scripts/load-world-national.py --country au
    python /app/scripts/load-world-national.py --country us
    python /app/scripts/load-world-national.py --country jp
    python /app/scripts/load-world-national.py --country kr
    python /app/scripts/load-world-national.py --country ca --dry-run
    python /app/scripts/load-world-national.py --country au --only cpi-all

Без Docker (worktree + локальная БД на :5434)::

    cd /Users/iprofi/tradingeconomics/rosstat-world-ui/backend
    PYTHONPATH=. RUSTATS_DATABASE_URL=postgresql+asyncpg://…@localhost:5434/…
        python scripts/load-world-national.py --country au
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.environ.get("PYTHONPATH_ROOT", "/app"))

from app.core.cache import bump_namespaces  # noqa: E402
from app.database import async_session  # noqa: E402
from app.services.world_national_ingest import (  # noqa: E402
    ingest_country,
    load_national_core_yaml,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("load-world-national")


async def run(args: argparse.Namespace) -> int:
    country = args.country.strip().lower()
    if args.dry_run:
        manifest = load_national_core_yaml(country)
        log.info(
            "DRY-RUN country=%s series=%d path=%s",
            manifest.country_code,
            len(manifest.series),
            manifest.path,
        )
        for spec in manifest.series:
            from app.services.world_national_ingest import (
                build_indicator_code,
                series_ref_from_spec,
            )

            code = build_indicator_code(manifest.country_code, spec.code_suffix)
            ref = series_ref_from_spec(spec, country_code=manifest.country_code)
            log.info(
                "  %s provider=%s dataset=%s series=%s freq=%s listed=%s hash=%s",
                code,
                spec.provider,
                spec.dataset_id,
                spec.series_id,
                spec.frequency,
                spec.is_listed,
                ref.slice_hash[:12],
            )
        return 0

    async with async_session() as db:
        async with db.begin():
            stats = await ingest_country(
                db,
                country,
                dry_run=False,
                only_suffix=args.only,
            )

    try:
        await bump_namespaces("world")
    except Exception as exc:  # noqa: BLE001
        log.warning("cache bump failed: %s", exc)

    log.info("=" * 60)
    log.info(
        "DONE country=%s ok=%d err=%d indicators=%d points_touched=%d",
        stats.country_code,
        stats.series_ok,
        stats.series_err,
        stats.indicators_upserted,
        stats.points_touched,
    )
    for res in stats.results:
        if res.error:
            log.info("  FAIL %s: %s", res.code, res.error)
        else:
            log.info(
                "  OK %s id=%s obs=%d touched=%d",
                res.code,
                res.indicator_id,
                res.observations,
                res.points_touched,
            )

    if stats.series_ok == 0:
        return 1
    return 0 if stats.series_err == 0 else 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--country",
        required=True,
        help="ISO country code / yaml stem (ca, au, …)",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Ingest a single code_suffix from the YAML (e.g. cpi-all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse YAML and print planned codes without DB/network",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
