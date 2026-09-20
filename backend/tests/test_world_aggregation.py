"""Трёхуровневая политика агрегации мировых рядов: curated → passport → fallback."""

from __future__ import annotations

from app.data.world_aggregation import (
    aggregation_decision_for,
    aggregation_policy_for,
    reset_passport_policy_cache,
)


class _Ind:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_curated_policy_still_wins():
    decision = aggregation_decision_for(_Ind(dataset_id="prc_hicp_midx", unit="I15"))
    assert decision.policy == "mean"
    assert decision.source == "curated"
    assert aggregation_policy_for(_Ind(dataset_id="nrg_cb_em", unit="GWH")) == "sum"


def test_passport_policy_from_yaml():
    reset_passport_policy_cache()
    payrolls = aggregation_decision_for(
        _Ind(provider="fred", dataset_id="PAYEMS", unit="THOUSANDS"),
    )
    assert payrolls.policy == "mean"
    assert payrolls.source == "passport"

    retail = aggregation_decision_for(
        _Ind(provider="fred", dataset_id="RSAFS", unit="USD_MN"),
    )
    assert retail.policy == "sum"
    assert retail.source == "passport"

    gdp = aggregation_decision_for(
        _Ind(provider="fred", dataset_id="GDPC1", unit="USD_BN_CHAINED"),
    )
    assert gdp.policy == "mean"
    assert gdp.source == "passport"

    money = aggregation_decision_for(
        _Ind(provider="boc_valet", dataset_id="V41552798", unit="CAD_MN"),
    )
    assert money.policy == "last"
    assert money.source == "passport"


def test_fallback_flow_sum_and_index_mean():
    flow = aggregation_decision_for(
        _Ind(provider="eurostat", dataset_id="ext_fake_m", unit="MIO_EUR"),
    )
    assert flow.policy == "sum"
    assert flow.source == "fallback"

    idx = aggregation_decision_for(
        _Ind(provider="eurostat", dataset_id="unknown_idx_m", unit="I15"),
    )
    assert idx.policy == "mean"
    assert idx.source == "fallback"

    stock = aggregation_decision_for(
        _Ind(provider="eurostat", dataset_id="nrg_stk_oam", unit="THS_T"),
    )
    assert stock.policy == "last"
    assert stock.source == "fallback"


def test_fallback_always_returns_a_policy():
    decision = aggregation_decision_for(_Ind(dataset_id="zz_unknown", unit=""))
    assert decision.policy == "mean"
    assert decision.source == "fallback"
    assert aggregation_policy_for(_Ind()) == "mean"


def test_invalid_passport_key_falls_back():
    reset_passport_policy_cache()
    # Нет такого ключа в YAML — не падаем, берём семантический фолбэк.
    decision = aggregation_decision_for(
        _Ind(provider="fred", dataset_id="NOT_A_SERIES", unit="INDEX"),
    )
    assert decision.source == "fallback"
    assert decision.policy == "mean"


def test_curated_empty_unit_covers_localized_unit_label():
    decision = aggregation_decision_for(
        _Ind(dataset_id="nrg_cb_cosm", unit="тыс. баррелей"),
    )
    assert decision.policy == "sum"
    assert decision.source == "curated"
