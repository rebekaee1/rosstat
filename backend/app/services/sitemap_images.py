"""Map data-backed public sitemap paths to their existing standalone image.

This is route resolution, not another data catalog: SiteUrl builders already
prove that the page has data. No database access, image rendering, HTTP requests,
or per-page files are involved. Unknown/static families have no inferred image.
Both dynamic responses and atomic static publication use this same resolver.
"""
from __future__ import annotations

import re
from functools import lru_cache
from urllib.parse import parse_qs, urlsplit

from app.services import site_paths as paths

_SEGMENT = re.compile(r"[a-z0-9-]+")
_WORLD_CODE = re.compile(r"[a-z0-9_.-]+")


@lru_cache(maxsize=1)
def _country_slugs() -> frozenset[str]:
    # The same static country catalog that seeds WorldCountry. Importing it
    # doesn't fetch data; cache the small set rather than any of the million URLs.
    from app.services.eurostat_parser import WORLD_COUNTRIES
    return frozenset(meta[0] for meta in WORLD_COUNTRIES.values())


def _concept_supported(code: str, surface: str) -> bool:
    from app.data.world_concepts import CONCEPT_BY_SLUG
    concept = CONCEPT_BY_SLUG.get(code)
    return concept is not None and surface in concept.enabled_surfaces


def _pair(value: str) -> tuple[str, str] | None:
    parts = value.split("-vs-")
    if len(parts) != 2 or parts[0] == parts[1] or not all(_SEGMENT.fullmatch(p) for p in parts):
        return None
    return parts[0], parts[1]


def image_path_for_page(path: str) -> str | None:
    """Return one public image path, preserving selected year when supported.

    Input is a relative canonical SiteUrl; arbitrary URLs and unsupported query
    modes are not assigned a plausible-looking fallback. Country existence is
    constrained by the seed catalog; indicator/region existence stays with the
    upstream database-backed SiteUrl registry.
    """
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith("/"):
        return None
    parts = parsed.path.strip("/").split("/")
    if not all(_WORLD_CODE.fullmatch(part) for part in parts):
        return None
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) - {"year"}:
        return None
    year = None
    if "year" in query:
        if len(query["year"]) != 1 or not paths.is_public_year(query["year"][0]):
            return None
        year = int(query["year"][0])

    if parts[0] == paths.RUSSIA:
        if parts == [paths.RUSSIA, "demographics"]:
            # The demographics page currently publishes its latest common year.
            return "/og/russia/demographics.png" if year is None else None
        if parts == [paths.RUSSIA, "today"] and year is None:
            return paths.og_today()
        if len(parts) == 3 and parts[1] == "today" and year is None and _SEGMENT.fullmatch(parts[2]):
            return paths.og_indicator(paths.RUSSIA, parts[2])
        if len(parts) in (3, 4) and parts[1] == "indicator" and _SEGMENT.fullmatch(parts[2]) and year is None:
            if len(parts) == 3:
                return paths.og_indicator(paths.RUSSIA, parts[2])
            period = parts[3]
            if paths.is_public_year(period) or paths.is_public_month_period(period):
                return paths.og_indicator(paths.RUSSIA, parts[2], period)
            return None
        if len(parts) == 3 and parts[1] == "region-rating" and _SEGMENT.fullmatch(parts[2]):
            image = paths.og_region_rating(parts[2])
            return f"{image}?year={year}" if year is not None else image
        if len(parts) == 3 and parts[1] == "region-vs" and year is None:
            pair = _pair(parts[2])
            return paths.og_region_vs(*pair) if pair else None
        if len(parts) in (4, 5) and parts[1] == "region" and all(_SEGMENT.fullmatch(p) for p in parts[2:4]):
            region, code = parts[2:4]
            if region == "map":
                if len(parts) != 4 or code == "overview":
                    return None
                image = paths.og_region_rating(code)
                return f"{image}?year={year}" if year is not None else image
            if year is not None:
                return None
            if len(parts) == 4:
                return paths.og_region(region, code)
            return paths.og_region_year(region, code, int(parts[4])) if paths.is_public_year(parts[4]) else None
        return None

    if parts[0] == "world":
        if len(parts) not in (3, 4) or parts[1] != "rating" or not _concept_supported(parts[2], "rating"):
            return None
        if len(parts) == 4:
            if year is not None or not paths.is_public_year(parts[3]):
                return None
            year = int(parts[3])
        return paths.og_world_rating_year(parts[2], year) if year is not None else paths.og_world_rating(parts[2])

    if len(parts) == 2 and year is None and (pair := _pair(parts[0])):
        countries = _country_slugs() | {paths.RUSSIA}
        if not all(country in countries for country in pair) or not _concept_supported(parts[1], "compare"):
            return None
        from app.services.seo_world_compare import og_world_vs_path
        return og_world_vs_path(*pair, parts[1])

    if parts[0] not in _country_slugs() or year is not None:
        return None
    country = parts[0]
    if len(parts) == 1:
        return paths.og_country(country)
    if len(parts) in (3, 4) and parts[1] == "indicator":
        if len(parts) == 3:
            return paths.og_indicator(country, parts[2])
        # World monthly landings do not have a public image endpoint.
        return paths.og_indicator(country, parts[2], int(parts[3])) if paths.is_public_year(parts[3]) else None
    if parts[1:] == ["regions"]:
        from app.services.seo_world_subnational import og_subnational_hub
        return og_subnational_hub(country)
    if len(parts) == 3 and parts[1] == "region-vs":
        pair = _pair(parts[2])
        if pair:
            from app.services.seo_world_subnational_compare import og_subnational_compare
            return og_subnational_compare(country, *pair)
    if len(parts) == 5 and parts[1] == "region" and parts[2] != "map" and all(_SEGMENT.fullmatch(p) for p in parts[2:4]) and paths.is_public_year(parts[4]):
        from app.services.seo_world_subnational_year import og_subnational_indicator_year
        return og_subnational_indicator_year(country, parts[2], parts[3], int(parts[4]))
    if len(parts) in (3, 4) and parts[1] == "region" and parts[2] != "map" and all(_SEGMENT.fullmatch(p) for p in parts[2:]):
        from app.services.seo_world_subnational import og_subnational_indicator, og_subnational_region
        return og_subnational_region(country, parts[2]) if len(parts) == 3 else og_subnational_indicator(country, parts[2], parts[3])
    return None
