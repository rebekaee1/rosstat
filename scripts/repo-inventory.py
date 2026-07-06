#!/usr/bin/env python3
"""Детерминированная инвентаризация репозитория → docs/repo-inventory.md.

Проходит по дереву проекта (backend/, frontend/, docs/, scripts/, mcp/,
корневые конфиги), исключая мусор (.git/.venv/node_modules/__pycache__/dist/
build/*.lock/бинарники). Для каждого файла: путь, число строк, оценка токенов
(символы / 4). В конце — суммарно файлов и токенов + разбивка по верхним папкам.

Цель — объективная картина «что вообще есть в проекте», независимая от того,
что у агента сейчас в контексте. Только подсчёт, ничего не меняет.

Запуск:
    python scripts/repo-inventory.py            # пишет docs/repo-inventory.md
    python scripts/repo-inventory.py --stdout    # печатает в stdout, не пишет файл
"""
from __future__ import annotations

import datetime as _dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "repo-inventory.md"


def _git_tracked() -> list[Path] | None:
    """git-tracked + untracked-not-ignored файлы (детерминированно; авто-исключает
    gitignored скрэтч *.temp.txt и build-артефакты dist/; стабильно до и после
    коммита новых файлов). None — git недоступен."""
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

# Папки, которые целиком пропускаем (мусор / производное / venv).
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", "dist", "build", ".idea", ".vscode",
    ".cursor",  # служебные артефакты Cursor, не код проекта
}

# Расширения бинарников / производных, которые не считаем.
SKIP_SUFFIXES = {
    ".lock", ".ttf", ".woff", ".woff2", ".eot", ".png", ".ico", ".svg",
    ".pdf", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".zip",
    ".gz", ".xlsx", ".xls", ".csv", ".pyc", ".so", ".bin", ".db",
    ".sqlite", ".sqlite3", ".pem", ".crt",
}

# Точные имена файлов, которые пропускаем.
SKIP_NAMES = {"package-lock.json"}

# Сгенерированные нами артефакты — не считаем (иначе инвентарь считает сам себя
# и числа «дребезжат» между прогонами; это инструменты, не исходники проекта).
SKIP_RELPATHS = {
    "docs/repo-inventory.md", "docs/indicator-index.json",
    "docs/indicator-index.md", "docs/dead-code-report.md",
}


def _est_tokens(text: str) -> int:
    """Грубая оценка токенов: символы / 4 (как в задаче)."""
    return len(text) // 4


def iter_files() -> list[Path]:
    tracked = _git_tracked()
    candidates = tracked if tracked is not None else [
        p for p in ROOT.rglob("*") if p.is_file()
    ]
    out: list[Path] = []
    for path in candidates:
        if not path.is_file():
            continue
        parts = set(path.relative_to(ROOT).parts)
        if parts & SKIP_DIRS:
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if path.name in SKIP_NAMES:
            continue
        if str(path.relative_to(ROOT)) in SKIP_RELPATHS:
            continue
        out.append(path)
    return sorted(out, key=lambda p: str(p.relative_to(ROOT)))


def _top_group(rel: str) -> str:
    head = rel.split("/", 1)[0]
    return head if "/" in rel else "(root)"


def build() -> str:
    files = iter_files()
    rows = []
    total_lines = 0
    total_tokens = 0
    by_group: dict[str, list[int]] = {}
    for path in files:
        rel = str(path.relative_to(ROOT))
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            # бинарь, проскользнувший мимо фильтра — пропускаем
            continue
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        tokens = _est_tokens(text)
        rows.append((rel, lines, tokens))
        total_lines += lines
        total_tokens += tokens
        g = _top_group(rel)
        agg = by_group.setdefault(g, [0, 0, 0])
        agg[0] += 1
        agg[1] += lines
        agg[2] += tokens

    out: list[str] = []
    out.append("# Repo inventory — объективная карта файлов проекта")
    out.append("")
    out.append(
        "> Генерируется `scripts/repo-inventory.py`. НЕ редактировать руками. "
        "Токены оценены как символы/4. Исключены: "
        ".git/.venv/node_modules/__pycache__/dist/build, *.lock и бинарники."
    )
    out.append("")
    out.append(f"**Сгенерировано:** {_dt.date.today().isoformat()}")
    out.append("")
    out.append(f"**Файлов:** {len(rows)}  ·  **Строк:** {total_lines:,}  ·  "
               f"**Токенов (≈):** {total_tokens:,}".replace(",", " "))
    out.append("")
    out.append("## По верхним папкам")
    out.append("")
    out.append("| Папка | Файлов | Строк | Токенов (≈) |")
    out.append("|-------|-------:|------:|------------:|")
    for g in sorted(by_group):
        c, ln, tk = by_group[g]
        out.append(f"| `{g}` | {c} | {ln:,} | {tk:,} |".replace(",", " "))
    out.append("")
    out.append("## Все файлы (по убыванию токенов)")
    out.append("")
    out.append("| Файл | Строк | Токенов (≈) |")
    out.append("|------|------:|------------:|")
    for rel, lines, tokens in sorted(rows, key=lambda r: (-r[2], r[0])):
        out.append(f"| `{rel}` | {lines:,} | {tokens:,} |".replace(",", " "))
    out.append("")
    return "\n".join(out)


def main() -> int:
    md = build()
    if "--stdout" in sys.argv:
        print(md)
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(md, encoding="utf-8")
    # Короткая сводка в stdout для CI/человека.
    totals = next(
        (l for l in md.splitlines() if l.startswith("**Файлов:**")), ""
    )
    print(f"repo-inventory: wrote {OUT.relative_to(ROOT)}")
    print(totals)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
