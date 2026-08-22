"""English public copy overlay for macro indicators.

Key = indicator code. Overlay wins over seed ``name_en`` / RU description
and methodology when the locale resolver applies EN. Do not put file names,
API ids, or implementation jargon in these strings.

Listed catalogue cards have full name/description/methodology/unit.
Unlisted siblings have economist names + short methodology (chart modes
inherit detail from the listed parent / view-mode EN twins).
"""

from __future__ import annotations

from typing import TypedDict


class IndicatorCopyEn(TypedDict, total=False):
    name: str
    description: str
    methodology: str
    unit: str


INDICATOR_COPY_EN: dict[str, IndicatorCopyEn] = {
    # --- Listed catalogue cards ---
    "cpi": {
        "name": "Consumer Price Index",
        "description": "The consumer price index (CPI) measures changes in prices of goods and services purchased by households for final consumption. It is the main gauge of consumer inflation and is used to index wages, pensions and social transfers.",
        "methodology": "The CPI compares the cost of a fixed basket of goods and services in the current period with its cost in the base period. Rosstat observes prices across a broad sample of localities and items. On the card, the default comparison base is the previous month (100 means no change).",
        "unit": "%",
    },
    "cpi-food": {
        "name": "Food CPI",
        "description": "The food CPI tracks prices of foodstuffs in the consumer basket. It shows how much grocery prices contribute to overall inflation and often leads turning points in the headline CPI.",
        "methodology": "Calculated by Rosstat as the price index for food items relative to the previous month (100 means no change). The same observation network and basket weights apply as for the headline CPI, restricted to the food segment. Chart modes on the card (trailing 12-month inflation, month-on-month, weekly, index) reuse this series.",
        "unit": "%",
    },
    "cpi-nonfood": {
        "name": "Non-food CPI",
        "description": "The non-food CPI tracks prices of non-food goods in the consumer basket — clothing, durables, fuel at the pump and other merchandise excluding food and services.",
        "methodology": "Rosstat publishes the non-food goods price index relative to the previous month. Coverage matches the non-food part of the CPI basket. Mode switches on the card transform the same official monthly (and weekly) series without changing the underlying source.",
        "unit": "%",
    },
    "cpi-services": {
        "name": "Services CPI",
        "description": "The services CPI measures prices of consumer services — housing and utilities, transport, communications, education, healthcare and other paid services in the household basket.",
        "methodology": "Rosstat calculates the services price index relative to the previous month using the services segment of the CPI basket. Chart modes on the card (trailing 12-month inflation, period growth, step changes, cumulative index) are derived from this official series.",
        "unit": "%",
    },
    "key-rate": {
        "name": "Key rate",
        "description": "The key rate is the Bank of Russia’s main monetary policy instrument. It anchors money-market rates and influences lending and deposit pricing across the banking system. Before 13 September 2013 the historical series uses the refinancing rate, which served the same policy role.",
        "methodology": "Official Bank of Russia key rate in percent per annum: each point is the rate in force from the decision date; between Board of Directors meetings the value does not change. Before 13 September 2013 the series historically shows the refinancing rate; from 2016 that rate was set equal to the key rate. The card also offers averages over week, month, quarter and year — computed from the same official series.",
        "unit": "%",
    },
    "usd-rub": {
        "name": "USD/RUB exchange rate",
        "description": "Official US dollar to Russian ruble exchange rate set by the Bank of Russia. Quoted as rubles per one US dollar and updated every business day.",
        "methodology": "The Bank of Russia sets the official USD/RUB rate daily from foreign-exchange market outcomes. Each point is the rate for that date in rubles per US dollar. Daily values and period averages (week, month, quarter, year) on the card come from the same series.",
        "unit": "RUB",
    },
    "eur-rub": {
        "name": "EUR/RUB exchange rate",
        "description": "Official euro to Russian ruble exchange rate set by the Bank of Russia. Quoted as rubles per one euro and updated every business day.",
        "methodology": "Official EUR/RUB rate that the Bank of Russia sets daily from foreign-exchange market outcomes. Each point is the rate for that date in rubles per one euro. The card offers the daily value and averages over week, month, quarter and year — the averages are computed from the same series for easier trend comparison.",
        "unit": "RUB",
    },
    "cny-rub": {
        "name": "CNY/RUB exchange rate",
        "description": "Official Chinese yuan to Russian ruble exchange rate set by the Bank of Russia. Quoted as rubles per one yuan and updated every business day.",
        "methodology": "Official CNY/RUB rate set daily by the Bank of Russia from foreign-exchange market outcomes. Each point is the rate for that date in rubles per yuan. Daily values and averages over week, month, quarter and year are computed from the same series for trend comparison.",
        "unit": "RUB",
    },
    "ruonia": {
        "name": "RUONIA",
        "description": "RUONIA (Ruble Overnight Index Average) is the indicative volume-weighted average rate on overnight ruble interbank loans and deposits.",
        "methodology": "Indicative volume-weighted rate on overnight ruble interbank loans and deposits; calculated by the Bank of Russia from deals of participating banks. Published on business days. The card offers the daily level and averages over week, month, quarter and year — the averages are computed from the same series for easier comparison.",
        "unit": "%",
    },
    "m0": {
        "name": "Money supply M0",
        "description": "Cash in circulation outside the banking system (monetary aggregate M0). Published monthly as of the first day of the month.",
        "methodology": "M0 is cash outside banks in billions of rubles at month-end, as estimated by the Bank of Russia. The card shows the monthly series and quarterly/annual averages; no forecast is produced. The money-aggregates family links M0 with narrow M1 and broad M2 without resetting the chart mode.",
        "unit": "bln RUB",
    },
    "m2": {
        "name": "Money supply M2",
        "description": "Broad money (aggregate M2): cash plus residents’ transferable and other deposits. Published monthly as of the first day of the month.",
        "methodology": "Broad money M2 in billions of rubles at month-end — the Bank of Russia’s main liquidity aggregate. Monthly path and averages over quarter and year on the card; no forecast is produced. The money-aggregates family also links cash M0 and aggregate M1 for comparison on aligned dates.",
        "unit": "bln RUB",
    },
    "mortgage-rate": {
        "name": "Mortgage rate",
        "description": "Weighted-average interest rate on ruble mortgage loans to resident households.",
        "methodology": "Weighted-average annual rate on ruble residential mortgages to resident individuals: new contracts and outstanding deals enter the calculation, weighted by monthly origination volumes from bank reporting. Published by the Bank of Russia monthly, usually with a one- to two-month lag. The card has a single mode — the rate level in percent per annum, without a separate maturity split.",
        "unit": "%",
    },
    "deposit-rate": {
        "name": "Deposit rate",
        "description": "Weighted-average interest rate on ruble household deposits with maturity up to one year, including demand deposits.",
        "methodology": "Published monthly by the Bank of Russia as a volume-weighted average of rates on household ruble deposits in the short-term bucket. Use the term switcher on the card for 1–3 years and over 3 years. The chart shows the rate level, not the month-on-month change.",
        "unit": "%",
    },
    "auto-loan-rate": {
        "name": "Auto loan rate",
        "description": "Weighted-average interest rate on ruble auto loans to households, all maturities combined.",
        "methodology": "Volume-weighted average rate on new and rolled-over ruble auto loans to households. The all-maturities aggregate reflects the mix of originations without a maturity breakdown. Calculated by the Bank of Russia from banks’ weighted-average rate reporting. Published monthly with about a one-month lag.",
        "unit": "%",
    },
    "credit-rate-corp-short": {
        "name": "Corporate loan rate",
        "description": "Weighted-average interest rate on ruble loans to non-financial organisations with maturity up to one year, including demand facilities.",
        "methodology": "Short-term corporate lending rate published monthly by the Bank of Russia from bank reporting. The term switcher on the card opens the 1–3 year and over-3-year buckets. The series is a rate level for the reporting month, not a change versus the previous month.",
        "unit": "%",
    },
    "credit-rate-ind-short": {
        "name": "Household loan rate",
        "description": "Weighted-average interest rate on ruble loans to households with maturity up to one year, including demand facilities.",
        "methodology": "Short-term household lending rate published monthly by the Bank of Russia from bank reporting. Switch terms on the card for medium- and long-term buckets. The chart shows the rate level for the month.",
        "unit": "%",
    },
    "unemployment": {
        "name": "Unemployment rate",
        "description": "Share of the labour force that is unemployed under International Labour Organization definitions. Based on Rosstat’s labour force survey.",
        "methodology": "Monthly unemployment rate as a percent of the labour force at month-end. Source: Rosstat labour force survey. The card offers the monthly path, a quarterly average and a trailing 12-month average via the smoothing switcher. Compare with employment and labour force in the same labour-market category.",
        "unit": "%",
    },
    "wages-nominal": {
        "name": "Average nominal wages",
        "description": "Average monthly nominal accrued wages of employees in organisations.",
        "methodology": "Average monthly nominal accrued wages of employees in organisations: gross accruals before personal income tax, including social payments under Rosstat rules. Coverage is large and medium organisations; sole proprietors and small business are outside the indicator. The card offers a monthly series from 2015 and an annual series from 1991 (frequency switcher); real wages adjusted for inflation appear as a separate series in the wages switcher. Publication usually lags the reference period by about two months.",
        "unit": "RUB",
    },
    "gdp-nominal": {
        "name": "Nominal GDP",
        "description": "Gross domestic product at current market prices (expenditure approach). Quarterly data.",
        "methodology": "Russia’s GDP in current prices from Rosstat quarterly national accounts. Each point is the quarterly volume in billions of rubles; history from 1995. Year-on-year and quarter-on-quarter growth and calendar-year totals are available via chart modes.",
        "unit": "bln RUB",
    },
    "gdp-real": {
        "name": "Real GDP",
        "description": "Gross domestic product in constant 2021 prices. Quarterly national accounts.",
        "methodology": "Russia’s GDP in constant 2021 prices from Rosstat quarterly estimates in the System of National Accounts. The series shows output volume without current-price effects; history from 1995. Year-on-year and quarter-on-quarter growth rates, and the calendar-year sum, are available via the mode switcher on the card.",
        "unit": "bln RUB",
    },
    "wages-real": {
        "name": "Real wages",
        "description": "Real wages measure the purchasing power of average accrued pay after adjusting for consumer inflation. Shown as an index with January 2015 = 100: a rising line means wages outpaced prices.",
        "methodology": "Nominal accrued wages are deflated by the consumer price index and rebased to 100 in January 2015. The index shows how real purchasing power evolved relative to the start of the series. Source: Rosstat.",
        "unit": "index",
    },
    "housing-affordability": {
        "name": "Housing affordability index",
        "description": "Ratio of the wages index to the secondary housing price index, both on a common 2010 base. Values above 100 mean wages have risen faster than housing costs since the base period (affordability improves); below 100 the opposite.",
        "methodology": "Computed monthly as (wages index ÷ secondary housing price index) × 100, both series on a 2010 base. The secondary market is used as the broader, less policy-distorted housing benchmark. Source inputs: Rosstat.",
        "unit": "index",
    },
    "m1": {
        "name": "Money supply M1",
        "description": "Monetary aggregate M1: cash (M0) plus transferable deposits. Published monthly as of the first day of the month.",
        "methodology": "Monetary aggregate M1 in billions of rubles: cash (M0) and transferable demand deposits at month-end as estimated by the Bank of Russia. The card shows the monthly series and quarterly and annual averages; no forecast is produced. The money-aggregates family lets you switch to M0 and M2 while keeping the chart mode.",
        "unit": "bln RUB",
    },
    "consumer-credit": {
        "name": "Household credit",
        "description": "Outstanding bank loans to households (stock). Bank of Russia banking-sector data.",
        "methodology": "Total household loan stock in trillions of rubles at month-end — mortgages, consumer and other ruble loans in one banking-sector portfolio. Source: Bank of Russia. Monthly stocks and quarterly or annual averages are available; in the household credit and deposits family the related series is household deposits in billions of rubles on the same dates. This is a debt stock, not monthly originations or rates on new contracts.",
        "unit": "trln RUB",
    },
    "business-credit": {
        "name": "Corporate credit",
        "description": "Outstanding bank loans to non-financial corporations and sole proprietors (stock). Bank of Russia data.",
        "methodology": "Total loan stock to non-financial organisations and individual entrepreneurs in trillions of rubles at month-end — working-capital and investment lending in one ruble portfolio. Source: Bank of Russia. Monthly path and quarterly or annual averages on the card. The indicator is the outstanding stock, not the volume of new originations.",
        "unit": "trln RUB",
    },
    "deposits-individual": {
        "name": "Household deposits",
        "description": "Total household deposits: transferable, time and foreign-currency accounts.",
        "methodology": "Stock of household bank deposits in billions of rubles at month-end — transferable, time and foreign-currency deposits in one aggregate. Source: Bank of Russia. The card shows monthly stocks and averages over quarters or years; the household credit-and-deposits family also includes household loans in trillions of rubles on the same dates. This is the stock of funds attracted, not monthly inflows or the average deposit rate.",
        "unit": "bln RUB",
    },
    "deposits-business": {
        "name": "Business deposits",
        "description": "Total deposits of non-financial organisations: transferable, time and foreign-currency accounts.",
        "methodology": "Stock of corporate deposits in banks in billions of rubles at month-end, Bank of Russia definition. Monthly path on the card. Compare with household deposits and corporate credit for a balance-sheet view of the banking sector.",
        "unit": "bln RUB",
    },
    "budget-deficit": {
        "name": "Federal budget balance",
        "description": "Monthly federal budget deficit (−) or surplus (+), computed as revenues minus expenditure.",
        "methodology": "Federal budget balance is the difference between revenues and expenditure for the calendar month in billions of rubles: negative values are a deficit, positive values a surplus. Source: Ministry of Finance of Russia. The card shows the monthly series and quarterly or annual averages; the family switcher links to revenue and expenditure for the same budget.",
        "unit": "bln RUB",
    },
    "housing-price-primary": {
        "name": "Primary housing price index",
        "description": "Quarterly prices of new-build apartments: index with 2010 = 100, plus quarter-on-quarter and year-on-year growth. A core primary-market housing indicator.",
        "methodology": "Rosstat’s quarterly primary-market housing price index. The card shows the index level, change versus the previous quarter and versus the same quarter a year earlier. History from 1998; a multi-quarter forecast may be available.",
        "unit": "index",
    },
    "housing-price-secondary": {
        "name": "Secondary housing price index",
        "description": "Quarterly secondary-market prices: index with 2010 = 100, plus quarter-on-quarter and year-on-year growth. Reflects transactions in the existing housing stock.",
        "methodology": "Separate Rosstat quarterly index for secondary-market transactions. The chart shows the index level, quarterly change and year-on-year growth; the housing-market switcher opens primary new-builds. History from 1998; four-quarter forecast.",
        "unit": "index",
    },
    "ipi": {
        "name": "Industrial production index",
        "description": "Industrial production index (2023 = 100): mining, manufacturing, electricity and gas, water and waste. Monthly Rosstat data.",
        "methodology": "Aggregate output index across the four main industry sections, rebased to the 2023 monthly average = 100. Weights of activities are fixed for a multi-year period. Published monthly by Rosstat with about a one-month lag. Section series (mining, manufacturing, energy, water) share the same family switcher.",
        "unit": "index",
    },
    "ipi-mining": {
        "name": "Industrial production: mining",
        "description": "Output index for mining and quarrying (2023 = 100): coal, oil, gas, ores and other minerals. Monthly Rosstat data.",
        "methodology": "Output index for OKVED2 section B (mining and quarrying) — one of four industrial-production components. Activity weights are fixed for a five-year period; the series is rebased to the 2023 monthly average = 100. Published monthly by Rosstat with a one-month lag.",
        "unit": "index",
    },
    "ipi-manufacturing": {
        "name": "Industrial production: manufacturing",
        "description": "Output index for manufacturing (2023 = 100): food, chemicals, metals, machinery and other processing industries. Monthly Rosstat data.",
        "methodology": "Output index for manufacturing — the largest of the four industrial-production components. Industry weights are fixed for a five-year period; the series is rebased to the 2023 monthly average = 100. Published monthly by Rosstat with about a one-month lag.",
        "unit": "index",
    },
    "ipi-energy": {
        "name": "Industrial production: electricity and gas",
        "description": "Output index for electricity, gas, steam and air conditioning supply (2023 = 100). Monthly Rosstat data.",
        "methodology": "Output index for OKVED2 section D (electricity, gas and steam supply) — one of four components of industrial production. Activity weights are fixed for a five-year period; the series is rebased to the 2023 monthly average = 100. Published monthly by Rosstat with about a one-month lag. The series has strong seasonality.",
        "unit": "index",
    },
    "ipi-water": {
        "name": "Industrial production: water supply",
        "description": "Output index for water supply, sewerage, waste collection and disposal (2023 = 100). Monthly Rosstat data.",
        "methodology": "Output index for OKVED2 section E (water supply, sewerage, waste collection and disposal) — the smallest of the four industrial-production components. Activity weights are fixed for a five-year period; the series is rebased to the 2023 monthly average = 100. Published monthly by Rosstat with about a one-month lag.",
        "unit": "index",
    },
    "population": {
        "name": "Population",
        "description": "Resident population of Russia as of 1 January (millions). Long Rosstat historical series from 1897, with annual values from 1970.",
        "methodology": "Resident population on 1 January from Rosstat current demographic accounts. Figures for 1897 and 1914 are shown within present-day Russian territory for long-run comparability.",
        "unit": "mln people",
    },
    "population-natural-growth": {
        "name": "Natural population change",
        "description": "Natural population change for the calendar year: births minus deaths, in thousands of people. Positive values mean natural increase; negative values mean natural decrease.",
        "methodology": "Annual difference between registered live births and deaths on the territory of Russia. Source: Rosstat vital statistics. Compare with migration and total population change in the same demographics group.",
        "unit": "ths people",
    },
    "population-total-growth": {
        "name": "Total population change",
        "description": "Total population change for the calendar year: natural change plus net migration, in thousands of people.",
        "methodology": "Sum of natural change and net migration for the year. Source: Rosstat. The series reconciles how the resident population stock evolves between 1 January readings.",
        "unit": "ths people",
    },
    "population-migration": {
        "name": "Net migration",
        "description": "Net migration for the calendar year, in thousands of people. Rosstat data from 1990.",
        "methodology": "Difference between arrivals and departures recorded in migration statistics for the year. Source: Rosstat. Together with natural change it explains total population change.",
        "unit": "ths people",
    },
    "current-account": {
        "name": "Current account balance",
        "description": "Current-account balance of Russia’s balance of payments. Quarterly data in millions of US dollars. Source: Bank of Russia.",
        "methodology": "Net balance on goods, services, primary and secondary income for the quarter under BPM6 balance-of-payments methodology. Positive values are a surplus. Source: Bank of Russia.",
        "unit": "mln USD",
    },
    "ppi": {
        "name": "Producer price index",
        "description": "Producer price index for industrial goods (2010 = 100). Monthly Rosstat data.",
        "methodology": "Tracks wholesale prices of industrial products sold on the domestic market. Built from a sample of enterprises and products and published monthly by Rosstat. Rebased to 2010 = 100; history accumulates from 2010. Chart modes cover month-on-month, year-on-year and index views.",
        "unit": "index",
    },
    "exports": {
        "name": "Goods exports",
        "description": "Exports of goods from Russia under balance-of-payments methodology. Quarterly data in millions of US dollars. Source: Bank of Russia.",
        "methodology": "Value of goods exports for the quarter in millions of US dollars. Balance-of-payments basis (not customs declarations alone). Source: Bank of Russia.",
        "unit": "mln USD",
    },
    "imports": {
        "name": "Goods imports",
        "description": "Imports of goods into Russia under balance-of-payments methodology. Quarterly data in millions of US dollars. Source: Bank of Russia.",
        "methodology": "Value of goods imports for the quarter in millions of US dollars on a balance-of-payments basis. Source: Bank of Russia.",
        "unit": "mln USD",
    },
    "trade-balance": {
        "name": "Trade balance",
        "description": "Goods trade balance (exports minus imports) under balance-of-payments methodology. Quarterly data. Source: Bank of Russia.",
        "methodology": "Difference between goods exports and imports for the quarter in millions of US dollars. Positive values are a surplus. Source: Bank of Russia.",
        "unit": "mln USD",
    },
    "international-reserves": {
        "name": "International reserves",
        "description": "International (gold and foreign-exchange) reserves of the Russian Federation. Weekly Bank of Russia data in billions of US dollars.",
        "methodology": "International reserves of the Russian Federation in billions of US dollars on the Bank of Russia publication date: foreign-currency assets, SDRs, the IMF reserve position and monetary gold in one aggregate. The card shows the weekly series and monthly, quarterly and annual averages from the same source; no forecast is produced. Increases or decreases reflect accumulation, use of reserves and asset revaluation.",
        "unit": "bln USD",
    },
    "external-debt": {
        "name": "External debt",
        "description": "Gross external debt of the Russian Federation in millions of US dollars. Quarterly stocks from 2003. Bank of Russia.",
        "methodology": "Total external liabilities of Russian residents to non-residents in millions of US dollars at quarter-end — the all-sectors aggregate as estimated by the Bank of Russia. Source: Bank of Russia. The chart shows the quarterly stock and the average of quarters within a year, with a near-term quarterly forecast. This is a debt stock on the reference date, not new borrowing during the quarter.",
        "unit": "mln USD",
    },
    "gdp-consumption": {
        "name": "Household consumption",
        "description": "Household final consumption expenditure at current prices. Expenditure-side GDP component. Quarterly data.",
        "methodology": "Household final consumption expenditure — a component of GDP by expenditure at current prices, in billions of rubles. Covers purchases of goods and services by households, including imputed housing services of owner-occupiers. Compiled by Rosstat under the System of National Accounts and released quarterly; history on Forecast Economy from 1995. Quarterly levels and annual averages are available; the forecast applies to the quarterly view.",
        "unit": "bln RUB",
    },
    "gdp-government": {
        "name": "Government consumption",
        "description": "General government final consumption expenditure at current prices. Expenditure-side GDP component.",
        "methodology": "General government final consumption — a component of GDP by the expenditure approach at current prices, in billions of rubles. It includes compensation of public-sector employees, government purchases of goods and services, and consumption of fixed capital of government institutions. Compiled by Rosstat under the System of National Accounts and published quarterly; history from 1995. The card shows the quarterly series, annual averages and a forecast in the quarterly mode. It does not match monthly federal budget execution.",
        "unit": "bln RUB",
    },
    "gdp-investment": {
        "name": "Gross fixed capital formation",
        "description": "Gross fixed capital formation at current prices. Covers construction, machinery, transport and related assets. Quarterly data.",
        "methodology": "Gross fixed capital formation is a GDP expenditure component (investment in fixed assets: buildings, structures, machinery, equipment, software and intellectual property). Calculated by Rosstat under SNA 2008 national accounts methodology and published quarterly. The historical series from 1995 is aligned to a common OKVED2 classification.",
        "unit": "bln RUB",
    },
    "labor-force": {
        "name": "Labour force",
        "description": "Economically active population (labour force). Rosstat labour force survey.",
        "methodology": "Labor force — economically active population in millions at month-end: employed plus unemployed under International Labour Organization definitions. Source: Rosstat labor force survey. The card shows the monthly series and averages over quarters and years; switching from employment in the labor-market employment group keeps the selected chart mode. No forecast is produced.",
        "unit": "mln people",
    },
    "employment": {
        "name": "Employment",
        "description": "Number of employed persons from Rosstat’s labour force survey.",
        "methodology": "Employed persons — those with paid work and those temporarily absent from a job — in millions at month-end from Rosstat’s labor force survey. The card shows the monthly series and averages over quarters and years; the labor-force tab in the same group shows the wider aggregate on the same dates. No forecast is produced.",
        "unit": "mln people",
    },
    "budget-revenue": {
        "name": "Federal budget revenue",
        "description": "Federal budget revenue by calendar month. Derived from Ministry of Finance open budget-execution data.",
        "methodology": "Federal budget revenue — tax and non-tax receipts for the calendar month in billions of rubles. Source: Ministry of Finance of Russia. Monthly values are recovered from official budget-execution statistics; monthly levels and quarterly or annual averages are available. The series is aligned with the expenditure and deficit/surplus cards in the federal-budget group.",
        "unit": "bln RUB",
    },
    "budget-expenditure": {
        "name": "Federal budget expenditure",
        "description": "Federal budget expenditure by calendar month. Derived from Ministry of Finance open budget-execution data.",
        "methodology": "Executed federal spending for the calendar month in billions of rubles. Source: Ministry of Finance of Russia. The monthly series appears in open execution statistics; the card offers a monthly view or averages over quarter or year. Aligned with revenue and balance in the federal-budget family.",
        "unit": "bln RUB",
    },
    "services-exports": {
        "name": "Services exports",
        "description": "Exports of services from Russia under balance-of-payments methodology. Quarterly data in millions of US dollars.",
        "methodology": "Value of services credits for the quarter (transport, travel, business services and other) in millions of US dollars. Source: Bank of Russia.",
        "unit": "mln USD",
    },
    "services-imports": {
        "name": "Services imports",
        "description": "Imports of services into Russia under balance-of-payments methodology. Quarterly data in millions of US dollars.",
        "methodology": "Value of services debits for the quarter in millions of US dollars. Source: Bank of Russia.",
        "unit": "mln USD",
    },
    "fdi-net": {
        "name": "Net foreign direct investment",
        "description": "Net inflow of foreign direct investment on the financial account of the balance of payments (quarterly flows in millions of US dollars). Covers non-residents’ acquisition of equity stakes and debt claims on Russian companies net of withdrawals. Not the same as the accumulated stock of direct investment in the international investment position. Source: Bank of Russia consolidated balance of payments, updated quarterly with about a two-month lag after the quarter ends.",
        "methodology": "Quarterly BPM6 financial-account flows published by the Bank of Russia, typically with about a two-month lag after the quarter ends. Positive values are net inflows. Do not confuse with accumulated FDI stocks.",
        "unit": "mln USD",
    },
    "births": {
        "name": "Number of births",
        "description": "Live births during the calendar year (thousands). Rosstat data from 1990.",
        "methodology": "All live births registered by civil registration authorities in Russia during the year. The latest year may start from monthly operational counts and is revised when annual finals are released — revisions are usually fractions of a percent.",
        "unit": "ths people",
    },
    "deaths": {
        "name": "Number of deaths",
        "description": "Deaths during the calendar year (thousands). Rosstat data from 1990.",
        "methodology": "All deaths registered by civil registration authorities on the territory of Russia during the calendar year. The latest year is first published from monthly operational registration and revised after annual finals — the revision is usually a fraction of a percent.",
        "unit": "ths people",
    },
    "birth-rate": {
        "name": "Birth rate",
        "description": "Crude birth rate: live births per 1,000 mid-year population. Rosstat data.",
        "methodology": "Annual vital rate from Rosstat demographic statistics. Useful alongside the absolute number of births and the death rate for reading natural change.",
        "unit": "‰",
    },
    "death-rate": {
        "name": "Death rate",
        "description": "Crude death rate: deaths per 1,000 mid-year population. Rosstat data.",
        "methodology": "Annual vital rate from Rosstat demographic statistics. Together with the birth rate it determines natural population change.",
        "unit": "‰",
    },
    "working-age-population": {
        "name": "Working-age population",
        "description": "Population of working age (men 16–59, women 16–54 under the statistical definition used in the long Rosstat series).",
        "methodology": "Stock on the reference date from Rosstat population structure statistics. Age boundaries follow the published demographic tables for historical comparability; they may differ from the current statutory retirement ages.",
        "unit": "mln people",
    },
    "pop-under-working-age": {
        "name": "Population below working age",
        "description": "Population younger than working age (ages 0–15). Rosstat data.",
        "methodology": "Stock of children and adolescents below working age from Rosstat population structure statistics. Compare with working-age and above-working-age cohorts for dependency analysis.",
        "unit": "mln people",
    },
    "pop-over-working-age": {
        "name": "Population above working age",
        "description": "Population older than working age (men 60+, women 55+ under the long Rosstat demographic definition).",
        "methodology": "Stock of persons above working age from Rosstat population structure statistics. Boundaries follow the published tables for historical consistency.",
        "unit": "mln people",
    },
    "pensioners": {
        "name": "Number of pensioners",
        "description": "Total number of pensioners in Russia (thousands as of 1 January). Rosstat / Social Fund data.",
        "methodology": "Headcount of pension recipients at the start of the year from official demographic and social statistics. The series is an annual stock, not monthly benefit flows.",
        "unit": "ths people",
    },
    "retail-trade": {
        "name": "Retail trade turnover",
        "description": "Retail trade turnover at current prices (billions of rubles). Monthly Rosstat short-term indicators.",
        "methodology": "Value of goods sold to households through retail channels in the reporting month. Published by Rosstat in short-term economic indicators. Current-price series — volume change requires a separate deflator view if needed.",
        "unit": "bln RUB",
    },
    "construction-work": {
        "name": "Construction work volume",
        "description": "Value of work performed in construction: new building, major repairs, reconstruction and modernisation.",
        "methodology": "Construction output at current prices. Covers new construction, reconstruction, expansion and technical re-equipment of facilities of all ownership forms. Monthly figures are published by Rosstat in the short-term economic indicators release.",
        "unit": "bln RUB",
    },
    "capital-investment": {
        "name": "Fixed capital investment",
        "description": "Investment in fixed capital — spending on creating and replacing fixed assets: construction, equipment, transport and IT infrastructure. Published quarterly by Rosstat.",
        "methodology": "Volume of fixed capital investment at current prices. Covers acquisition, creation and modernisation of fixed assets (buildings, structures, machinery and equipment) by enterprises and organisations of all ownership forms. Published quarterly by Rosstat with about a two-month lag after the quarter ends; no official monthly breakdown is released for this indicator.",
        "unit": "bln RUB",
    },
    "housing-commissioned": {
        "name": "Housing completions",
        "description": "Residential floor area brought into use (millions of square metres of total floor area). Monthly Rosstat short-term indicators.",
        "methodology": "Floor area of dwellings brought into use during the month, nationwide. Source: Rosstat. Completions are a physical volume measure, distinct from construction-work value and from housing price indices.",
        "unit": "mln m²",
    },
    "depreciation-rate": {
        "name": "Fixed capital depreciation rate",
        "description": "Degree of wear of fixed assets (%). Annual Rosstat data from 1990.",
        "methodology": "Share of accumulated depreciation in the gross book value of fixed assets at year-end. Source: Rosstat. Higher values mean an older capital stock on average.",
        "unit": "%",
    },
    "grad-students": {
        "name": "Postgraduate (aspirantura) enrolment",
        "description": "Number of postgraduate research students (aspirantura) at the start of the academic year. Rosstat data.",
        "methodology": "Headcount enrolled in postgraduate research programmes at the beginning of the academic year. Source: Rosstat education and science statistics.",
        "unit": "people",
    },
    "doctoral-students": {
        "name": "Doctoral students",
        "description": "Number of doctoral candidates at the start of the academic year. Rosstat data.",
        "methodology": "Headcount in doctoral programmes at the beginning of the academic year. Source: Rosstat education and science statistics.",
        "unit": "people",
    },
    "rd-organizations": {
        "name": "R&D organisations",
        "description": "Number of organisations performing research and development. Rosstat data.",
        "methodology": "Count of legal entities that reported R&D activity in the reference year. Source: Rosstat science and innovation statistics.",
        "unit": "units",
    },
    "rd-personnel": {
        "name": "R&D personnel",
        "description": "Number of persons engaged in research and development. Rosstat data.",
        "methodology": "Headcount of R&D personnel in the reference year. Source: Rosstat science and innovation statistics.",
        "unit": "people",
    },
    "innovation-activity": {
        "name": "Innovation activity rate",
        "description": "Share of organisations that were innovation-active (%). From 2018 the indicator follows an updated Rosstat methodology aligned with the Oslo Manual (4th edition) and is not comparable with the pre-2018 series; the chart therefore starts in 2018.",
        "methodology": "Annual percentage of organisations classified as innovation-active under the post-2018 definition. Source: Rosstat. Not comparable with the pre-2018 series.",
        "unit": "%",
    },
    "tech-innovation-share": {
        "name": "Share of firms with technological innovation",
        "description": "Share of organisations that implemented technological innovations in the reporting year (%). From 2018 the indicator follows Rosstat’s updated methodology (4th edition of the Oslo Manual) and is not comparable with the earlier series, so history starts in 2018. Rosstat data.",
        "methodology": "Annual percentage under the post-2018 definition of technological innovation. Source: Rosstat. Not comparable with pre-2018 releases.",
        "unit": "%",
    },
    "small-business-innovation": {
        "name": "Small business innovation",
        "description": "Share of small enterprises that engaged in innovation activity (%). Rosstat data.",
        "methodology": "Annual percentage of small enterprises reporting innovation activity. Source: Rosstat innovation statistics.",
        "unit": "%",
    },
    "gold-price": {
        "name": "Gold price (Bank of Russia)",
        "description": "Accounting price of gold set by the Bank of Russia. Daily data in rubles per gram.",
        "methodology": "Bank of Russia accounting price of gold in rubles per gram on the publication date — an official regulatory reference, not a dollar exchange quote. Source: Bank of Russia. The card shows the daily series and averages over week, month, quarter and year from the same path; no forecast is produced. Moves in the ruble price reflect both the global metal market and the ruble exchange rate.",
        "unit": "RUB/g",
    },
    "btc-usd": {
        "name": "Bitcoin (BTC/USD)",
        "description": "Bitcoin price in US dollars from a major cryptocurrency exchange (Binance). Bitcoin is the first and largest cryptocurrency by market capitalisation; the series is used as a risk-appetite benchmark alongside gold, foreign exchange and commodity prices.",
        "methodology": "Daily bitcoin spot price in US dollars on Binance: each point is the calendar-day close. The market trades around the clock, including weekends. The series offers the daily path and averages over week, month, quarter and year computed from the same daily closes.",
        "unit": "USD",
    },
    "eth-usd": {
        "name": "Ethereum (ETH/USD)",
        "description": "Ethereum price in US dollars from a major cryptocurrency exchange (Binance). Ethereum is the second-largest cryptocurrency by market capitalisation and the leading smart-contract platform; the series is compared with bitcoin and other dollar-denominated assets.",
        "methodology": "Daily ether spot price in US dollars on Binance: each point is the calendar-day close. The market trades around the clock, including weekends. The series offers the daily path and averages over week, month, quarter and year computed from the same daily closes.",
        "unit": "USD",
    },
    "sol-usd": {
        "name": "Solana (SOL/USD)",
        "description": "Solana token price in US dollars from a major cryptocurrency exchange (Binance). Solana is one of the larger high-throughput blockchain platforms; its price reflects demand for alternative crypto assets beyond bitcoin and ether.",
        "methodology": "Daily Solana spot price in US dollars on Binance: each point is the calendar-day close. The market trades around the clock, including weekends. The series offers the daily path and averages over week, month, quarter and year computed from the same daily closes.",
        "unit": "USD",
    },
    "imoex": {
        "name": "MOEX Russia Index",
        "description": "Flagship Russian equity index — capitalisation-weighted measure of the most liquid large-cap shares. Calculated in rubles and used as the main gauge of the Russian stock market.",
        "methodology": "Calculated by Moscow Exchange in real time from transaction prices of constituents; weights are capped and reviewed quarterly. Each point in the series is the trading-day close.",
        "unit": "points",
    },
    "mcftr": {
        "name": "MOEX Total Return Index",
        "description": "Equity total-return index: price changes plus reinvested dividends. Shows the full return of a broad equity market investment, not price moves alone.",
        "methodology": "Calculated by Moscow Exchange on the same constituent base as the main equity index, but with dividends reinvested into the index. Each point is the trading-day close.",
        "unit": "points",
    },
    "rtsi": {
        "name": "RTS Index",
        "description": "Dollar-denominated Russian equity index on the same shares as the ruble market index, converted into US dollars. Sensitive to both equity prices and the ruble exchange rate.",
        "methodology": "Calculated by Moscow Exchange in US dollars from constituent trades and the exchange rate. Each point is the trading-day close.",
        "unit": "points",
    },
    "rgbi": {
        "name": "Russian Government Bond Index (RGBI)",
        "description": "Government bond (OFZ) market index based on clean prices of the most liquid fixed-coupon issues. A falling index usually accompanies rising OFZ yields; a rising index accompanies falling yields.",
        "methodology": "Calculated by Moscow Exchange from clean prices of a basket of federal loan bonds. Each point is the trading-day close.",
        "unit": "points",
    },
    "corp-bond-index": {
        "name": "MOEX Corporate Bond Index",
        "description": "Corporate bond market index reflecting total return of a basket of liquid ruble corporate issues including coupons. Used as a corporate credit-market benchmark.",
        "methodology": "Calculated by Moscow Exchange on a basket of corporate bonds as a total-return index (with coupon reinvestment). Each point is the trading-day close.",
        "unit": "points",
    },
    "usd-index": {
        "name": "Broad U.S. Dollar Index",
        "description": "Broad nominal index of the US dollar against currencies of major trading partners. January 2006 = 100. Tracks the dollar’s external value alongside commodity prices and US Treasury yields.",
        "methodology": "Daily nominal broad US dollar index from the Federal Reserve Board H.10 release. Each point is a business-day value; weekends and holidays are excluded. The card offers the daily level and averages over week, month, quarter and year from the same series; no forecast is produced.",
        "unit": "points",
    },
    "eur-usd": {
        "name": "EUR/USD exchange rate",
        "description": "ECB euro foreign exchange reference rate: US dollars per one euro. Published each euro-area working day around 16:00 CET. This is a reference value, not a transaction rate.",
        "methodology": "Daily ECB reference rate, US dollars per one euro. Each point is a TARGET working day; weekends and euro-area holidays have no observations. The card offers the daily value and averages over week, month, quarter and year from the same series; no forecast is produced.",
        "unit": "USD",
    },
    "gbp-eur": {
        "name": "GBP per euro",
        "description": "ECB reference rate: pounds sterling per one euro. Used to obtain the pound–dollar cross from two ECB rates.",
        "methodology": "Daily ECB reference rate, pounds per one euro. Each point is a TARGET working day. The series is not listed as a standalone card.",
        "unit": "GBP",
    },
    "cny-eur": {
        "name": "CNY per euro",
        "description": "ECB reference rate: Chinese yuan per one euro. Used to obtain the dollar–yuan cross from two ECB rates.",
        "methodology": "Daily ECB reference rate, yuan per one euro. Each point is a TARGET working day. The series is not listed as a standalone card.",
        "unit": "CNY",
    },
    "gbp-usd": {
        "name": "GBP/USD exchange rate",
        "description": "Reference cross rate of the pound sterling against the US dollar: dollars per one pound, from two ECB euro reference rates. This is not a Bank of England official rate and not a transaction price.",
        "methodology": "Ratio of the ECB dollar-per-euro rate to the ECB pound-per-euro rate on the same TARGET working day. Each point is US dollars per one pound. The card offers the daily value and period averages from the same series; no forecast is produced.",
        "unit": "USD",
    },
    "usd-cny": {
        "name": "USD/CNY exchange rate",
        "description": "Reference cross rate of the US dollar against the Chinese yuan: yuan per one dollar, from two ECB euro reference rates. This is not the PBOC central parity and not a transaction price.",
        "methodology": "Ratio of the ECB yuan-per-euro rate to the ECB dollar-per-euro rate on the same TARGET working day. Each point is yuan per one US dollar. The card offers the daily value and period averages from the same series; no forecast is produced.",
        "unit": "CNY",
    },
    "ust-10y": {
        "name": "U.S. 10-year Treasury yield",
        "description": "Yield on 10-year US Treasury securities — a global benchmark for long-term rates. Rising yields usually mean tighter financial conditions; falling yields mean easier conditions. The series is compared with the dollar index and commodity prices.",
        "methodology": "Daily yield on constant-maturity 10-year US Treasury securities from the US Department of the Treasury. Each point is the trading-day value in percent per annum; weekends and holidays have no points. The card offers the daily value and period averages from the same series; no forecast is produced.",
        "unit": "%",
    },
    "brent": {
        "name": "Brent crude oil",
        "description": "Spot price of Europe Brent crude in US dollars per barrel at the end of each trading day. Brent is a key global oil benchmark; its path is compared with other commodity benchmarks, exchange rates and interest rates.",
        "methodology": "Official daily Europe Brent spot price FOB in US dollars per barrel from the U.S. Energy Information Administration. Each point is the value for the calendar publication day; weekends and holidays are excluded. The card offers the daily level and averages over week, month, quarter and year computed from the same series for trend comparison.",
        "unit": "USD/bbl",
    },
    "copper": {
        "name": "Copper",
        "description": "World copper price in US dollars per metric tonne — monthly average from the World Bank commodity price data. Copper is a key industrial metal; its price is treated as a leading indicator of the global economy and the commodity cycle.",
        "methodology": "Monthly average copper price in dollars per tonne from the World Bank commodity price data. Each point is a calendar month. The card offers the monthly value and quarterly and annual averages from the same series; no forecast is produced.",
        "unit": "USD/t",
    },
    "silver": {
        "name": "Silver",
        "description": "World silver price in US dollars per troy ounce — monthly average from the World Bank commodity price data. Silver has both precious-metal and industrial demand.",
        "methodology": "Monthly average silver price in dollars per troy ounce from the World Bank commodity price data. Each point is a calendar month. The card offers the monthly value and quarterly and annual averages; no forecast is produced.",
        "unit": "USD/oz",
    },
    "natural-gas": {
        "name": "Natural gas (Henry Hub)",
        "description": "Spot price of natural gas in US dollars per million British thermal units at the Henry Hub benchmark. Gas is a major Russian export, and its price is linked to energy-sector revenues.",
        "methodology": "Daily Henry Hub spot price from the U.S. Energy Information Administration: each point is a trading day. The card offers the daily level and averages over week, month, quarter and year from the same series; no forecast is produced.",
        "unit": "USD/mmBtu",
    },
    "wheat": {
        "name": "Wheat (US HRW)",
        "description": "World price of US hard red winter (HRW) wheat in dollars per metric tonne — monthly average from the World Bank commodity price data. Russia is a top wheat exporter, so global prices link to agribusiness revenues.",
        "methodology": "Monthly average US HRW wheat price in dollars per tonne from the World Bank commodity price data. Each point is a calendar month. The card offers the monthly value and quarterly and annual averages; no forecast is produced.",
        "unit": "USD/t",
    },
    "soybean": {
        "name": "Soybeans",
        "description": "World soybean price in US dollars per metric tonne — monthly average from the World Bank commodity price data. Soybeans are a key crop and a gauge of demand for animal feed and vegetable oils.",
        "methodology": "Monthly average soybean price in dollars per tonne from the World Bank commodity price data. Each point is a calendar month. The card offers the monthly value and quarterly and annual averages; no forecast is produced.",
        "unit": "USD/t",
    },
    "coal": {
        "name": "Coal (Australia, Newcastle)",
        "description": "World thermal coal price in US dollars per metric tonne on the Australian Newcastle benchmark — monthly average from the World Bank commodity price data. Coal is a key energy commodity in global raw-material trade.",
        "methodology": "Monthly average price of Australian thermal coal (Newcastle) in dollars per tonne from the World Bank commodity price data. Each point is a calendar month. The card offers the monthly value and quarterly and annual averages from the same series; no forecast is produced.",
        "unit": "USD/t",
    },
    "fuel-ai92": {
        "name": "Gasoline AI-92",
        "description": "Average consumer price of AI-92 gasoline in Russia, rubles per litre. Weekly Rosstat end-of-period data.",
        "methodology": "Russia-wide average consumer price of AI-92 motor gasoline at week-end, rubles per litre. Rosstat averages prices across a sample of regions and filling stations and publishes weekly. The card shows the weekly series and averages over month, quarter and year; the forecast is built from monthly averages, with quarterly and annual projections derived from the monthly forecast.",
        "unit": "RUB/l",
    },
    # --- Unlisted siblings / variants (short copy) ---
    "deposit-rate-medium": {
        "name": "Deposit rate (1–3 years)",
        "methodology": "Weighted-average rate on household ruble deposits with maturity from 1 to 3 years. Bank of Russia monthly data; same family as the short-term deposit rate.",
        "unit": "%",
    },
    "deposit-rate-long": {
        "name": "Deposit rate (over 3 years)",
        "methodology": "Weighted-average rate on household ruble deposits with maturity over 3 years. Bank of Russia monthly data.",
        "unit": "%",
    },
    "credit-rate-corp-1to3y": {
        "name": "Corporate loan rate (1–3 years)",
        "methodology": "Weighted-average rate on ruble loans to non-financial organisations, maturity 1–3 years. Bank of Russia monthly data.",
        "unit": "%",
    },
    "credit-rate-corp-over3y": {
        "name": "Corporate loan rate (over 3 years)",
        "methodology": "Weighted-average rate on ruble loans to non-financial organisations, maturity over 3 years. Bank of Russia monthly data.",
        "unit": "%",
    },
    "credit-rate-ind-1to3y": {
        "name": "Household loan rate (1–3 years)",
        "methodology": "Weighted-average rate on ruble loans to households, maturity 1–3 years. Bank of Russia monthly data.",
        "unit": "%",
    },
    "credit-rate-ind-over3y": {
        "name": "Household loan rate (over 3 years)",
        "methodology": "Weighted-average rate on ruble loans to households, maturity over 3 years. Bank of Russia monthly data.",
        "unit": "%",
    },
    "wages-nominal-annual": {
        "name": "Average wages (annual)",
        "methodology": "Calendar-year view of average nominal accrued wages. Derived from the monthly wages series for year-mode charts.",
        "unit": "RUB",
    },
    "wages-nominal-annual-yoy": {
        "name": "Average wages (YoY, annual)",
        "methodology": "Year-on-year change in average nominal wages on an annual frequency.",
        "unit": "%",
    },
    "wages-index": {
        "name": "Wages index (2010 = 100)",
        "methodology": "Nominal wages rebased to 2010 = 100 for affordability and real-wage calculations.",
        "unit": "index",
    },
    "housing-affordability-primary": {
        "name": "Housing affordability (primary market)",
        "methodology": "Affordability using primary-market prices instead of secondary. Same wages numerator as the listed affordability index.",
        "unit": "index",
    },
    "gdp-yoy": {
        "name": "Nominal GDP growth YoY",
        "methodology": "Year-on-year percent change in nominal GDP. Derived from the quarterly nominal GDP series.",
        "unit": "%",
    },
    "gdp-qoq": {
        "name": "Nominal GDP growth QoQ",
        "methodology": "Quarter-on-quarter percent change in nominal GDP.",
        "unit": "%",
    },
    "gdp-real-yoy": {
        "name": "Real GDP growth YoY",
        "methodology": "Year-on-year percent change in real GDP (constant prices).",
        "unit": "%",
    },
    "gdp-real-qoq": {
        "name": "Real GDP growth QoQ",
        "methodology": "Quarter-on-quarter percent change in real GDP.",
        "unit": "%",
    },
    "gdp-nominal-annual": {
        "name": "Nominal GDP (annual)",
        "methodology": "Calendar-year sum of quarterly nominal GDP.",
        "unit": "bln RUB",
    },
    "gdp-real-annual": {
        "name": "Real GDP (annual)",
        "methodology": "Calendar-year sum of quarterly real GDP.",
        "unit": "bln RUB",
    },
    "inflation-quarterly": {
        "name": "Quarterly inflation",
        "methodology": "CPI inflation at quarterly frequency (end-of-quarter reading of the trailing annual rate).",
        "unit": "%",
    },
    "inflation-annual": {
        "name": "Annual inflation",
        "methodology": "December-to-December CPI inflation for completed calendar years.",
        "unit": "%",
    },
    "cpi-food-quarterly": {
        "name": "Food CPI quarterly inflation",
        "methodology": "Quarterly-frequency inflation for the food CPI basket.",
        "unit": "%",
    },
    "cpi-food-annual": {
        "name": "Food CPI annual inflation",
        "methodology": "December-to-December inflation for the food CPI basket.",
        "unit": "%",
    },
    "cpi-food-yoy": {
        "name": "Food CPI YoY",
        "methodology": "Month-to-same-month-previous-year change for the food CPI basket.",
        "unit": "%",
    },
    "cpi-food-qoq": {
        "name": "Food CPI QoQ",
        "methodology": "Quarter-on-quarter change for the food CPI basket.",
        "unit": "%",
    },
    "cpi-food-period-weekly": {
        "name": "Food CPI weekly MTD",
        "methodology": "Month-to-date cumulative change from weekly indices, food CPI slice.",
        "unit": "%",
    },
    "cpi-food-period-monthly": {
        "name": "Food CPI monthly from weekly",
        "methodology": "Calendar-month growth implied by weekly indices, food CPI slice.",
        "unit": "%",
    },
    "cpi-nonfood-quarterly": {
        "name": "Non-food CPI quarterly inflation",
        "methodology": "Quarterly-frequency inflation for the non-food CPI basket.",
        "unit": "%",
    },
    "cpi-nonfood-annual": {
        "name": "Non-food CPI annual inflation",
        "methodology": "December-to-December inflation for the non-food CPI basket.",
        "unit": "%",
    },
    "cpi-nonfood-yoy": {
        "name": "Non-food CPI YoY",
        "methodology": "Month-to-same-month-previous-year change for the non-food CPI basket.",
        "unit": "%",
    },
    "cpi-nonfood-qoq": {
        "name": "Non-food CPI QoQ",
        "methodology": "Quarter-on-quarter change for the non-food CPI basket.",
        "unit": "%",
    },
    "cpi-nonfood-period-weekly": {
        "name": "Non-food CPI weekly MTD",
        "methodology": "Month-to-date cumulative change from weekly indices, non-food CPI slice.",
        "unit": "%",
    },
    "cpi-nonfood-period-monthly": {
        "name": "Non-food CPI monthly from weekly",
        "methodology": "Calendar-month growth implied by weekly indices, non-food CPI slice.",
        "unit": "%",
    },
    "cpi-services-quarterly": {
        "name": "Services CPI quarterly inflation",
        "methodology": "Quarterly-frequency inflation for the services CPI basket.",
        "unit": "%",
    },
    "cpi-services-annual": {
        "name": "Services CPI annual inflation",
        "methodology": "December-to-December inflation for the services CPI basket.",
        "unit": "%",
    },
    "cpi-services-yoy": {
        "name": "Services CPI YoY",
        "methodology": "Month-to-same-month-previous-year change for the services CPI basket.",
        "unit": "%",
    },
    "cpi-services-qoq": {
        "name": "Services CPI QoQ",
        "methodology": "Quarter-on-quarter change for the services CPI basket.",
        "unit": "%",
    },
    "cpi-services-period-weekly": {
        "name": "Services CPI weekly MTD",
        "methodology": "Month-to-date cumulative change from weekly indices, services CPI slice.",
        "unit": "%",
    },
    "cpi-services-period-monthly": {
        "name": "Services CPI monthly from weekly",
        "methodology": "Calendar-month growth implied by weekly indices, services CPI slice.",
        "unit": "%",
    },
    "cpi-yoy": {
        "name": "CPI YoY",
        "methodology": "Month versus same month previous year for headline CPI.",
        "unit": "%",
    },
    "cpi-qoq": {
        "name": "CPI QoQ",
        "methodology": "Quarter-on-quarter change in the headline CPI level.",
        "unit": "%",
    },
    "cpi-period-weekly": {
        "name": "CPI weekly MTD",
        "methodology": "Month-to-date cumulative CPI change from weekly Rosstat estimates.",
        "unit": "%",
    },
    "cpi-period-monthly": {
        "name": "CPI monthly from weekly",
        "methodology": "Calendar-month CPI growth implied by weekly estimates.",
        "unit": "%",
    },
    "inflation-weekly": {
        "name": "Weekly CPI change",
        "methodology": "Week-on-week change in the headline consumer price index.",
        "unit": "%",
    },
    "inflation-weekly-food": {
        "name": "Weekly food CPI",
        "methodology": "Week-on-week change for the food CPI slice.",
        "unit": "%",
    },
    "inflation-weekly-nonfood": {
        "name": "Weekly non-food CPI",
        "methodology": "Week-on-week change for the non-food CPI slice.",
        "unit": "%",
    },
    "inflation-weekly-services": {
        "name": "Weekly services CPI",
        "methodology": "Week-on-week change for the services CPI slice.",
        "unit": "%",
    },
    "housing-qoq-secondary": {
        "name": "Secondary housing prices QoQ",
        "methodology": "Quarter-on-quarter change in secondary housing prices.",
        "unit": "%",
    },
    "housing-yoy-primary": {
        "name": "Primary housing prices YoY",
        "methodology": "Year-on-year change in primary housing prices.",
        "unit": "%",
    },
    "housing-qoq-primary": {
        "name": "Primary housing prices QoQ",
        "methodology": "Quarter-on-quarter change in primary housing prices.",
        "unit": "%",
    },
    "housing-yoy-secondary": {
        "name": "Secondary housing prices YoY",
        "methodology": "Year-on-year change in secondary housing prices.",
        "unit": "%",
    },
    "housing-annual-primary": {
        "name": "Primary housing prices annual",
        "methodology": "Calendar-year change in primary housing prices.",
        "unit": "%",
    },
    "housing-annual-secondary": {
        "name": "Secondary housing prices annual",
        "methodology": "Calendar-year change in secondary housing prices.",
        "unit": "%",
    },
    "unemployment-quarterly": {
        "name": "Unemployment rate (quarterly avg)",
        "methodology": "Simple average of monthly unemployment rates within the calendar quarter.",
        "unit": "%",
    },
    "unemployment-annual": {
        "name": "Unemployment rate (12M average)",
        "methodology": "Trailing twelve-month average of the monthly unemployment rate.",
        "unit": "%",
    },
    "current-account-yoy-abs": {
        "name": "Current account YoY change (abs.)",
        "methodology": "Year-on-year absolute change in the current-account balance.",
        "unit": "mln USD",
    },
    "trade-balance-yoy-abs": {
        "name": "Trade balance YoY change (abs.)",
        "methodology": "Year-on-year absolute change in the goods trade balance.",
        "unit": "mln USD",
    },
    "current-account-yoy": {
        "name": "Current account YoY change (%)",
        "methodology": "Percent year-on-year change in the current-account balance. For signed balances prefer the absolute-change series.",
        "unit": "%",
    },
    "ipi-yoy": {
        "name": "Industrial production YoY",
        "methodology": "Year-on-year percent change in the industrial production index.",
        "unit": "%",
    },
    "exports-monthly": {
        "name": "Goods exports (monthly)",
        "methodology": "Monthly goods exports on a balance-of-payments basis.",
        "unit": "mln USD",
    },
    "imports-monthly": {
        "name": "Goods imports (monthly)",
        "methodology": "Monthly goods imports on a balance-of-payments basis.",
        "unit": "mln USD",
    },
    "trade-balance-monthly": {
        "name": "Trade balance (monthly)",
        "methodology": "Monthly goods trade balance.",
        "unit": "mln USD",
    },
    "exports-yoy": {
        "name": "Exports YoY",
        "methodology": "Year-on-year percent change in goods exports.",
        "unit": "%",
    },
    "imports-yoy": {
        "name": "Imports YoY",
        "methodology": "Year-on-year percent change in goods imports.",
        "unit": "%",
    },
    "exports-qoq": {
        "name": "Exports QoQ",
        "methodology": "Quarter-on-quarter percent change in goods exports.",
        "unit": "%",
    },
    "imports-qoq": {
        "name": "Imports QoQ",
        "methodology": "Quarter-on-quarter percent change in goods imports.",
        "unit": "%",
    },
    "services-exports-monthly": {
        "name": "Services exports (monthly)",
        "methodology": "Monthly services exports on a balance-of-payments basis.",
        "unit": "mln USD",
    },
    "services-imports-monthly": {
        "name": "Services imports (monthly)",
        "methodology": "Monthly services imports on a balance-of-payments basis.",
        "unit": "mln USD",
    },
    "ppi-yoy": {
        "name": "Producer price index YoY",
        "methodology": "Year-on-year change in producer prices.",
        "unit": "%",
    },
    "ppi-qoq": {
        "name": "Producer price index QoQ",
        "methodology": "Quarter-on-quarter change in producer prices.",
        "unit": "%",
    },
    "ppi-annual": {
        "name": "Producer price index annual",
        "methodology": "December-to-December change in producer prices.",
        "unit": "%",
    },
    "wages-yoy": {
        "name": "Wages YoY",
        "methodology": "Year-on-year percent change in average nominal wages.",
        "unit": "%",
    },
    "steel": {
        "name": "Steel (HRC)",
        "methodology": "World hot-rolled coil steel price in US dollars per tonne from World Bank commodity data. Related commodity series.",
        "unit": "USD/t",
    },
    "fuel-ai95": {
        "name": "Gasoline AI-95",
        "methodology": "Average retail price of AI-95 gasoline, rubles per litre. Weekly Rosstat; same fuel family as AI-92.",
        "unit": "RUB/l",
    },
    "fuel-diesel": {
        "name": "Diesel fuel",
        "methodology": "Average retail price of diesel fuel, rubles per litre. Weekly Rosstat; same fuel family as AI-92.",
        "unit": "RUB/l",
    },
    "weo-gdp-usd": {
        "name": "GDP in current US dollars",
        "description": (
            "Annual estimate of Russia’s GDP at current prices, billions of US dollars, "
            "from the IMF World Economic Outlook. This is not Rosstat’s ruble series "
            "and not a conversion at the Bank of Russia exchange rate."
        ),
        "methodology": (
            "Annual GDP estimate in current US dollars. "
            "Source: International Monetary Fund, World Economic Outlook. "
            "The series contains published IMF values and estimates; no forecast is produced on the card."
        ),
        "unit": "billion $",
    },
    "weo-gdp-per-capita-usd": {
        "name": "GDP per capita in current US dollars",
        "description": (
            "Annual estimate of Russia’s GDP per capita in current US dollars "
            "from the IMF World Economic Outlook. This is not a Rosstat series "
            "and not a conversion of rubles at the Bank of Russia exchange rate."
        ),
        "methodology": (
            "Annual GDP per capita estimate in current US dollars. "
            "Source: International Monetary Fund, World Economic Outlook. "
            "The series contains published IMF values and estimates; no forecast is produced on the card."
        ),
        "unit": "$ per person",
    },
}


def get_indicator_copy_en(code: str) -> IndicatorCopyEn | None:
    """Return EN overlay for ``code``, or None if missing."""
    return INDICATOR_COPY_EN.get(code)

