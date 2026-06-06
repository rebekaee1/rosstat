"""SEO-блоки и публичные тексты карточки usd-rub."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"R01235|XML_dynamic|currency_base/daily|cbr\.ru/|bulk_upsert|parser|ADR-\d",
    re.I,
)


def test_usd_rub_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS["usd-rub"]
    assert len(blocks) == 8
    assert any("доллар" in b["title"].lower() for b in blocks)


def test_usd_rub_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS["usd-rub"]:
        assert len(block["body"]) > 80
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_usd_rub_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == "usd-rub")
    text = ind["methodology"]
    assert "xml" not in text.lower()
    assert FORBIDDEN.search(text) is None
    assert "доллар" in text.lower()
