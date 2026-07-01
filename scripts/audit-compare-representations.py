#!/usr/bin/env python3
"""Аудит режима сравнения: для каждого ЛИСТИРУЕМОГО индикатора резолвит
представления (level/pop/yoy) той же логикой, что frontend
`compareRepresentation.js`, и проверяет через API, что итоговый ряд НЕ пуст.

Находит «битые комбинации» — когда переключатель показывает представление, а
данных за ним нет (частый источник дефектов в комбинаторике сравнения).

Запуск: python3 scripts/audit-compare-representations.py
Требует поднятый backend на localhost:8000.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAMILIES = json.loads(
    (ROOT / "frontend/src/lib/viewModelFamilies.generated.json").read_text()
)


def _psql(sql: str) -> str:
    """Выполнить SQL в контейнере postgres, вернуть tab-separated вывод."""
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres",
         "psql", "-U", "rustats", "-d", "rustats", "-tA", "-F", "\t", "-c", sql],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0:
        print("psql error:", out.stderr, file=sys.stderr)
        sys.exit(1)
    return out.stdout


# Число точек по каждому коду + метаданные — одним запросом.
_COUNTS: dict[str, int] = {}
_META: dict[str, dict] = {}
for line in _psql(
    "SELECT i.code, i.is_listed, i.unit, i.frequency, count(d.id) "
    "FROM indicators i LEFT JOIN indicator_data d ON d.indicator_id=i.id "
    "GROUP BY i.code, i.is_listed, i.unit, i.frequency"
).splitlines():
    parts = line.split("\t")
    if len(parts) < 5:
        continue
    code, is_listed, unit, freq, cnt = parts
    _COUNTS[code] = int(cnt)
    _META[code] = {
        "is_listed": is_listed == "t",
        "unit": unit or None,
        "frequency": freq or None,
    }

CPI_CODES = {"cpi", "cpi-food", "cpi-nonfood", "cpi-services"}
HOUSING_CODES = {"housing-price-primary", "housing-price-secondary"}


def resolve(code: str, unit: str | None):
    """→ {level:{code,transform}, pop?:{...}, yoy?:{...}} — зеркало JS-резолвера."""
    if code in CPI_CODES:
        return {
            "level": {"code": code, "transform": "cpiCumulative"},
            "pop": {"code": code, "transform": "sub100"},
            "yoy": {"code": f"{code}-yoy", "transform": None},
        }
    if code == "ppi":
        return {
            "level": {"code": "ppi", "transform": None},
            "pop": {"code": "ppi", "transform": "mom"},
            "yoy": {"code": "ppi-yoy", "transform": None},
        }
    if code in HOUSING_CODES:
        sl = "secondary" if code.endswith("secondary") else "primary"
        return {
            "level": {"code": code, "transform": None},
            "pop": {"code": f"housing-qoq-{sl}", "transform": None},
            "yoy": {"code": f"housing-yoy-{sl}", "transform": None},
        }
    fam = FAMILIES.get(code)
    if fam:
        modes = fam["modes"]
        native = next((m for m in modes if m.get("isNative")), modes[0])
        pop = next((m for m in modes if m.get("group") == "pop"), None)
        yoy = next((m for m in modes if m.get("group") == "yoy"), None)
        out = {"level": {"code": native["code"], "transform": None}}
        if pop:
            out["pop"] = {"code": pop["code"], "transform": None}
        if yoy:
            out["yoy"] = {"code": yoy["code"], "transform": None}
        return out
    return {"level": {"code": code, "transform": None}}


def pts(code: str) -> int:
    return _COUNTS.get(code, -1)


def main() -> int:
    listed = sorted(c for c, m in _META.items() if m["is_listed"])
    print(f"Listed indicators: {len(listed)}\n")

    problems: list[str] = []
    for code in listed:
        reps = resolve(code, _META[code]["unit"])
        row = []
        for rep_id in ("level", "pop", "yoy"):
            spec = reps.get(rep_id)
            if not spec:
                row.append(f"{rep_id}:—")
                continue
            n = pts(spec["code"])
            tag = f"{rep_id}:{spec['code']}={n}"
            row.append(tag)
            if n == 0:
                problems.append(
                    f"EMPTY  {code:32} {rep_id:5} → {spec['code']} (0 points)"
                )
            elif n < 0:
                problems.append(
                    f"MISSING {code:31} {rep_id:5} → {spec['code']} (code not in DB)"
                )
            elif 0 < n < 5:
                problems.append(
                    f"THIN   {code:32} {rep_id:5} → {spec['code']} ({n} points)"
                )
        print(f"  {code:32} | " + " | ".join(row))

    print("\n=== PROBLEMS ===")
    if not problems:
        print("none — все представления всех листируемых индикаторов непусты")
    else:
        for p in problems:
            print(p)
    print(f"\nTotal problems: {len(problems)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
