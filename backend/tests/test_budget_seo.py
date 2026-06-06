"""SEO-блоки и публичные тексты карточек федерального бюджета."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"budget_target|minfin_budget|bulk_upsert|parser|ADR-\d|\.csv",
    re.I,
)

BUDGET_CODES = ("budget-deficit", "budget-revenue", "budget-expenditure")


def test_budget_indicators_have_eight_seo_blocks() -> None:
    for code in BUDGET_CODES:
        blocks = INDICATOR_SEO_BLOCKS[code]
        assert len(blocks) == 8, code


def test_budget_seo_blocks_public_language() -> None:
    for code in BUDGET_CODES:
        for block in INDICATOR_SEO_BLOCKS[code]:
            assert len(block["body"]) >= 100, (code, block["title"], len(block["body"]))
            assert not FORBIDDEN.search(block["body"]), (code, block["title"])


def test_budget_seo_titles_unique_per_card() -> None:
    for code in BUDGET_CODES:
        titles = [b["title"] for b in INDICATOR_SEO_BLOCKS[code]]
        assert len(titles) == len(set(titles)), code


def test_budget_seo_no_duplicate_bodies_across_cards() -> None:
    seen: dict[str, str] = {}
    for code in BUDGET_CODES:
        for block in INDICATOR_SEO_BLOCKS[code]:
            body = block["body"].strip()
            assert body not in seen, f"{code} duplicates {seen[body]}"
            seen[body] = code


def test_budget_seed_methodology_public_language() -> None:
    for code in BUDGET_CODES:
        ind = next(i for i in INDICATORS if i["code"] == code)
        text = ind.get("methodology") or ""
        assert len(text) > 80, code
        assert FORBIDDEN.search(text) is None, code
        assert "Минфин" in text, code
