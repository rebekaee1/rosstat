"""Конфигурация deposit-rate* (CBR publication 18, dataset 37)."""

from __future__ import annotations

from seed_data import INDICATORS


def _by_code(code: str) -> dict:
    for ind in INDICATORS:
        if ind["code"] == code:
            return ind
    raise AssertionError(f"{code!r} not in seed_data.INDICATORS")


def test_deposit_rate_short_dataservice() -> None:
    ind = _by_code("deposit-rate")
    ds = ind["model_config_json"]["dataservice"]
    assert ds["publicationId"] == 18
    assert ds["datasetId"] == 37
    assert ds["element_id"] == 7


def test_deposit_rate_term_element_ids() -> None:
    assert _by_code("deposit-rate-medium")["model_config_json"]["dataservice"]["element_id"] == 9
    assert _by_code("deposit-rate-long")["model_config_json"]["dataservice"]["element_id"] == 10
