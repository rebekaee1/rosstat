"""Exact native slice guards; every nearby/missing/provider control stays closed."""
import pytest
from sqlalchemy import Column, Integer, JSON, MetaData, String, Table, create_engine, insert, select

from app.services.search_dimensions import (DIMENSION_RULES, DIMENSION_ANY_RULES, dimension_constraints,
    dimension_metadata, native_dimension_labels, native_dimension_text, prepare_dimensions)
from app.services.search_intent import match_score, parse_intent


@pytest.fixture
def catalogue():
    engine = create_engine("sqlite://")
    metadata = MetaData()
    table = Table("native_rows", metadata, Column("id", Integer, primary_key=True),
        Column("provider", String), Column("slice_json", JSON))
    metadata.create_all(engine)
    with engine.begin() as connection:
        yield connection, table
    engine.dispose()


def selected(connection, table, query, limit=100):
    intent = parse_intent(query, [])
    assert not intent.error
    clauses = dimension_constraints(intent.terms, table.c.provider, table.c.slice_json)
    assert clauses
    return list(connection.scalars(select(table.c.id).where(*clauses).order_by(table.c.id).limit(limit)))


@pytest.mark.parametrize("query,key,axis,value,wrong", [
    ("both sexes", "search-dim-sex-total", "sex", "T", "F"),
    ("оба пола", "search-dim-sex-total", "sex", "TOTAL", "M"),
    ("male sex", "search-dim-sex-male", "sex", "M", "F"),
    ("female sex", "search-dim-sex-female", "sex", "F", "M"),
    ("all citizens", "search-dim-citizen-total", "citizen", "TOTAL", "NAT"),
    ("all partner countries", "search-dim-partner-total", "partner", "WORLD", "FOR"),
    ("все страны партнеры", "search-dim-partner-total", "partner", "TOTAL", "NAT"),
    ("all household types", "search-dim-household-type-total", "hhcomp", "TOTAL", "A1"),
    ("all income quintiles", "search-dim-income-quintiles-total", "quant_inc", "TOTAL", "QU1"),
    ("all income threshold groups", "search-dim-income-threshold-groups-total", "rskpovth", "TOTAL", "A_60"),
    ("all income groups", "search-dim-income-groups-total", "quant_inc", "TOTAL", "QU2"),
    ("all income groups", "search-dim-income-groups-total", "rskpovth", "TOTAL", "B_60"),
    ("all economic activities", "search-dim-activities-total", "nace_r2", "TOTAL", "C"),
    ("all NACE activities", "search-dim-activities-total", "nace_r1", "TOTAL", "A"),
    ("below upper secondary", "search-dim-education-below-upper-secondary", "isced11", "ED0-2", "ED3_4"),
    ("labour status employed", "search-dim-status-employed", "wstatus", "EMP", "UNE"),
    ("clinical status practising", "search-dim-clinical-practising", "wstatus", "PRACT", "LIC"),
    ("clinical status professionally active", "search-dim-clinical-active", "wstatus", "PACT", "PRACT"),
    ("clinical status licensed to practice", "search-dim-clinical-licensed", "wstatus", "LIC", "PRACT"),
    ("medical specialty physicians", "search-dim-medical-physicians", "med_spec", "PHYS", "NRS"),
    ("medical specialty dentists", "search-dim-medical-dent", "med_spec", "DENT", "PHYS"),
    ("internet access frequency daily", "search-dim-internet-daily", "indic_is", "I_IDAY", "I_IWEEK"),
    ("all individuals", "search-dim-individuals-total", "ind_type", "IND_TOTAL", "IND_EMP"),
    ("opening stocks", "search-dim-oil-opening-stock", "stk_flow", "STKOP_NAT", "STKCL_NAT"),
    ("ages 15 to 74", "search-dim-age-y15-74", "age", "Y15-74", "Y15-64"),
    ("under 6", "search-dim-age-y-lt6", "age", "Y_LT6", "Y_LT5"),
    ("младше 6 лет", "search-dim-age-y-lt6", "age", "Y_LT6", "Y6-11"),
])
def test_explicit_native_axes_have_identical_sql_and_python_requirements(catalogue, query, key, axis, value, wrong):
    connection, table = catalogue
    intent = parse_intent(query, [])
    assert key in {group[0] for group in intent.terms}
    connection.execute(insert(table), [
        {"id": 1, "provider": "eurostat", "slice_json": {axis: wrong}},
        {"id": 2, "provider": "eurostat", "slice_json": {}},
        {"id": 3, "provider": "BEA", "slice_json": {axis: value}},
        {"id": 4, "provider": None, "slice_json": {axis: value}},
        {"id": 5, "provider": "eurostat", "slice_json": {"unrelated": value}},
        {"id": 6, "provider": "eurostat", "slice_json": {axis: value}},
    ])
    assert selected(connection, table, query) == [6]
    good = dimension_metadata("eurostat", {axis: value})
    assert key in good.split()
    assert match_score(intent, names=("Native measure",), metadata=good) is not None
    for provider, fields in (("eurostat", {axis: wrong}), ("eurostat", {}),
            ("BEA", {axis: value}), (None, {axis: value}), ("eurostat", {"unrelated": value})):
        assert key not in dimension_metadata(provider, fields).split()
        assert match_score(intent, names=("Native measure",), metadata=dimension_metadata(provider, fields)) is None


