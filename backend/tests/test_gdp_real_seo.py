"""SEO-блоки и публичные тексты реального ВВП."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"VVP_kvartal|bulk_upsert|parser|ADR-\d|\.xls|\.xlsx|element_id|ОКВЭД|СНС-2008",
    re.I,
)

GDP_REAL_CODE = "gdp-real"


def test_gdp_real_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS[GDP_REAL_CODE]
    assert len(blocks) == 8
    assert any("реальн" in b["title"].lower() for b in blocks)


def test_gdp_real_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS[GDP_REAL_CODE]:
        assert len(block["body"]) >= 420, (block["title"], len(block["body"]))
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_gdp_real_seo_titles_unique() -> None:
    titles = [b["title"] for b in INDICATOR_SEO_BLOCKS[GDP_REAL_CODE]]
    assert len(titles) == len(set(titles))


def test_gdp_real_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == GDP_REAL_CODE)
    text = ind.get("methodology") or ""
    assert len(text) > 120
    assert FORBIDDEN.search(text) is None
    assert "Росстат" in text
    assert "1995" in text
