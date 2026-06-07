#!/usr/bin/env python3
"""Экспорт canonical view-mode конфига в JSON-зеркало для frontend-движка.

Источник истины — backend/app/data/view_model_families.py. Этот скрипт печатает
его frontend-проекцию в frontend/src/lib/viewModelFamilies.generated.json, чтобы
generic-движок (resolver/groups/picker) читал ровно те же семьи, режимы и коды,
что и backend-генератор derived-рядов. Запускать после правок конфига:

    python scripts/export-view-models.py

Файл .generated.json коммитится (детерминированный вывод), фронт его импортирует.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.data.view_model_families import to_frontend_families  # noqa: E402

OUT = ROOT / "frontend" / "src" / "lib" / "viewModelFamilies.generated.json"


def main() -> int:
    blob = to_frontend_families()
    OUT.write_text(
        json.dumps(blob, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(blob)} families -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