@pytest.mark.parametrize("query,fields", [
    ("both sexes", {"sex": "T"}), ("all citizens", {"citizen": "TOTAL"}),
    ("all partner countries", {"partner": "TOTAL"}), ("all household types", {"hhcomp": "TOTAL"}),
    ("all income quintiles", {"quant_inc": "TOTAL"}), ("all income groups", {"rskpovth": "TOTAL"}),
    ("all economic activities", {"nace_r2": "TOTAL"}),
])
def test_135_wrong_axis_totals_cannot_clip_the_actual_result_before_limit(catalogue, query, fields):
    connection, table = catalogue
    wrong_axes = [axis for axis in ("sex", "citizen", "partner", "hhcomp", "quant_inc", "rskpovth", "nace_r2",
        "nace_r1", "age", "wstatus", "med_spec", "indic_is", "ind_type", "stk_flow", "siec", "unrelated")
        if axis not in fields and not (query == "all income groups" and axis == "quant_inc")
        and not (query == "all economic activities" and axis == "nace_r1")]
    connection.execute(insert(table), [{"id": index + 1, "provider": "eurostat",
        "slice_json": {wrong_axes[index % len(wrong_axes)]: "TOTAL"}} for index in range(135)]
        + [{"id": 200, "provider": "eurostat", "slice_json": fields}])
    assert selected(connection, table, query) == [200]


def test_clinical_specialty_and_practising_status_are_independent_required_axes(catalogue):
    connection, table = catalogue
    connection.execute(insert(table), [
        {"id": 1, "provider": "eurostat", "slice_json": {"wstatus": "PRACT", "med_spec": "NRS"}},
        {"id": 2, "provider": "eurostat", "slice_json": {"wstatus": "LIC", "med_spec": "PHYS"}},
        {"id": 3, "provider": "eurostat", "slice_json": {"wstatus": "PRACT", "med_spec": "PHYS"}},
        {"id": 4, "provider": "eurostat", "slice_json": {"wstatus": "PRACT", "med_spec": "DENT"}},
    ])
    assert selected(connection, table, "practising physicians") == [3]
    assert selected(connection, table, "practicing dentists") == [4]
    assert selected(connection, table, "практикующие врачи") == [3]
    intent = parse_intent("practising physicians magical", [])
    assert "magical" in {group[0] for group in intent.terms}
    assert match_score(intent, names=("Health personnel",),
        metadata=dimension_metadata("eurostat", {"wstatus": "PRACT", "med_spec": "PHYS"})) is None


def test_age_span_shield_keeps_outside_year_month_and_unknown_constraints():
    prepared = prepare_dimensions("population ages 15 74 both sexes 2024 magical")
    assert "2024 magical" in prepared
    assert "15" not in prepared and "74" not in prepared
    intent = parse_intent("ages 15–74 2024-03 magical", [])
    assert (intent.year, intent.month) == (2024, 3)
    assert "search-dim-age-y15-74" in {group[0] for group in intent.terms}
    assert "magical" in {group[0] for group in intent.terms}
    for query in ("2024", "previous month", "quarter 2", "population age magical", "ages 17 93"):
        assert prepare_dimensions(query) == query


