#!/usr/bin/env python3
"""Эксперимент индексации по типам программных страниц (круг 13, SEO).

Нужен, чтобы владелец решал про годовые страницы по цифрам, а не по ощущению:
фиксированная выборка адресов по типам страниц, проверка в Google URL Inspection
в день 0, через 14 и через 30 дней, сравнение доли «в индексе» по типам.

    # 1. выбрать выборку (читает опубликованные файлы sitemap, БД и Google не трогает)
    docker compose exec -T scheduler python - sample --per-type 20 < backend/scripts/seo-index-experiment.py
    # 2. проверить выборку в Google (по 20 адресов за запрос; лимит Google 2000 в сутки)
    docker compose exec -T scheduler python - inspect < backend/scripts/seo-index-experiment.py
    # 3. сравнить проверки разных дней
    docker compose exec -T scheduler python - compare < backend/scripts/seo-index-experiment.py

Выборка и результаты лежат в Redis состояния (ключ ``seo:index-experiment``), 120 дней.
Типы: годы мира (world-years), годы регионов мира (world-region-years), годы
регионов России (regional-years), годы показателей России (years), сравнения стран
(world-vs), карточки показателей стран (world-indicators).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
from datetime import date

sys.path.insert(0, "/app")

KEY = "seo:index-experiment"
TTL_S = 120 * 24 * 3600
HOSTS = ("forecasteconomy.com", "ru.forecasteconomy.com")
# тип -> префикс шардов sitemap (имя без «sitemap-» и «.xml»)
TYPES = {
    "world-years": "world-years-",
    "world-region-years": "world-region-years-",
    "regional-years": "regional-years-",
    "russia-years": "years",
    "world-vs": "world-vs",
    "world-cards": "world-indicators-",
}
_LOC = re.compile(r"<loc>([^<]+)</loc>")


def pick_sample(shards: dict[str, list[str]], per_type: int, seed: int) -> dict[str, list[str]]:
    """По типам: случайные адреса из случайных шардов, поровну по двум хостам.

    ``shards`` — тип -> список путей всех его шардов (уже объединённый). Сид
    фиксирует выборку: повторный запуск даст тот же набор.
    """
    rng = random.Random(seed)
    out: dict[str, list[str]] = {}
    for typ, paths in sorted(shards.items()):
        unique = sorted(set(paths))
        rng.shuffle(unique)
        chosen = unique[:per_type]
        out[typ] = [
            f"https://{HOSTS[i % 2]}{path}" for i, path in enumerate(chosen)
        ]
    return out


def indexed_share(results: list[dict]) -> dict[str, tuple[int, int]]:
    """тип -> (в индексе, проверено)."""
    shares: dict[str, list[int]] = {}
    for item in results:
        cell = shares.setdefault(item["type"], [0, 0])
        cell[1] += 1
        cell[0] += 1 if item.get("indexed") else 0
    return {typ: (a, b) for typ, (a, b) in shares.items()}


def format_compare(history: dict[str, list[dict]]) -> str:
    days = sorted(history)
    if not days:
        return "Проверок ещё не было."
    types = sorted({item["type"] for day in days for item in history[day]})
    head = "тип".ljust(20) + "".join(day.ljust(16) for day in days)
    lines = [head]
    for typ in types:
        row = typ.ljust(20)
        for day in days:
            a, b = indexed_share(history[day]).get(typ, (0, 0))
            row += (f"{a}/{b} ({100 * a // b}%)" if b else "-").ljust(16)
        lines.append(row)
    return "\n".join(lines)


def _read_shard_paths(host: str, prefix: str, seed: int, max_shards: int = 12) -> list[str]:
    """Пути из случайных шардов типа (не больше ``max_shards`` файлов: прод не грузим)."""
    from html import unescape
    from urllib.parse import urlparse

    from app.services.sitemap_static import published_sections, section_file

    origin = f"https://{host}"
    names = [n for n in (published_sections(origin) or []) if n == prefix or (prefix.endswith("-") and n.startswith(prefix))]
    names = random.Random(seed).sample(names, min(max_shards, len(names)))
    paths: list[str] = []
    for name in names:
        file = section_file(name, origin)
        if file is None:
            continue
        for match in _LOC.finditer(file.read_text(encoding="utf-8")):
            parsed = urlparse(unescape(match.group(1)))
            paths.append(parsed.path)
    return paths


async def cmd_sample(per_type: int, seed: int) -> None:
    from app.core.cache import get_state_redis

    # Пути у хостов общие (sitemap строится один на оба): читаем файлы одного хоста.
    shards = {typ: _read_shard_paths(HOSTS[0], prefix, seed) for typ, prefix in TYPES.items()}
    sample = pick_sample(shards, per_type, seed)
    redis = await get_state_redis()
    await redis.hset(KEY, "sample", json.dumps(sample, ensure_ascii=False))
    await redis.expire(KEY, TTL_S)
    print({typ: len(urls) for typ, urls in sample.items()})


async def cmd_inspect() -> None:
    import httpx

    from app.core.cache import get_state_redis
    from app.services.gsc_client import GscClient, configured_site
    from app.services.seo_index_control import parse_inspection

    redis = await get_state_redis()
    raw = await redis.hget(KEY, "sample")
    if not raw:
        sys.exit("Сначала: sample")
    sample = json.loads(raw)
    flat = [(typ, url) for typ, urls in sample.items() for url in urls]
    results: list[dict] = []
    async with httpx.AsyncClient(timeout=60) as http:
        client = GscClient.from_settings(http)
        for start in range(0, len(flat), 20):
            batch = flat[start:start + 20]
            reports = await client.inspect_sample(configured_site(), [url for _typ, url in batch])
            for (typ, _url), report in zip(batch, reports, strict=True):
                parsed = parse_inspection(report)
                parsed["type"] = typ
                results.append(parsed)
    await redis.hset(KEY, date.today().isoformat(), json.dumps(results, ensure_ascii=False))
    await redis.expire(KEY, TTL_S)
    print(format_compare({date.today().isoformat(): results}))


async def cmd_compare() -> None:
    from app.core.cache import get_state_redis

    redis = await get_state_redis()
    raw = await redis.hgetall(KEY)
    history = {}
    for key, value in raw.items():
        key = key.decode() if isinstance(key, bytes) else key
        if key == "sample":
            continue
        history[key] = json.loads(value)
    print(format_compare(history))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--per-type", type=int, default=20)
    s.add_argument("--seed", type=int, default=13)
    sub.add_parser("inspect")
    sub.add_parser("compare")
    args = parser.parse_args()
    if args.cmd == "sample":
        asyncio.run(cmd_sample(args.per_type, args.seed))
    elif args.cmd == "inspect":
        asyncio.run(cmd_inspect())
    else:
        asyncio.run(cmd_compare())


if __name__ == "__main__":
    main()
