"""Private candidate controls for relationships, independently of native codes."""
import pytest

from app.services.search_intent import parse_intent, match_score
from app.services.search_language import measure_matches
from app.services.search_units import unit_metadata
from app.services.search_vocabulary import prepare_subject_roles, prepare_temporal_roles


def eligible(query, title, metadata=""):
    intent = parse_intent(query, [])
    return (not intent.error and measure_matches(intent.terms, code="", names=(title,))
        and match_score(intent, names=(title,), metadata=metadata) is not None)


@pytest.mark.parametrize("phrase,mode,frequency", [
    ("same month last year", "yoy", "monthly"),
    ("same month of the previous year", "yoy", "monthly"),
    ("тому же месяцу прошлого года", "yoy", "monthly"),
    ("over previous month", "pop", "monthly"),
    ("over the previous month", "pop", "monthly"),
    ("к предыдущему месяцу", "pop", "monthly"),
    ("over previous quarter", "pop", "quarterly"),
    ("по сравнению с предыдущим кварталом", "pop", "quarterly"),
    ("average over the quarter", "avg", "quarterly"),
    ("среднее за квартал", "avg", "quarterly"),
])
def test_relative_window_produces_two_independent_required_facets(phrase, mode, frequency):
    query = "reservoir pressure " + phrase
    intent = parse_intent(query, [])
    assert not intent.error
    assert {"search-mode-" + mode, "search-freq-" + frequency} <= {group[0] for group in intent.terms}
    metadata = "search-mode-" + mode + " search-freq-" + frequency
    assert eligible(query, "Reservoir pressure", metadata)
    assert not eligible(query, "Reservoir pressure", "search-mode-level search-freq-" + frequency)
    assert not eligible(query, "Reservoir pressure", "search-mode-" + mode + " search-freq-annual")
    assert not eligible(query + " magical", "Reservoir pressure", metadata)


def test_relative_window_rewrite_does_not_consume_absolute_or_unknown_periods():
    for text in ("Q1 2024", "first quarter", "year on year", "annual rate of change", "magical quarter"):
        assert prepare_temporal_roles(text) == text
    assert "magical 2024 2" in prepare_temporal_roles("pressure over previous month magical 2024 2")
    assert "search-freq-annual" not in {g[0] for g in parse_intent("pressure year on year", []).terms}


@pytest.mark.parametrize("query,title,role,wrong", [
    ("earnings contribution to income change quarterly", "Quarterly earnings contributions to income change",
        "earnings-income-contribution", "Quarterly bank deposit rate and income change"),
    ("вклад заработков в изменение дохода по кварталам", "Квартальный вклад заработков в изменение дохода",
        "earnings-income-contribution", "Квартальные банковские вклады населения"),
    ("consumption contribution to change annual", "Contributions to consumption change",
        "consumption-change-contribution", "Bank deposits used for consumption"),
    ("вклад категорий в изменение потребления годовые", "Вклад категорий в изменение потребления",
        "consumption-change-contribution", "Вклады населения"),
])
def test_contribution_is_part_of_change_and_never_bank_deposit(query, title, role, wrong):
    intent = parse_intent(query, [])
    assert role in {group[0] for group in intent.terms}
    assert "deposit" not in {group[0] for group in intent.terms}
    metadata = "search-freq-quarterly search-freq-annual"
    assert eligible(query, title, metadata)
    assert not eligible(query, wrong, metadata)
    for qualifier in ("net", "private", "age 65", "unknownindustry", "kilowatts"):
        assert qualifier in prepare_subject_roles("earnings contribution to income change " + qualifier)
        assert not eligible(query + " " + qualifier, title, metadata)


@pytest.mark.parametrize("query,title", [
    ("farm earnings annual", "Income and earnings by industry: Farm earnings"),
    ("заработки в фермерских хозяйствах ежегодно", "Заработки в фермерских хозяйствах"),
])
def test_farm_earnings_do_not_become_average_employee_salary(query, title):
    intent = parse_intent(query, [])
    assert "farm-earnings" in {group[0] for group in intent.terms}
    assert "wages-nominal" not in {group[0] for group in intent.terms}
    assert eligible(query, title, "search-freq-annual")
    assert not eligible(query, "Average farm salary", "search-freq-annual")
    assert not eligible(query + " net", title, "search-freq-annual")
    assert not eligible(query + " hired workers", title, "search-freq-annual")


