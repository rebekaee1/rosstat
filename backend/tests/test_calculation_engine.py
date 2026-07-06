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
    "housing-annual-primary", "housing-annual-secondary",
    "wages-index", "housing-affordability", "housing-affordability-primary",
    # Годовой ряд зарплаты 1991+ = immutable исторический хвост + annual mean
    # месячного (annual_mean_with_prefix). Ранее заливался one-shot скриптом,
    # теперь движок продолжает ряд сам при закрытии года (2026-07).
    "wages-nominal-annual",
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


def test_run_for_updated_sources_recomputes_dependents_closure(monkeypatch):
    """П-2: пересчитывается транзитивное замыкание зависимых, не весь реестр.

    Семантика ADR-0002 сохраняется, потому что парсеры включают в
    `source_codes` и добавления, и in-place ревизии (П-3: `bulk_upsert`
    возвращает точные added/updated, `run_etl_for_indicator` возвращает
    status == success). Незатронутый source не меняет свои derived по
    определению чистых op'ов — их пересчёт был пустой тратой CPU.
    """
    engine = CalculationEngine()
    calls: dict[str, int] = {"a": 0, "b": 0, "c": 0, "deep": 0}

    def fn(name):
        async def _fn(_db):
            calls[name] += 1
            return 0
        return _fn

    engine.register("a", ["src1"], fn("a"))
    engine.register("b", ["src2"], fn("b"))
    engine.register("c", ["src3"], fn("c"))
    engine.register("deep", ["a"], fn("deep"))  # derived-от-derived

    monkeypatch.setattr(
        "app.services.calculation_engine.cache_invalidate_indicator",
        AsyncMock(),
    )

    result = asyncio.run(
        engine.run_for_updated_sources(db=None, source_codes=["src1"])
    )

    # src1 → a → deep; b и c не зависят от src1 и не пересчитываются
    assert calls == {"a": 1, "b": 0, "c": 0, "deep": 1}
    assert result == []


def test_dependents_closure_is_topologically_ordered():
    """Р-1: цепочка derived-от-derived считается в порядке зависимости —
    зависимый всегда после своего derived-источника, при любом порядке
    регистрации."""
    engine = CalculationEngine()

    async def noop(_db):
        return 0

    # Регистрируем НАМЕРЕННО в обратном порядке зависимости
    engine.register("lvl3", ["lvl2"], noop)
    engine.register("lvl2", ["lvl1"], noop)
    engine.register("lvl1", ["src"], noop)
    engine.register("unrelated", ["other-src"], noop)

    order = engine.dependents_closure_topo(["src"])
    assert order == ["lvl1", "lvl2", "lvl3"]
    assert "unrelated" not in order


def test_real_registry_topo_invariant():
    """На реальном реестре: каждый derived-источник встречается в topo-выдаче
    раньше своих зависимых (28 цепочек глубиной до 4 уровней)."""
    all_sources = sorted({
        s for (srcs, _fn) in calculation_engine._derived.values() for s in srcs
    })
    order = calculation_engine.dependents_closure_topo(all_sources)
    # замыкание всех источников = весь реестр
    assert set(order) == set(calculation_engine._derived.keys())
    pos = {code: i for i, code in enumerate(order)}
    for code, (srcs, _fn) in calculation_engine._derived.items():
        for s in srcs:
            if s in pos:  # source сам является derived
                assert pos[s] < pos[code], (
                    f"{code} посчитается раньше своего derived-источника {s}"
                )


def test_direct_dependents_delegates_to_closure(monkeypatch):
    """run_for_direct_dependents теперь включает транзитивные уровни:
    replace_series-источник (Минфин) тянет и глубоких зависимых."""
    engine = CalculationEngine()
    calls: dict[str, int] = {"direct": 0, "transitive": 0}

    def fn(name, n=0):
        async def _fn(_db):
            calls[name] += 1
            return n
        return _fn

    engine.register("direct", ["budget-revenue"], fn("direct", n=2))
    engine.register("transitive", ["direct"], fn("transitive"))

    invalidate = AsyncMock()
    monkeypatch.setattr(
        "app.services.calculation_engine.cache_invalidate_indicator",
        invalidate,
    )

    result = asyncio.run(
        engine.run_for_direct_dependents(db=None, source_codes=["budget-revenue"])
    )
    assert calls == {"direct": 1, "transitive": 1}
    assert result == ["direct"]


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


def test_run_for_direct_dependents_only_touches_matching_sources(monkeypatch):
    """Каскад после одного source — только прямые dependent-derived."""
    engine = CalculationEngine()
    calls: dict[str, int] = {"a": 0, "b": 0, "c": 0}

    async def fn_a(_db):
        calls["a"] += 1
        return 2

    async def fn_b(_db):
        calls["b"] += 1
        return 0

    async def fn_c(_db):
        calls["c"] += 1
        return 0

    engine.register("a", ["budget-revenue"], fn_a)
    engine.register("b", ["budget-revenue", "other"], fn_b)
    engine.register("c", ["gdp-nominal"], fn_c)

    invalidate = AsyncMock()
    monkeypatch.setattr(
        "app.services.calculation_engine.cache_invalidate_indicator",
        invalidate,
    )

    result = asyncio.run(
        engine.run_for_direct_dependents(db=None, source_codes=["budget-revenue"])
    )

    assert calls == {"a": 1, "b": 1, "c": 0}
    assert result == ["a"]


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
    """Зарплата сглаживается скользящей средней за 12 мес ДО деления (убирает
    скачки от премий). При общей базе 2010 индекс доступности ≈ 100 (паритет);
    ряд помесячный, начинается с месяца, у которого набралось 12 мес. зарплаты."""
    from datetime import date
    from app.services import derived_ops as ops

    # цены — квартальный индекс (база 2010=100); зарплата — помесячный индекс,
    # 2 полных года, чтобы скользящая средняя за 12 мес дала точки.
    price = [
        (date(y, mo, 1), 100.0)
        for y in (2010, 2011)
        for mo in (3, 6, 9, 12)
    ] + [(date(2009, 12, 1), 100.0)]
    wage = [(date(y, m, 1), 100.0) for y in (2010, 2011) for m in range(1, 13)]
    aff = ops.affordability_index_monthly(price, wage)
    # rolling-12m: первые 11 месяцев 2010 отбрасываются (нет полного окна).
    # Остаётся декабрь 2010 + все 12 месяцев 2011 = 13 точек.
    assert len(aff) == 13
    assert aff[0][0] == date(2010, 12, 1)
    # паритет: при ровной зарплате 100 и цене 100 доступность = 100
    for _d, v in aff:
        assert abs(v - 100.0) < 0.01

    # Сглаживание гасит разовый всплеск зарплаты (премия): сырое деление дало бы
    # резкий скачок, после rolling-12m — мягкий.
    wage_spike = []
    for y in (2010, 2011):
        for m in range(1, 13):
            val = 100.0
            if y == 2011 and m == 12:
                val = 220.0  # «премия» в декабре
            wage_spike.append((date(y, m, 1), val))
    price_flat = [
        (date(y, mo, 1), 100.0) for y in (2010, 2011) for mo in (3, 6, 9, 12)
    ]
    out = dict(ops.affordability_index_monthly(price_flat, wage_spike))
    # декабрь 2011: среднее за 12 мес = (100*11 + 220)/12 ≈ 110 → доступность ≈ 110,
    # а не 220 (как было бы при сыром значении).
    assert abs(out[date(2011, 12, 1)] - 110.0) < 0.5
