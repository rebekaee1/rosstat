"""Разовый IndexNow-батч по всем публичным URL сайта.

Запуск (изнутри backend-контейнера):
    python /app/scripts/indexnow-ping-all.py                # все секции
    python /app/scripts/indexnow-ping-all.py --dry-run      # только посчитать
    python /app/scripts/indexnow-ping-all.py --sections core regional years

Секции — из site_urls.collect_url_sections: core, today, ratings, regions,
region-vs, calendar, years, regional-N (алиас `regional` включает все чанки).
Протокол: до 10 000 URL на POST, батчи шлёт indexnow.ping_urls автоматически.
"""

import argparse
import asyncio
import sys

sys.path.insert(0, "/app")

from app.database import async_session  # noqa: E402
from app.services.indexnow import ping_urls  # noqa: E402
from app.services.site_urls import collect_all_paths, collect_url_sections  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sections", nargs="*", default=None)
    args = parser.parse_args()

    async with async_session() as db:
        grouped = await collect_url_sections(db)
        paths = await collect_all_paths(db, sections=args.sections)

    print("Секции реестра URL:")
    for name, urls in grouped.items():
        marker = ""
        if args.sections is not None:
            included = name in args.sections or (
                name.startswith("regional-") and "regional" in args.sections
            )
            marker = "  → в пинг" if included else "  (пропущена)"
        print(f"  {name:14s} {len(urls):6d}{marker}")
    print(f"Итого к отправке: {len(paths)}")

    if args.dry_run:
        return 0
    if not paths:
        print("Нечего отправлять")
        return 1

    ok = await ping_urls(paths)
    print("IndexNow:", "все батчи приняты" if ok else "часть батчей отклонена (см. логи)")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
