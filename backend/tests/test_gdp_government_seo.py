"""SEO-блоки и публичные тексты государственного потребления."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"GDP-quarters|bulk_upsert|parser|ADR-\d|\.xls|\.xlsx|element_id|gdp_row|ОКВЭД",
    re.I,
)

GDP_GOVERNMENT_CODE = "gdp-government"


def test_gdp_government_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS[GDP_GOVERNMENT_CODE]
    assert len(blocks) == 8
    assert any("государ" in b["title"].lower() for b in blocks)


def test_gdp_government_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS[GDP_GOVERNMENT_CODE]:
        assert len(block["body"]) >= 420, (block["title"], len(block["body"]))
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_gdp_government_seo_titles_unique() -> None:
    titles = [b["title"] for b in INDICATOR_SEO_BLOCKS[GDP_GOVERNMENT_CODE]]
    assert len(titles) == len(set(titles))


def test_gdp_government_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == GDP_GOVERNMENT_CODE)
    text = ind.get("methodology") or ""
    assert len(text) > 120
    assert FORBIDDEN.search(text) is None
    assert "Росстат" in text
    assert "1995" in text
