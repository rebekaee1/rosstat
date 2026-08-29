"""WEO Russia cards: listed catalogue, annual modes, no platform forecast."""

from __future__ import annotations

from app.data.indicator_seo import INDICATOR_SEO_BLOCKS
from seed_data import INDICATOR_HIDDEN_FROM_LISTING, INDICATORS

WEO_LISTED = (
    "weo-gdp-usd",
    "weo-gdp-per-capita-usd",
    "weo-budget-balance-gdp",
    "weo-government-debt-gdp",
)
WEO_SIBLINGS = (
    "weo-gdp-usd-yoy",
    "weo-gdp-usd-index",
    "weo-gdp-per-capita-usd-yoy",
    "weo-gdp-per-capita-usd-index",
    "weo-budget-balance-gdp-yoy",
    "weo-government-debt-gdp-yoy",
)


def test_weo_russia_cards_not_hidden_from_listing():
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code in WEO_LISTED:
        assert code not in INDICATOR_HIDDEN_FROM_LISTING
        assert by_code[code]["is_active"] is True
        assert by_code[code]["frequency"] == "annual"


def test_weo_gdp_seed_category_and_no_platform_forecast():
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code in ("weo-gdp-usd", "weo-gdp-per-capita-usd"):
        ind = by_code[code]
        assert ind["category"] == "ВВП"
        cfg = ind.get("model_config_json") or {}
        assert int(cfg.get("forecast_steps") or 0) == 0
        assert cfg.get("forecast_strategy") in (None, "")
        assert cfg.get("forecast_strategy") != "gdp_nominal_quarterly"
    for code in ("weo-budget-balance-gdp", "weo-government-debt-gdp"):
        ind = by_code[code]
        assert ind["category"] == "Государственные финансы"
        cfg = ind.get("model_config_json") or {}
        assert int(cfg.get("forecast_steps") or 0) == 0
        assert cfg.get("forecast_strategy") in (None, "")
        assert cfg.get("forecast_strategy") != "gdp_nominal_quarterly"
    assert by_code["weo-government-debt-gdp"]["model_config_json"]["weo_code"] == (
        "GGXWDG_NGDP"
    )


def test_weo_view_mode_siblings_hidden_without_quarterly_forecast():
    by_code = {ind["code"]: ind for ind in INDICATORS}
    for code in WEO_SIBLINGS:
        assert code in INDICATOR_HIDDEN_FROM_LISTING, code
        cfg = by_code[code].get("model_config_json") or {}
        assert int(cfg.get("forecast_steps") or 0) == 0
        assert cfg.get("forecast_strategy") != "gdp_nominal_quarterly"
        assert by_code[code]["frequency"] == "annual"


def test_weo_seo_blocks_exist_and_public():
    for code in WEO_LISTED:
        blocks = INDICATOR_SEO_BLOCKS[code]
        assert len(blocks) == 6
        titles = [block["title"] for block in blocks]
        assert len(titles) == len(set(titles))
        blob = " ".join(block["body"] for block in blocks)
        assert " · " not in blob
        for token in (
            "парсер", "bulk_upsert", "ADR-", ".xlsx",
            "NGDPD", "GGXCNL", "GGXWDG",
        ):
            assert token not in blob, (code, token)
