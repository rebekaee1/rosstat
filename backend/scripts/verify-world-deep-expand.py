#!/usr/bin/env python3
"""Пост-проверка авто-deep: сходимость срезов, имена, variants.

Пишет:
  /tmp/eurostat-deep-verify.txt
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import select, func

from app.data.eurostat_deep_expand import (
    EXPANDABLE_DIMS,
    is_expandable_dim,
    is_totalish,
    plan_dataset_slices,
)
from app.data.eurostat_dim_labels_ru import label_for_dim_member
from app.database import async_session
from app.models import WorldCountry, WorldIndicator

OUT = Path("/tmp/eurostat-deep-verify.txt")


async def main() -> None:
    async with async_session() as db:
        rows = (
            await db.execute(
                select(
                    WorldIndicator.dataset_id,
                    WorldIndicator.slice_json,
                    WorldIndicator.slice_hash,
                    WorldIndicator.name_ru,
                    WorldIndicator.is_listed,
                    WorldIndicator.code,
                    WorldCountry.slug,
                )
                .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
                .where(WorldIndicator.provider == "eurostat")
            )
        ).all()

    by_ds: dict[str, list] = defaultdict(list)
    for ds, sj, sh, name, listed, code, slug in rows:
        by_ds[(ds or "").lower()].append(
            {"sj": sj or {}, "hash": sh, "name": name or "", "listed": listed, "code": code, "slug": slug}
        )

    multi = {ds: items for ds, items in by_ds.items() if len({i["hash"] for i in items}) > 1}
    # naming issues among listed
    bad_names = []
    latin = []
    for ds, items in by_ds.items():
        for it in items:
            if not it["listed"]:
                continue
            name = it["name"]
            if any(ord(ch) < 128 and ch.isalpha() for ch in name) and any(
                w in name.lower() for w in ("total", "index", "rate", "number", "eurostat")
            ):
                latin.append((it["slug"], it["code"], name[:80]))
            # non-total dim without label in name
            for dim, val in (it["sj"] or {}).items():
                if not is_expandable_dim(dim):
                    continue
                if is_totalish(dim, str(val)):
                    continue
                lab = label_for_dim_member(dim, str(val))
                if lab and lab.lower() not in name.lower():
                    bad_names.append((it["slug"], it["code"], dim, val, name[:90]))
                    break
                if lab is None:
                    bad_names.append((it["slug"], it["code"], dim, val, "NO_LABEL|" + name[:70]))
                    break

    lines = [
        "# Eurostat deep-expand verification",
        f"datasets_total={len(by_ds)}",
        f"datasets_multi_slice={len(multi)}",
        f"indicators_total={len(rows)}",
        f"listed_name_mismatches={len(bad_names)}",
        f"listed_suspicious_latin={len(latin)}",
        "",
        "## Top multi-slice datasets",
    ]
    top = sorted(
        ((ds, len({i['hash'] for i in items})) for ds, items in multi.items()),
        key=lambda x: -x[1],
    )[:40]
    for ds, n in top:
        lines.append(f"  {ds}: {n} slices")

    lines.append("")
    lines.append("## Sample name mismatches (first 40)")
    for row in bad_names[:40]:
        lines.append("  " + " | ".join(map(str, row)))

    lines.append("")
    lines.append("## Sample latin/suspicious (first 20)")
    for row in latin[:20]:
        lines.append("  " + " | ".join(row))

    # spot-check plans for a few known
    lines.append("")
    lines.append("## Spot plan checks")
    for ds in ("ilc_di04", "une_rt_m", "ilc_di07", "demo_pjan"):
        try:
            plan = plan_dataset_slices(ds)
            lines.append(f"  {ds}: source={plan.source} specs={len(plan.specs)} skips={len(plan.skips)}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"  {ds}: ERROR {exc}")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.read_text())


if __name__ == "__main__":
    asyncio.run(main())
