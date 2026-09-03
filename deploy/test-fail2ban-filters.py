#!/usr/bin/env python3
"""Самопроверка failregex фильтров fail2ban против реальных строк лога.

Читает failregex/ignoreregex из deploy/fail2ban/filter.d-*.conf.
fail2ban снимает ISO8601-дату до failregex — тесты делают то же.
Запуск: python3 deploy/test-fail2ban-filters.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILTER_DIR = ROOT / "fail2ban"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+\-]\d{2}:\d{2}")


def parse_filter(name: str) -> tuple[re.Pattern[str], re.Pattern[str] | None]:
    text = (FILTER_DIR / f"filter.d-{name}.conf").read_text()
    failregex = ignoreregex = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("failregex"):
            failregex = line.split("=", 1)[1].strip()
        elif line.startswith("ignoreregex"):
            ignoreregex = line.split("=", 1)[1].strip()
    if not failregex:
        raise SystemExit(f"{name}: нет failregex")
    fail = re.compile(failregex.replace("<HOST>", r"(?P<host>\S+)"))
    ignore = re.compile(ignoreregex) if ignoreregex else None
    return fail, ignore


def after_date(line: str) -> str:
    return DATE.sub("", line, count=1)


def matched_ip(pattern: re.Pattern[str], line: str) -> str | None:
    m = pattern.search(after_date(line))
    return m.group("host") if m else None


SECURITY_429_HTML = (
    '2026-08-27T10:15:26+00:00 1.2.3.4 429 '
    '"GET /russia/region/moskva/valovoy-regionalnyy-produkt HTTP/1.1" '
    '"Mozilla/5.0 research/1.0"'
)
SECURITY_429_TICKER = (
    '2026-09-03T21:30:11+00:00 67.159.43.220 429 '
    '"GET /api/v1/ticker/live?lane=world HTTP/1.1" '
    '"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Cursor/3.18.25"'
)
SECURITY_200 = SECURITY_429_HTML.replace(" 429 ", " 200 ")
HONEYPOT_SCRAPER = (
    '2026-08-27T10:16:00+00:00 5.6.7.8 403 '
    '"GET /russia/util/links-exchange HTTP/1.1" '
    '"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"'
)
HONEYPOT_YANDEX = (
    '2026-09-03T14:42:11+00:00 77.88.5.1 403 '
    '"GET /__honeypot__/trap HTTP/1.1" '
    '"Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"'
)
CATALOG = (
    '2026-09-03T14:42:11+00:00 9.9.9.9 200 '
    '"GET /russia/indicator/cpi HTTP/1.1" '
    '"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"'
)
CATALOG_YANDEX = (
    '2026-09-03T14:42:11+00:00 9.9.9.9 200 '
    '"GET /russia/indicator/cpi HTTP/1.1" '
    '"Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"'
)
TICKER = (
    '2026-09-03T14:42:11+00:00 67.159.43.220 200 '
    '"GET /api/v1/ticker/live HTTP/1.1" '
    '"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"'
)
ASSET = (
    '2026-09-03T14:42:11+00:00 9.9.9.9 200 '
    '"GET /assets/index-abc123.js HTTP/1.1" '
    '"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"'
)
OG = (
    '2026-09-03T14:42:11+00:00 9.9.9.9 200 '
    '"GET /og/cpi.png HTTP/1.1" '
    '"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"'
)
HEALTH = (
    '2026-09-03T14:42:11+00:00 9.9.9.9 200 '
    '"GET /health HTTP/1.1" '
    '"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"'
)
HOME = (
    '2026-09-03T14:42:11+00:00 9.9.9.9 200 '
    '"GET / HTTP/1.1" '
    '"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"'
)


def expect(ok: bool, label: str, fail: list[int]) -> None:
    print(("OK  " if ok else "FAIL") + " " + label)
    if not ok:
        fail.append(1)


def main() -> int:
    nginx_429, _ = parse_filter("nginx-429")
    honeytrap, honey_ignore = parse_filter("honeytrap")
    volume, volume_ignore = parse_filter("nginx-volume")
    fail: list[int] = []

    expect(matched_ip(nginx_429, SECURITY_429_HTML) == "1.2.3.4",
           "nginx-429: HTML 429 → 1.2.3.4", fail)
    expect(matched_ip(nginx_429, SECURITY_429_TICKER) is None,
           "nginx-429: ticker /api/ не матч", fail)
    expect(matched_ip(nginx_429, SECURITY_200) is None,
           "nginx-429: 200 не матч", fail)
    expect(matched_ip(honeytrap, SECURITY_429_HTML) is None,
           "honeytrap: 429 не матч", fail)

    expect(matched_ip(honeytrap, HONEYPOT_SCRAPER) == "5.6.7.8",
           "honeytrap: скрейпер → 5.6.7.8", fail)
    yandex_honey_hit = matched_ip(honeytrap, HONEYPOT_YANDEX) == "77.88.5.1"
    yandex_honey_ignored = bool(honey_ignore and honey_ignore.search(HONEYPOT_YANDEX))
    expect(yandex_honey_hit and yandex_honey_ignored,
           "honeytrap: YandexBot на ловушке игнорируется", fail)

    expect(matched_ip(volume, CATALOG) == "9.9.9.9",
           "nginx-volume: каталог → 9.9.9.9", fail)
    expect(matched_ip(volume, HOME) == "9.9.9.9",
           "nginx-volume: главная → 9.9.9.9", fail)
    expect(matched_ip(volume, TICKER) is None,
           "nginx-volume: ticker /api/ не матч", fail)
    expect(matched_ip(volume, ASSET) is None,
           "nginx-volume: /assets/ не матч", fail)
    expect(matched_ip(volume, OG) is None,
           "nginx-volume: /og/ не матч", fail)
    expect(matched_ip(volume, HEALTH) is None,
           "nginx-volume: /health не матч", fail)

    yandex_vol_hit = matched_ip(volume, CATALOG_YANDEX) == "9.9.9.9"
    yandex_vol_ignored = bool(volume_ignore and volume_ignore.search(CATALOG_YANDEX))
    expect(yandex_vol_hit and yandex_vol_ignored,
           "nginx-volume: YandexBot ignored", fail)

    print()
    if fail:
        print(f"{sum(fail)} case(s) FAILED")
        return 1
    print("OK: все фильтры соответствуют формату лога после снятия даты")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
