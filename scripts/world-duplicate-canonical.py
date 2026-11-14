#!/usr/bin/env python3
"""Пробный расчёт основной версии одинаковых рядов стран мира (14.11.2026), только чтение.

Тот же код, что ночная сборка sitemap (`world_canonical.build_duplicate_map`): сколько неосновных
карточек получат canonical на основную и уйдут из sitemap вместе с годовыми страницами, сколько
оставлено из-за показов в Search Console. Запуск: ``backend/.venv/bin/python
scripts/world-duplicate-canonical.py [--json путь]`` с ``RUSTATS_DATABASE_URL`` локальной копии.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def run() -> dict:
    from sqlalchemy import text

    from app.database import async_session
    from app.services import world_canonical as wc

    started = time.monotonic()
    async with async_session() as db:
        rows = await wc._load_rows(db)
        groups = wc.candidate_groups(rows)
        digests = await wc._digests(db, sorted({r.id for g in groups for r in g}))
        kept = await wc._searched(db)
        mapping = wc.resolve_map(groups, digests, kept)
        excluded = wc.excluded_pairs(mapping)
        by_id = {(r.slug, r.code): r for r in rows}
        year_pages = sum(
            (r.history_end.year - r.history_start.year + 1)
            for pair in excluded if (r := by_id.get(pair)) and r.history_start and r.history_end
        )
        identical = sum(1 for g in groups if len({digests.get(r.id) for r in g}) == 1)
        kept_hits = sum(
            1 for g in groups if len({digests.get(r.id) for r in g}) == 1
            for r in sorted(g, key=wc.primary_key)[1:] if (r.slug, r.code) in kept
        )
        searched_rows = (await db.execute(text("SELECT count(*) FROM gsc_page_daily"))).scalar()
    return mapping, {
        "candidate_groups": len(groups),
        "identical_groups": identical,
        "non_primary_cards": len(excluded),
        "non_primary_year_pages_estimate": year_pages,
        "kept_for_search_impressions": kept_hits,
        "gsc_page_rows": searched_rows,
        "seconds": round(time.monotonic() - started, 1),
    }


def wc_pairs(mapping: dict) -> list:
    return [(slug, code) for slug, codes in mapping.items() for code in codes]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--map-json", type=Path, help="записать сам список (как world-canonical.json генерации)")
    args = parser.parse_args()
    mapping, report = asyncio.run(run())
    if args.map_json:
        args.map_json.write_text(json.dumps({"pairs": len(wc_pairs(mapping)), "map": mapping}, ensure_ascii=False),
                                 encoding="utf-8")
    for key, value in report.items():
        print(f"{key}: {value}")
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
