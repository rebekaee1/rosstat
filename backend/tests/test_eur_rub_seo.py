"""SEO-блоки и публичные тексты карточки eur-rub."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"R01239|XML_dynamic|currency_base/daily|cbr\.ru/|bulk_upsert|parser|ADR-\d",
    re.I,
)


def test_eur_rub_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS["eur-rub"]
    assert len(blocks) == 8
    assert any("евро" in b["title"].lower() for b in blocks)


def test_eur_rub_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS["eur-rub"]:
        assert len(block["body"]) > 80
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_eur_rub_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == "eur-rub")
    text = ind["methodology"]
    assert "xml" not in text.lower()
    assert FORBIDDEN.search(text) is None
    assert "евро" in text.lower()
