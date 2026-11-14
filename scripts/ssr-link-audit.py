#!/usr/bin/env python3
"""Аудит внутренних ссылок серверных страниц (14.11.2026): куда ведут ссылки SSR на обоих хостах.

Обходит стартовые страницы каждого типа через настоящий nginx (локальный стенд, не боевой) и
проверяет каждую внутреннюю ссылку без следования переадресации: 200, переадресация (301/302/308 —
куда), 404/410, прочее; у 200 — свой ли canonical (ссылка на неосновную версию ряда или на страницу
с canonical на другой адрес тратит обход). Отчёт группирует ссылки по шаблону адреса и типу
страницы-источника — чтобы чинить место, где ссылка ставится, а не отдельный адрес.

Запуск (локальный стенд: nginx с конфигурацией сайта перед backend рабочего дерева):
``python3 scripts/ssr-link-audit.py --base http://127.0.0.1:8013 [--json путь] [--max-links 3000]``.
Только чтение; на боевом не запускать.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import urljoin, urlparse

HOSTS = {"en": "forecasteconomy.com", "ru": "ru.forecasteconomy.com"}
SEEDS = {
    "home": "/",
    "russia-card": "/russia/indicator/key-rate",
    "russia-year": "/russia/indicator/key-rate/2024",
    "russia-month": "/russia/indicator/cpi/2026-05",
    "russia-regions": "/russia/region",
    "russia-region": "/russia/region/moskva",
    "russia-today": "/russia/today",
    "world-rating": "/world/rating/unemployment-rate",
    "world-country": "/austria",
    "world-card": "/austria/indicator/at-weo-pcpipch",
    "world-year": "/austria/indicator/at-weo-pcpipch/2023",
    "world-vs": "/austria-vs-germany/population",
    "world-regions": "/united-states/regions",
    "world-region": "/united-states/region/alabama",
    "world-country-lfs": "/denmark",
    "world-card-lfs": "/denmark/indicator/dk-lfsq_urgaed-y15-74-total-t-pc",
}
_HREF = re.compile(r'<a\s[^>]*href="([^"#]+)"', re.I)
_CANONICAL = re.compile(r'<link rel="canonical" href="([^"]+)"')
_SKIP = ("/api/", "/og/", "/assets/", "/sitemap", "/compare?", "/login", "/register", "/account", "/embed/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(NoRedirect)


def fetch(base: str, host: str, path: str) -> tuple[int, str, str]:
    """(статус, Location, тело) без следования переадресации; разные адреса клиента — не упираться в лимиты."""
    ip = f"10.{random.randint(0, 250)}.{random.randint(0, 250)}.{random.randint(1, 250)}"
    req = urllib.request.Request(base + path, headers={
        "Host": host, "User-Agent": "Mozilla/5.0 (Macintosh) Chrome/131.0 Safari/537.36",
        "X-Forwarded-For": ip, "Accept": "text/html",
    })
    try:
        with _OPENER.open(req, timeout=90) as resp:
            return resp.status, "", resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, err.headers.get("Location", ""), ""
    except Exception as err:  # noqa: BLE001
        return 0, type(err).__name__, ""


def internal_links(html: str, host: str) -> list[str]:
    out = []
    for raw in _HREF.findall(html):
        href = unescape(raw).strip()
        parsed = urlparse(urljoin(f"https://{host}/", href))
        if parsed.hostname != host:
            continue
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        if not path.startswith("/") or any(path.startswith(s) for s in _SKIP):
            continue
        out.append(path)
    return out


def pattern(path: str) -> str:
    """Шаблон адреса для группировки: коды и годы — заглушками."""
    p = path.split("?")[0]
    p = re.sub(r"/\d{4}(-\d{2})?$", "/{period}", p)
    parts = p.strip("/").split("/")
    if len(parts) >= 3 and parts[1] == "indicator":
        parts[0], parts[2] = "{country}", "{code}"
    elif len(parts) >= 2 and parts[1] == "region":
        parts[0] = "{country}"
        if len(parts) > 2:
            parts[2] = "{region}"
        if len(parts) > 3:
            parts[3] = "{code}"
    elif len(parts) == 2 and "-vs-" in parts[0]:
        parts[0], parts[1] = "{a}-vs-{b}", "{concept}"
    return "/" + "/".join(parts)


def audit(base: str, max_links: int, workers: int = 6, duplicates: dict | None = None) -> dict:
    findings: dict = {"checked": 0, "by_status": Counter(), "problems": defaultdict(lambda: {"count": 0, "examples": []})}
    for loc, host in HOSTS.items():
        sources: dict[str, set[str]] = defaultdict(set)
        for kind, path in SEEDS.items():
            status, _loc, html = fetch(base, host, path)
            if status != 200:
                key = f"{loc} seed {kind}: HTTP {status}"
                findings["problems"][key]["count"] += 1
                continue
            for link in set(internal_links(html, host)):
                sources[link].add(kind)
        links = sorted(sources)[: max_links // 2]

        def check(link: str):
            status, location, html = fetch(base, host, link)
            canonical = ""
            if status == 200:
                m = _CANONICAL.search(html)
                canonical = m.group(1) if m else ""
            return link, status, location, canonical

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for link, status, location, canonical in pool.map(check, links):
                findings["checked"] += 1
                findings["by_status"][status] += 1
                problem = None
                parts = link.split("?")[0].strip("/").split("/")
                if (duplicates and len(parts) >= 3 and parts[1] == "indicator"
                        and parts[2] in duplicates.get(parts[0], {})):
                    problem = "неосновная версия ряда (world_canonical)"
                elif status in (301, 302, 307, 308):
                    problem = f"переадресация → {pattern(urlparse(location).path or location)}"
                elif status != 200:
                    problem = f"HTTP {status}"
                elif canonical and urlparse(canonical).path.rstrip("/") != link.split("?")[0].rstrip("/"):
                    problem = f"canonical на другой адрес ({pattern(urlparse(canonical).path)})"
                if problem:
                    for kind in sorted(sources[link]):
                        key = f"{loc} | {kind} → {pattern(link)} | {problem}"
                        entry = findings["problems"][key]
                        entry["count"] += 1
                        if len(entry["examples"]) < 3:
                            entry["examples"].append({"link": link, "location": location, "canonical": canonical})
    findings["by_status"] = dict(findings["by_status"])
    findings["problems"] = dict(sorted(findings["problems"].items(), key=lambda kv: -kv[1]["count"]))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="адрес локального nginx стенда, например http://127.0.0.1:8013")
    parser.add_argument("--max-links", type=int, default=3000)
    parser.add_argument("--json", type=str)
    parser.add_argument("--duplicate-map", type=str,
                        help="world-canonical.json (scripts/world-duplicate-canonical.py --map-json): ссылки на неосновные")
    args = parser.parse_args()
    duplicates = None
    if args.duplicate_map:
        with open(args.duplicate_map, encoding="utf-8") as fh:
            duplicates = json.load(fh).get("map", {})
    report = audit(args.base.rstrip("/"), args.max_links, duplicates=duplicates)
    print(f"проверено ссылок: {report['checked']}; статусы: {report['by_status']}")
    for key, entry in report["problems"].items():
        print(f"{entry['count']:5d}  {key}  e.g. {entry['examples'][:1]}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
