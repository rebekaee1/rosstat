"""SEO-блоки и публичные тексты карточки key-rate."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"bulk_upsert|parser|PARSER|\.xlsx|ADR-\d|forecast_strategy",
    re.I,
)


def test_key_rate_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS["key-rate"]
    assert len(blocks) == 8
    titles = [b["title"] for b in blocks]
    assert "Что такое ключевая ставка" in titles
    assert "Какой режим на графике" in titles


def test_key_rate_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS["key-rate"]:
        assert block["title"]
        assert len(block["body"]) > 80
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_key_rate_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == "key-rate")
    text = ind["methodology"]
    assert "единая база" not in text.lower()
    assert "подгружается" not in text.lower()
    assert FORBIDDEN.search(text) is None
    assert "средн" in text.lower()
