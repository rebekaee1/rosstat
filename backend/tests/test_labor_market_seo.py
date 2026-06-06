"""SEO-блоки рынка труда: занятость и рабочая сила."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"osn-\{|bulk_upsert|parser|ADR-\d|\.xlsx|\.pdf|element_id",
    re.I,
)

LABOR_MARKET_CODES = ("employment", "labor-force")


def test_labor_market_has_eight_seo_blocks_each() -> None:
    for code in LABOR_MARKET_CODES:
        blocks = INDICATOR_SEO_BLOCKS[code]
        assert len(blocks) == 8
        assert any("занят" in b["title"].lower() or "рабоч" in b["title"].lower() for b in blocks)


def test_labor_market_seo_blocks_public_language() -> None:
    for code in LABOR_MARKET_CODES:
        for block in INDICATOR_SEO_BLOCKS[code]:
            assert len(block["body"]) >= 420, (code, block["title"], len(block["body"]))
            assert not FORBIDDEN.search(block["body"]), block["title"]


def test_labor_market_seo_titles_unique_per_code() -> None:
    for code in LABOR_MARKET_CODES:
        titles = [b["title"] for b in INDICATOR_SEO_BLOCKS[code]]
        assert len(titles) == len(set(titles))


def test_employment_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == "employment")
    text = ind.get("methodology") or ""
    assert len(text) > 80
    assert FORBIDDEN.search(text) is None
    assert "Росстат" in text


def test_labor_force_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == "labor-force")
    text = ind.get("methodology") or ""
    assert len(text) > 80
    assert FORBIDDEN.search(text) is None
    assert "Росстат" in text
    assert "Занятое" in text or "занят" in text.lower()
