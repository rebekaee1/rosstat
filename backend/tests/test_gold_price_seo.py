"""SEO-блоки и публичные тексты учётной цены золота."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"cbr_gold|metall_base|bulk_upsert|parser|ADR-\d|\.xlsx|\.html",
    re.I,
)

GOLD_PRICE_CODE = "gold-price"


def test_gold_price_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS[GOLD_PRICE_CODE]
    assert len(blocks) == 8
    assert any("золот" in b["title"].lower() for b in blocks)


def test_gold_price_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS[GOLD_PRICE_CODE]:
        assert len(block["body"]) >= 380, (block["title"], len(block["body"]))
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_gold_price_seo_titles_unique() -> None:
    titles = [b["title"] for b in INDICATOR_SEO_BLOCKS[GOLD_PRICE_CODE]]
    assert len(titles) == len(set(titles))


def test_gold_price_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == GOLD_PRICE_CODE)
    text = ind.get("methodology") or ""
    assert len(text) > 80
    assert FORBIDDEN.search(text) is None
    assert "Банк России" in text
    assert "руб" in text.lower()
