#!/usr/bin/env python3
"""Снять с листинга остановленные у источника дубли мировых рядов (круги 12–13).

Список наборов — `app/data/world_superseded.py` (HICP cind/cann/cmon → prc_hicp_minr, HICP fp →
prc_hicp_fpd, prc_ppp_ind → prc_ppp_ind_1: закрыты Евростатом, канон — набор-преемник). Скрипт трогает только
`is_listed` этих наборов и только если у страны есть живой листингованный канон
(иначе ряд остаётся, чтобы страница не исчезла без замены). По умолчанию —
сухой прогон; запись и сброс мировых кэшей — с ``--apply``. Идемпотентен.

    docker compose exec backend python /app/scripts/unlist-superseded-world.py          # покажет
    docker compose exec backend python /app/scripts/unlist-superseded-world.py --apply  # применит
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy import select

sys.path.insert(0, "/app")

from app.core.cache import bump_namespaces  # noqa: E402
from app.data.world_superseded import (  # noqa: E402
    SUPERSEDED_WORLD_DATASETS,
    live_superseded_canonical,
    superseded_target,
)
from app.database import async_session  # noqa: E402
from app.models import WorldIndicator  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("unlist-superseded")


async def run(apply: bool) -> int:
    changed = 0
    async with async_session() as db:
        rows = (
            await db.execute(
                select(WorldIndicator).where(
                    WorldIndicator.provider == "eurostat",
                    WorldIndicator.dataset_id.in_(list(SUPERSEDED_WORLD_DATASETS)),
                    WorldIndicator.is_listed.is_(True),
                )
            )
        ).scalars().all()
        for ind in rows:
            target = superseded_target(ind.dataset_id, ind.code, ind.slice_json, ind.unit)
            if target is None:
                continue
            canonical = await live_superseded_canonical(
                db, ind.country_id, ind.dataset_id, ind.code, ind.slice_json, ind.unit,
                ind.history_start,
            )
            if canonical is None:
                log.info("keep %s: нет живого канона %s (или он короче по истории)", ind.code, target[0])
                continue
            log.info("%s %s -> %s", "unlist" if apply else "would unlist", ind.code, target[0])
            if apply:
                ind.is_listed = False
            changed += 1
        if apply and changed:
            await db.commit()
    if apply and changed:
        await bump_namespaces("world", "world-catalog", "ssr-world")
    log.info("%s: %d", "unlisted" if apply else "candidates", changed)
    return changed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    asyncio.run(run(args.apply))
