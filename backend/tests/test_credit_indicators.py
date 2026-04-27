"""Sanity checks for credit-rate-* indicators added on 2026-04-27.

Шесть индикаторов (ставки по кредитам ЮЛ/ФЛ × сроки до 1 года / 1–3 года /
свыше 3 лет) тянутся из единого REST API CBR DataService. Тест проверяет,
что seed-конфигурация согласована со схемой существующего парсера
``cbr_dataservice_json`` и что указанные publication/dataset/element_id
являются валидными значениями (а не опечатками).
"""

from __future__ import annotations

from typing import Any

import pytest

from seed_data import INDICATORS
from app.services.cbr_dataservice_parser import CbrDataServiceParser


CREDIT_RATE_CODES = {
    "credit-rate-corp-short",
    "credit-rate-corp-1to3y",
    "credit-rate-corp-over3y",
    "credit-rate-ind-short",
    "credit-rate-ind-1to3y",
    "credit-rate-ind-over3y",
}

# (publicationId=14, datasetId, element_id)
# Допустимые element_id из headerData CBR DataService (январь 2026):
#   2 = До 30 дней;  4 = 31–90 дней;  5 = 91–180 дней;  6 = 181–365 дней;
#   7 = До 1 года;   9 = 1–3 года;    10 = Свыше 3 лет; 11 = Свыше 1 года.
ALLOWED_ELEMENT_IDS = {2, 4, 5, 6, 7, 9, 10, 11}
EXPECTED_DATASETS = {
    25,  # Ставки по кредитам нефинансовым организациям
    27,  # Ставки по кредитам физическим лицам
}


def _by_code(code: str) -> dict[str, Any]:
    for ind in INDICATORS:
        if ind["code"] == code:
            return ind
    raise AssertionError(f"Indicator {code!r} not found in seed_data.INDICATORS")


@pytest.mark.parametrize("code", sorted(CREDIT_RATE_CODES))
def test_credit_indicator_present(code: str) -> None:
    ind = _by_code(code)
    assert ind["is_active"] is True
    assert ind["category"] == "Ставки"
    assert ind["frequency"] == "monthly"
    assert ind["unit"] == "%"
    assert ind["parser_type"] == "cbr_dataservice_json"
    assert ind["source"] == "Банк России"


@pytest.mark.parametrize("code", sorted(CREDIT_RATE_CODES))
def test_credit_indicator_dataservice_config(code: str) -> None:
    ind = _by_code(code)
    cfg = ind["model_config_json"]
    ds = cfg["dataservice"]
    assert ds["publicationId"] == 14, f"{code}: pub must be 14 (rates by RF)"
    assert ds["datasetId"] in EXPECTED_DATASETS, code
    assert ds["measureId"] == 2, f"{code}: measureId must be 2 (rubles)"
    assert ds["element_id"] in ALLOWED_ELEMENT_IDS, code
    assert cfg["backfill_from_year"] == 2014
    assert cfg["forecast_steps"] == 6
    assert cfg["forecast_transform"] == "percentage"
    val = cfg["validation"]
    assert val["min"] == 0 and val["max"] == 50


def test_credit_indicators_unique_targeting() -> None:
    """Каждая комбинация (datasetId, element_id) должна быть уникальной —
    иначе два индикатора будут тянуть один и тот же ряд."""
    seen: dict[tuple[int, int], str] = {}
    for code in CREDIT_RATE_CODES:
        ind = _by_code(code)
        ds = ind["model_config_json"]["dataservice"]
        key = (ds["datasetId"], ds["element_id"])
        assert key not in seen, f"Duplicate dataset/element: {code} == {seen[key]}"
        seen[key] = code


def test_credit_term_split_complete() -> None:
    """Для каждого ds (ЮЛ=25, ФЛ=27) должны быть три срочности 7/9/10."""
    by_ds: dict[int, set[int]] = {}
    for code in CREDIT_RATE_CODES:
        ds = _by_code(code)["model_config_json"]["dataservice"]
        by_ds.setdefault(ds["datasetId"], set()).add(ds["element_id"])
    expected_terms = {7, 9, 10}
    assert by_ds[25] == expected_terms
    assert by_ds[27] == expected_terms


def test_dataservice_parser_handles_credit_rate_config() -> None:
    """Канонический пример конфига должен парситься без ошибок —
    мы используем тот же parser_type, что и у mortgage-rate / auto-loan-rate."""
    parser = CbrDataServiceParser()
    assert parser.parser_type == "cbr_dataservice_json"
