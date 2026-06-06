"""SEO-блоки и публичные тексты карточки btc-usd."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"BTCUSDT|klines|lastPrice|UTC-сутки|bulk_upsert|parser|ADR-\d",
    re.I,
)


def test_btc_usd_has_eight_seo_blocks() -> None:
    blocks = INDICATOR_SEO_BLOCKS["btc-usd"]
    assert len(blocks) == 8


def test_btc_usd_seo_blocks_public_language() -> None:
    for block in INDICATOR_SEO_BLOCKS["btc-usd"]:
        assert len(block["body"]) > 80
        assert not FORBIDDEN.search(block["body"]), block["title"]


def test_btc_usd_seed_methodology_public_language() -> None:
    ind = next(i for i in INDICATORS if i["code"] == "btc-usd")
    text = ind["methodology"]
    assert "btcusdt" not in text.lower()
    assert FORBIDDEN.search(text) is None
