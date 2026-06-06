"""SEO-блоки и публичные тексты средней заработной платы."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"osn-\{|bulk_upsert|parser|ADR-\d|\.xlsx|\.pdf|element_id|П-4|\?mode=",
    re.I,
)

WAGES_NOMINAL_CODE = "wages-nominal"


def test_wages_nominal_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS[WAGES_NOMINAL_CODE]
    assert len(blocks) == 8
    assert any("зарплат" in b["title"].lower() for b in blocks)


def test_wages_nominal_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS[WAGES_NOMINAL_CODE]:
        assert len(block["body"]) >= 420, (block["title"], len(block["body"]))
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_wages_nominal_seo_titles_unique() -> None:
    titles = [b["title"] for b in INDICATOR_SEO_BLOCKS[WAGES_NOMINAL_CODE]]
    assert len(titles) == len(set(titles))


def test_wages_nominal_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == WAGES_NOMINAL_CODE)
    text = ind.get("methodology") or ""
    assert len(text) > 120
    assert FORBIDDEN.search(text) is None
    assert "Росстат" in text
    assert "1991" in text or "2015" in text
