#!/usr/bin/env python3
"""Аудит свежести публичных рядов платформы (круг 12), чистое чтение.

Те же правила, что у сторожа (`app/services/freshness.py`) и значка «Устарело»
на странице. Печатает таблицу «источник · рядов · устарело · причины · примеры».

    docker compose exec backend python /app/scripts/audit-freshness.py
    docker compose exec backend python /app/scripts/audit-freshness.py --toc   # + наборы Евростата, которых нет в оглавлении

Оглавление Евростата (`toc/txt`) содержит записи двух видов, `dataset` и `table`;
`tec*`, `tps*`, `ei_*` и часть других наборов идут как `table`. Сверка по одному виду
давала ложные «наборы, которых нет в оглавлении» (круг 12, первый аудит: 72 набора,
на деле таких 11).
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app")

from app.database import async_session  # noqa: E402
from app.services.freshness import CAUSE_LABELS, collect_freshness  # noqa: E402


async def toc_report() -> None:
    from sqlalchemy import func, select

    from app.models import WorldIndicator
    from app.services.world_eurostat_ingest import fetch_toc

    toc = await fetch_toc()
    async with async_session() as db:
        rows = (await db.execute(
            select(
                WorldIndicator.dataset_id,
                func.count(),
                func.count().filter(WorldIndicator.is_listed.is_(True)),
                func.max(WorldIndicator.history_end),
            ).where(WorldIndicator.provider == "eurostat").group_by(WorldIndicator.dataset_id)
        )).all()
    missing = sorted((r for r in rows if r[0] not in toc), key=lambda r: -r[2])
    print(f"В оглавлении Евростата {len(toc)} записей; наборов базы без записи: {len(missing)}")
    print("| набор | рядов | публичных | данные до |")
    print("|---|---:|---:|---|")
    for dataset_id, total, listed, end in missing:
        print(f"| {dataset_id} | {total} | {listed} | {end} |")
    print()


async def main() -> None:
    if "--toc" in sys.argv:
        await toc_report()
    async with async_session() as db:
        report = await collect_freshness(db)
    data = report.as_dict()
    print(f"Сводка на {data['today']}: просрочено {data['stale_series']} из {data['total_series']}")
    print("Причины:", ", ".join(f"{CAUSE_LABELS.get(k, k)}={v}" for k, v in data["stale_by_cause"].items()))
    print()
    print("| источник | рядов | устарело | причины | примеры |")
    print("|---|---:|---:|---|---|")
    for g in data["groups"]:
        causes = ", ".join(f"{CAUSE_LABELS.get(k, k)} {v}" for k, v in g["causes"].items())
        print(f"| {g['source']} | {g['total']} | {g['stale']} | {causes} | {', '.join(g['examples'])} |")


if __name__ == "__main__":
    asyncio.run(main())
