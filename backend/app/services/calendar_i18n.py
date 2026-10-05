"""English text for public calendar events.

Descriptions are stored once, in Russian, next to the event. For an English page the API answers with the
English twin of the per-indicator context sentence (what the indicator measures); a description that has no
twin is left out rather than shown in the wrong language. Keys are the calendar rule codes used in
``INDICATOR_CALENDAR_CONTEXT``.
"""
from __future__ import annotations

INDICATOR_CALENDAR_CONTEXT_EN: dict[str, str] = {
    "cpi": "The consumer price index tracks how the cost of a fixed basket of goods and services changes. It is the main measure of inflation for households.",
    "cpi-food": "Change in retail prices of food, the grocery part of consumer inflation.",
    "cpi-nonfood": "Change in retail prices of non-food goods, one of the parts of consumer inflation.",
    "cpi-services": "Change in prices of paid services for households, the services part of consumer inflation.",
    "ipi": "The industrial production index shows how output changes in mining, manufacturing, energy and water supply.",
    "unemployment": "The share of the labour force that has no job but is actively looking for one, measured by the International Labour Organization method.",
    "wages-nominal": "Average monthly wages paid by organisations, before tax.",
    "retail-trade": "The value of goods sold to households through shops and markets, a gauge of consumer demand.",
    "housing-commissioned": "Floor area of new homes put into use, a gauge of housing construction activity.",
    "ppi": "The producer price index shows how factory-gate prices change. It usually moves ahead of consumer inflation.",
    "construction-work": "The value of construction work carried out.",
    "gdp-nominal": "The market value of all final goods and services produced in the country in a quarter, at current prices.",
    "gdp-real": "Output of goods and services at constant prices, with the effect of inflation removed.",
    "budget-revenue": "Federal budget receipts: tax and non-tax revenue for the month.",
    "budget-expenditure": "Actual spending of the federal budget for the month.",
    "budget-deficit": "The difference between federal revenue and spending: a surplus when revenue is higher, a deficit when it is lower.",
    "usd-rub": "The official US dollar to rouble rate set by the Bank of Russia.",
    "eur-rub": "The official euro to rouble rate set by the Bank of Russia.",
    "cny-rub": "The official Chinese yuan to rouble rate set by the Bank of Russia.",
    "gold-price": "The accounting price of gold set by the Bank of Russia from world quotes.",
    "ruonia": "The average rate at which the largest banks lend roubles to each other overnight.",
    "key-rate": "The key rate is the Bank of Russia's main monetary policy tool. It sets the price of money in the economy.",
    "international-reserves": "The state's highly liquid foreign assets: foreign currency, gold and the reserve position in international financial institutions.",
    "m2": "Money supply M2: cash plus rouble balances of companies and households.",
    "m1": "Money supply M1: cash plus balances that can be withdrawn at any moment.",
    "m0": "Money supply M0: cash in circulation outside banks.",
    "business-credit": "Loans issued by banks to companies.",
    "consumer-credit": "Loans issued by banks to individuals.",
    "deposits-business": "Companies' funds held in bank accounts and deposits.",
    "deposits-individual": "Individuals' funds held in bank accounts and deposits.",
    "deposit-rate": "The average interest rate on bank deposits.",
    "credit-rate-corp-short": "The average rate on short-term loans to companies (up to 1 year).",
    "credit-rate-corp-1to3y": "The average rate on loans to companies for 1 to 3 years.",
    "credit-rate-corp-over3y": "The average rate on loans to companies for over 3 years.",
    "credit-rate-ind-short": "The average rate on short-term loans to individuals (up to 1 year).",
    "credit-rate-ind-1to3y": "The average rate on loans to individuals for 1 to 3 years.",
    "credit-rate-ind-over3y": "The average rate on loans to individuals for over 3 years.",
    "mortgage-rate": "The average rate on home loans (mortgages).",
    "auto-loan-rate": "The average rate on car loans.",
    "exports": "The value of goods shipped out of Russia in the month.",
    "imports": "The value of goods brought into Russia in the month.",
    "trade-balance": "The balance of goods trade: exports minus imports.",
    "services-exports": "The value of services provided by Russian residents to non-residents.",
    "services-imports": "The value of services received by Russian residents from non-residents.",
    "current-account": "The current account balance: trade in goods and services plus primary and secondary income.",
    "external-debt": "Total debt of the Russian state, banks and companies to non-residents.",
    "fdi-net": "Net inflow of foreign direct investment into the non-bank sector.",
}

# Russian context texts as they were stored before the wording was simplified. Events created from them stay in
# the database until the next calendar sync, so the English lookup keeps recognising them.
LEGACY_CONTEXT_RU: dict[str, str] = {
    "ipi": "Индекс промышленного производства отражает динамику выпуска в добыче, обработке, энергетике и водоснабжении относительно базового периода.",
    "ruonia": "Индикативная взвешенная ставка однодневных рублёвых межбанковских кредитов крупнейших банков.",
    "exports": "Стоимость вывезенных из России товаров за период.",
    "imports": "Стоимость ввезённых в Россию товаров за период.",
    "budget-revenue": "Поступления в федеральный бюджет: налоговые и неналоговые доходы за отчётный период.",
    "budget-expenditure": "Кассовые расходы федерального бюджета за отчётный период.",
    "m2": "Денежный агрегат М2 — наличные деньги и средства на рублёвых счетах организаций и населения.",
    "m1": "Денежный агрегат М1 — наличные деньги и средства на текущих счетах до востребования.",
    "m0": "Денежный агрегат М0 — наличные деньги в обращении вне банковской системы.",
}


def english_event_description(description: str | None, indicator_code: str | None = None) -> str | None:
    """English twin of a stored (Russian) event description, or None when there is no translation."""
    from app.services.calendar_sources.official_calendar import INDICATOR_CALENDAR_CONTEXT

    text = (description or "").strip()
    if not text:
        return None
    for table in (INDICATOR_CALENDAR_CONTEXT, LEGACY_CONTEXT_RU):
        for code, ru in table.items():
            if text.startswith(ru):
                return INDICATOR_CALENDAR_CONTEXT_EN.get(code)
    if indicator_code:
        return INDICATOR_CALENDAR_CONTEXT_EN.get(indicator_code)
    return None
