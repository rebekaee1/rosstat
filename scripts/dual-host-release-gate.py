#!/usr/bin/env python3
"""Fast RU/EN release gate for representative public SEO URL shapes."""
from __future__ import annotations
import argparse
import re
import sys
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

DATA_IMAGE_PATHS = frozenset({
    "/russia/indicator/cpi", "/russia/indicator/cpi/2024",
    "/russia/indicator/cpi/2024-01", "/russia/today", "/russia/today/cpi",
    "/russia/region-rating/chislennost-naseleniya", "/world/rating/population",
    "/germany",
})

DEFAULT_PATHS = (
    "/", "/about", "/methodology", "/compare", "/calculator",
    "/russia", "/russia/category/prices", "/russia/indicator/cpi",
    "/russia/indicator/cpi/2024", "/russia/indicator/cpi/2024-01",
    "/russia/today", "/russia/today/cpi", "/russia/calendar",
    "/russia/region", "/russia/region/moskva",
    "/russia/region-rating/chislennost-naseleniya",
    "/world/rating/population", "/germany",
)
CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ru-origin", default="http://localhost:3000")
    parser.add_argument("--en-origin", default="http://localhost:3000")
    parser.add_argument("--ru-host", default="ru.forecasteconomy.com")
    parser.add_argument("--en-host", default="forecasteconomy.com")
    args = parser.parse_args()
    # Local nginx needs Host routing while URL stays localhost.
    paths = DEFAULT_PATHS
    errors = []
    for locale, origin, host in (("ru", args.ru_origin, args.ru_host), ("en", args.en_origin, args.en_host)):
        # Use explicit Host for local dual-host smoke.
        with httpx.Client(timeout=30, follow_redirects=False, headers={"Host": host, "User-Agent": "YandexBot/3.0"}) as client:
            # Inline variant of check to preserve Host; production origins can use the same contract.
            for path in paths:
                response = client.get(f"{origin.rstrip('/')}{path}")
                if response.status_code != 200:
                    errors.append(f"{locale} {path}: HTTP {response.status_code}"); continue
                soup = BeautifulSoup(response.text, "html.parser")
                canonical = soup.select_one('link[rel="canonical"]')
                expected_origin = "https://ru.forecasteconomy.com" if locale == "ru" else "https://forecasteconomy.com"
                expected_canonical = expected_origin if path == "/" else expected_origin + path
                if not canonical or canonical.get("href") != expected_canonical:
                    errors.append(f"{locale} {path}: canonical {canonical and canonical.get('href')!r}")
                alts = {a.get("hreflang"): a.get("href") for a in soup.select('link[rel="alternate"][hreflang]')}
                if not {"ru", "en", "x-default"}.issubset(alts): errors.append(f"{locale} {path}: incomplete hreflang")
                if locale == "en" and CYRILLIC.search(soup.get_text(" ", strip=True)):
                    errors.append(f"en {path}: Cyrillic visible text")
                og = soup.select_one('meta[property="og:image"]')
                if path in DATA_IMAGE_PATHS:
                    if not og: errors.append(f"{locale} {path}: no og:image")
                    if '"ImageObject"' not in response.text: errors.append(f"{locale} {path}: no ImageObject")
                    visible = soup.select_one("figure.seo-chart img")
                    if not visible or not visible.get("alt"): errors.append(f"{locale} {path}: no visible SEO image/alt")
                if og:
                    image_path = og.get("content", "").replace(expected_origin, "")
                    image = client.get(f"{origin.rstrip('/')}{image_path}")
                    if image.status_code != 200 or not image.headers.get("content-type", "").startswith("image/") or len(image.content) < 1000:
                        errors.append(f"{locale} {path}: broken OG {image.status_code}")
    if errors:
        print("\n".join(errors)); return 1
    print(f"OK: {len(paths) * 2} RU/EN representative pages")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
