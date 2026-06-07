"""Tests for the calculation_engine helpers, registration, and dispatch semantics."""

import asyncio
from unittest.mock import AsyncMock

from app.data.view_model_families import iter_derived_specs
from app.services.calculation_engine import CalculationEngine, calculation_engine

# Легаси hand-written derived (не из canonical view-mode конфига). Регрессионный
# якорь: эти коды обязаны оставаться зарегистрированными независимо от конфига.
# Last bump: 2026-05-22 (Phase 1 balance-yoy-abs).
LEGACY_DERIVED = {
    "inflation-quarterly", "inflation-annual", "wages-real",
    "cpi-food-quarterly", "cpi-food-annual",
    "cpi-nonfood-quarterly", "cpi-nonfood-annual",
    "cpi-services-quarterly", "cpi-services-annual",
    "cpi-yoy", "cpi-food-yoy", "cpi-nonfood-yoy", "cpi-services-yoy",
    "cpi-qoq", "cpi-food-qoq", "cpi-nonfood-qoq", "cpi-services-qoq",
    "cpi-period-weekly", "cpi-food-period-weekly",
    "cpi-nonfood-period-weekly", "cpi-services-period-weekly",
    "cpi-period-monthly", "cpi-food-period-monthly",
    "cpi-nonfood-period-monthly", "cpi-services-period-monthly",
    "ppi-annual",
    "gdp-yoy", "gdp-qoq",
    "gdp-real-yoy", "gdp-real-qoq",
    "gdp-nominal-annual", "gdp-real-annual",
    "unemployment-quarterly", "unemployment-annual",
    "ipi-yoy",
    "exports-yoy", "imports-yoy", "ppi-yoy", "ppi-qoq", "wages-yoy",
    "exports-qoq", "imports-qoq",
    "current-account-yoy-abs", "trade-balance-yoy-abs",
    "housing-yoy-primary", "housing-yoy-secondary",
    "housing-qoq-primary", "housing-qoq-secondary",
    "wages-index", "housing-affordability", "housing-affordability-primary",
}


def test_all_derived_registered():
    """Зарегистрированы и легаси-derived, и все config-driven sibling-ряды.

    Источник истины для режимных рядов — app.data.view_model_families.
    Движок регистрирует объединение легаси + конфиг (легаси-коды, переиспользуемые
    конфигом через overrides, не дублируются — см. calculation_engine).
    """
    config_codes = {dst for dst, _src, _pipe in iter_derived_specs()}
    expected = LEGACY_DERIVED | config_codes
    registered = set(calculation_engine._derived.keys())
    assert LEGACY_DERIVED <= registered, "пропали легаси-derived"
    assert config_codes <= registered, "не зарегистрированы config-driven sibling-ряды"
    assert registered == expected


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


# --- Housing affordability ops (база 2010, помесячный ряд) -------------------

def test_wages_index_rebase_uses_base_year_from_second_series():
    """wages-index приведён к базе 2010: базовое среднее берётся из годового ряда
    (помесячный ряд начинается позже 2010), все точки делятся на это среднее."""
    from datetime import date
    from app.services import derived_ops as ops

    monthly = [(date(2015, 1, 1), 34000.0), (date(2020, 6, 1), 50000.0)]
    annual = [(date(2010, 1, 1), 20000.0), (date(2014, 1, 1), 32000.0)]
    out = dict(ops.rebase_to_index_with_base(monthly, annual, 2010))
    assert out[date(2015, 1, 1)] == round(34000.0 / 20000.0 * 100, 2)
    # без базового года в опорном ряде — пустой результат
    assert ops.rebase_to_index_with_base(monthly, annual, 1999) == []


def test_affordability_index_monthly_parity_and_frequency():
    """При общей базе 2010 (оба индекса = 100 в окрестности 2010) индекс
    доступности ≈ 100 (паритет), а сам ряд помесячный (по месяцам зарплаты)."""
    from datetime import date
    from app.services import derived_ops as ops

    # цены — квартальный индекс (база 2010=100), зарплата — помесячный индекс 2010=100
    price = [
        (date(2009, 12, 1), 100.0), (date(2010, 3, 1), 100.0),
        (date(2010, 6, 1), 100.0), (date(2010, 9, 1), 100.0),
        (date(2010, 12, 1), 100.0),
    ]
    wage = [(date(2010, m, 1), 100.0) for m in range(1, 13)]
    aff = ops.affordability_index_monthly(price, wage)
    # помесячный: 12 точек за 2010 год
    assert len(aff) == 12
    months = [d.month for d, _ in aff]
    assert months == list(range(1, 13))
    # паритет: в базовом году ≈ 100
    for _d, v in aff:
        assert abs(v - 100.0) < 0.01
    # forward-fill квартальной цены: месяц без своего квартала берёт предыдущий
    price_ff = [(date(2010, 1, 1), 100.0), (date(2010, 4, 1), 200.0)]
    wage_ff = [(date(2010, 2, 1), 100.0), (date(2010, 3, 1), 100.0), (date(2010, 5, 1), 100.0)]
    out = dict(ops.affordability_index_monthly(price_ff, wage_ff))
    assert out[date(2010, 2, 1)] == 100.0   # квартал Q1 (цена 100)
    assert out[date(2010, 5, 1)] == 50.0    # квартал Q2 (цена 200) → 100/200*100
