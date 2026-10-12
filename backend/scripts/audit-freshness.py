#!/usr/bin/env python3
"""Аудит свежести публичных рядов платформы (круг 12), чистое чтение.

Те же правила, что у сторожа (`app/services/freshness.py`) и значка «Устарело»
на странице. Печатает таблицу «источник · рядов · устарело · причины · примеры».

    docker compose exec backend python /app/scripts/audit-freshness.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app")

from app.database import async_session  # noqa: E402
from app.services.freshness import CAUSE_LABELS, collect_freshness  # noqa: E402


async def main() -> None:
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
