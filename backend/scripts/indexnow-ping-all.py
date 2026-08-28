"""Разовый IndexNow-батч по секциям единого реестра URL.

Запуск (изнутри backend-контейнера):
    python /app/scripts/indexnow-ping-all.py                  # план подачи (dry-run)
    python /app/scripts/indexnow-ping-all.py --apply          # подать секции по умолчанию
    python /app/scripts/indexnow-ping-all.py --sections months,world-vs --apply
    python /app/scripts/indexnow-ping-all.py --sections world-years-1 --limit 10000 --apply

Источник URL — site_urls.collect_url_sections (единый реестр; порядок секций =
приоритет подачи). По умолчанию подаются все «мелкие» секции каталога:
всё, кроме чанков летних лендингов (regional-years-N, world-years-N) —
миллионный массив летних URL льётся только явно, посекционно с --limit и по
отдельному решению владельца.

Алиасы секций (как в collect_all_paths): ``regional`` → все regional-*,
``world`` → все world-* (включая world-years-N — перед --apply смотреть план).

Протокол IndexNow: ≤10 000 URL на POST (батчение посекционно), ретраи 429/5xx/
сетевых ошибок с экспоненциальной паузой и jitter (Retry-After уважается),
отчёт по кодам ответов на каждый батч и итог по прогону.
"""

import argparse
import asyncio
import logging
import random
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import async_session  # noqa: E402
from app.services.site_urls import collect_url_sections  # noqa: E402

logger = logging.getLogger("indexnow-ping-all")

# Лимит протокола IndexNow — 10 000 URL на один POST.
_BATCH_LIMIT = 10_000
# Ретраи 429/5xx/сети: 3 попытки, пауза 2/4/8 с (×jitter), Retry-After приоритетнее.
_RETRIES = 3
_BASE_PAUSE = 2.0
_PAUSE_CAP = 60.0

# Чанки летних лендингов (~1.6M URL) в дефолтный набор не входят.
_VOLATILE_PREFIXES = ("regional-years-", "world-years-")

_NAME_WIDTH = 22


def _matches(name: str, requested: set[str]) -> bool:
    return (
        name in requested
        or (name.startswith("regional-") and "regional" in requested)
        or (name.startswith("world-") and "world" in requested)
    )


def select_sections(
    grouped: dict[str, list], requested: list[str] | None
) -> tuple[list[str], list[str]]:
    """→ (выбранные секции в порядке реестра, неизвестные имена из --sections)."""
    names = list(grouped)
    if requested is None:
        return [n for n in names if not n.startswith(_VOLATILE_PREFIXES)], []
    req = set(requested)
    selected = [n for n in names if _matches(n, req)]
    unknown = [
        token for token in req if not any(_matches(n, {token}) for n in names)
    ]
    return selected, unknown


