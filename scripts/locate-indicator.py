#!/usr/bin/env python3
"""Доктор-скрипт: где встречается код индикатора.

Детерминированная grep-обёртка по дереву проекта (с исключением мусора).
Печатает все файлы и номера строк, где упоминается `<code>`, сгруппированные
по типу: seed / parser / derived / family / seo / variants / tests / other.

Первый шаг при любой задаче про индикатор — чтобы НЕ угадывать, где править.
Парный артефакт — docs/indicator-index.json (там ui_stack, источник, стратегия,
флаги shadowed_legacy).

Запуск:
    python scripts/locate-indicator.py cpi
    python scripts/locate-indicator.py exports-yoy --json
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", "dist", "build", ".idea", ".vscode", ".cursor",
}
SKIP_SUFFIXES = {
    ".lock", ".ttf", ".woff", ".woff2", ".eot", ".png", ".ico", ".svg",
    ".pdf", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".zip", ".gz",
    ".xlsx", ".xls", ".pyc", ".so", ".bin", ".db", ".sqlite", ".sqlite3",
    ".pem", ".crt",
}
SKIP_NAMES = {"package-lock.json"}

# Порядок групп вывода.
KIND_ORDER = ["seed", "parser", "derived", "family", "seo", "variants", "tests", "other"]
KIND_TITLE = {
    "seed": "SEED (backend/seed_data.py)",
    "parser": "ПАРСЕР (*_parser.py)",
    "derived": "DERIVED (calculation_engine / derived_ops / view_model_families)",
    "family": "FAMILY / UI-режимы (frontend *ViewMode* / viewModeEngine / GenericIndicatorView)",
    "seo": "SEO (indicator_seo / seo_content / seo_renderer)",
    "variants": "VARIANTS (indicatorVariants.js)",
    "tests": "ТЕСТЫ",
    "other": "ПРОЧЕЕ",
}


def _classify(rel: str) -> str:
    # Тесты — первыми: иначе test_calculation_engine.py / test_cbr_keyrate.py
    # ошибочно попали бы в derived/parser по совпадению имени.
    if rel.endswith(".test.js") or "/tests/" in rel or rel.startswith("backend/tests"):
        return "tests"
    if rel == "backend/seed_data.py":
        return "seed"
    if rel.endswith("_parser.py") or rel.endswith("/parser.py") or "cbr_keyrate.py" in rel:
        return "parser"
    if "calculation_engine" in rel or "derived_ops" in rel or "view_model_families" in rel:
        return "derived"
    if "indicator_seo" in rel or "seo_content" in rel or "seo_renderer" in rel:
        return "seo"
    if "indicatorVariants" in rel:
        return "variants"
    if "ViewMode" in rel or "viewModeFamilies" in rel or "viewModeEngine" in rel or "GenericIndicatorView" in rel:
        return "family"
    return "other"


def _git_tracked() -> list[Path] | None:
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        )
        others = subprocess.run(
            ["git", "ls-files", "-z", "--others", "--exclude-standard"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    rels = set(tracked.stdout.split("\0")) | set(others.stdout.split("\0"))
    return [ROOT / r for r in sorted(rels) if r]


def _text_files() -> list[Path]:
    tracked = _git_tracked()
    candidates = tracked if tracked is not None else [
        p for p in ROOT.rglob("*") if p.is_file()
    ]
    out: list[Path] = []
    for p in candidates:
        if not p.is_file():
            continue
        if set(p.relative_to(ROOT).parts) & SKIP_DIRS:
            continue
        if p.suffix.lower() in SKIP_SUFFIXES or p.name in SKIP_NAMES:
            continue
        out.append(p)
    return out


def locate(code: str) -> list[tuple[str, int, str, str]]:
    """Вернуть [(rel, lineno, kind, line_text), ...] — точные вхождения кода."""
    pattern = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(code)}(?![A-Za-z0-9_-])")
    hits: list[tuple[str, int, str, str]] = []
    for p in _text_files():
        rel = str(p.relative_to(ROOT))
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(lines, 1):
            if pattern.search(line):
                hits.append((rel, i, _classify(rel), line.strip()[:200]))
    return hits


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not args:
        print("usage: python scripts/locate-indicator.py <code> [--json]", file=sys.stderr)
        return 2
    code = args[0]
    if not re.fullmatch(r"[a-z0-9-]+", code):
        print(f"invalid code format: {code!r} (ожидается [a-z0-9-]+)", file=sys.stderr)
        return 2

    hits = locate(code)

    if as_json:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for rel, ln, kind, text in hits:
            grouped[kind].append({"file": rel, "line": ln, "text": text})
        print(json.dumps({
            "code": code,
            "total": len(hits),
            "by_kind": {k: grouped.get(k, []) for k in KIND_ORDER if grouped.get(k)},
        }, ensure_ascii=False, indent=2))
        return 0

    if not hits:
        print(f"'{code}': вхождений не найдено.")
        return 0

    by_kind: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for rel, ln, kind, text in hits:
        by_kind[kind].append((rel, ln, text))

    print(f"== {code} — {len(hits)} вхождений ==")
    print(f"(подсказка: ui_stack/источник/стратегия/флаги — в docs/indicator-index.json → запись '{code}')")
    for kind in KIND_ORDER:
        rows = by_kind.get(kind)
        if not rows:
            continue
        print(f"\n--- {KIND_TITLE[kind]} ({len(rows)}) ---")
        for rel, ln, text in rows:
            print(f"  {rel}:{ln}: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
