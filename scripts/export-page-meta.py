#!/usr/bin/env python3
"""Экспорт PAGE_META / CATEGORY_META / world SEO в JSON-зеркало для frontend.

Источник истины — backend (`seo_content.py`, `seo_world.py`). Скрипт пишет
`frontend/src/lib/pageMeta.generated.json`, чтобы React читал те же
title/description/h1, что SSR (ADR-0003).

    python scripts/export-page-meta.py          # перезаписать зеркало
    python scripts/export-page-meta.py --check  # упасть, если зеркало устарело
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.page_meta_export import build_page_meta_blob  # noqa: E402

OUT = ROOT / "frontend" / "src" / "lib" / "pageMeta.generated.json"


def _dumps(blob: dict) -> str:
    return json.dumps(blob, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Не писать файл: сравнить с диском и выйти 1 при расхождении",
    )
    args = parser.parse_args()
    blob = build_page_meta_blob()
    text = _dumps(blob)

    if args.check:
        if not OUT.exists():
            print(f"page-meta: missing {OUT.relative_to(ROOT)} — run export-page-meta.py", file=sys.stderr)
            return 1
        current = OUT.read_text(encoding="utf-8")
        if current != text:
            print(
                "page-meta: --check FAILED — pageMeta.generated.json расходится с "
                "seo_content.py / seo_world.py. Запустите: python scripts/export-page-meta.py",
                file=sys.stderr,
            )
            return 1
        print("page-meta: --check OK")
        return 0

    OUT.write_text(text, encoding="utf-8")
    print(
        f"Wrote {len(blob['pages'])} pages, {len(blob['categories'])} categories "
        f"-> {OUT.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