@pytest.mark.parametrize("query,title", [
    ("employee compensation annual", "Employee compensation by industry"),
    ("оплата труда работников ежегодная", "Оплата труда по отраслям"),
])
def test_employee_compensation_preserves_its_wider_measure_definition(query, title):
    intent = parse_intent(query, [])
    assert "employee-compensation" in {group[0] for group in intent.terms}
    assert "wages-nominal" not in {group[0] for group in intent.terms}
    assert eligible(query, title, "search-freq-annual")
    assert not eligible(query, "Workers compensation benefits", "search-freq-annual")
    assert not eligible(query, "Average nominal wages", "search-freq-annual")
    assert not eligible(query + " number of employees", title, "search-freq-annual")
    assert not eligible(query + " magicalunit", title, "search-freq-annual")


@pytest.mark.parametrize("title", [
    "GDP by industry, current dollars", "GDP by industry, current prices",
    "ВВП по отраслям, текущие цены", "ВВП в текущих ценах",
])
def test_nominal_valuation_accepts_current_dollars_and_current_prices(title):
    assert eligible("nominal GDP", title)
    for wrong in ("Real GDP in constant dollars", "GDP deflator", "PPP GDP", "Real GDP in current prices"):
        assert not eligible("nominal GDP", wrong)
    assert not eligible("nominal GDP magicalindustry", title)
    assert not eligible("nominal GDP percent", title, unit_metadata("Dollars"))


def test_daily_internet_use_is_a_definition_not_observation_frequency():
    query = "daily internet use annual percent"
    intent = parse_intent(query, [])
    assert {"internet-daily-use", "search-freq-annual"} <= {group[0] for group in intent.terms}
    assert "search-freq-daily" not in {group[0] for group in intent.terms}
    metadata = "search-freq-annual search-unit-percent"
    assert eligible(query, "Population with daily internet use", metadata)
    assert not eligible(query, "Population frequently using the internet", metadata)
    assert not eligible(query, "Population with weekly internet use", metadata)
    assert not eligible(query, "Population with daily internet use", "search-freq-monthly search-unit-percent")
    assert not eligible(query + " private", "Population with daily internet use", metadata)
    assert "search-freq-daily" in {g[0] for g in parse_intent("internet expenditure daily", []).terms}


def test_relation_roles_keep_explicit_quantity_and_unknown_subsets():
    for query in ("farm earnings", "employee compensation", "earnings contribution to income change"):
        for qualifier in ("net", "gross", "private", "age 45", "magical", "kilowatts"):
            assert qualifier in prepare_subject_roles(query + " " + qualifier)
    assert not eligible("employee compensation percent", "Employee compensation", unit_metadata("Dollars"))
    assert not eligible("employee compensation persons", "Employee compensation", unit_metadata("Dollars"))


@pytest.mark.parametrize("query,title", [
    ("cannot afford small weekly personal spending annual", "People who cannot afford a small amount of money to spend each week on themselves"),
    ("не могли позволить себе небольшие еженедельные траты на себя ежегодно", "Люди, которым недоступны небольшие еженедельные траты на себя"),
])
def test_weekly_spending_defines_annual_deprivation_and_keeps_negative_polarity(query, title):
    intent = parse_intent(query, [])
    assert {"deprivation-weekly-spending", "search-freq-annual"} <= {g[0] for g in intent.terms}
    assert "search-freq-weekly" not in {g[0] for g in intent.terms}
    assert eligible(query, title, "search-freq-annual")
    assert not eligible(query, "People who can afford small weekly personal spending", "search-freq-annual")
    assert not eligible(query, title, "search-freq-monthly")
    assert not eligible(query + " all quintiles", title, "search-freq-annual")
    assert not eligible(query + " private", title, "search-freq-annual")
    assert "cannot" not in prepare_subject_roles("can afford small weekly personal spending")
    prepared = prepare_subject_roles("cannot afford small weekly personal spending every income group не employed")
    assert "every income group не employed" in prepared
