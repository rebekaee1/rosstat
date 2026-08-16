"""Инвариант ADR-0013: слаги стран/регионов ∩ reserved first segments = ∅.

Постоянный guard (не разовая проверка): падает в CI, если новый слаг
пересёкся со служебным первым сегментом.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.site_paths import (
    RESERVED_FIRST_SEGMENTS,
    RUSSIA,
    is_reserved_first_segment,
)

# Активные слаги world_countries на момент path-cut (47). При добавлении
# страны в загрузчик — расширить список или читать из seed-артефакта.
_KNOWN_WORLD_COUNTRY_SLUGS = frozenset({
    "albania", "australia", "austria", "belgium", "bosnia", "brazil",
    "bulgaria", "canada", "china", "croatia", "cyprus", "czechia",
    "denmark", "estonia", "finland", "france", "georgia", "germany",
    "greece", "hungary", "iceland", "india", "ireland", "italy", "japan",
    "latvia", "lithuania", "luxembourg", "malta", "mexico", "moldova",
    "montenegro", "netherlands", "north-macedonia", "norway", "poland",
    "portugal", "romania", "serbia", "slovakia", "slovenia", "spain",
    "sweden", "switzerland", "turkey", "united-kingdom", "united-states",
})

_REGIONS_JSON = (
    Path(__file__).resolve().parents[1] / "app" / "data" / "regional" / "regions.json"
)


def test_reserved_covers_platform_roots():
    required = {
        "about", "compare", "calculator", "world", "api", "assets", "og",
        "admin", "embed", "indicator", "category", "today", "regions", "region",
        "login", "privacy", "terms",
    }
    assert required <= RESERVED_FIRST_SEGMENTS


def test_russia_is_not_reserved():
    """russia — канонический слаг страны, не служебный корень."""
    assert RUSSIA not in RESERVED_FIRST_SEGMENTS
    assert not is_reserved_first_segment(RUSSIA)


def test_sitemap_variants_reserved():
    assert is_reserved_first_segment("sitemap.xml")
    assert is_reserved_first_segment("sitemap-core.xml")
    assert is_reserved_first_segment("sitemap-regional-1.xml")


def test_world_country_slugs_do_not_collide_with_reserved():
    collisions = sorted(s for s in _KNOWN_WORLD_COUNTRY_SLUGS if is_reserved_first_segment(s))
    assert collisions == [], f"world slug ∩ reserved: {collisions}"


def test_russia_not_in_world_country_slugs():
    assert RUSSIA not in _KNOWN_WORLD_COUNTRY_SLUGS


def test_region_slugs_do_not_collide_with_reserved():
    rows = json.loads(_REGIONS_JSON.read_text(encoding="utf-8"))
    # Все территории артефакта (region/district/country/remainder): слаг
    # не должен совпасть с reserved, иначе при ошибочном выносе в корень
    # перехватит служебный путь.
    slugs = {row["slug"] for row in rows if row.get("slug")}
    assert len(slugs) >= 85
    collisions = sorted(s for s in slugs if is_reserved_first_segment(s))
    assert collisions == [], f"region slug ∩ reserved: {collisions}"
