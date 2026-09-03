#!/usr/bin/env python3
"""Снимок счётчиков sitemap с прода или локального /sitemap-stats.json.

Пишет docs/site-inventory.json — живая цифра для агентов вместо хроники
AGENTS.md. Запуск:

    python scripts/sitemap-inventory.py                 # localhost
    python scripts/sitemap-inventory.py --url https://forecasteconomy.com/sitemap-stats.json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "site-inventory.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:3000/sitemap-stats.json",
        help="URL sitemap-stats.json",
    )
    args = parser.parse_args()
    try:
        with urllib.request.urlopen(args.url, timeout=20) as resp:
            stats = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"sitemap-inventory: не прочитал {args.url}: {exc}", file=sys.stderr)
        return 1
    total = int(stats.get("urls_total") or stats.get("url_count") or stats.get("urls") or 0)
    if not total and isinstance(stats.get("sections"), dict):
        total = sum(int(v or 0) for v in stats["sections"].values())
    payload = {
        "as_of": date.today().isoformat(),
        "source": args.url,
        "note": "Живые цифры после ночной сборки. Хроника AGENTS.md не источник.",
        "sitemap_urls": total,
        "raw": {k: stats[k] for k in stats if k != "urls"},
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} sitemap_urls={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
