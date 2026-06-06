"""SEO-блоки и публичные тексты международных резервов."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"publicationId|datasetId|dataservice|bulk_upsert|parser|ADR-\d|element_id|mrrf_7d|\.xlsx",
    re.I,
)

INTERNATIONAL_RESERVES_CODE = "international-reserves"


def test_international_reserves_has_eight_seo_blocks() -> None:
    assert len(INDICATOR_SEO_BLOCKS[INTERNATIONAL_RESERVES_CODE]) == 8


def test_international_reserves_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS[INTERNATIONAL_RESERVES_CODE]:
        assert len(block["body"]) >= 380, (block["title"], len(block["body"]))
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_international_reserves_seo_titles_unique() -> None:
    titles = [b["title"] for b in INDICATOR_SEO_BLOCKS[INTERNATIONAL_RESERVES_CODE]]
    assert len(titles) == len(set(titles))


def test_international_reserves_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == INTERNATIONAL_RESERVES_CODE)
    text = ind.get("methodology") or ""
    assert len(text) > 80
    assert FORBIDDEN.search(text) is None
    assert re.search(r"Банк России|Банка России", text)
