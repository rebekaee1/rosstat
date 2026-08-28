"""Матчинг поискового спроса (demand_router): реальные запросы Вебмастера.

Кластеры 2026-08 — топ непокрытых показов за 90 дней. Заодно фиксирует
два контракта маршрутизатора: год в запросе ведёт на годовой лендинг,
«сегодня» не даёт года (карточка, не архив).
"""
from app.services.demand_router import match_query


def test_auto_loan_cluster_with_year_lands_on_year_page():
    route = match_query("ставки по автокредитам в 2019")
    assert route.matched and route.code == "auto-loan-rate"
    assert route.year == 2019
    assert route.path == "/russia/indicator/auto-loan-rate/2019"


def test_auto_loan_word_order_and_percentage():
    for q in ("средний процент по автокредиту 2019", "автокредит процентная ставка 2019"):
        r = match_query(q)
        assert r.code == "auto-loan-rate" and r.year == 2019, q


def test_ruonia_today_goes_to_card_without_year():
    route = match_query("руония на сегодня")
    assert route.matched and route.code == "ruonia"
    assert route.year is None
    assert route.path == "/russia/indicator/ruonia"

    translit = match_query("ставка RUONIA на сегодня")
    assert translit.code == "ruonia" and translit.year is None

    # «ставка руония» не должна утонуть в key-rate через общий «ставк».
    assert match_query("ставка руония").code == "ruonia"
    # Кириллический и латинский транслит тикера.
    assert match_query("МРОНИЯ овернайт").code == "ruonia"
    assert match_query("mronia").code == "ruonia"


def test_cpi_full_phrase_not_only_abbreviation():
    # «ипц» — аббревиатура; полный фразеологизм матчится через стемы,
    # несмотря на падежные окончания («потребительских»).
    route = match_query("индекс потребительских цен на 2026 год")
    assert route.matched and route.code == "cpi"
    assert route.year == 2026
    assert route.path == "/russia/indicator/cpi/2026"


def test_deposits_volumes_vs_deposit_rate():
    # Голое «вклады» — объёмы; «ставка/процент + вклад» — ставка.
    volumes = match_query("вклады населения")
    assert volumes.code == "deposits-individual" and volumes.year is None

    rate_year = match_query("ставка по вкладам в 2019")
    assert rate_year.code == "deposit-rate" and rate_year.year == 2019
    assert rate_year.path == "/russia/indicator/deposit-rate/2019"

    pct = match_query("процент по вкладу 2024")
    assert pct.code == "deposit-rate" and pct.year == 2024


def test_business_deposits_specific_beats_generic():
    route = match_query("депозиты юридических лиц")
    assert route.code == "deposits-business" and route.year is None


def test_mortgage_percent_with_year():
    route = match_query("процент по ипотеке 2014")
    assert route.matched and route.code == "mortgage-rate"
    assert route.year == 2014
    assert route.path == "/russia/indicator/mortgage-rate/2014"

    # Чередование к/ч: «ипотечная ставка» мачтится тем же корнем.
    assert match_query("ипотечная ставка").code == "mortgage-rate"


def test_ipi_family_routing():
    overall = match_query("индекс промышленного производства")
    assert overall.code == "ipi" and overall.year is None

    mining = match_query("добыча полезных ископаемых")
    assert mining.code == "ipi-mining"

    manufacturing = match_query("обрабатывающее производство")
    assert manufacturing.code == "ipi-manufacturing"


def test_budget_pairs_route_but_bare_budget_stays_unmatched():
    # Дискреция: голое «бюджет» — карта пробелов отчёта; пары со словом
    # «доходы/расходы/дефицит» однозначны и маршрутизируются.
    assert match_query("федеральный бюджет по годам").code is None
    assert match_query("дефицит бюджета 2026").code == "budget-deficit"
    assert match_query("исполнение бюджета доходы 2025").code == "budget-revenue"

    # Конъюнкция обоих рядов («доходы и расходы…») детерминированно уходит
    # на страницу расходов: стем-пара «расходы+бюджет» длиннее «доходы+бюджет».
    conjunction = match_query("доходы и расходы федерального бюджета по годам")
    assert conjunction.code == "budget-expenditure"


def test_existing_coverage_not_regressed():
    assert match_query("ключевая ставка цб").code == "key-rate"
    assert match_query("инфляция в россии").code == "cpi"
    assert match_query("курс доллара к рублю").code == "usd-rub"
    assert match_query("валовой внутренний продукт").code == "gdp-nominal"


def test_blacklist_still_blocks():
    route = match_query("график сп 500")
    assert not route.matched
    assert any(reason.startswith("blacklist:") for reason in route.reasons)
