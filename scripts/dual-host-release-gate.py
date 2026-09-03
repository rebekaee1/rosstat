#!/usr/bin/env python3
"""Fast dual-host release gate for representative public SEO URL shapes.

After RUSTATS_APEX_LOCALE_EN, production apex is English with a full
hreflang set; ru. is the Russian canon. The gate reads <html lang> on
apex instead of guessing the flag. Search-bot UA is used so geo-redirect
for humans does not fire.
"""
from __future__ import annotations
import argparse
import re
import httpx
from bs4 import BeautifulSoup

DATA_IMAGE_PATHS = frozenset({
    "/russia/indicator/cpi", "/russia/indicator/cpi/2024",
    "/russia/indicator/cpi/2024-01", "/russia/today", "/russia/today/cpi",
    "/russia/region-rating/chislennost-naseleniya", "/world/rating/population",
})

DEFAULT_PATHS = (
    "/", "/about", "/methodology", "/compare", "/calculator",
    "/russia", "/russia/category/prices", "/russia/indicator/cpi",
    "/russia/indicator/cpi/2024", "/russia/indicator/cpi/2024-01",
    "/russia/today", "/russia/today/cpi", "/russia/calendar",
    "/russia/region", "/russia/region/moskva",
    "/russia/region-rating/chislennost-naseleniya",
    "/world/rating/population",
)
# Страновые мировые пути (/germany и т.п.) в гейт не входят: мировой data plane
# на проде сознательно не залит (владелец мировую экономику на прод не выкладывал),
# поэтому /germany там стабильно 404 и до, и после языкового релиза. Вернуть путь
# в список можно только вместе с решением о заливке мировых данных на прод.
CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def _html_lang(soup: BeautifulSoup) -> str:
    node = soup.find("html")
    raw = (node.get("lang") if node else "") or ""
    return raw.lower()[:2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ru-origin", default="http://localhost:3000")
    parser.add_argument("--en-origin", default="http://localhost:3000")
    parser.add_argument("--ru-host", default="ru.forecasteconomy.com")
    parser.add_argument("--en-host", default="forecasteconomy.com")
    args = parser.parse_args()
    paths = DEFAULT_PATHS
    errors = []

    with httpx.Client(
        timeout=30,
        follow_redirects=False,
        headers={"Host": args.en_host, "User-Agent": "YandexBot/3.0"},
    ) as probe:
        home = probe.get(f"{args.en_origin.rstrip('/')}/")
        apex_lang = _html_lang(BeautifulSoup(home.text, "html.parser")) if home.status_code == 200 else "ru"
    apex_is_en = apex_lang == "en"

    for locale, origin, host in (("ru", args.ru_origin, args.ru_host), ("en", args.en_origin, args.en_host)):
        expected_lang = "en" if locale == "en" and apex_is_en else "ru"
        with httpx.Client(timeout=30, follow_redirects=False, headers={"Host": host, "User-Agent": "YandexBot/3.0"}) as client:
            for path in paths:
                response = client.get(f"{origin.rstrip('/')}{path}")
                if response.status_code != 200:
                    errors.append(f"{locale} {path}: HTTP {response.status_code}"); continue
                soup = BeautifulSoup(response.text, "html.parser")
                if _html_lang(soup) != expected_lang:
                    errors.append(f"{locale} {path}: lang={_html_lang(soup)!r} expected {expected_lang!r}")
                canonical = soup.select_one('link[rel="canonical"]')
                # До cutover ru. каноничен на apex (один индекс Яндекса).
                if locale == "ru" and not apex_is_en:
                    expected_origin = "https://forecasteconomy.com"
                else:
                    expected_origin = "https://ru.forecasteconomy.com" if locale == "ru" else "https://forecasteconomy.com"
                expected_canonical = expected_origin if path == "/" else expected_origin + path
                if not canonical or canonical.get("href") != expected_canonical:
                    errors.append(f"{locale} {path}: canonical {canonical and canonical.get('href')!r}")
                alts = {a.get("hreflang"): a.get("href") for a in soup.select('link[rel="alternate"][hreflang]')}
                if apex_is_en:
                    if not {"ru", "en", "x-default"}.issubset(alts):
                        errors.append(f"{locale} {path}: incomplete hreflang")
                elif alts:
                    errors.append(f"{locale} {path}: hreflang before EN cutover")
                if (
                    expected_lang == "en"
                    and CYRILLIC.search(soup.get_text(" ", strip=True))
                    and not path.startswith("/russia/region")
                ):
                    errors.append(f"en {path}: Cyrillic visible text")
                og = soup.select_one('meta[property="og:image"]')
                if path in DATA_IMAGE_PATHS:
                    if not og: errors.append(f"{locale} {path}: no og:image")
                    if '"ImageObject"' not in response.text: errors.append(f"{locale} {path}: no ImageObject")
                    visible = soup.select_one("figure.seo-chart img")
                    if not visible or not visible.get("alt"): errors.append(f"{locale} {path}: no visible SEO image/alt")
                if og:
                    og_content = og.get("content", "")
                    image_path = (
                        og_content
                        .replace("https://forecasteconomy.com", "")
                        .replace("https://ru.forecasteconomy.com", "")
                    )
                    image = client.get(f"{origin.rstrip('/')}{image_path}")
                    if image.status_code != 200 or not image.headers.get("content-type", "").startswith("image/") or len(image.content) < 1000:
                        errors.append(f"{locale} {path}: broken OG {image.status_code}")
    if errors:
        print("\n".join(errors)); return 1
    mode = "EN-apex cutover" if apex_is_en else "pre-cutover (apex ru)"
    print(f"OK: {len(paths) * 2} RU/EN representative pages ({mode})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
