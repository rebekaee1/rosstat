"""Typed semantics derive from registered pipelines and native price units."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from sqlalchemy import column, literal, select
from sqlalchemy.dialects import postgresql

from app.services.search import (
    _bespoke_mode_metadata, _family_metadata, _family_price_evidence,
    _registered_price_codes, _result_measure_names, _world_lexical,
    _world_mode_metadata,
)
from app.services.search_intent import SearchIntent, match_score, parse_intent


def test_terminal_registered_period_last_establishes_eop_only():
    metadata = _family_metadata()
    assert "search-mode-eop" in metadata["natural-gas-eop-year"]
    assert "search-freq-annual" in metadata["natural-gas-eop-year"]
    assert "search-mode-eop" not in metadata["natural-gas-yoy-year"]
    assert "search-mode-eop" not in metadata["natural-gas-avg-year"]
    assert "search-mode-eop" not in metadata["gdp-nominal"]


def test_registered_source_frequency_is_distinct_from_output_frequency():
    metadata = _family_metadata()["natural-gas-eop-year"]
    assert "search-source-freq-daily" in metadata
    assert "search-freq-annual" in metadata
    assert "search-source-freq-annual" not in metadata
    intent = replace(parse_intent("sample", []), terms=(("search-source-freq-daily",), ("search-freq-annual",)))
    assert match_score(intent, names=("sample",), metadata=metadata) is not None
    assert match_score(intent, names=("sample",), metadata="search-freq-annual") is None


@pytest.mark.parametrize("unit", ["USD/т", "USD/млн БТЕ", "USD/унция", "руб./г"])
def test_price_evidence_requires_registered_commodity_and_physical_quotient(unit):
    family = SimpleNamespace(unit=unit, category="Товарные рынки")
    assert _family_price_evidence(family)
    assert not _family_price_evidence(SimpleNamespace(unit=unit, category="ВВП"))
    assert not _family_price_evidence(SimpleNamespace(unit="USD", category="Товарные рынки"))
    assert not _family_price_evidence(SimpleNamespace(unit="USD/person", category="Товарные рынки"))
    assert not _family_price_evidence(SimpleNamespace(unit="tonne", category="Товарные рынки"))


def test_price_final_guard_uses_actual_registered_family_never_code_prefix():
    codes = _registered_price_codes()
    assert "soybean-yoy-year" in codes
    assert "natural-gas-eop-year" in codes
    assert "silver" in codes
    assert "usd-index" not in codes
    assert "soybean-magical" not in codes
    item = {"kind": "russia", "code": "soybean-yoy-year", "name_en": "Soybeans"}
    assert _result_measure_names(item, {})[-1] == "price"
    assert "price" not in _result_measure_names({**item, "code": "soybean-magical"}, {})
    assert "price" not in _result_measure_names({**item, "kind": "subnational_indicator"}, {})


def test_bespoke_mode_uses_exact_existing_canonical_mapping():
    mapping = _bespoke_mode_metadata()
    assert mapping["inflation-annual"] == "search-mode-yoy"
    assert mapping["housing-qoq-primary"] == "search-mode-pop"
    assert "inflation-magical" not in mapping
    assert "cpi-period-monthly" not in mapping


def test_world_eop_needs_native_label_and_never_code_suffix():
    assert "search-mode-eop" in _world_mode_metadata(SimpleNamespace(
        name_ru="", name_en="Inventory at end of year", code="native", frequency="annual"))
    assert "search-mode-eop" in _world_mode_metadata(SimpleNamespace(
        name_ru="", name_en="Inventory at end-of-period", code="native", frequency="annual"))
    assert "search-mode-eop" not in _world_mode_metadata(SimpleNamespace(
        name_ru="", name_en="Average inventory", code="native-eop", frequency="annual"))
    intent = replace(parse_intent("sample", []), terms=(("search-mode-eop",),))
    sql = str(select(literal(1)).where(*_world_lexical(intent, postgres=True)).compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "end of year" in sql
    assert "world_indicators.code" not in sql


@pytest.mark.parametrize("key", ["current-prices", "constant-prices"])
def test_valuation_unit_sql_python_parity_with_conflicts_and_missing_evidence(key):
    from sqlalchemy import Column, MetaData, String, Table, create_engine
    from app.services.search_language import measure_matches
    from app.services.search_language_sql import measure_constraints
    valuation, opposite = ("current", "constant") if key == "current-prices" else ("constant", "current")
    intent = ((key,),)
    fixtures = [
        ("good", "GDP per capita", "Millions of " + valuation + " dollars", True),
        ("wrong", "GDP per capita", "Millions of " + opposite + " dollars", False),
        ("missing", "GDP per capita", "USD", False),
        ("crossfields", "GDP per capita, " + valuation + " transfers", "USD", False),
        ("contradictory", "GDP per capita, " + opposite + " prices", "Millions of " + valuation + " dollars", False),
        ("native-title", "GDP per capita, " + valuation + " prices", "USD", True),
    ]
    table = Table("valuation_fixture", MetaData(), Column("code", String), Column("title", String), Column("unit", String))
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    with engine.begin() as db:
        db.execute(table.insert(), [{"code": code, "title": title, "unit": unit} for code, title, unit, _ in fixtures])
        constraints = measure_constraints(intent, table.c.code, (table.c.title,), postgres=False, unit_columns=(table.c.unit,))
        accepted = set(db.execute(select(table.c.code).where(*constraints)).scalars())
    for code, title, unit, expected in fixtures:
        assert (code in accepted) == expected
        assert measure_matches(intent, code=code, names=(title,), unit_names=(unit,)) == expected
    assert not measure_matches((("birth-count",),), code="", names=("Inventions",), unit_names=("births",))



def test_native_price_sql_python_parity_and_valuation_exclusion():
    from sqlalchemy import Column, MetaData, String, Table, create_engine
    from app.services.search import _native_price_constraint, _native_price_metadata
    fixtures = [
        ("price", "Inventory price", True),
        ("plural", "Inventory prices", True),
        ("ampersand", "Inventory&price", True),
        ("currency", "Inventory price$", True),
        ("valuation", "GDP at current prices", False),
        ("punctuation", "GDP at current---prices", False),
        ("valuation-only", "Constant prices", False),
        ("both", "Inventory price, in constant prices", True),
        ("partial", "Pricewaterhouse revenue", False),
        ("missing", "Inventories", False),
        ("ru", "средние цены", True),
        ("ru-valuation", "ввп в текущих ценах", False),
    ]
    table = Table("price_fixture", MetaData(), Column("code", String), Column("title", String))
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    with engine.begin() as db:
        db.execute(table.insert(), [{"code": code, "title": title} for code, title, _ in fixtures])
        accepted = set(db.execute(select(table.c.code).where(_native_price_constraint(table.c.title, postgres=False))).scalars())
    for code, title, expected in fixtures:
        assert (code in accepted) == expected
        assert bool(_native_price_metadata(title)) == expected
