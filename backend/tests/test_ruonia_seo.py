"""SEO-блоки и публичные тексты карточки ruonia."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"hd_base|HTML-таблица|cbr\.ru/|bulk_upsert|parser|ADR-\d",
    re.I,
)


def test_ruonia_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS["ruonia"]
    assert len(blocks) == 8
    assert any(b["title"] == "Что такое RUONIA" for b in blocks)


def test_ruonia_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS["ruonia"]:
        assert len(block["body"]) > 80
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_ruonia_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == "ruonia")
    text = ind["methodology"]
    assert "html" not in text.lower()
    assert FORBIDDEN.search(text) is None
    assert "межбанк" in text.lower() or "овернайт" in text.lower()
