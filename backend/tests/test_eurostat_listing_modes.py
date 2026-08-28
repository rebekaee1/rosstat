"""Редакторские режимы listing: full_ok / headline_ok / no."""

from __future__ import annotations

from app.data.eurostat_listing import (
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
    """M2: скоростные ряды HICP скрыты — уровень + матрица режимов покрывают смысл.

    Индексная карточка prc_hicp_midx (I15) сама считает yoy/step по частотам;
    отдельные датасеты темпов дают экономисту 3-4 одноимённые строки и
    размывают SEO.
    """
    for ds in ("prc_hicp_manr", "prc_hicp_mmor", "prc_hicp_mv12r", "prc_hicp_cann"):
        assert listing_mode_for_dataset(ds) == "no", ds
        entry = load_listing_decisions()[ds]
        assert entry["listable"] is False
        assert entry["reason"], ds

    # индексный уровень остаётся на витрине: канонический набор закреплён full_ok
    assert listing_mode_for_dataset("prc_hicp_midx") == "full_ok"


def test_listing_decisions_hicp_duplicates_hidden():
    """M9-регресс: имена-дубликаты канонического HICP скрыты, midx возвращён.

    prc_hicp_minr/fpd/ct имели то же публичное имя («…индекс (2015 = 100)»),
    но большую глубину точек — dedupe_display_names оставлял их на витрине,
    а канонический prc_hicp_midx (курится концепт-слоем hicp-index) вытеснял.
    cmon — темп при постоянных налогах, дубль вычисляемого режима.
    """
    dec = load_listing_decisions()
    for ds in ("prc_hicp_minr", "prc_hicp_fpd", "prc_hicp_ct", "prc_hicp_cmon"):
        assert listing_mode_for_dataset(ds) == "no", ds
        assert dec[ds]["listable"] is False
        assert dec[ds]["reason"], ds

    # канонический индекс явно закреплён полным режимом
    assert listing_mode_for_dataset("prc_hicp_midx") == "full_ok"
    # содержательный срез при постоянных налогах остаётся
    assert listing_mode_for_dataset("prc_hicp_cind") == "full_ok"
    # flash-оценки prc_hicp_fp (другое имя) не затронуты
    assert listing_mode_for_dataset("prc_hicp_fp") is None


def test_variant_group_key_house_price_stem_alias():
    """M3б: prc_hpi_* и ei_hppi_q — одна variant-группа (индекс цен на жильё)."""
    alias_group = variant_group_key(country_id=7, dataset_id="ei_hppi_q")
    assert variant_group_key(country_id=7, dataset_id="prc_hpi_q") == alias_group
    assert variant_group_key(country_id=7, dataset_id="prc_hpi_a") == alias_group

    # prc_hpi_ooq — свой стем (жильё собственников), вне алиаса
    assert variant_group_key(country_id=7, dataset_id="prc_hpi_ooq") != alias_group

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
