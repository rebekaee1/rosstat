"""Редакторские режимы listing: full_ok / headline_ok / no."""

from __future__ import annotations

from app.data.eurostat_listing import (
    is_derived_change_unit,
    is_headline_aggregate_slice,
    listing_mode_for_dataset,
    load_listing_decisions,
    variant_group_key,
    varying_narrowing_dims,
)


def test_listing_decisions_loaded():
    dec = load_listing_decisions()
    assert len(dec) >= 1000
    assert listing_mode_for_dataset("demo_fabort") == "no"
    assert listing_mode_for_dataset("isoc_bde15ar2") in {"full_ok", "headline_ok"}


def test_listing_decisions_hicp_rates_hidden():
    """Скоростные ряды HICP скрыты — уровень + матрица режимов покрывают смысл.

    Живая индексная карточка prc_hicp_minr (I15, ECOICOP ver.2) считает
    yoy/step по частотам; замороженные manr/mmor/mv12r — отдельные датасеты.
    """
    for ds in ("prc_hicp_manr", "prc_hicp_mmor", "prc_hicp_mv12r", "prc_hicp_cann"):
        assert listing_mode_for_dataset(ds) == "no", ds
        entry = load_listing_decisions()[ds]
        assert entry["listable"] is False
        assert entry["reason"], ds

    assert listing_mode_for_dataset("prc_hicp_minr") == "full_ok"
    assert listing_mode_for_dataset("prc_hicp_midx") == "no"


def test_listing_decisions_hicp_duplicates_hidden():
    """Преемник ECOICOP ver.2 на витрине; замороженные наборы сняты.

    prc_hicp_minr — канон. Замороженные midx/aind/fp и короткие main table
    tec00118/teicp000 не дают вторую плитку ГИПЦ.
    """
    dec = load_listing_decisions()
    for ds in (
        "prc_hicp_midx", "prc_hicp_aind", "prc_hicp_fp",
        "prc_hicp_fpd", "prc_hicp_ct", "prc_hicp_cmon",
        "tec00118", "teicp000",
    ):
        assert listing_mode_for_dataset(ds) == "no", ds
        assert dec[ds]["listable"] is False
        assert dec[ds]["reason"], ds

    assert listing_mode_for_dataset("prc_hicp_minr") == "full_ok"
    assert listing_mode_for_dataset("prc_hicp_ainr") == "full_ok"
    assert listing_mode_for_dataset("prc_hicp_cind") == "no"
    assert listing_mode_for_dataset("prc_hicp_cmon") == "no"
    assert listing_mode_for_dataset("prc_hicp_cann") == "no"


def test_variant_group_key_house_price_stem_alias():
    """M3б: prc_hpi_* и ei_hppi_q — одна variant-группа (индекс цен на жильё)."""
    alias_group = variant_group_key(country_id=7, dataset_id="ei_hppi_q")
    assert variant_group_key(country_id=7, dataset_id="prc_hpi_q") == alias_group
    assert variant_group_key(country_id=7, dataset_id="prc_hpi_a") == alias_group

    # prc_hpi_ooq — свой стем (жильё собственников), вне алиаса
    assert variant_group_key(country_id=7, dataset_id="prc_hpi_ooq") != alias_group

    # темпы ГИПЦ — не срезы variant-пикера
    assert variant_group_key(country_id=7, dataset_id="prc_hicp_manr") != variant_group_key(
        country_id=7, dataset_id="prc_hicp_midx"
    )
    assert is_derived_change_unit("RCH_A")
    assert is_derived_change_unit("RCH_M")
    assert is_derived_change_unit("RCH_MV12MAVR")
    assert not is_derived_change_unit("I15")
    assert not is_derived_change_unit("I25")

    # чужие семьи не затронуты; страны не смешиваются
    assert variant_group_key(country_id=1, dataset_id="une_rt_m") == (1, "une_rt")
    assert variant_group_key(country_id=8, dataset_id="prc_hpi_q")[0] == 8


def test_varying_dims_ignore_constant_identity():
    slices = [
        {"age": "TOTAL", "sex": "T", "wstatus": "EMP", "freq": "A"},
        {"age": "TOTAL", "sex": "T", "wstatus": "EMP", "freq": "A"},
    ]
    assert varying_narrowing_dims(slices) == frozenset()
    assert is_headline_aggregate_slice(
        slices[0], varying_dims=varying_narrowing_dims(slices)
    )


def test_headline_requires_total_on_varying_age():
    slices = [
        {"age": "Y3", "sex": "T", "freq": "A"},
        {"age": "Y4", "sex": "T", "freq": "A"},
        {"age": "TOTAL", "sex": "T", "freq": "A"},
    ]
    varying = varying_narrowing_dims(slices)
    assert "age" in varying
    assert is_headline_aggregate_slice(slices[2], varying_dims=varying)
    assert not is_headline_aggregate_slice(slices[0], varying_dims=varying)
