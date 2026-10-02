"""Economic subject/quantity controls for the post-blind general parser repairs."""
import pytest

from app.services.search_intent import parse_intent, match_score
from app.services.search_language import measure_matches
from app.services.search_units import unit_metadata, denominator_metadata
from app.services.search import _world_lexical
from sqlalchemy.dialects import postgresql
import asyncio
from datetime import date
from test_search_federated import get, search_client  # noqa: F401


def sql_text(clause):
    return str(clause.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.mark.parametrize("query", ["average pension", "средняя назначенная пенсия"])
def test_pension_amount_is_not_recipient_headcount(query):
    intent = parse_intent(query, [])
    assert measure_matches(intent.terms, code="pension", names=("Average assigned pension",))
    assert measure_matches(intent.terms, code="pensioners", names=("Средний размер назначенных пенсий",))
    assert not measure_matches(intent.terms, code="pensioners", names=("Number of pensioners",))
    assert not measure_matches(intent.terms, code="recipients", names=("Численность пенсионеров",))


def test_neutral_predicate_does_not_become_an_economic_noun():
    intent = parse_intent("How much gold do banks hold magical", [])
    assert not intent.corrected
    assert ("magical",) in intent.terms
    assert match_score(intent, names=("Gold reserves",)) is None


@pytest.mark.parametrize("query,pair,other", [
    ("курс доллара к рублю", "usd-rub", "usd-index"),
    ("usd jpy", "jp-fx-usd-jpy", "jp-effective-exchange"),
    ("курс юаня к рублю", "cny-rub", "cny-usd"),
])
def test_currency_pair_requires_both_currencies_and_rejects_an_index(query, pair, other):
    intent = parse_intent(query, [])
    assert measure_matches(intent.terms, code=pair, names=("Exchange rate",))
    assert not measure_matches(intent.terms, code=other, names=("Dollar index / effective exchange rate",))


@pytest.mark.parametrize("query", ["milk go", "nomimal w", "inflation rr"])
def test_unfinished_unknown_world_qualifier_fails_closed_before_scan(query):
    clauses = _world_lexical(parse_intent(query, []), postgres=True)
    assert len(clauses) == 1
    assert sql_text(clauses[0]) == "false"


def test_short_world_prefix_numeric_denominator_and_literal_keep_retrieval():
    assert sql_text(_world_lexical(parse_intent("ин", []), postgres=True)[0]) != "false"
    numeric = parse_intent("inflation 12", [])
    assert sql_text(_world_lexical(numeric, postgres=True)[0]) != "false"
    literal = parse_intent("some native indicator unfinished p", [], literal_content="some native indicator unfinished p")
    assert sql_text(_world_lexical(literal, postgres=True)[0]) != "false"


@pytest.mark.parametrize("unit,expected", [("AUD_MN", "aud"), ("GBP_BN", "gbp"), ("CNY_MN", "cny")])
def test_registered_currency_is_native_metadata_and_not_interchangeable(unit, expected):
    markers = unit_metadata(unit)
    assert f"search-unit-{expected}" in markers
    assert "search-unit-usd" not in markers


def test_index_subject_is_not_automatically_a_native_unit_request():
    intent = parse_intent("Индекс Московской биржи", [])
    assert ("search-unit-index",) not in intent.terms
    assert ("search-unit-index",) in parse_intent("население в единицах индекса", []).terms


def test_native_denominator_is_exact_and_promille_requires_a_demographic_measure():
    assert "search-denominator-1000-persons" in denominator_metadata("Birth rate", "‰")
    assert "search-denominator-1000-persons" not in denominator_metadata("Paved road share", "‰")
    assert "search-denominator-1000-persons" not in denominator_metadata("Crimes per 10000 population")
    assert "search-denominator-10000-persons" in denominator_metadata("Crimes per 10000 population")
    assert "search-denominator-10000-persons" in denominator_metadata("Crimes per 10 000 population")
    assert "search-denominator-1000-persons" in denominator_metadata("Births per 1\u202f000 people")
    assert "search-unit-square-metre" not in unit_metadata("sq km")
    assert "search-unit-square-metre" not in unit_metadata("square miles")


def test_denominator_uses_actual_measure_and_units_without_relaxing_period(auth_env, search_client):
    from app.models import Indicator, IndicatorData

    async def seed():
        async with auth_env["session_maker"]() as db:
            entries = [
                Indicator(code="fixture-birth-promille", name="Общий коэффициент рождаемости", name_en="Crude birth rate", unit="‰", frequency="annual"),
                Indicator(code="fixture-birth-denominator", name="Родившиеся на 10000 человек", name_en="Births per 10000 population", unit="persons", frequency="annual"),
                Indicator(code="fixture-birth-count", name="Число родившихся", name_en="Number of births", unit="persons", frequency="annual"),
            ]
            db.add_all(entries)
            await db.flush()
            db.add_all(IndicatorData(indicator_id=row.id, date=date(2024, 1, 1), value=12) for row in entries)
            await db.commit()

    asyncio.run(seed())
    thousand = get(search_client, "births per 1000 population Russia 2024")["results"]
    assert [row["code"] for row in thousand] == ["fixture-birth-promille"]
    ten_thousand = get(search_client, "births per 10000 population Russia 2024")["results"]
    assert [row["code"] for row in ten_thousand] == ["fixture-birth-denominator"]
    assert not get(search_client, "births per 1000 population Russia 2023")["results"]
