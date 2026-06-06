"""Конфигурация auto-loan-rate после переразкладки CBR dataset 28 (2025-12)."""

from __future__ import annotations

from seed_data import INDICATORS


def _by_code(code: str) -> dict:
    for ind in INDICATORS:
        if ind["code"] == code:
            return ind
    raise AssertionError(f"{code!r} not in seed_data.INDICATORS")


def test_auto_loan_rate_dataservice_element_110() -> None:
    ind = _by_code("auto-loan-rate")
    ds = ind["model_config_json"]["dataservice"]
    assert ds["publicationId"] == 14
    assert ds["datasetId"] == 28
    assert ds["element_id"] == 110
    assert ind.get("methodology")


def test_auto_loan_rate_monthly_percentage() -> None:
    ind = _by_code("auto-loan-rate")
    assert ind["frequency"] == "monthly"
    assert ind["unit"] == "%"
    assert ind["parser_type"] == "cbr_dataservice_json"
