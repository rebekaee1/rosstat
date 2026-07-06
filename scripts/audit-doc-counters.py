#!/usr/bin/env python3
"""Guard против дрейфа счётчиков в документации (Д-8, CTO-аудит 2026-07-06).

Документы (README/CONTEXT/data_sources) называют конкретные числа: сколько
рядов в seed, сколько source-индикаторов, derived-спеков, ops, парсер-типов,
generic-семей. Числа правятся руками и систематически отстают от кода.

Скрипт вычисляет истинные значения ИЗ КОДА (import seed_data / engine /
registry) и сверяет с каждым вхождением известных фраз-паттернов в доках.
Расхождение = exit 1 со списком «файл:строка: фраза → ожидалось N».

Запуск:
    python scripts/audit-doc-counters.py          # проверка (для CI/check-all)
    python scripts/audit-doc-counters.py --print   # только показать истинные числа
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))


def true_counters() -> dict[str, int]:
    import inspect

    from seed_data import INDICATORS  # noqa: PLC0415
    from app.services.calculation_engine import DERIVED_SPECS  # noqa: PLC0415
    from app.data import view_model_families as vmf  # noqa: PLC0415
    from app.services.rosstat_cpi_parser import PARSER_REGISTRY  # noqa: PLC0415
    from app.services import derived_ops  # noqa: PLC0415

    generated = sum(1 for _ in vmf.iter_derived_specs())
    ops = sum(
        1
        for name, fn in vars(derived_ops).items()
        if callable(fn)
        and not name.startswith("_")
        and inspect.getmodule(fn) is derived_ops
    )
    dst = {s.dst_code for s in DERIVED_SPECS}
    codes = {i["code"] for i in INDICATORS}
    return {
        "rows": len(INDICATORS),
        "source": len(codes - dst),
        "specs": len(DERIVED_SPECS),
        "manual": len(DERIVED_SPECS) - generated,
        "generated": generated,
        "ops": ops,
        "parsers": len(PARSER_REGISTRY),
        "families": len(vmf.FAMILY_BY_BASE),
    }


# Фраза-паттерн (первая группа — число) → ключ истинного счётчика.
# Паттерны специально узкие: ловят только канонические формулировки доков.
PATTERNS: list[tuple[str, str]] = [
    (r"Source-индикаторы \((\d+)\)", "source"),
    (r"(\d+) source-индикатор", "source"),
    (r"\((\d+) source\)", "source"),
    (r"(\d+) парсер-тип", "parsers"),
    (r"(\d+) спеков", "specs"),
    (r"\*\*(\d+) entries\*\*", "specs"),
    (r"(\d+) derived \(через", "specs"),
    (r"и (\d+) derived", "specs"),
    (r"(\d+) ручных \+", "manual"),
    (r"(\d+) сгенерированных", "generated"),
    (r"(\d+) generic\)", "generated"),
    (r"(\d+) чистых ops", "ops"),
    (r"(\d+) публичных чистых функций", "ops"),
    (r"(\d+) generic view-mode family", "families"),
    (r"(\d+) generic-семь", "families"),
    (r"(\d+) рядов в seed", "rows"),
    (r"всего в seed (\d+) рядов", "rows"),
    (r"(\d+) рядов seed", "rows"),
]

DOCS = ["README.md", "CONTEXT.md", "docs/data_sources.md"]


def main() -> int:
    truth = true_counters()
    if "--print" in sys.argv:
        for k, v in truth.items():
            print(f"{k}: {v}")
        return 0

    errors: list[str] = []
    for rel in DOCS:
        path = ROOT / rel
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            for pattern, key in PATTERNS:
                for m in re.finditer(pattern, line):
                    got = int(m.group(1))
                    if got != truth[key]:
                        errors.append(
                            f"{rel}:{lineno}: «{m.group(0)}» — в коде "
                            f"{key}={truth[key]}"
                        )
    if errors:
        print("audit-doc-counters: счётчики в доках разошлись с кодом:",
              file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(
        "audit-doc-counters: OK "
        + " ".join(f"{k}={v}" for k, v in truth.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
