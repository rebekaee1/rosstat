"""Конфигурация credit-rate-corp-* (CBR dataset 25, publication 14)."""

from __future__ import annotations

from seed_data import INDICATORS


def _by_code(code: str) -> dict:
    for ind in INDICATORS:
        if ind["code"] == code:
            return ind
    raise AssertionError(f"{code!r} not in seed_data.INDICATORS")


def test_credit_rate_corp_short_dataservice() -> None:
    ind = _by_code("credit-rate-corp-short")
    ds = ind["model_config_json"]["dataservice"]
    assert ds["publicationId"] == 14
    assert ds["datasetId"] == 25
    assert ds["element_id"] == 7
    assert ind["frequency"] == "monthly"
    assert ind["unit"] == "%"


def test_credit_rate_corp_term_slices_element_ids() -> None:
    assert _by_code("credit-rate-corp-1to3y")["model_config_json"]["dataservice"]["element_id"] == 9
    assert _by_code("credit-rate-corp-over3y")["model_config_json"]["dataservice"]["element_id"] == 10
