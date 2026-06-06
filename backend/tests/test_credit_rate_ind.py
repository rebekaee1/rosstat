"""Конфигурация credit-rate-ind-* (CBR dataset 27)."""

from __future__ import annotations

from seed_data import INDICATORS


def _by_code(code: str) -> dict:
    for ind in INDICATORS:
        if ind["code"] == code:
            return ind
    raise AssertionError(f"{code!r} not in seed_data.INDICATORS")


def test_credit_rate_ind_short_dataservice() -> None:
    ind = _by_code("credit-rate-ind-short")
    ds = ind["model_config_json"]["dataservice"]
    assert ds["datasetId"] == 27
    assert ds["element_id"] == 7


def test_credit_rate_ind_term_element_ids() -> None:
    assert _by_code("credit-rate-ind-1to3y")["model_config_json"]["dataservice"]["element_id"] == 9
    assert _by_code("credit-rate-ind-over3y")["model_config_json"]["dataservice"]["element_id"] == 10
