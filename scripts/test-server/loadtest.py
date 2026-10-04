#!/usr/bin/env python3
"""Простая нагрузочная проверка витрины (stdlib only): набор URL × уровни параллелизма.

Запускать НА сервере против 127.0.0.1 (без задержки туннеля), только на тестовом стенде:
    python3 loadtest.py --base http://127.0.0.1 --seconds 40 --levels 2,4,8,16
Печатает по уровню: запросов/с, p50/p95/p99, доля ошибок (≥500 и сетевые) и 429. Параллельно можно снимать
`docker stats` (см. docs/research/capacity-measurement-2026-10-04.md). Не использовать на боевом сервере.
"""
import argparse
import itertools
import json
import statistics
import threading
import time
import urllib.error
import urllib.request

PAGES = [
    ("home_ssr", "/"),
    ("indicator_ssr", "/russia/indicator/key-rate"),
    ("indicator_year_ssr", "/russia/indicator/key-rate/2024"),
    ("country_ssr", "/germany"),
    ("world_rating_ssr", "/world/rating/gdp-usd"),
    ("api_indicators", "/api/v1/indicators"),
    ("api_world_countries", "/api/v1/world/countries"),
    ("api_search_cached", "/api/v1/search?q=%D0%B8%D0%BD%D1%84%D0%BB%D1%8F%D1%86%D0%B8%D1%8F&limit=50"),
    ("api_search_cold", None),   # уникальный запрос каждый раз: мера стоимости непопавшего в кэш поиска
    ("og_image", "/og/key-rate.png"),
]
COLD_QUERIES = ["население", "безработица", "ввп на душу", "дизель", "экспорт", "ставка", "курс", "цены", "доходы", "бюджет",
                "inflation", "gdp", "population", "unemployment", "exports", "interest", "wages", "debt"]


def fetch(url: str, headers: dict) -> tuple[int, float]:
    started = time.perf_counter()
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            response.read()
            return response.status, time.perf_counter() - started
    except urllib.error.HTTPError as error:
        return error.code, time.perf_counter() - started
    except Exception:
        return 0, time.perf_counter() - started


def run_level(base: str, level: int, seconds: float, headers: dict) -> dict:
    deadline = time.monotonic() + seconds
    results: dict[str, list[tuple[int, float]]] = {name: [] for name, _ in PAGES}
    lock = threading.Lock()
    counter = itertools.count()

    def worker(offset: int):
        index = offset
        while time.monotonic() < deadline:
            name, path = PAGES[index % len(PAGES)]
            index += level
            if path is None:
                from urllib.parse import quote
                query = COLD_QUERIES[next(counter) % len(COLD_QUERIES)] + f" {next(counter)}"
                path = f"/api/v1/search?q={quote(query)}&limit=50"
            status, took = fetch(base + path, headers)
            with lock:
                results[name].append((status, took))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(level)]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.monotonic() - started
    flat = [item for items in results.values() for item in items]
    times = sorted(took for _, took in flat)

    def pct(p):
        return round(times[min(len(times) - 1, int(len(times) * p))], 3) if times else None

    return {
        "level": level, "requests": len(flat), "rps": round(len(flat) / elapsed, 1),
        "p50_s": pct(0.5), "p95_s": pct(0.95), "p99_s": pct(0.99),
        "errors_5xx_or_network": sum(1 for status, _ in flat if status == 0 or status >= 500),
        "rate_limited_429": sum(1 for status, _ in flat if status == 429),
        "by_page_p50_s": {name: (round(statistics.median(took for _, took in items), 3) if items else None)
                          for name, items in results.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1")
    parser.add_argument("--seconds", type=float, default=40)
    parser.add_argument("--levels", default="2,4,8,16")
    parser.add_argument("--host", default="", help="заголовок Host (например ru-хост)")
    args = parser.parse_args()
    # Один человекоподобный UA и один Cookie-less клиент: цель — стоимость обработки, не обход антискрейпа.
    headers = {"User-Agent": "Mozilla/5.0 (loadtest; internal) AppleWebKit/537.36 Chrome/120 Safari/537.36", "Accept": "*/*"}
    if args.host:
        headers["Host"] = args.host
    for level in [int(x) for x in args.levels.split(",")]:
        print(json.dumps(run_level(args.base, level, args.seconds, headers), ensure_ascii=False), flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
