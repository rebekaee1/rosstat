from __future__ import annotations

import hashlib
import html
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SeoPageSnapshot


TRACKING_PARAMS = {
    "etext", "ybaip", "yclid", "ysclid", "gclid", "fbclid", "_openstat",
    "openstat", "clid", "yandex_referrer", "_ga", "utm_source", "utm_medium",
    "utm_campaign", "utm_term", "utm_content", "utm_referrer", "from", "ref",
    "ref_src", "source", "mc_cid", "mc_eid", "igshid",
}


@dataclass
class SeoFacts:
    url: str
    status_code: int
    title: str = ""
    description: str = ""
    canonical: str = ""
    h1_count: int = 0
    json_ld_count: int = 0
    links: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)

    @property
    def content_hash(self) -> str:
        payload = "|".join([
            self.url,
            self.title,
            self.description,
            self.canonical,
            str(self.h1_count),
            str(self.json_ld_count),
            ",".join(sorted(self.links)),
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SeoHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.h1_count = 0
        self.json_ld_count = 0
        self.links: set[str] = set()
        self._in_title = False
        self._script_type = ""

    def handle_starttag(self, tag: str, attrs):
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

    def handle_endtag(self, tag: str):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._script_type = ""

    def handle_data(self, data: str):
        if self._in_title:
            self.title += data
        elif self._script_type == "application/ld+json" and data.strip():
            self.json_ld_count += 1


def normalize_internal(base_url: str, href: str) -> str | None:
    if href.startswith(("mailto:", "tel:", "#", "javascript:")):
        return None
    absolute = urllib.parse.urljoin(base_url, href)
    parsed_base = urllib.parse.urlparse(base_url)
    parsed = urllib.parse.urlparse(absolute)
    if parsed.netloc != parsed_base.netloc:
        return None
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/", "", parsed.query, ""))


async def crawl_url(url: str, *, base_url: str, user_agent: str | None = None) -> SeoFacts:
    headers = {"User-Agent": user_agent or "ForecastAnalyticsBot/1.0"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
    parser = SeoHtmlParser()
    parser.feed(response.text)
    facts = SeoFacts(
        url=url.rstrip("/") or "/",
        status_code=response.status_code,
        title=html.unescape(parser.title).strip(),
        description=html.unescape(parser.description).strip(),
        canonical=parser.canonical.rstrip("/"),
        h1_count=parser.h1_count,
        json_ld_count=parser.json_ld_count,
        links={link for link in (normalize_internal(base_url, href) for href in parser.links) if link},
    )
    if response.status_code != 200:
        facts.errors.append(f"HTTP {response.status_code}")
    if not facts.title:
        facts.errors.append("missing title")
    if not facts.description:
        facts.errors.append("missing description")
    if facts.h1_count != 1:
        facts.errors.append(f"h1 count is {facts.h1_count}")
    if facts.json_ld_count < 1:
        facts.errors.append("missing JSON-LD")
    for link in facts.links:
        params = set(urllib.parse.parse_qs(urllib.parse.urlparse(link).query).keys())
        polluted = sorted(params & TRACKING_PARAMS)
        if polluted:
            facts.errors.append(f"tracking params in internal link {link}: {','.join(polluted)}")
    return facts


async def store_seo_snapshot(db: AsyncSession, facts: SeoFacts) -> SeoPageSnapshot:
    from sqlalchemy import select

    existing_q = await db.execute(
        select(SeoPageSnapshot).where(
            SeoPageSnapshot.url == facts.url,
            SeoPageSnapshot.content_hash == facts.content_hash,
        )
    )
    existing = existing_q.scalar_one_or_none()
    if existing:
        existing.status_code = facts.status_code
        existing.title = facts.title
        existing.description = facts.description
        existing.canonical = facts.canonical
        existing.h1_count = facts.h1_count
        existing.json_ld_count = facts.json_ld_count
        existing.internal_links_count = len(facts.links)
        existing.facts_json = {"links": sorted(facts.links), "errors": facts.errors}
        db.add(existing)
        await db.flush()
        return existing

    snapshot = SeoPageSnapshot(
        url=facts.url,
        status_code=facts.status_code,
        title=facts.title,
        description=facts.description,
        canonical=facts.canonical,
        h1_count=facts.h1_count,
        json_ld_count=facts.json_ld_count,
        internal_links_count=len(facts.links),
        content_hash=facts.content_hash,
        facts_json={"links": sorted(facts.links), "errors": facts.errors},
    )
    db.add(snapshot)
    await db.flush()
    return snapshot
