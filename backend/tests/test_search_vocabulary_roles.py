"""Compositional economic roles preserve quantities and neighbouring measures.

These tests use public human measure names, never destination codes or replayed
query answers. Each positive has a nearby subject/role or quantity control.
"""
import pytest

from app.services.search_intent import match_score, parse_intent
from app.services.search_language import measure_matches
from app.services.search_units import unit_metadata
from app.services.search_vocabulary import prepare_subject_roles, prepare_vocabulary


def keys(query):
    return {group[0] for group in parse_intent(query, []).terms}


@pytest.mark.parametrize("query,role,correct,wrong", [
    ("households outstanding bank loan balance", "credit-stock-households",
        "Consumer Credit Outstanding", "Business Credit Outstanding"),
    ("задолженность физических лиц по банковским кредитам", "credit-stock-households",
        "Кредиты физическим лицам", "Ставки по кредитам физическим лицам"),
    ("businesses bank loans outstanding", "credit-stock-business",
        "Business Credit Outstanding", "Consumer Credit Outstanding"),
    ("задолженность бизнеса по кредитам", "credit-stock-business",
        "Кредиты бизнесу", "Consumer Credit Outstanding"),
])
def test_outstanding_stock_keeps_the_borrower_role(query, role, correct, wrong):
    intent = parse_intent(query, [])
    assert role in keys(query)
    assert match_score(intent, names=(correct,)) is not None
    assert measure_matches(intent.terms, code="", names=(correct,))
    # A rate can contain the stock title as a suffix. The shared typed guard
    # must reject it even when a keyword scorer could match the whole phrase.
    assert not measure_matches(intent.terms, code="", names=(wrong,))


@pytest.mark.parametrize("qualifier", ["net", "gross", "private", "women", "age 65", "magical", "kilowatts", "2024"])
def test_stock_role_rewrite_retains_every_unresolved_qualifier(qualifier):
    prepared = prepare_subject_roles("households bank loans outstanding " + qualifier)
    assert prepared.startswith("household credit outstanding ")
    assert qualifier in prepared


def test_loan_rates_and_conflicting_sectors_are_not_rewritten_as_stocks():
    for query in ("households credit outstanding interest rate",
            "households and businesses loans outstanding",
            "households new loans", "businesses loan originations"):
        assert prepare_subject_roles(query) == query
    intent = parse_intent("bank lending rates for legal entities monthly percent", [])
    assert "borrower-legal-entities" in {group[0] for group in intent.terms}
    assert match_score(intent, names=("Corporate Loan Rate",),
        metadata="search-freq-monthly search-unit-percent") is not None
    assert match_score(intent, names=("Consumer Loan Rate",),
        metadata="search-freq-monthly search-unit-percent") is None
    assert "borrower-legal-entities" in keys("кредиты юридическим лицам задолженность")
    assert "short" in keys("bank loan rates for legal entities short term")


@pytest.mark.parametrize("query,role,correct,wrong", [
    ("people engaged in research and development", "research-personnel",
        "R&D Personnel", "R&D Organizations"),
    ("персонал научных исследований и разработок", "research-personnel",
        "Персонал НИР", "Число организаций НИР"),
    ("organizations performing research and development", "research-organizations",
        "R&D Organizations", "R&D Personnel"),
    ("организации выполняют научные исследования и разработки", "research-organizations",
        "Число организаций НИР", "Персонал НИР"),
])
def test_research_domain_resolves_personnel_and_organization_roles(query, role, correct, wrong):
    intent = parse_intent(query, [])
    assert role in {group[0] for group in intent.terms}
    assert match_score(intent, names=(correct,)) is not None
    assert match_score(intent, names=(wrong,)) is None


def test_research_role_keeps_subset_and_quantity_qualifiers():
    for qualifier in ("private", "women", "age 45", "funding", "magical"):
        prepared = prepare_subject_roles("research and development personnel " + qualifier)
        assert qualifier in prepared
        assert match_score(parse_intent(prepared, []), names=("R&D Personnel",)) is None
    assert prepare_subject_roles("researchers in basic science") == "researchers in basic science"
    assert prepare_subject_roles("research and development personnel organizations") == "research and development personnel organizations"