async def ping_section(
    client: httpx.AsyncClient, urls: list[str], *, base: str, host: str
) -> dict[int, int]:
    """Пнуть одну секцию батчами ≤10k. → число URL по кодам ответов (-1 = сеть)."""
    stats: dict[int, int] = {}
    for offset in range(0, len(urls), _BATCH_LIMIT):
        batch = urls[offset : offset + _BATCH_LIMIT]
        payload = {
            "host": host,
            "key": settings.indexnow_key,
            "keyLocation": f"{base}/{settings.indexnow_key}.txt",
            "urlList": batch,
        }
        for attempt in range(1, _RETRIES + 1):
            try:
                resp = await client.post(settings.indexnow_endpoint, json=payload)
            except httpx.HTTPError as exc:
                logger.warning(
                    "IndexNow: network error (attempt %d/%d): %s", attempt, _RETRIES, exc
                )
                if attempt == _RETRIES:
                    stats[-1] = stats.get(-1, 0) + len(batch)
                    break
                await asyncio.sleep(min(_PAUSE_CAP, _BASE_PAUSE * 2 ** (attempt - 1)))
                continue

            code = resp.status_code
            stats[code] = stats.get(code, 0) + len(batch)
            if code in (200, 202):
                break
            if code != 429 and not 500 <= code < 600:
                # Прочие 4xx — ретрай бессмыслен (ключ/хост/лимит payload).
                logger.warning(
                    "IndexNow: status %d for %d URL(s): %s",
                    code, len(batch), resp.text[:200],
                )
                break
            if attempt == _RETRIES:
                logger.warning(
                    "IndexNow: status %d persists after %d attempts (%d URL(s))",
                    code, _RETRIES, len(batch),
                )
                break

            retry_after = resp.headers.get("Retry-After", "")
            if retry_after.isdigit():
                pause = float(retry_after)
            else:
                pause = min(_PAUSE_CAP, _BASE_PAUSE * 2 ** (attempt - 1))
                if code == 429:
                    pause *= 1 + random.random() * 0.5
            await asyncio.sleep(max(0.5, min(_PAUSE_CAP, pause)))
    return stats


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true",
        help="реальная подача в IndexNow (по умолчанию — dry-run: только план)",
    )
    parser.add_argument(
        "--sections", nargs="*", default=None,
        help="имена секций реестра или алиасы regional/world; "
        "по умолчанию — все, кроме regional-years-N/world-years-N",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="обрезать каждую выбранную секцию до N URL",
    )
    parser.add_argument(
        "--origin", default=None,
        help="Absolute origin for urlList (default: RUSTATS_PUBLIC_BASE_URL). "
        "Use https://ru.forecasteconomy.com only after that host is live.",
    )
    parser.add_argument(
        "--host", default=None,
        help="IndexNow host field (default: hostname of --origin / public_host).",
    )
    args = parser.parse_args()

    async with async_session() as db:
        grouped = await collect_url_sections(db)

    req: list[str] | None = None
    if args.sections is not None:
        req = [
            token.strip()
            for chunk in args.sections
            for token in chunk.split(",")
            if token.strip()
        ]
    selected, unknown = select_sections(grouped, req)
    if unknown:
        print("Неизвестные секции: " + ", ".join(unknown))
        print(
            "Доступны: " + ", ".join(grouped)
            + " (+ алиасы regional, world — все секции с префиксом)"
        )
        return 1

    selected_set = set(selected)
    plan: list[tuple[str, list[str]]] = []
    for name, urls in grouped.items():
        if name not in selected_set:
            continue
        section_paths = [u.path for u in urls]
        if args.limit is not None:
            section_paths = section_paths[: args.limit]
        if section_paths:
            plan.append((name, section_paths))

    total = sum(len(paths_list) for _, paths_list in plan)
    batches = sum((len(p) + _BATCH_LIMIT - 1) // _BATCH_LIMIT for _, p in plan)
    print("Секции реестра URL:")
    for name, urls in grouped.items():
        if name in selected_set:
            marker = "  → в пинг"
        elif name.startswith(_VOLATILE_PREFIXES) and req is None:
            marker = "  (летние чанки — только с --sections)"
        else:
            marker = "  (пропущена)"
        print(f"  {name:{_NAME_WIDTH}s} {len(urls):7d}{marker}")
    print(f"Итого к отправке: {total} URL, {batches} батч(ей) ≤{_BATCH_LIMIT}")
    print(f"Режим: {'ПОДАЧА (--apply)' if args.apply else 'dry-run (подача — с --apply)'}")
    if args.origin or args.host:
        print(f"Origin: {args.origin or '(default public_origin)'}")
        print(f"Host:   {args.host or '(from origin)'}")

    if not args.apply:
        return 0
    if not plan:
        print("Нечего отправлять")
        return 1
    if not settings.indexnow_enabled or not settings.indexnow_key:
        print("IndexNow отключён (indexnow_enabled/indexnow_key) — подача невозможна")
        return 2

    base = (args.origin or settings.public_origin).rstrip("/")
    if args.host:
        ping_host = args.host.split(":", 1)[0].strip().lower()
    else:
        ping_host = urlparse(base).hostname or settings.public_host

    stats_total: dict[int, int] = {}
    async with httpx.AsyncClient(timeout=60) as client:
        for name, paths_list in plan:
            stats = await ping_section(client, paths_list, base=base, host=ping_host)
            summary = ", ".join(
                f"{code}: {count}" for code, count in sorted(stats.items())
            )
            print(f"  {name:{_NAME_WIDTH}s} {len(paths_list):7d}  [{summary}]")
            for code, count in stats.items():
                stats_total[code] = stats_total.get(code, 0) + count

    accepted = stats_total.get(200, 0) + stats_total.get(202, 0)
    rejected = total - accepted
    print(f"IndexNow итог: принято {accepted} из {total}")
    errors = {
        code: count
        for code, count in stats_total.items()
        if code not in (200, 202)
    }
    if errors:
        print(
            "Отклонено/ошибки: "
            + ", ".join(f"{code}: {count}" for code, count in sorted(errors.items()))
        )
    return 0 if not rejected else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
