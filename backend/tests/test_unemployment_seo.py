"""SEO-блоки и публичные тексты уровня безработицы."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"osn-\{|bulk_upsert|parser|ADR-\d|\.xlsx|\.pdf|element_id",
    re.I,
)

UNEMPLOYMENT_CODE = "unemployment"


def test_unemployment_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS[UNEMPLOYMENT_CODE]
    assert len(blocks) == 8
    assert any("безработ" in b["title"].lower() for b in blocks)


def test_unemployment_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS[UNEMPLOYMENT_CODE]:
        assert len(block["body"]) >= 420, (block["title"], len(block["body"]))
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_unemployment_seo_titles_unique() -> None:
    titles = [b["title"] for b in INDICATOR_SEO_BLOCKS[UNEMPLOYMENT_CODE]]
    assert len(titles) == len(set(titles))


def test_unemployment_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == UNEMPLOYMENT_CODE)
    text = ind.get("methodology") or ""
    assert len(text) > 80
    assert FORBIDDEN.search(text) is None
    assert "Росстат" in text
    assert "12" in text or "квартал" in text.lower()