@pytest.mark.parametrize("query,role,title", [
    ("amount of Medicare benefits", "benefits-medicare", "Transfer receipts: Medicare benefits"),
    ("Medicaid payments", "benefits-medicaid", "Quarterly transfer receipts: Medicaid"),
    ("сумма продовольственной помощи SNAP", "benefits-snap", "Transfer receipts: Supplemental Nutrition Assistance Program (SNAP)"),
    ("Social Security benefit amount", "benefits-social-security", "Transfer receipts: Social Security benefits"),
    ("railroad retirement and disability benefit payments", "benefits-railroad", "Transfer receipts: Railroad retirement and disability benefits"),
    ("workers compensation money", "benefits-workers-compensation", "Transfer receipts: Workers' compensation"),
    ("пособия по поддержанию доходов сумма", "benefits-income-maintenance", "State economic profile: Income maintenance benefits"),
    ("veterans pension and disability benefits amount", "benefits-veterans", "Transfer receipts: Veterans' pension and disability benefits"),
    ("education and training assistance amount", "benefits-education-training", "Transfer receipts: Education and training assistance"),
])
def test_programme_amount_uses_actual_monetary_units(query, role, title):
    intent = parse_intent(query, [])
    assert {role, "search-unit-money"} <= {group[0] for group in intent.terms}
    assert match_score(intent, names=(title,), metadata=unit_metadata("Thousands of dollars")) is not None
    assert match_score(intent, names=(title,), metadata=unit_metadata("Persons")) is None
    assert match_score(intent, names=("Food price index",), metadata=unit_metadata("Thousands of dollars")) is None
    assert match_score(parse_intent(query + " percent", []), names=(title,),
        metadata=unit_metadata("Thousands of dollars")) is None


def test_transfer_programmes_do_not_absorb_recipient_or_variant_qualifiers():
    for qualifier in ("number of recipients", "net", "private", "children age 15", "magical", "kilowatts"):
        prepared = prepare_subject_roles("medicare benefit amount " + qualifier)
        assert "monetary value" in prepared
        assert qualifier in prepared
        assert match_score(parse_intent(prepared, []), names=("Medicare benefits",),
            metadata=unit_metadata("Dollars")) is None
    assert "cpi-food" not in keys("SNAP food assistance amount")
    assert "consumer-credit" not in keys("Additional Child Tax Credit")


def test_programme_identity_does_not_turn_a_recipient_count_into_money():
    intent = parse_intent("number of Medicare recipients", [])
    assert "benefits-medicare" in {group[0] for group in intent.terms}
    assert "search-unit-money" not in {group[0] for group in intent.terms}
    assert match_score(intent, names=("Number of Medicare recipients",),
        metadata=unit_metadata("Persons")) is not None
    assert match_score(intent, names=("Transfer receipts: Medicare benefits",),
        metadata=unit_metadata("Thousands of dollars")) is None
    payments = parse_intent("number of Medicare benefit payments", [])
    assert "search-unit-money" not in {group[0] for group in payments.terms}
    assert match_score(payments, names=("Number of Medicare benefit payments",),
        metadata=unit_metadata("Count")) is not None
    assert match_score(payments, names=("Transfer receipts: Medicare benefits",),
        metadata=unit_metadata("Thousands of dollars")) is None


@pytest.mark.parametrize("query,role,title,count_title", [
    ("коэффициента рождаемости", "birth-rate", "Коэффициент рождаемости", "Число родившихся"),
    ("crude birth rate", "birth-rate", "Birth Rate", "Number of births"),
    ("коэффициента смертности", "death-rate", "Коэффициент смертности", "Число умерших"),
    ("crude death rate", "death-rate", "Death Rate", "Number of deaths"),
])
def test_rate_measure_inflections_are_not_headcounts(query, role, title, count_title):
    intent = parse_intent(query, [])
    assert role in {group[0] for group in intent.terms}
    assert match_score(intent, names=(title,)) is not None
    assert match_score(intent, names=(count_title,)) is None


