"""Редакторские режимы listing: full_ok / headline_ok / no."""

from __future__ import annotations

from app.data.eurostat_listing import (
    is_headline_aggregate_slice,
    listing_mode_for_dataset,
    load_listing_decisions,
    varying_narrowing_dims,
)


def test_listing_decisions_loaded():
    dec = load_listing_decisions()
    assert len(dec) >= 1000
    assert listing_mode_for_dataset("demo_fabort") == "no"
    assert listing_mode_for_dataset("isoc_bde15ar2") in {"full_ok", "headline_ok"}


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
