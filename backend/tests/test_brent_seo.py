"""SEO-блоки и публичные тексты карточки brent."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"MOEX|FORTS|BR-\d|BZ=F|yahoo|Yahoo|bulk_upsert|parser|ADR-\d",
    re.I,
)


def test_brent_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS["brent"]
    assert len(blocks) == 8
    assert any("brent" in b["title"].lower() or "нефт" in b["title"].lower() for b in blocks)


def test_brent_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS["brent"]:
        assert len(block["body"]) > 80
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_brent_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == "brent")
    text = ind["methodology"]
    assert "moex" not in text.lower()
    assert FORBIDDEN.search(text) is None
    assert "brent" in text.lower() or "баррел" in text.lower()
