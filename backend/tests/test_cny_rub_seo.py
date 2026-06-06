"""SEO-блоки и публичные тексты карточки cny-rub."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"R01375|XML_dynamic|currency_base/daily|cbr\.ru/|bulk_upsert|parser|ADR-\d",
    re.I,
)


def test_cny_rub_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS["cny-rub"]
    assert len(blocks) == 8
    assert any("юан" in b["title"].lower() for b in blocks)


def test_cny_rub_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS["cny-rub"]:
        assert len(block["body"]) > 80
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_cny_rub_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == "cny-rub")
    text = ind["methodology"]
    assert "xml" not in text.lower()
    assert FORBIDDEN.search(text) is None
    assert "юан" in text.lower()
