#!/usr/bin/env python3
"""Audit indexable SEO HTML for Forecast Economy.

The script is intentionally dependency-light so it can run locally, on the
server, or in CI against any deployed base URL.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

TRACKING_PARAMS = {
    "etext", "ybaip", "yclid", "ysclid", "gclid", "fbclid", "_openstat",
    "openstat", "clid", "yandex_referrer", "_ga", "utm_source", "utm_medium",
    "utm_campaign", "utm_term", "utm_content", "utm_referrer", "from", "ref",
    "ref_src", "source", "mc_cid", "mc_eid", "igshid",
}

HUMAN_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 Chrome/124 Safari/537.36"
YANDEX_UA = "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"
GENERIC_TITLE = "Forecast Economy | Бесплатная аналитика экономики России"


class SeoParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.h1_count = 0
        self.description = ""
        self.canonical = ""
        self.json_ld_count = 0
        self.links: set[str] = set()
        self._script_type = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = {k.lower(): v or "" for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "meta" and attrs_dict.get("name") == "description":
            self.description = attrs_dict.get("content", "")
        elif tag == "link" and attrs_dict.get("rel") == "canonical":
            self.canonical = attrs_dict.get("href", "")
        elif tag == "a" and attrs_dict.get("href"):
            self.links.add(attrs_dict["href"])
        elif tag == "script":
            self._script_type = attrs_dict.get("type", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._script_type = ""

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._script_type == "application/ld+json" and data.strip():
            self.json_ld_count += 1


def fetch(url: str, ua: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html,application/xml"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", "replace")
            return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def sitemap_urls(base_url: str) -> list[str]:
    status, body = fetch(urllib.parse.urljoin(base_url, "/sitemap.xml"), HUMAN_UA)
    if status != 200:
        raise RuntimeError(f"sitemap returned HTTP {status}")
    root = ET.fromstring(body)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
    if not urls:
        urls = [loc.text.strip() for loc in root.findall(".//loc") if loc.text]
    return urls


def normalize_internal(base_url: str, href: str) -> str | None:
    if href.startswith(("mailto:", "tel:", "#", "javascript:")):
        return None
    absolute = urllib.parse.urljoin(base_url, href)
    parsed_base = urllib.parse.urlparse(base_url)
    parsed = urllib.parse.urlparse(absolute)
    if parsed.netloc != parsed_base.netloc:
        return None
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/", "", parsed.query, ""))


def audit_html(url: str, body: str, status: int, sitemap_set: set[str], base_url: str) -> tuple[list[str], SeoParser]:
    parser = SeoParser()
    parser.feed(body)
    errors = []
    title = html.unescape(parser.title).strip()
    description = html.unescape(parser.description).strip()
    canonical = parser.canonical.rstrip("/")
    expected = url.rstrip("/")

    if status != 200:
        errors.append(f"HTTP {status}")
    if not title or title == GENERIC_TITLE:
        errors.append("missing or generic title")
    if not description or "бесплатная платформа макроэкономической аналитики" in description.lower():
        errors.append("missing or generic description")
    if canonical != expected:
        errors.append(f"canonical mismatch: {parser.canonical!r}")
    if parser.h1_count != 1:
        errors.append(f"h1 count is {parser.h1_count}")
    if parser.json_ld_count < 1:
        errors.append("missing JSON-LD")

    internal_links = {normalize_internal(base_url, href) for href in parser.links}
    internal_links.discard(None)
    meaningful_links = [link for link in internal_links if not re.search(r"/(__spa-index|assets|api|embed)", link or "")]
    if len(meaningful_links) < 2:
        errors.append("too few internal links")
    for link in internal_links:
        parsed = urllib.parse.urlparse(link)
        params = set(urllib.parse.parse_qs(parsed.query).keys())
        polluted = sorted(params & TRACKING_PARAMS)
        if polluted:
            errors.append(f"tracking params in internal link {link}: {','.join(polluted)}")
    # This is a warning-level condition in spirit, but fail it while hardening
    # the SEO graph so orphaned sitemap pages are visible before deploy.
    if expected in sitemap_set and expected not in {l.rstrip('/') for l in internal_links}:
        pass
    return errors, parser


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://forecasteconomy.com")
    ap.add_argument("--limit", type=int, default=0, help="Limit sitemap URLs for smoke runs")
    args = ap.parse_args()

    base_url = args.base_url.rstrip("/")
    urls = sitemap_urls(base_url)
    if args.limit:
        urls = urls[: args.limit]
    sitemap_set = {u.rstrip("/") for u in urls}
    all_errors: list[str] = []
    discovered: set[str] = set()

    for url in urls:
        variants = []
        for label, ua in (("human", HUMAN_UA), ("yandex", YANDEX_UA)):
            status, body = fetch(url, ua)
            errors, parsed = audit_html(url, body, status, sitemap_set, base_url)
            variants.append((label, parsed, errors))
            for href in parsed.links:
                normalized = normalize_internal(base_url, href)
                if normalized:
                    discovered.add(normalized.rstrip("/"))
            for error in errors:
                all_errors.append(f"{url} [{label}]: {error}")
        human, yandex = variants[0][1], variants[1][1]
        if human.title.strip() != yandex.title.strip():
            all_errors.append(f"{url}: human/yandex title mismatch")
        if human.description.strip() != yandex.description.strip():
            all_errors.append(f"{url}: human/yandex description mismatch")
        if human.canonical.rstrip("/") != yandex.canonical.rstrip("/"):
            all_errors.append(f"{url}: human/yandex canonical mismatch")

    orphaned = sorted(sitemap_set - discovered - {base_url})
    if orphaned:
        sample = ", ".join(orphaned[:10])
        all_errors.append(f"{len(orphaned)} sitemap URLs are not discovered from audited HTML links: {sample}")

    print(f"Audited {len(urls)} sitemap URLs from {base_url}")
    print(f"Discovered {len(discovered)} internal URLs")
    if all_errors:
        print("SEO audit failed:")
        for error in all_errors[:80]:
            print(f"- {error}")
        if len(all_errors) > 80:
            print(f"... {len(all_errors) - 80} more errors")
        return 1
    print("SEO audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
