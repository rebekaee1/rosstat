"""Справочник валют Банка России (08.11.2026): все слои получают каждую валюту."""

from __future__ import annotations

import re
from pathlib import Path

from app.data.cbr_currencies import CBR_CURRENCIES, CBR_QUOTE_UNITS
from app.data.global_market_indicators import market_indicator_codes_for_country
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
from app.data.indicator_seo import INDICATOR_SEO, INDICATOR_SEO_BLOCKS, INDICATOR_SEO_KEYWORDS
from app.data.view_model_families import FAMILY_BY_BASE
from app.services.cbr_fx_parser import CURRENCY_MAP, parse_fx_xml
from app.services.search_intent import parse_intent
from app.services.search_language import MEASURE_RULES, measure_matches
from app.services.site_paths import is_currency_indicator

ROOT = Path(__file__).resolve().parents[2]


def test_every_currency_reaches_every_layer():
    import seed_data

    seed_codes = {row["code"]: row for row in seed_data.INDICATORS}
    assert len(CBR_CURRENCIES) == 49
    for c in CBR_CURRENCIES:
        row = seed_codes[c.code]
        assert row["parser_type"] == "cbr_fx_xml" and row["category"] == "Валюты"
        assert len(row["unit"]) <= 20 and len(row["name"]) <= 200
        assert CURRENCY_MAP[c.code] == c.cbr_id
        assert c.code in FAMILY_BY_BASE
        assert c.code in INDICATOR_SEO and c.code in INDICATOR_SEO_KEYWORDS
        assert len(INDICATOR_SEO_BLOCKS[c.code]) == 8
        assert c.code in INDICATOR_COPY_EN
        assert c.code in MEASURE_RULES
        assert is_currency_indicator(c.code) and is_currency_indicator(f"{c.code}-avg-month")


def test_frontend_currency_paths_mirror_backend():
    text = (ROOT / "frontend/src/lib/sitePaths.js").read_text(encoding="utf-8")
    block = text.split("const CURRENCY_BASE_CODES", 1)[1].split("]);", 1)[0]
    front = set(re.findall(r"'([a-z]{3}-[a-z]{3})'", block))
    assert {c.code for c in CBR_CURRENCIES} <= front


def test_quote_units_scale_each_record_by_its_own_nominal():
    xml = (
        '<ValCurs><Record Date="01.01.2009" Id="R01717"><Nominal>1000</Nominal><Value>21,1200</Value></Record>'
        '<Record Date="07.11.2026" Id="R01717"><Nominal>10000</Nominal><Value>68,6004</Value></Record></ValCurs>'
    )
    points = parse_fx_xml(xml, CBR_QUOTE_UNITS["uzs-rub"])
    assert [v for _, v in points] == [211.2, 68.6004]


def test_country_page_links_its_currency():
    assert "jpy-rub" in market_indicator_codes_for_country("japan")
    assert "gbp-rub" in market_indicator_codes_for_country("united-kingdom")
    assert "try-rub" in market_indicator_codes_for_country("turkey")


def test_search_phrases_find_new_currencies():
    for query, code in (
        ("курс сума", "uzs-rub"), ("курс белорусского рубля", "byn-rub"), ("драм к рублю", "amd-rub"),
        ("курс дирхама", "aed-rub"), ("gbp rub", "gbp-rub"), ("курс австралийского доллара", "aud-rub"),
    ):
        intent = parse_intent(query, [])
        assert [group[0] for group in intent.terms] == [code], (query, intent.terms)


def test_measure_rule_separates_similar_currencies():
    gbp = (("gbp-rub",),)
    assert measure_matches(gbp, code="gbp-rub", names=("Курс фунта стерлингов",))
    assert not measure_matches(gbp, code="egp-rub", names=("Курс египетского фунта",))
    aud = (("aud-rub",),)
    assert not measure_matches(aud, code="usd-rub", names=("Курс доллара США",))


def test_r8d_travel_city_aliases_lead_to_currency():
    """Круг 8: человек в поездке ищет по городу или курорту, а не по названию валюты."""
    from app.data.cbr_currencies import search_concepts

    by_code = {codes[0]: aliases for aliases, codes in search_concepts()}
    assert "пхукет" in by_code["thb-rub"]
    assert "нячанг" in by_code["vnd-rub"]
    assert "хургада" in by_code["egp-rub"]
    assert "дубай" in by_code["aed-rub"]
