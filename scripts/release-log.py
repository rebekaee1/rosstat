#!/usr/bin/env python3
"""Журнал выпусков для аналитика Пульса (14.11.2026). Вызывает scripts/deploy.sh перед сборкой образа.

Пишет backend/app/data/release_log.json (в .gitignore, попадает в образ backend через COPY): последние MAX_RELEASES
выпусков — короткий SHA, дата (МСК) и заголовки коммитов между прошлым и новым выпуском. Только заголовки: без тел
коммитов, авторов и почт. Служебные коммиты (одобрение выпуска, слияния, docs(knowledge) — рецензии и карты) отбрасываются. Не больше MAX_LINES строк на
выпуск, остаток — числом. Ошибка скрипта не должна ронять выпуск: deploy.sh вызывает его с `|| echo WARN`.

  scripts/release-log.py <прошлый SHA> <новый SHA> [путь к файлу]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_RELEASES = 6
MAX_LINES = 15
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "backend/app/data/release_log.json"
_SKIP = re.compile(r"^(?:chore\(deploy\): одобрить|docs\(knowledge\)|merge[:( ]|Merge )", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def subjects(prev: str, new: str) -> list[str]:
    out = subprocess.run(["git", "log", "--no-merges", "--format=%h %s", f"{prev}..{new}"],
                         check=True, capture_output=True, text=True).stdout
    lines = []
    for line in out.splitlines():
        sha, _, subject = line.partition(" ")
        if not subject or _SKIP.search(subject):
            continue
        lines.append(f"{sha[:8]} {_EMAIL.sub('[почта]', subject)[:160]}")
    return lines


def update(path: Path, prev: str, new: str, today: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        releases = [r for r in data.get("releases", []) if isinstance(r, dict)]
    except (FileNotFoundError, ValueError, AttributeError):
        releases = []
    lines = subjects(prev, new)
    short = subprocess.run(["git", "rev-parse", "--short=8", new], check=True, capture_output=True,
                           text=True).stdout.strip()
    releases = [r for r in releases if r.get("sha") != short]
    releases.append({"sha": short, "date": today, "lines": lines[:MAX_LINES], "more": max(0, len(lines) - MAX_LINES)})
    data = {"releases": releases[-MAX_RELEASES:]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[3]) if len(argv) > 3 else DEFAULT_PATH
    today = (datetime.now(timezone.utc) + timedelta(hours=3)).date().isoformat()
    data = update(path, argv[1], argv[2], today)
    last = data["releases"][-1]
    print(f"release-log: {last['sha']} {last['date']}, строк {len(last['lines'])} (+{last['more']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
