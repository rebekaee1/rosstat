"""Native catalogue/type/phrase and raw-prefix controls, without answer codes."""
from dataclasses import replace
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql

from app.models import WorldIndicator
from app.services.search import _world_lexical
from app.services.search_dimensions import (_KNOWN_AXES, dimension_constraints, dimension_metadata,
    native_dimension_match_clause, native_dimension_labels, native_dimension_text)
from app.services.search_intent import (complete_nominal_alternative, match_score,
    matching_alternatives, parse_intent)


@pytest.fixture
def catalogue():
    engine = create_engine("sqlite://")
    WorldIndicator.__table__.create(engine)
    try:
        with engine.begin() as connection:
            yield connection
    finally:
        engine.dispose()


def insert_row(connection, code, fields, provider="eurostat", **extra):
    connection.execute(WorldIndicator.__table__.insert(), dict(country_id=1, frequency="annual",
        code=code, slice_hash=code, dataset_id="synthetic", provider=provider,
        slice_json=fields, name_en="", name_ru="", unit="Number", **extra))


@pytest.mark.parametrize("fields,provider", [
    ({"indic_em": "P34"}, "eurostat"), ({"na_item": "P31"}, "eurostat"),
    ({"na_item": "P34"}, "BEA"), ({"na_item": "P34"}, "not eurostat"),
    ({"na_item": ["P34"]}, "eurostat"), ({"na_item": {"member": "P34"}}, "eurostat"),
    ({"na_item": True}, "eurostat"), ({"na_item": 0}, "eurostat"),
    ({"na_item": None}, "eurostat"), ({"na_item": "unknown"}, "eurostat"),
    ({"Na_item": "P34"}, "eurostat"), ({}, "eurostat"),
])
def test_native_boolean_witness_requires_actual_provider_axis_and_string_member(catalogue, fields, provider):
    insert_row(catalogue, "wrong", fields, provider)
    clause = native_dimension_match_clause(WorldIndicator.provider, WorldIndicator.slice_json,
        (("non resident households", True),))
    assert not catalogue.execute(select(WorldIndicator.code).where(clause)).all()
    assert not any("non-resident" in label for label in native_dimension_labels(provider, fields))


def test_native_boolean_phrase_has_sql_python_and_separator_parity(catalogue):
    insert_row(catalogue, "native", {"na_item": " p34 "}, " EUROSTAT ")
    for word in ("non-resident households", "нерезидентных домохозяйств"):
        intent = replace(parse_intent("sample", []), terms=((word,),))
        labels = dimension_metadata(" EUROSTAT ", {"na_item": " p34 "})
        assert match_score(intent, metadata=labels) is not None
        clause = native_dimension_match_clause(WorldIndicator.provider, WorldIndicator.slice_json, ((word, True),))
        assert catalogue.execute(select(WorldIndicator.code).where(clause)).scalar_one() == "native"
    assert not catalogue.execute(select(WorldIndicator.code).where(native_dimension_match_clause(
        WorldIndicator.provider, WorldIndicator.slice_json, (("non resident householdsmanship", True),)))).all()
    assert not catalogue.execute(select(WorldIndicator.code).where(native_dimension_match_clause(
        WorldIndicator.provider, WorldIndicator.slice_json, (("antihouseholds", True),)))).all()


@pytest.mark.parametrize("fields", [{"sex": "T"}, {"na_item": "TOTAL"}, {"hhcomp": "TOTAL"}, {"age": "TOTAL"}])
def test_unknown_all_and_typed_markers_cannot_fabricate_flat_native_labels(catalogue, fields):
    insert_row(catalogue, "native", fields)
    for word in ("all", "total", "magical", "search-dim-magical"):
        clause = native_dimension_match_clause(WorldIndicator.provider, WorldIndicator.slice_json, ((word, False),))
        assert not catalogue.execute(select(WorldIndicator.code).where(clause)).all()
    assert not catalogue.execute(select(WorldIndicator.code).where(*dimension_constraints(
        (("search-dim-magical",),), WorldIndicator.provider, WorldIndicator.slice_json))).all()