@pytest.mark.parametrize("query,role,correct,wrong", [
    ("wage and salary jobs", "wage-salary-employment", "State economic profile: Wage and salary employment", "Wage and salary earnings"),
    ("net earnings", "net-earnings", "Per capita net earnings", "Gross earnings"),
    ("employee compensation", "employee-compensation", "Compensation of employees", "Workers' compensation"),
    ("дивиденды, проценты и рента", "dividend-interest-rent-income", "Dividends, interest, and rent", "Housing rent price index"),
    ("current transfer receipts of individuals from businesses", "transfers-business-to-persons", "Current transfer receipts of individuals from businesses", "Current transfer receipts of government from businesses"),
])
def test_long_compound_subjects_win_over_parts(query, role, correct, wrong):
    intent = parse_intent(query, [])
    assert role in {group[0] for group in intent.terms}
    assert match_score(intent, names=(correct,)) is not None
    assert match_score(intent, names=(wrong,)) is None
    if role == "dividend-interest-rent-income":
        assert "rent" not in {group[0] for group in intent.terms}


@pytest.mark.parametrize("word,frequency", [
    ("annual", "annual"), ("yearly", "annual"), ("годовые", "annual"),
    ("годовых", "annual"), ("ежегодная", "annual"),
    ("quarterly", "quarterly"), ("квартальные", "quarterly"), ("квартальных", "quarterly"),
    ("monthly", "monthly"), ("месячные", "monthly"), ("по месяцам", "monthly"),
    ("weekly", "weekly"), ("еженедельно", "weekly"),
    ("daily", "daily"), ("каждый день", "daily"),
])
def test_productive_frequency_forms_require_the_actual_frequency(word, frequency):
    intent = parse_intent("Medicaid " + word, [])
    assert "search-freq-" + frequency in {group[0] for group in intent.terms}
    assert match_score(intent, names=("Medicaid",), metadata="search-freq-" + frequency) is not None
    different = "weekly" if frequency != "weekly" else "monthly"
    assert match_score(intent, names=("Medicaid",), metadata="search-freq-" + different) is None


def test_observation_frequency_does_not_consume_explicit_tenor_or_unknown_period():
    prepared = prepare_vocabulary("loan rate daily 1 week magical")
    assert "1 week" in prepared and "magical" in prepared
    assert "search-freq-weekly" not in keys("loan rate недельный")
    intent = parse_intent("Medicaid yearly monthly", [])
    assert intent.error == "unsupported_query"
    assert "search-mode-yoy" in keys("consumer price index annual rate of change monthly")
    assert "search-freq-annual" not in keys("consumer price index annual rate of change monthly")


@pytest.mark.parametrize("query,title,unit", [
    ("grain sown area hectares", "Grain sown area", "hectares"),
    ("grain area hectares", "Grain sown area", "hectares"),
    ("площадь зерновых гектары", "Посевная площадь зерновых", "гектары"),
])
def test_hectare_area_unit_never_becomes_grain_yield(query, title, unit):
    intent = parse_intent(query, [])
    assert "grain-area" in {group[0] for group in intent.terms}
    assert "grain-yield" not in {group[0] for group in intent.terms}
    assert match_score(intent, names=(title,), metadata=unit) is not None
    assert match_score(intent, names=(title,), metadata="square kilometres") is None
    assert match_score(intent, names=("Grain yield",), metadata=unit) is None


@pytest.mark.parametrize("query", ["grain per hectare", "зерно получают с одного гектара", "grain yield"])
def test_grain_yield_requires_a_yield_or_per_hectare_relation(query):
    prepared = prepare_vocabulary(query)
    assert prepared.startswith("grain yield ")
    assert "grain-area" not in keys(prepared)
    assert "grain-yield" in keys(prepared)
    assert match_score(parse_intent(prepared, []), names=("Grain yield",)) is not None
    assert match_score(parse_intent(prepared, []), names=("Grain sown area",)) is None
    assert not prepare_vocabulary("grain hectares").startswith("grain yield ")
    assert "one year magical" in prepare_vocabulary("grain per one hectare one year magical")


def test_grain_area_keeps_a_conflicting_yield_and_unknown_unit_required():
    prepared = prepare_vocabulary("grain sown area yield hectares magical")
    assert prepared.startswith("grain sown area ")
    assert "yield hectares magical" in prepared
    assert match_score(parse_intent(prepared, []), names=("Grain sown area",), metadata="hectares") is None