def test_daily_use_dimension_remains_separate_from_annual_observations(catalogue):
    connection, table = catalogue
    query = "internet access frequency daily annual percent"
    intent = parse_intent(query, [])
    assert {"search-dim-internet-daily", "search-freq-annual", "search-unit-percent"} <= {g[0] for g in intent.terms}
    assert "search-freq-daily" not in {g[0] for g in intent.terms}
    fields = {"indic_is": "I_IDAY"}
    metadata = dimension_metadata("eurostat", fields) + " search-freq-annual search-unit-percent"
    assert match_score(intent, names=("Internet access",), metadata=metadata) is not None
    assert match_score(intent, names=("Internet access",), metadata=dimension_metadata("eurostat", fields)
        + " search-freq-monthly search-unit-percent") is None
    assert "daily" in " ".join(native_dimension_labels("eurostat", fields))
    assert not native_dimension_labels("eurostat", {"indic_is": "I_IWEEK"})


@pytest.mark.parametrize("fields", [
    {"sex": "T"}, {"hhcomp": "TOTAL"}, {"partner": "WORLD"}, {"citizen": "TOTAL"},
    {"quant_inc": "TOTAL"}, {"rskpovth": "TOTAL"}, {"nace_r2": "TOTAL"}, {"ind_type": "IND_TOTAL"},
])
def test_aggregate_marker_does_not_supply_unresolved_all_as_a_flat_total_witness(catalogue, fields):
    connection, table = catalogue
    assert not native_dimension_labels("eurostat", fields)
    intent = parse_intent("all", [])
    assert match_score(intent, names=("Native measure",), metadata=dimension_metadata("eurostat", fields)) is None
    connection.execute(insert(table), {"id": 1, "provider": "eurostat", "slice_json": fields})
    text = connection.scalar(select(native_dimension_text(table.c.provider, table.c.slice_json, intent.terms)))
    assert text == ""


@pytest.mark.parametrize("fields,terms", [
    ({"wstatus": "PRACT", "med_spec": "PHYS"}, (("practising",), ("physicians",))),
    ({"indic_is": "I_IDAY"}, (("daily",),)),
    ({"siec": "O4000"}, (("petroleum",),)),
    ({"isced11": "ED0-2"}, (("secondary",),)),
    ({"age": "Y_LT6"}, (("search-dim-age-y-lt6",),)),
])
def test_sql_label_witnesses_are_exact_present_members_and_match_python(catalogue, fields, terms):
    connection, table = catalogue
    connection.execute(insert(table), [
        {"id": 1, "provider": "eurostat", "slice_json": fields},
        {"id": 2, "provider": "BEA", "slice_json": fields},
        {"id": 3, "provider": "eurostat", "slice_json": {}},
    ])
    expr = native_dimension_text(table.c.provider, table.c.slice_json, terms)
    rows = connection.execute(select(table.c.id, expr).order_by(table.c.id)).all()
    assert rows[0][1].strip()
    assert rows[1][1] == rows[2][1] == ""
    labels = native_dimension_labels("eurostat", fields)
    assert all(label in rows[0][1] for label in labels)


def test_missing_unknown_malformed_native_dimensions_are_not_invented(catalogue):
    connection, table = catalogue
    for fields in ({"Age": "Y_LT6"}, {"age": 6}, {"age": ["Y_LT6"]}, {"age": None},
            {"age": "magical"}, {"unrelated": "Y_LT6"}):
        assert "search-dim-age-y-lt6" not in dimension_metadata("eurostat", fields)
    connection.execute(insert(table), {"id": 1, "provider": "eurostat", "slice_json": {"age": "Y_LT6"}})
    clauses = dimension_constraints((("search-dim-magical",),), table.c.provider, table.c.slice_json)
    assert list(connection.scalars(select(table.c.id).where(*clauses))) == []
    assert native_dimension_labels("not eurostat", {"age": "Y_LT6"}) == ()
    assert dimension_metadata("eurostat", None) == ""


def test_single_letters_do_not_expand_sql_label_catalogue(catalogue):
    _connection, table = catalogue
    assert str(native_dimension_text(table.c.provider, table.c.slice_json, (("a",), ("us",)))) == ":param_1"
    expression = native_dimension_text(table.c.provider, table.c.slice_json, (("search-dim-age-y-lt6",),))
    compiled = str(expression.compile(compile_kwargs={"literal_binds": True}))
    assert "Y_LT6" in compiled
    assert "Y_LT5" not in compiled and "Y15-74" not in compiled