def test_all_required_native_terms_precede_limit_and_unknown_tail_remains_required(catalogue):
    for i in range(140):
        insert_row(catalogue, f"aaa-{i:03}", {"indic_em": "P34"})
    insert_row(catalogue, "zzz", {"na_item": "P34"})
    intent = replace(parse_intent("sample", []), terms=(("non resident households",),))
    stmt = select(WorldIndicator.code).where(*_world_lexical(intent, postgres=False)).order_by(WorldIndicator.code).limit(1)
    assert catalogue.execute(stmt).scalar_one() == "zzz"
    unknown = replace(intent, terms=intent.terms + (("magical",),))
    assert not catalogue.execute(select(WorldIndicator.code).where(*_world_lexical(unknown, postgres=False))).all()


def test_whole_native_forms_and_original_raw_prefix_are_distinct(catalogue):
    insert_row(catalogue, "native", {"na_item": "P34"})
    assert catalogue.execute(select(WorldIndicator.code).where(native_dimension_match_clause(
        WorldIndicator.provider, WorldIndicator.slice_json, (("househ", False),)))).scalar_one() == "native"
    assert not catalogue.execute(select(WorldIndicator.code).where(native_dimension_match_clause(
        WorldIndicator.provider, WorldIndicator.slice_json, (("househ", True),)))).all()
    pg = select(WorldIndicator.code).where(native_dimension_match_clause(WorldIndicator.provider,
        WorldIndicator.slice_json, (("households", True),))).compile(dialect=postgresql.dialect())
    assert "jsonb_typeof" in str(pg) and "'string'" in str(pg)
    assert len(pg.params) < 30 and len(str(pg)) < 2500


@pytest.mark.parametrize("word,title", [
    ("reservoi", "Reservoir pressure"), ("statisti", "Statistics"),
    ("безра", "Безработица"), ("золотова", "Золотовалютные резервы"),
    ("ruoni", "RUONIA Overnight"),
])
def test_original_raw_singleton_keeps_native_identity_autocomplete(word, title):
    intent = parse_intent(word, [])
    assert (word,) in intent.terms
    assert match_score(intent, names=(title,)) is not None
    assert match_score(parse_intent(word + " magical", []), names=(title,)) is None
    assert match_score(intent, names=("Other subject",), metadata="search-unit-usd") is None


def test_added_nominal_alternatives_cannot_gain_prefix_or_change_parsed_instrumental_group():
    raw = ("technology",); expanded = matching_alternatives(raw)
    assert not complete_nominal_alternative(raw, expanded, "technology")
    assert complete_nominal_alternative(raw, expanded, "technologies")
    intent = parse_intent("technology", [])
    assert match_score(intent, names=("Technologies",)) is not None
    assert match_score(intent, names=("Technologiesography",)) is None
    for word, valid, wrong in (("методами", "методы", "методи"), ("болезнями", "болезни", "болезны")):
        intent = parse_intent("pressure " + word, [])
        assert match_score(intent, names=("Pressure " + valid,)) is not None
        assert match_score(intent, names=("Pressure " + wrong,)) is None
        assert match_score(intent, names=("Pressure " + valid + "ография",)) is None


@pytest.mark.parametrize("query", ["Индекс цен про", "возрастная стр", "Индекс цен произ"])
def test_native_label_sql_has_grouped_identity_predicates_not_repeated_label_case_pool(query):
    intent = parse_intent(query, [])
    stmt = select(WorldIndicator.code).where(*_world_lexical(intent, postgres=True))
    compiled = stmt.compile(dialect=postgresql.dialect())
    assert len(str(compiled).encode()) < 10000 and len(compiled.params) < 150
    # Type-witness CASEs are bounded by selected axes; no translated labels
    # become database parameters repeated for every required query term.
    assert not any("non-resident households" in str(value) for value in compiled.params.values())


def test_simple_native_display_case_retains_exact_labels_and_one_member_expression_per_axis(catalogue):
    insert_row(catalogue, "native", {"na_item": "P34"})
    expression = native_dimension_text(WorldIndicator.provider, WorldIndicator.slice_json,
        (("non-resident",), ("households",)))
    text = catalogue.execute(select(expression)).scalar_one()
    assert "non-resident" in text and "нерезидентных" in text
    compiled = select(expression).compile(dialect=postgresql.dialect())
    axes = {value for value in compiled.params.values() if isinstance(value, str) and value in _KNOWN_AXES}
    assert str(compiled).count("jsonb_typeof") == len(axes)
