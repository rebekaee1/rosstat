#!/usr/bin/env python3
"""Страж контекста аналитика Пульса (14.11.2026): предупреждение, не падение.

Если в диапазоне <база>..HEAD есть коммиты, меняющие счёт метрик (сессионизация и витрины аналитики, оценка робота,
сводка роботов, классы роботов в nginx, sitemap и правила индексации), а в backend/app/data/pulse_context.yaml нет
записи с датой не раньше даты базы или с `commit` одного из этих коммитов — печатает предупреждение: аналитик
иначе назовёт смену счёта обвалом. Выход всегда 0.

  scripts/check-pulse-context.py [база]   # по умолчанию merge-base с origin/main (или main)
Перед выпуском: база = SHA на боевом.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTEXT = ROOT / "backend/app/data/pulse_context.yaml"
METRIC_PATHS = (
    "backend/app/tasks/analytics_rollups.py",
    "backend/app/services/analytics_marts.py",
    "backend/app/services/admin_bi.py",
    "backend/app/services/bot_score.py",
    "backend/app/services/bot_traffic.py",
    "backend/app/services/pulse.py",
    "frontend/nginx.conf",
    "backend/app/services/index_policy.py",
    "backend/app/services/sitemap_priority.py",
    "backend/app/services/sitemap_static.py",
    "backend/app/api/sitemap.py",
)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def default_base() -> str:
    for ref in ("origin/main", "main"):
        try:
            return git("merge-base", "HEAD", ref)
        except subprocess.CalledProcessError:
            continue
    return "HEAD"


def main(argv: list[str]) -> int:
    import yaml

    base = argv[1] if len(argv) > 1 else default_base()
    try:
        commits = git("log", "--format=%h", f"{base}..HEAD", "--", *METRIC_PATHS).split()
        base_day = date.fromisoformat(git("show", "-s", "--format=%cs", base))
    except subprocess.CalledProcessError as exc:
        print(f"pulse-context: проверка пропущена ({exc})")
        return 0
    if not commits:
        print("pulse-context: изменений счёта метрик нет")
        return 0
    try:
        entries = (yaml.safe_load(CONTEXT.read_text(encoding="utf-8")) or {}).get("entries") or []
    except FileNotFoundError:
        entries = []
    covered = [
        e for e in entries
        if (str(e.get("date", "")) >= base_day.isoformat())
        or any(str(e.get("commit") or "-").startswith(c[:7]) or c.startswith(str(e.get("commit") or "-")[:7])
               for c in commits)
    ]
    if covered:
        print(f"pulse-context: изменений счёта метрик {len(commits)}, записей в контексте за период {len(covered)} - ок")
        return 0
    print(f"ВНИМАНИЕ pulse-context: {len(commits)} коммит(ов) меняют счёт метрик ({', '.join(commits[:8])}), а в "
          f"backend/app/data/pulse_context.yaml нет записи с датой не раньше {base_day} - добавьте, что ждать в цифрах.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
