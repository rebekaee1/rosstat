"""SEO-блоки и публичные тексты карточки mortgage-rate."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"0409128|publicationId|datasetId|element_id|bulk_upsert|parser|\.xlsx|ADR-\d",
    re.I,
)


def test_mortgage_rate_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS["mortgage-rate"]
    assert len(blocks) == 8
    assert any(b["title"] == "Что такое ставка по ипотеке" for b in blocks)


def test_mortgage_rate_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS["mortgage-rate"]:
        assert len(block["body"]) > 80
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_mortgage_rate_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == "mortgage-rate")
    text = ind["methodology"]
    assert "0409128" not in text
    assert FORBIDDEN.search(text) is None
    assert "ипотеч" in text.lower()
