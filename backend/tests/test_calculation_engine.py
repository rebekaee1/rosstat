"""Tests for the calculation_engine helpers, registration, and dispatch semantics."""

import asyncio
from unittest.mock import AsyncMock

from app.services.calculation_engine import CalculationEngine, calculation_engine


def test_all_derived_registered():
    """Verify all expected derived indicators are registered."""
    expected = {
        "inflation-quarterly", "inflation-annual", "wages-real",
        "cpi-food-quarterly", "cpi-food-annual",
        "cpi-nonfood-quarterly", "cpi-nonfood-annual",
        "cpi-services-quarterly", "cpi-services-annual",
        "ppi-annual",
        "gdp-yoy", "gdp-qoq", "gdp-real-annual",
        "unemployment-quarterly", "unemployment-annual",
        "current-account-yoy", "ipi-yoy",
        "exports-yoy", "imports-yoy", "ppi-yoy", "wages-yoy",
        "exports-qoq", "imports-qoq",
        "housing-yoy-primary", "housing-yoy-secondary",
    }
    assert set(calculation_engine._derived.keys()) == expected


def test_derived_sources_exist():
    for code, (sources, fn) in calculation_engine._derived.items():
        assert len(sources) > 0, f"{code} has no sources"
        assert callable(fn), f"{code} fn is not callable"


def test_run_for_updated_sources_recomputes_every_derived_when_any_source_changed(monkeypatch):
    """ADR-0002: derived series always reflect the current source state.

    Before this fix, only derived whose source code intersected `source_codes`
    were recomputed. Any source revised in place (records_updated > 0 but
    records_added == 0) silently skipped its derived. This test guards the
    new dispatch rule: as long as the ETL batch was non-empty, every derived
    is recomputed end-to-end — irrespective of which source codes were in
    the batch.
    """
    engine = CalculationEngine()
    calls: dict[str, int] = {"a": 0, "b": 0, "c": 0}

    async def fn_a(_db):
        calls["a"] += 1
        return 0

    async def fn_b(_db):
        calls["b"] += 1
        return 0

    async def fn_c(_db):
        calls["c"] += 1
        return 0

    engine.register("a", ["src1"], fn_a)
    engine.register("b", ["src2"], fn_b)
    engine.register("c", ["src3"], fn_c)

    monkeypatch.setattr(
        "app.services.calculation_engine.cache_invalidate_indicator",
        AsyncMock(),
    )

    result = asyncio.run(
        engine.run_for_updated_sources(db=None, source_codes=["src1"])
    )

    assert calls == {"a": 1, "b": 1, "c": 1}
    assert result == []


def test_run_for_updated_sources_short_circuits_on_empty_batch(monkeypatch):
    """If no source updated at all, skip derived entirely — there's nothing to derive from."""
    engine = CalculationEngine()
    calls: dict[str, int] = {"a": 0}

    async def fn_a(_db):
        calls["a"] += 1
        return 0

    engine.register("a", ["src1"], fn_a)
    monkeypatch.setattr(
        "app.services.calculation_engine.cache_invalidate_indicator",
        AsyncMock(),
    )

    result = asyncio.run(
        engine.run_for_updated_sources(db=None, source_codes=[])
    )

    assert calls == {"a": 0}
    assert result == []


def test_run_for_updated_sources_returns_only_codes_with_actual_changes(monkeypatch):
    """`updated` list reflects derived whose values actually changed (n > 0)."""
    engine = CalculationEngine()

    async def fn_no_change(_db):
        return 0

    async def fn_changed(_db):
        return 7

    engine.register("noop", ["src1"], fn_no_change)
    engine.register("changed", ["src1"], fn_changed)

    invalidate = AsyncMock()
    monkeypatch.setattr(
        "app.services.calculation_engine.cache_invalidate_indicator",
        invalidate,
    )

    result = asyncio.run(
        engine.run_for_updated_sources(db=None, source_codes=["src1"])
    )

    assert result == ["changed"]
    invalidate.assert_awaited_once_with("changed")


def test_run_for_updated_sources_isolates_failures(monkeypatch):
    """One failing derived must not stop the rest from being computed."""
    engine = CalculationEngine()
    calls: dict[str, int] = {"good": 0, "bad": 0, "after": 0}

    async def fn_good(_db):
        calls["good"] += 1
        return 0

    async def fn_bad(_db):
        calls["bad"] += 1
        raise RuntimeError("boom")

    async def fn_after(_db):
        calls["after"] += 1
        return 0

    engine.register("good", ["s"], fn_good)
    engine.register("bad", ["s"], fn_bad)
    engine.register("after", ["s"], fn_after)

    monkeypatch.setattr(
        "app.services.calculation_engine.cache_invalidate_indicator",
        AsyncMock(),
    )

    result = asyncio.run(
        engine.run_for_updated_sources(db=None, source_codes=["s"])
    )

    assert calls == {"good": 1, "bad": 1, "after": 1}
    assert result == []
