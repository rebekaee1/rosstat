#!/usr/bin/env python3
"""Сводка «до → после» из JSON perf-ab.sh: python3 scripts/dev/perf-ab-report.py OUT_DIR [normal|human]. Медианы холодных прогонов."""
import json
import statistics
import sys
from pathlib import Path

out = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else "normal"
METRICS = [("fcp", "FCP"), ("lcp", "LCP"), ("speedIndex", "SI"), ("tbt", "TBT"), ("tti", "TTI"), ("revealAt", "SPA"), ("cls", "CLS"), ("requests", "запр."), ("transferKB", "КБ")]


def med(values):
    v = [x for x in values if x is not None]
    return statistics.median(v) if v else None


def load(variant):
    data = {}
    for f in sorted((out / mode).glob(f"{variant}__*.json")):
        _, lang, slug = f.stem.split("__", 2)
        d = json.loads(f.read_text())
        for g in d["results"]:
            runs = [r for r in g["runs"] if r["kind"] == "cold"]
            data[(lang, g["path"])] = runs
    return data


base, new = load("base"), load("new")


def fmt(a, b, key):
    if a is None and b is None:
        return "—"
    f = (lambda v: "—" if v is None else (f"{v:.2f}" if key == "cls" else str(int(round(v)))))
    if a is None or b is None:
        return f"{f(a)} → {f(b)}"
    return f"{f(a)} → {f(b)}"


print(f"| страница | " + " | ".join(label for _, label in METRICS) + " |")
print("|---|" + "---|" * len(METRICS))
for key in sorted(base):
    if key not in new:
        continue
    ra, rb = base[key], new[key]
    cells = []
    for m, _ in METRICS:
        a = med([r.get(m) for r in ra])
        b = med([r.get(m) for r in rb])
        # TTI: «—» если достигнут не во всех прогонах
        if m == "tti":
            na = sum(1 for r in ra if r.get(m) is not None)
            nb = sum(1 for r in rb if r.get(m) is not None)
            sa = "—" if a is None else str(int(a))
            sb = "—" if b is None else str(int(b))
            cells.append(f"{sa} ({na}/{len(ra)}) → {sb} ({nb}/{len(rb)})")
        else:
            cells.append(fmt(a, b, m))
    print(f"| {key[0]} {key[1]} | " + " | ".join(cells) + " |")
