#!/usr/bin/env python3
"""Догрузка глубоких срезов Eurostat (une_rt_* age×unit) без полного каталога.

Запуск::

    docker compose exec backend python /app/scripts/load-world-deep-slices.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.core.cache import bump_namespaces  # noqa: E402
from app.data.eurostat_listing import DEEP_DATASET_SLICES  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models import WorldCountry  # noqa: E402
from app.services.eurostat_parser import (  # noqa: E402
    WORLD_COUNTRIES,
    fetch_deep_slices,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("load-world-deep-slices")


async def main() -> int:
    # load-world-eurostat module name on disk uses hyphens → import via runpy
    # Prefer direct import of helpers by path.
    import importlib.util
    from pathlib import Path

    path = Path("/app/scripts/load-world-eurostat.py")
    if not path.exists():
        path = Path(__file__).resolve().with_name("load-world-eurostat.py")
    spec = importlib.util.spec_from_file_location("load_world_eurostat", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    await mod.ensure_countries(set(WORLD_COUNTRIES.keys()))
    async with async_session() as db:
        rows = (await db.execute(select(WorldCountry))).scalars().all()
        country_ids = {c.code: c.id for c in rows}
        country_names = {c.code: c.name_ru for c in rows}
        for geo, meta in WORLD_COUNTRIES.items():
            slug = meta[0]
            for c in rows:
                if c.slug == slug:
                    country_ids.setdefault(geo, c.id)
                    country_names.setdefault(geo, c.name_ru)

    t0 = time.time()
    total_ind = 0
    total_pts = 0
    for ds_id in sorted(DEEP_DATASET_SLICES):
        log.info("fetching deep slices for %s …", ds_id)
        results = fetch_deep_slices(ds_id)
        for one in results:
            missing = set(one.series_by_geo) - set(country_ids)
            if missing:
                extra = await mod.ensure_countries(missing)
                country_ids.update(extra)
                for g in missing:
                    country_names[g] = WORLD_COUNTRIES.get(g, ("", g, g, "", 0))[1]
            n_ind, n_pts = await mod.persist_result(one, country_ids, country_names)
            total_ind += n_ind
            total_pts += n_pts
            age = (one.slice_ or {}).get("age")
            unit = one.unit or (one.slice_ or {}).get("unit")
            de_pts = len(one.series_by_geo.get("DE") or [])
            log.info(
                "  OK %s age=%s unit=%s geos=%d DE_pts=%d ind=%d pts=%d",
                ds_id,
                age,
                unit,
                len(one.series_by_geo),
                de_pts,
                n_ind,
                n_pts,
            )

    try:
        await bump_namespaces("world")
    except Exception as exc:  # noqa: BLE001
        log.warning("cache bump failed: %s", exc)

    log.info(
        "DONE in %.1fs | indicators upserted=%d points touched=%d",
        time.time() - t0,
        total_ind,
        total_pts,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
