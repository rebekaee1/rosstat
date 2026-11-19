#!/usr/bin/env python3
"""Применить расчистку гипотез Пульса по таблице решений (14.11.2026, app/services/hypotheses_triage.py).

Вход — решения.csv (14.11) или план JSON (19.11: hypotheses-plan-2026-11-19.json, действия close_true / close_false /
close_duplicate / close_obsolete / keep).

По умолчанию — только план (сколько закрыть, объединить, пропустить), база не меняется. Запись — только с --apply,
тогда же пишется журнал применённого (JSONL: id, действие, было/стало). Повторный запуск ничего не меняет.
Запускать на боевом — только по слову владельца:

    docker compose exec -T backend python /app/scripts/apply-hypotheses-triage.py /tmp/решения.csv
    docker compose exec -T backend python /app/scripts/apply-hypotheses-triage.py /tmp/решения.csv --apply \
        --journal /tmp/hypotheses-triage-applied.jsonl

План JSON копируется в контейнер так же (`docker compose cp … backend:/tmp/plan.json`), путь с суффиксом .json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/app")

from app.services.hypotheses_triage import apply_triage, read_decisions  # noqa: E402


async def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", type=Path, help="решения.csv или план .json")
    p.add_argument("--apply", action="store_true", help="записать в базу (без него - только план)")
    p.add_argument("--journal", type=Path, default=Path("hypotheses-triage-applied.jsonl"))
    args = p.parse_args(argv)

    from app.database import analytics_session

    decisions = read_decisions(args.csv)
    async with analytics_session() as db:
        result = await apply_triage(db, decisions, apply=args.apply)
    counts = Counter(c["action"] for c in result["changes"])
    mode = "ПРИМЕНЕНО" if args.apply else "ПЛАН (база не менялась; --apply для записи)"
    print(f"{mode}: закрыть подтверждёнными {counts['close_true']}, опровергнутыми {counts['close_false']}, "
          f"объединить {counts['merge']}, устаревшими {counts['close_obsolete']}; оставить {result['kept']}; пропущено {len(result['skipped'])}")
    for s in result["skipped"][:20]:
        print(f"  пропуск #{s['id']}: {s['why']}")
    if args.apply and result["changes"]:
        with open(args.journal, "a", encoding="utf-8") as f:
            for c in result["changes"]:
                f.write(json.dumps(c, ensure_ascii=False, default=str) + "\n")
        print(f"журнал: {args.journal} (+{len(result['changes'])})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
