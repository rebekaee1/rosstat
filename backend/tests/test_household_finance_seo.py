"""SEO-блоки и публичные тексты: кредиты и вклады населения."""

from __future__ import annotations

import re

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATORS

FORBIDDEN = re.compile(
    r"publicationId|datasetId|dataservice|bulk_upsert|parser|ADR-\d|element_id",
    re.I,
)

HOUSEHOLD_FINANCE_CODES = ("consumer-credit", "deposits-individual")


def test_household_finance_indicators_have_eight_seo_blocks() -> None:
    for code in HOUSEHOLD_FINANCE_CODES:
        blocks = INDICATOR_SEO_BLOCKS[code]
        assert len(blocks) == 8, code


def test_household_finance_seo_blocks_public_language() -> None:
    for code in HOUSEHOLD_FINANCE_CODES:
        for block in INDICATOR_SEO_BLOCKS[code]:
            assert len(block["body"]) >= 380, (code, block["title"], len(block["body"]))
            assert not FORBIDDEN.search(block["body"]), (code, block["title"])


def test_household_finance_seo_titles_unique_per_card() -> None:
    for code in HOUSEHOLD_FINANCE_CODES:
        titles = [b["title"] for b in INDICATOR_SEO_BLOCKS[code]]
        assert len(titles) == len(set(titles)), code


def test_household_finance_seo_titles_unique_across_cards() -> None:
    titles: list[str] = []
    for code in HOUSEHOLD_FINANCE_CODES:
        titles.extend(b["title"] for b in INDICATOR_SEO_BLOCKS[code])
    assert len(titles) == len(set(titles)), "shared title between consumer-credit and deposits-individual"


def test_household_finance_seo_no_duplicate_bodies_across_cards() -> None:
    seen: dict[str, str] = {}
    for code in HOUSEHOLD_FINANCE_CODES:
        for block in INDICATOR_SEO_BLOCKS[code]:
            body = block["body"].strip()
            assert body not in seen, f"{code} duplicates {seen[body]}"
            seen[body] = code


def test_household_finance_seed_methodology_public_language() -> None:
    for code in HOUSEHOLD_FINANCE_CODES:
        ind = next(i for i in INDICATORS if i["code"] == code)
        text = ind.get("methodology") or ""
        assert len(text) > 80, code
        assert FORBIDDEN.search(text) is None, code
        assert "Банк России" in text, code
