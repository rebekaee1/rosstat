"""English SEO twins for hubs, categories, and programmatic page templates.

Framework imports:
  - ``seo_i18n.get_page_seo`` / ``get_category_seo`` → ``PAGE_META_EN`` / ``CATEGORY_META_EN``
  - ``seo_i18n.world_home_*`` → ``WORLD_HOME_*_EN``
  - ``seo_i18n.regional_template(key)`` → ``REGIONAL_TEMPLATES_EN``

Template dicts below (``TODAY_*``, ``WORLD_TEMPLATES_EN``, ``CALENDAR_TEMPLATES_EN``)
are ready for ``seo_today`` / ``seo_world`` / ``seo_calendar`` to resolve the same way
as ``regional_template`` — wire when EN SSR for those families is enabled.

Parity: same keys as ``seo_content.PAGE_META`` / ``CATEGORY_META``.
Tone: FRED/Eurostat. No mid-dot. No parser/ADR jargon. One language per string.
"""

from __future__ import annotations

from app.services import site_paths as paths
from app.services.seo_content import CategorySeo, PageSeo, SeoBlock

# ---------------------------------------------------------------------------
# Categories (12) — titles must match frontend categories.js seoTitleEn
# ---------------------------------------------------------------------------

CATEGORY_META_EN: dict[str, CategorySeo] = {
    "prices": CategorySeo(
        slug="prices",
        name="Prices and inflation",
        api_category="Цены",
        title="Prices and inflation in Russia",
        description="CPI, inflation, and housing prices — Rosstat data and forecasts.",
        intro=(
            "This section covers consumer prices, inflation, and housing prices. "
            "CPI dynamics, annual and quarterly changes, and related indices "
            "for major groups of goods and services."
        ),
        flagship_code="cpi",
        keywords=(
            "inflation in Russia, CPI, consumer price index, price growth, "
            "Rosstat inflation, food prices, housing prices, inflation forecast, "
            "Russia inflation, PPI"
        ),
        blocks=(
            SeoBlock(
                "Why this section matters",
                "Price indicators help assess inflation pressure, purchasing power, "
                "and the dynamics of individual components of the consumer basket.",
            ),
        ),
    ),
    "rates": CategorySeo(
        slug="rates",
        name="Interest rates",
        api_category="Ставки",
        title="Interest rates in Russia",
        description="Key rate, RUONIA, mortgage and deposit rates — Bank of Russia data.",
        intro=(
            "This section brings together the key rate, money-market rates, "
            "and rates on bank products."
        ),
        flagship_code="key-rate",
        keywords=(
            "Bank of Russia key rate, key rate, RUONIA, mortgage rate, "
            "deposit rate, CBR rate, refinancing rate, key rate forecast"
        ),
    ),
    "currencies": CategorySeo(
        slug="currencies",
        name="Currencies",
        api_category="Валюты",
        title="Bank of Russia exchange rates",
        description=(
            "USD, EUR, and CNY against the ruble — official daily rates "
            "from the Bank of Russia."
        ),
        intro=(
            "Official daily exchange rates of major currencies against the ruble, "
            "set by the Bank of Russia."
        ),
        flagship_code="usd-rub",
        keywords=(
            "USD RUB, EUR RUB, CNY RUB, dollar exchange rate, euro exchange rate, "
            "Bank of Russia FX rates, Russia currency market"
        ),
    ),
    "indices": CategorySeo(
        slug="indices",
        name="Market indices",
        api_category="Индексы",
        title="Russian market indices",
        description=(
            "MOEX, RTS, RGBI, and bond indices — daily data from Moscow Exchange."
        ),
        intro=(
            "Major Russian market indices: MOEX and RTS equity indices, "
            "total return, and government and corporate bond indices."
        ),
        flagship_code="imoex",
        keywords=(
            "MOEX index, IMOEX, RTS index, RTSI, RGBI, bond index, "
            "Moscow Exchange, Russia stock index, MCFTR"
        ),
    ),
    "finance": CategorySeo(
        slug="finance",
        name="Money and budget",
        api_category="Финансы",
        title="Money and budget in Russia",
        description=(
            "Money supply, reserves, credit, deposits, and the budget — "
            "Bank of Russia and Ministry of Finance data."
        ),
        intro=(
            "Dynamics of money supply, credit, deposits, reserves, "
            "and public finances."
        ),
        flagship_code="m2",
        keywords=(
            "M2 money supply, M0 M1 M2, international reserves, "
            "external debt, credit portfolio, budget revenue and expenditure, "
            "federal budget deficit"
        ),
    ),
    "commodities": CategorySeo(
        slug="commodities",
        name="Commodities",
        api_category="Товарные рынки",
        title="Commodity prices and markets",
        description=(
            "Brent crude, natural gas, gold, copper, wheat — global commodity "
            "prices from official sources."
        ),
        intro=(
            "Global prices for key commodities: oil, precious and industrial metals, "
            "energy, and agricultural products."
        ),
        flagship_code="brent",
        keywords=(
            "oil price, Brent, gold price, silver price, copper price, "
            "natural gas price, wheat price, commodities, commodity quotes, "
            "commodity markets"
        ),
    ),
    "labor": CategorySeo(
        slug="labor",
        name="Labor market",
        api_category="Рынок труда",
        title="Labor market in Russia",
        description="Unemployment, wages, and employment — monthly Rosstat data.",
        intro=(
            "Employment, unemployment, and wage dynamics in Russia."
        ),
        flagship_code="unemployment",
        keywords=(
            "unemployment rate, unemployment in Russia, average wages, "
            "real wages, labor force, employment in Russia, "
            "Rosstat labor market"
        ),
    ),
    "gdp": CategorySeo(
        slug="gdp",
        name="GDP and growth",
        api_category="ВВП",
        title="GDP and economic growth in Russia",
        description=(
            "GDP, consumption, government spending, and investment — "
            "quarterly Rosstat data."
        ),
        intro=(
            "Economic growth, nominal GDP, and derived rates of change "
            "for the Russian economy."
        ),
        flagship_code="gdp-nominal",
        keywords=(
            "Russia GDP, nominal GDP, real GDP, GDP growth, "
            "GDP dynamics, Russia economy, GDP forecast, "
            "quarterly GDP, economic growth"
        ),
    ),
    "population": CategorySeo(
        slug="population",
        name="Population",
        api_category="Население",
        title="Population of Russia",
        description=(
            "Population size, births, deaths, and pensioners — "
            "Rosstat demographic data."
        ),
        intro=(
            "Demographic indicators cover population size, natural change, "
            "and migration."
        ),
        flagship_code="population",
        keywords=(
            "Russia population, Russia demographics, birth rate, "
            "death rate, migration, pensioners, Rosstat population, "
            "working-age population"
        ),
    ),
    "trade": CategorySeo(
        slug="trade",
        name="Foreign trade",
        api_category="Торговля",
        title="Foreign trade of Russia",
        description=(
            "Exports, imports, trade balance, and the current account — "
            "quarterly Bank of Russia data."
        ),
        intro=(
            "External economic flows and balance-of-payments indicators."
        ),
        flagship_code="current-account",
        keywords=(
            "Russia exports, Russia imports, trade balance, current account, "
            "foreign trade, balance of payments, retail trade turnover, "
            "Russia external trade"
        ),
    ),
    "business": CategorySeo(
        slug="business",
        name="Business and investment",
        api_category="Бизнес",
        title="Business and investment in Russia",
        description=(
            "Industrial production index (mining, manufacturing, energy, water supply), "
            "retail trade, and investment — Rosstat data."
        ),
        intro=(
            "Business and investment indicators help assess industrial activity "
            "and fixed capital formation. The industrial production index is also "
            "available by section: mining, manufacturing, electricity and gas supply, "
            "and water supply and waste management."
        ),
        flagship_code="ipi",
        keywords=(
            "industrial production index, IPI, fixed capital investment, "
            "housing completions, construction output, business in Russia, "
            "capital expenditure, fixed assets"
        ),
    ),
    "science": CategorySeo(
        slug="science",
        name="Science and education",
        api_category="Наука",
        title="Science and education in Russia",
        description=(
            "Postgraduate students, R&D organizations, and innovation activity — "
            "Rosstat data."
        ),
        intro=(
            "Indicators of science, education, and innovation activity."
        ),
        flagship_code="rd-personnel",
        keywords=(
            "science in Russia, research and development, R&D, "
            "innovation activity, graduate students, research organizations, "
            "Rosstat education"
        ),
    ),
}

# ---------------------------------------------------------------------------
# Static pages (14)
# ---------------------------------------------------------------------------

PAGE_META_EN: dict[str, PageSeo] = {
    "home": PageSeo(
        slug="home",
        path="/",
        title="Forecast Economy — macroeconomic indicators for countries and Russia",
        description=(
            "Official macroeconomic indicators for countries, Russia, and its regions: "
            "charts, tables, comparisons, and forecasts from statistical agencies "
            "and central banks."
        ),
        h1="Official macroeconomic indicators in one place",
        intro=(
            "Forecast Economy collects macroeconomic indicators for countries from "
            "national statistical agencies, central banks, and Eurostat. "
            "Russia and its regions are covered with deep historical series. "
            "Data come only from official primary sources and are shown as charts, "
            "tables, comparisons, and forecasts. Viewing is open to everyone; "
            "downloads require free registration."
        ),
        keywords=(
            "country macroeconomic indicators, country statistics, "
            "Russia economy, Russia macroeconomics, Russia GDP, inflation in Russia, "
            "CPI, key rate, USD RUB, EUR RUB, Bank of Russia FX rates, "
            "Rosstat data, Bank of Russia, Eurostat, inflation forecast, "
            "Russia economic data, country statistics"
        ),
        links=(
            (paths.today(), "Economy today: FX, key rate, inflation"),
            (paths.russia_indicator("cpi"), "Consumer Price Index"),
            (paths.region_hub(), "Regions of Russia"),
            ("/world", "Country statistics"),
            (paths.demographics(), "Age structure of the population"),
            ("/calculator", "Inflation calculator"),
            ("/compare", "Compare indicators"),
            (paths.calendar(), "Release calendar"),
        ),
        blocks=(
            SeoBlock(
                "About the platform",
                "The platform provides more than 100 Russian macroeconomic indicators, "
                "489 regional indicators, and statistics for available countries. "
                "Cards show history, view modes, tables, and comparable series; "
                "forecasts appear only where the model has passed a quality check.",
            ),
            SeoBlock(
                "Data sources",
                "Official primary sources only: Rosstat, the Bank of Russia, "
                "the Ministry of Finance, Eurostat, and national statistical "
                "agencies of available countries.",
            ),
        ),
    ),
    "about": PageSeo(
        slug="about",
        path="/about",
        title="About Forecast Economy",
        description=(
            "Analytics platform for official economic data on Russia, regions, "
            "and available countries: charts, tables, comparisons, and forecasts."
        ),
        h1="About Forecast Economy",
        intro=(
            "Forecast Economy is an analytics project on the economy of Russia, "
            "its regions, and available countries. We present official indicators "
            "in a comparable form: charts, tables, sources, analysis modes, "
            "and quality-checked forecasts."
        ),
        keywords=(
            "Forecast Economy, about, Russia economic data, "
            "macroeconomic analytics, open Rosstat data, economic forecasts"
        ),
        links=(("/privacy", "Privacy policy"), ("/", "Home")),
    ),
    "methodology": PageSeo(
        slug="methodology",
        path="/methodology",
        title="Forecast methodology for economic indicators — Forecast Economy",
        description=(
            "How forecasts of economic indicators for Russia and other countries "
            "are built: series preparation, historical validation, statistical "
            "models, intervals, updates, and limitations."
        ),
        h1="Forecast methodology",
        intro=(
            "Every forecast on Forecast Economy is produced by a statistical model "
            "trained on the official historical series of the indicator. "
            "We do not fit results to expectations or add expert assumptions: "
            "the forecast is determined by the source data and the algorithm. "
            "Below is the full calculation path — from series preparation to the "
            "confidence interval — and the indicators we deliberately do not forecast."
        ),
        keywords=(
            "forecast methodology, how forecasts are calculated, economic indicator forecast, "
            "statistical forecast, confidence interval, ARIMA, "
            "inflation forecast methodology, GDP forecast, time series extrapolation"
        ),
        links=(
            (paths.russia_indicator("cpi"), "Consumer Price Index"),
            (paths.russia_indicator("key-rate"), "Key rate"),
            ("/about", "About"),
            ("/", "Home"),
        ),
        blocks=(
            SeoBlock(
                "Principles",
                "We forecast only series from official primary sources. "
                "The forecast is produced from the series history by a fixed algorithm "
                "and can be reproduced from published data. Alongside the central "
                "estimate we show a confidence interval that widens with the forecast horizon.",
            ),
            SeoBlock(
                "Calculation steps",
                "The series is checked against the source and aligned to its frequency. "
                "We then assess trend, seasonality, and stationarity (augmented Dickey–Fuller), "
                "choose a stable transform — levels, differences, or log differences — "
                "and fit a statistical model: regression on lagged values with several "
                "training windows; for seasonal series, ARIMA and SARIMA-family models. "
                "Window estimates are combined with weights inverse to their dispersion, "
                "the forecast is mapped back to original units, and a confidence interval "
                "is built around it.",
            ),
            SeoBlock(
                "Model by indicator type",
                "Monthly indicators (wages, rates, money supply, budget, trade) use a "
                "general autoregressive model; quarterly positive series (GDP and its "
                "components, exports, imports, external debt) use a model on log differences; "
                "series that change sign (current account, balances) use a model on level "
                "differences; inflation uses a combined model with pronounced seasonality. "
                "Derived series (annual totals, year-on-year and period-on-period change) "
                "are obtained from the base-series forecast, so they stay consistent across "
                "chart modes.",
            ),
            SeoBlock(
                "What we do not forecast",
                "Statistical extrapolation loses meaning where current news, not series "
                "inertia, drive the path: exchange-traded quotes and indices, intraday FX, "
                "cryptocurrencies, and daily or intra-week series. For those we publish "
                "full history without a forecast line, and the forecast toggle stays inactive.",
            ),
            SeoBlock(
                "Limitations",
                "The forecast relies on stable patterns in the past and may diverge from "
                "outcomes under economic shocks, changes in monetary or fiscal policy, "
                "or revisions of historical data by the source. Materials are informational "
                "and are not personalized investment advice.",
            ),
        ),
    ),
    "privacy": PageSeo(
        slug="privacy",
        path="/privacy",
        title="Privacy policy",
        description=(
            "Personal data processing policy for forecasteconomy.com: "
            "operator, data categories, cookies, and user rights."
        ),
        h1="Privacy and personal data processing policy",
        intro=(
            "The operator is IIMPACT PLUS LLC, tax ID (INN) 9705243471. This page describes "
            "which data are processed when you use the site, how to manage cookie "
            "consent, and what rights visitors have."
        ),
        keywords=(
            "privacy policy, personal data processing, "
            "Forecast Economy privacy, cookies, cookie consent"
        ),
        links=(("/terms", "Terms of use"), ("/about", "About"), ("/", "Home")),
    ),
    "terms": PageSeo(
        slug="terms",
        path="/terms",
        title="Terms of use",
        description=(
            "Terms of use for forecasteconomy.com: materials, widgets, "
            "and liability limitations."
        ),
        h1="Terms of use",
        intro=(
            "Terms of use for the Forecast Economy analytics platform: how materials "
            "and widgets may be used, the nature of the information, and the parties' liability."
        ),
        keywords=(
            "terms of use, user agreement, "
            "Forecast Economy terms, use of materials"
        ),
        links=(("/privacy", "Privacy policy"), ("/about", "About"), ("/", "Home")),
    ),
    "compare": PageSeo(
        slug="compare",
        path="/compare",
        title="Compare indicators",
        description=(
            "Compare country and Russian indicators on one chart: federal series, "
            "regions, and comparable indicators for other countries."
        ),
        h1="Compare indicators",
        intro=(
            "First choose a country, then an indicator. For Russia, federal series "
            "and regional series are available. Two regions are compared in the "
            "regions section."
        ),
        keywords=(
            "compare indicators, overlay charts, inflation and key rate, "
            "ruble exchange rate and money supply, macroeconomics on one chart, "
            "compare GDP and inflation"
        ),
        links=(
            (paths.russia_indicator("cpi"), "CPI"),
            (paths.russia_indicator("key-rate"), "Key rate"),
            (paths.russia_category("finance"), "Finance and FX"),
        ),
    ),
    "calculator": PageSeo(
        slug="calculator",
        path="/calculator",
        title="Inflation calculator for Russia",
        description=(
            "Estimate the loss of purchasing power over any period. "
            "Rosstat CPI data since 1991."
        ),
        h1="Inflation calculator",
        intro=(
            "The calculator shows how the purchasing power of the ruble changed "
            "over the selected period using the consumer price index."
        ),
        keywords=(
            "inflation calculator, inflation calculation, ruble depreciation, "
            "purchasing power, inflation over a period, CPI calculator, "
            "what money was worth"
        ),
        links=(
            (paths.russia_indicator("cpi"), "CPI"),
            (paths.russia_category("prices"), "Prices and inflation"),
        ),
    ),
    "calculator-mortgage": PageSeo(
        slug="calculator-mortgage",
        path="/calculator/mortgage",
        title="Mortgage calculator — payment, overpayment, amortization schedule",
        description=(
            "Estimate the monthly mortgage payment, total cost of credit, and overpayment. "
            "Annuity formula; reference — Bank of Russia key rate."
        ),
        h1="Mortgage calculator",
        intro=(
            "The calculator computes an annuity mortgage payment, total overpayment, "
            "and an annual amortization schedule."
        ),
        keywords=(
            "mortgage calculator, calculate mortgage, monthly mortgage payment, "
            "mortgage overpayment, annuity payment, online mortgage calculator, "
            "mortgage rate"
        ),
        links=(
            (paths.russia_indicator("key-rate"), "Bank of Russia key rate"),
            (paths.russia_indicator("housing-price-primary"), "Housing prices"),
            ("/calculator", "Inflation calculator"),
        ),
    ),
    "calculator-compound": PageSeo(
        slug="calculator-compound",
        path="/calculator/compound",
        title="Compound interest calculator — capital growth with contributions",
        description=(
            "Estimate savings growth with compound interest: capitalization, "
            "monthly contributions, and an inflation adjustment."
        ),
        h1="Compound interest calculator",
        intro=(
            "The calculator shows how capital grows when interest is reinvested "
            "and contributions are regular, and what its real value is after inflation."
        ),
        keywords=(
            "compound interest calculator, compound interest, interest capitalization, "
            "deposit calculator, capital growth, investment calculator, "
            "savings with contributions"
        ),
        links=(
            (paths.russia_indicator("key-rate"), "Bank of Russia key rate"),
            (paths.russia_indicator("ruonia"), "RUONIA"),
            ("/calculator", "Inflation calculator"),
        ),
    ),
    "calendar": PageSeo(
        slug="calendar",
        path=paths.calendar(),
        title="Russia economic release calendar",
        description=(
            "Schedule of macroeconomic data releases: Rosstat, Bank of Russia, "
            "Ministry of Finance."
        ),
        h1="Economic release calendar",
        intro=(
            "The calendar helps track release dates for macroeconomic data "
            "and updates from official sources."
        ),
        keywords=(
            "economic calendar, release calendar, Rosstat schedule, "
            "Bank of Russia meeting dates, CBR calendar, Russia data releases"
        ),
        links=(
            (paths.russia_category("prices"), "Prices"),
            (paths.russia_category("rates"), "Rates"),
        ),
    ),
    "demographics": PageSeo(
        slug="demographics",
        path=paths.demographics(),
        title="Age structure of Russia's population",
        description=(
            "Children, working-age, and above working-age — Rosstat data since 1990."
        ),
        h1="Age structure of Russia's population",
        intro=(
            "This page shows the distribution of Russia's population by age group "
            "and helps analyze demographic dependency."
        ),
        keywords=(
            "age structure of population, Russia demographics, population size, "
            "working-age population, children in Russia, pensioners, demographic dependency, "
            "population pyramid"
        ),
        links=(
            (paths.russia_category("population"), "Population"),
            (paths.russia_indicator("population"), "Population size"),
        ),
    ),
    "widgets": PageSeo(
        slug="widgets",
        path="/widgets",
        title="Forecast Economy widgets",
        description="Embeddable charts, cards, and tickers for your website.",
        h1="Forecast Economy widgets",
        intro=(
            "Widgets let you embed Forecast Economy charts and cards on an external site."
        ),
        keywords=(
            "economy widgets, embeddable charts, embed CPI charts, "
            "FX rate widget, key rate widget, economic widgets"
        ),
        links=(
            (paths.russia_indicator("cpi"), "CPI"),
            ("/compare", "Compare"),
        ),
    ),
    "russia": PageSeo(
        slug="russia",
        path=paths.russia_home(),
        title="Russia — macroeconomics, regions, and calendar",
        description=(
            "Russia country card: macroeconomic indicators, categories, "
            "regional statistics, release calendar, and a current snapshot."
        ),
        h1="Russia",
        intro=(
            "The Russia section brings together macroeconomic indicators from official "
            "sources, regional statistics by federal subject, and the release calendar. "
            "The platform home page remains the shared entry point; this is the entry "
            "to Russian Federation data."
        ),
        keywords=(
            "Russia economy, Russia macroeconomics, Russia statistics, "
            "Russia indicators, regions of Russia, Rosstat, Bank of Russia"
        ),
        links=(
            (paths.today(), "Economy today"),
            (paths.russia_categories(), "Indicator categories"),
            (paths.russia_category("prices"), "Prices and inflation"),
            (paths.region_hub(), "Regions"),
            (paths.calendar(), "Calendar"),
            (paths.demographics(), "Demographics"),
            ("/world", "World countries"),
        ),
    ),
    "russia-categories": PageSeo(
        slug="russia-categories",
        path=paths.russia_categories(),
        title="Russia indicator categories — Forecast Economy",
        description=(
            "Catalog of Russia's macroeconomic categories: prices, GDP, labor market, "
            "currencies, finance, trade, and other official statistics sections."
        ),
        h1="Russia indicator categories",
        intro=(
            "Sections of Russia's macroeconomy: from prices and FX to GDP, the labor market, "
            "and demographics. Each category contains official series with charts and tables."
        ),
        keywords=(
            "Russia economy categories, macroeconomic sections, "
            "Russia statistics by topic, Russia indicators catalog"
        ),
        links=(
            (paths.russia_home(), "Russia"),
            (paths.today(), "Today"),
            (paths.region_hub(), "Regions"),
            ("/compare", "Compare"),
        ),
    ),
}

# ---------------------------------------------------------------------------
# World hub constants
# ---------------------------------------------------------------------------

WORLD_HOME_TITLE_EN: str = "World economy — country statistics"
WORLD_HOME_DESC_EN: str = (
    "Official country statistics: prices, GDP, labor market, trade, and finance. "
    "Charts and tables from Eurostat, national statistical agencies, and central banks."
)
WORLD_HOME_H1_EN: str = "World economy: country statistics"

# Placeholders: {country}, {gen} (genitive-style “of X” / English uses “in X”),
# {prep}, {n_phrase}, {source_phrase}, {display}, {last_value}, {unit_sfx},
# {last_label}, {period}, {source}, {query_name}, {year}, {N}, {total}, {name},
# {with_data}, {without_data}, {n_countries}, {n_sections}, {unit}, {sources}
WORLD_TEMPLATES_EN: dict[str, str] = {
    "country_title": "Economy of {country}: statistics and indicators",
    "country_h1": "Economy of {country}: statistics and indicators",
    "country_desc_national": (
        "{country}: {n_phrase} — prices, GDP, labor market, trade, and finance. "
        "Source: {source_phrase}. Charts and latest values on Forecast Economy."
    ),
    "country_desc_eurostat": (
        "{country}: {n_phrase} from Eurostat — prices, GDP, labor market, trade, "
        "and finance. Charts and latest values on Forecast Economy."
    ),
    "indicator_title": "{display} in {country}: {last_value}{unit_sfx} ({last_label})",
    "indicator_desc": (
        "{display} in {country}: {last_value}{unit_sfx} as of {last_label}. "
        "Dynamics over {period}, chart and table. Source: {source}."
    ),
    "indicator_h1": "{display} in {country}",
    "rating_title": "Country ranking by {query_name}",
    "rating_title_year": "Country ranking by {query_name}, {year}",
    "rating_title_for_year": "Country ranking by {query_name} for {year}",
    "rating_desc": (
        "{title}: full table of {N} of {total}, map, and links to country cards. "
        "Official statistics from national agencies and Eurostat."
    ),
    "rating_intro": (
        "Country ranking by “{name}” for {year}. The table covers {with_data}; "
        "another {without_data}."
    ),
    "n_indicators_one": "{n} indicator",
    "n_indicators_many": "{n} indicators",
    # Body / keywords
    "keywords_home": (
        "world economy statistics, country economy, eurostat data, "
        "inflation by country, gdp by country"
    ),
    "keywords_rating": (
        "{name} by country, country ranking by {name}, {name} {year}, "
        "world economy ranking"
    ),
    "keywords_country": (
        "{country} economy, {country} statistics, {country} gdp, "
        "{country} inflation, {country} unemployment"
    ),
    "keywords_indicator": (
        "{display} {country}, {country} {display} chart, {country} statistics"
    ),
    "home_eyebrow": "Official country statistics",
    "home_lead": (
        "This section collects official series by country — prices, gross domestic "
        "product, labour market, foreign trade, and finance. Data are currently "
        "available for {n_countries} countries and {n_phrase} with charts and value "
        "tables. The European core is Eurostat; series outside Europe come from "
        "national statistical agencies and central banks."
    ),
    "home_h2_countries": "Countries",
    "home_h2_russia": "Russia and comparison",
    "home_russia_p": (
        "Russia’s macroeconomy is on the "
        '<a href="/">home showcase</a> and in the '
        '<a href="{prices}">prices</a>, '
        '<a href="{gdp}">GDP</a>, and '
        '<a href="{labor}">labour market</a> catalogues. '
        "Compare series on the "
        '<a href="/compare">indicator comparison</a> page.'
    ),
    "rating_eyebrow": "Comparable country indicators",
    "rating_th_rank": "Rank",
    "rating_th_country": "Country",
    "rating_th_value": "Value",
    "rating_th_unit": "Unit",
    "rating_th_period": "Period",
    "rating_h2_full": "Full country ranking",
    "rating_h2_missing": "Countries without data for {year}",
    "rating_missing_p": (
        "These countries have no published value for the selected indicator in {year}."
    ),
    "rating_h2_other": "Other ranking indicators",
    "rating_h2_years": "Other years",
    "rating_h2_source": "Data source",
    "rating_source_p": (
        "{sources}. Units: {unit}. For each calendar year the last published value "
        "within the year is used."
    ),
    "rating_tile_first": "First value in current order — {country}",
    "rating_tile_last": "Last value in current order — {country}",
    "rating_tile_with_data": "Countries with data",
    "rating_tile_last_date": "Latest date in the slice",
    "rating_no_data": "no data",
    "rating_unit_fallback": "source units",
    "rating_of_total": "{with_data} of {total}",
    "rating_money_guard": (
        " Monetary indicators are not converted to another currency: only series "
        "already published in a comparable unit enter the ranking."
    ),
    "rating_index_guard": (
        " Consumer price change over the year is compared in percent: national "
        "index base periods cancel out in this calculation, so figures are "
        "comparable across countries."
    ),
    "rating_with_data": "{n} countries with a published value",
    "rating_without_data": (
        "{n} in the world catalogue have no value for this year"
    ),
    "country_eyebrow_national": "National statistics — {country}",
    "country_eyebrow_eurostat": "Eurostat statistics — {country}",
    "country_lead_national": (
        "Official national series for {country}: {n_phrase} across {n_sections} "
        "sections — prices, GDP, labour market, foreign trade, finance, and other "
        "topics. Each indicator has a dynamics chart, a value table, and a link to "
        "the primary source."
    ),
    "country_lead_eurostat": (
        "Official Eurostat series for {country}: {n_phrase} across {n_sections} "
        "sections — prices, GDP, labour market, foreign trade, finance, and other "
        "topics. Each indicator has a dynamics chart, a value table, and a link to "
        "the primary source."
    ),
    "country_h2_key": "Key indicators",
    "country_h2_source": "Data source",
    "country_source_national": (
        "Data are published by {source_phrase}. Series on this site use the source "
        "units; the date of the latest value is shown for each indicator."
    ),
    "country_source_eurostat": (
        "Data are published by Eurostat. Series on this site use the source units; "
        "the date of the latest value is shown for each indicator."
    ),
    "country_h2_neighbors": "Other countries",
    "country_h2_russia": "Russia",
    "country_russia_p": (
        "Compare with Russian series in "
        '<a href="/compare">indicator comparison</a> and on the '
        '<a href="/">home showcase</a> of Forecast Economy.'
    ),
    "th_indicator": "Indicator",
    "th_value": "Value",
    "th_period": "Period",
    "indicator_tile_last": "Latest value",
    "indicator_tile_date": "Date",
    "indicator_tile_period": "Period",
    "indicator_tile_source": "Source",
    "indicator_table_h2": "Latest values",
    "indicator_h2_source": "Data source",
    "indicator_source_p": (
        "{source}. Units: {unit}. Observation period: {period}."
    ),
    "indicator_h2_russia": "Russia",
    "indicator_russia_p": (
        "Russian macro indicators — on the "
        '<a href="/">home page</a> and in '
        '<a href="/compare">comparison</a>.'
    ),
    "indicator_lead": (
        "{display} in {country}: latest value {last_value}{unit_sfx} as of {last_label}."
    ),
    "indicator_desc_fallback": (
        "{display} in {country} — official series from {source}. "
        "The chart shows dynamics over the available observation period"
        "{unit_clause}."
    ),
    "indicator_unit_clause": "; values are shown in {unit}",
    "indicator_period_line": (
        "Observation period: {period}. Source — {source}."
    ),
    "indicator_period_line_freq": (
        "Observation period: {period}, published {freq}. Source — {source}."
    ),
    "indicator_h2_peers": "This indicator in other countries",
    "indicator_h2_siblings": "More in “{category}” — {country}",
    "indicator_open_source": "Open the series on the {source} website",
    "indicator_unit_fallback": "source units",
    "indicator_alt": (
        "{display} in {country}: dynamics chart {period}, "
        "latest value {last_value}{unit_sfx}, source {source}"
    ),
    "indicator_figcaption": (
        "{display} in {country}, {period}. Source: {source}."
    ),
    "indicator_dataset_desc": (
        "{display}{unit_part} in {country}, {period}. Source: {source}."
    ),
    "period_year": "{year}",
    "freq_monthly": "monthly",
    "freq_quarterly": "quarterly",
    "freq_annual": "annually",
    "freq_daily": "daily",
    "freq_weekly": "weekly",
}

# ---------------------------------------------------------------------------
# Today hub + per-code query/question twins
# ---------------------------------------------------------------------------

TODAY_HUB_TITLE_EN: str = (
    "Russia's economy today, {date}: FX rates, key rate, inflation, prices"
)
TODAY_HUB_DESC_EN: str = (
    "Key Russian economic indicators for today: USD, EUR, and CNY exchange rates, "
    "Bank of Russia key rate, inflation, gold and fuel prices, MOEX index. "
    "Official data, updated as sources publish."
)
TODAY_HUB_H1_EN: str = "Russia's economy today"

# Per-code EN twins for TodaySpec.query / question (series codes unchanged).
TODAY_SPECS_EN: dict[str, dict[str, str]] = {
    "usd-rub": {
        "query": "USD/RUB exchange rate",
        "question": "What is the dollar exchange rate today?",
    },
    "eur-rub": {
        "query": "EUR/RUB exchange rate",
        "question": "What is the euro exchange rate today?",
    },
    "cny-rub": {
        "query": "CNY/RUB exchange rate",
        "question": "What is the yuan exchange rate today?",
    },
    "key-rate": {
        "query": "Bank of Russia key rate",
        "question": "What is the Bank of Russia key rate today?",
    },
    "cpi": {
        "query": "Inflation",
        "question": "What is inflation in Russia now?",
    },
    "gold-price": {
        "query": "Gold price",
        "question": "What is the price of a gram of gold today?",
    },
    "fuel-ai92": {
        "query": "AI-92 gasoline price",
        "question": "What is the AI-92 gasoline price today?",
    },
    "fuel-ai95": {
        "query": "AI-95 gasoline price",
        "question": "What is the AI-95 gasoline price today?",
    },
    "fuel-diesel": {
        "query": "Diesel fuel price",
        "question": "What is the diesel fuel price today?",
    },
    "imoex": {
        "query": "MOEX Index",
        "question": "What is the MOEX Index today?",
    },
}

TODAY_TEMPLATES_EN: dict[str, str] = {
    "title_fresh": "{query} today, {date} — {value_text}",
    "title_stale": "{query} — latest value as of {last_date}: {value_text}",
    "desc": (
        "{query}{stale_clause}: {value_text} ({fresh_frame}, {change}). "
        "Source — {source}. Chart, recent values table, and forecast."
    ),
    "stale_clause": " — latest available value",
    "fresh_clause": " as of today",
    "h1_fresh": "{query} today",
    "h1_stale": "{query} — latest value",
    "keywords": "{query_lower} today, {query_lower} now, {query_lower} as of today, {seo_keywords}",
    "change_flat": "unchanged from the previous value",
    "change_up_pp": "up {delta} pp from the previous value",
    "change_down_pp": "down {delta} pp from the previous value",
    "change_up": "up {text} from the previous value",
    "change_down": "down {text} from the previous value",
    "badge_flat": "unchanged",
    "faq_h2": "Questions and answers",
    "faq_answer_last": "According to the latest data ({date}) — {value}",
    "faq_answer_change": "The value is {change}",
    "faq_freq_q": "How often is the data updated?",
    "faq_freq_a": (
        "Data is updated as the source publishes ({source}); "
        "the page always shows the latest available value."
    ),
    "eyebrow_fresh": "Indicator for today",
    "eyebrow_stale": "Latest available value",
    "stale_note": (
        "No new publications from the source yet: showing the latest available "
        "value as of {date}."
    ),
    "tile_prev": "Previous",
    "tile_min": "Minimum over {n} obs.",
    "tile_max": "Maximum over {n} obs.",
    "tile_updated": "Updated",
    "on_date": "as of {date}",
    "source_meta": "source: {source}",
    "body_lead": (
        "Current value as of {date}: <strong>{value}</strong> — {change} "
        "Official source data ({source}); the page updates automatically as new "
        "values are released."
    ),
    "chart_alt": "{query} today — chart, latest value {value}, source {source}",
    "chart_caption": "{query}: dynamics. Source: {source}. forecasteconomy.com",
    "cta_chart": "Interactive chart and forecast →",
    "table_h2": "Latest values",
    "th_date": "Date",
    "th_value": "Value",
    "range_note": (
        "Range of the last {n} observations: from {vmin} to {vmax} {unit}"
    ),
    "history_h2": "Full history and forecast",
    "history_p": (
        "Interactive chart with history from the first available year, view modes, "
        "and forecast — on the "
        '<a href="{href}">{name}</a> page.'
    ),
    "hub_eyebrow": "Snapshot for {date}",
    "hub_lead": (
        "Current values of key indicators. Each card opens the indicator page with "
        "latest values, a chart, and a table; full history and forecast are on the "
        "indicator cards."
    ),
    "hub_h2": "Indicators for today",
    "hub_more_h2": "More data",
    "hub_more_p": (
        "More than 100 macroeconomic indicators — on the "
        '<a href="/">home page</a>; '
        "regional statistics — in "
        '<a href="{regions}">Regions of Russia</a>; '
        "upcoming release dates — in the "
        '<a href="{calendar}">statistics calendar</a>.'
    ),
    "hub_item_today": "{query} today",
    "hub_keywords": (
        "dollar exchange rate today, key rate today, inflation now, "
        "russia economy today, gold price today, gasoline price today"
    ),
    "hub_alt": (
        "Russia's economy today, {date}: USD, EUR and CNY rates, key rate, "
        "inflation, gold and fuel prices, MOEX index"
    ),
    "hub_caption": (
        "Key indicators of Russia's economy as of {date}. forecasteconomy.com"
    ),
}

# ---------------------------------------------------------------------------
# Calendar month pages
# ---------------------------------------------------------------------------

CALENDAR_TEMPLATES_EN: dict[str, object] = {
    "title": "Economic statistics calendar — {month} {year}: release dates",
    "desc_future": (
        "Which data on Russia's economy will be released in {month_gen} {year}: "
        "{n} publications from Rosstat, the Bank of Russia, and the Ministry of Finance "
        "with exact dates — inflation, the key rate, GDP, and other indicators."
    ),
    "desc_past": (
        "Which data on Russia's economy were released in {month_gen} {year}: "
        "{n} publications from Rosstat, the Bank of Russia, and the Ministry of Finance "
        "with exact dates — inflation, the key rate, GDP, and other indicators."
    ),
    "h1": "Statistics calendar: {month} {year}",
    "intro": (
        "Official release dates for Russia's economic statistics in {month_gen} {year}. "
        "Dates are official, from the agencies' own disclosure calendars."
    ),
    "keywords": (
        "statistics calendar {month} {year}, when inflation is released {month} {year}, "
        "rosstat releases {month} {year}, cbr calendar {year}"
    ),
    "eyebrow": "Release calendar",
    "tile_publications": "Releases",
    "tile_rosstat": "Rosstat",
    "tile_cbr": "Bank of Russia",
    "tile_other": "Ministry of Finance and others",
    "h2_month": "Releases this month",
    "h2_neighbors": "Adjacent months",
    "th_date": "Date",
    "th_publication": "Release",
    "th_agency": "Agency",
    "th_status": "Status",
    "status_expected": "expected",
    "status_dash": "—",
    "actual_prefix": " Actual: {value}.",
    "interactive": "Interactive calendar",
    "source_rosstat": "Rosstat",
    "source_cbr": "Bank of Russia",
    "source_minfin": "Ministry of Finance of Russia",
    # English month names (index 1–12); genitive form unused in EN — same as nominative.
    "months": (
        "",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
}

# ---------------------------------------------------------------------------
# Regional SSR templates (hub / profile / rating / indicator / compare)
# Placeholders documented for seo_regional / seo_region_compare wiring.
# ---------------------------------------------------------------------------

REGIONAL_TEMPLATES_EN: dict[str, str] = {
    'regions_hub.title': 'Regions of Russia — socio-economic indicators for 85 federal subjects',
    'regions_hub.description': 'Statistics for 85 regions of Russia: population, wages, GRP, unemployment, investment, prices — 489 Rosstat indicators from 1990. Charts, regional rankings, and comparison with the national level.',
    'regions_hub.h1': 'Regions of Russia',
    'region_profile.title': '{region} — regional statistics: population, wages, GRP, prices',
    'region_profile.description': "Official Rosstat data for {region}: population, labour market, wages, GRP, investment, construction, prices. Charts and the region's place in Russia-wide rankings.",
    'region_profile.h1': '{region}: socio-economic indicators',
    'region_indicator.title': '{indicator} — {region}: {value} ({year})',
    'region_indicator.description': '{indicator} in {region}: {value} {unit} in {year}. Dynamics since the 1990s, comparison with Russia, and place among federal subjects.',
    'region_indicator.h1': '{indicator} in {region}',
    'region_rating_hub.title': 'Rankings of Russian regions by Rosstat indicators',
    'region_rating_hub.description': 'Compare federal subjects of the Russian Federation on socio-economic indicators: full ranking tables, top and bottom of each ranking. Rosstat data.',
    'region_rating_hub.h1': 'Rankings of Russian regions',
    'region_rating.title': 'Ranking of Russian regions: {indicator} ({year})',
    'region_rating.description': "{indicator} across regions of Russia in {year}: full ranking of federal subjects, top and bottom of the table, links to each region's time series.",
    'region_rating.h1': '{indicator}: ranking of regions, {year}',
    'region_vs.title': '{region_a} and {region_b}: comparing regions — wages, population, prices',
    'region_vs.description': 'Compare {region_a} and {region_b} on key socio-economic indicators: population, wages, GRP, unemployment, prices. Official Rosstat data.',
    'region_vs.h1': '{region_a} and {region_b}: regional comparison',
    'region_vs.intro': (
        'Official Rosstat data for two federal subjects: population, wages, unemployment, '
        'gross regional product, investment, prices and incomes. For each indicator — values '
        'for the latest available year and which region is higher.'
    ),
    'region_vs.eyebrow': 'Comparing Russian regions',
    'region_vs.alt': (
        'Comparing {region_a} and {region_b}: population, wages, GRP, unemployment — Rosstat data'
    ),
    'region_vs.caption': (
        '{region_a} and {region_b}: key indicators. Source: Rosstat. forecasteconomy.com'
    ),
    'region_vs.table_h2': 'Summary table',
    'region_vs.th_indicator': 'Indicator',
    'region_vs.th_year': 'Year',
    'region_vs.section_dynamics': 'Dynamics — {region}',
    'region_vs.rating_link': 'Ranking of all regions',
    'region_vs.profiles_h2': 'Region profiles',
    'region_vs.profiles_p': (
        'All indicators for each region: <a href="{href_a}">{region_a}</a>, '
        '<a href="{href_b}">{region_b}</a>. '
        'Interactive comparison of any series — in the <a href="/compare">Compare</a> section.'
    ),
    'region_vs.keywords': (
        '{region_a} or {region_b}, compare {region_a} {region_b}, regional statistics'
    ),
    'region_vs.jsonld_name': 'Regional comparison: {region_a} and {region_b}',
    'region_vs.image_name': '{region_a} and {region_b} — regional comparison',
    'region_rating.alt': (
        '{indicator} across Russian regions — {rank_word} for {year}, '
        '{best_label} — {top_name} ({top_value})'
    ),
    'region_rating.russia_tile': 'Russia overall',
    'region_rating.data_for': 'Data for',
    'region_rating.year_suffix': '{year}',
    'region_rating.regions_n': '{n} regions',
    'region_rating.th_region': 'Region',
    'region_rating.faq_h2': 'Questions and answers',
    'region_rating.faq_year_q': 'Which year do the figures cover, and where do they come from?',
    'region_rating.faq_year_a': (
        'Figures for {year} from the Rosstat yearbook '
        '"Regions of Russia. Socio-economic indicators".'
    ),
    'region_rating.map_h2': 'On the regions map',
    'region_rating.map_p': (
        'The same indicator on an interactive map of Russia — region colours by value, '
        'year slider: <a href="{href}">open the «{indicator}» map</a>.'
    ),
    'region_rating.macro_h2': 'Russia-wide dynamics',
    'region_rating.macro_p': (
        'The indicator for Russia as a whole, with more frequent updates and a forecast — '
        'on the <a href="{href}">national indicator card</a>.'
    ),
    'region_rating.source_h2': 'Data source',
    'region_rating.source_p': (
        'Rosstat yearbook "Regions of Russia. Socio-economic indicators". '
        'Values for {year}, units: {unit}. '
        'Each region has a page with the full indicator series since 1990.'
    ),
    'region_rating.keywords': (
        '{indicator} by region, {indicator} by federal subject, '
        '{indicator} regional comparison'
    ),
    'region_rating.image_name': '{indicator} — {rank_word} of Russian regions, {year}',
    'region_rating.siblings_rankings': 'Other rankings in «{section}»',
    'region_rating.siblings_indicators': 'Other indicators in «{section}»',
    'region_map.title': 'Map of Russian regions: {indicator} ({year})',
    'region_map.description': '{indicator} on the map of Russian regions for {year}. Spatial view of 85 federal subjects with links to rankings and regional cards.',
    'region_map.h1': '{indicator} on the map of Russian regions, {year}',
}

# ---------------------------------------------------------------------------
# Annual landing /russia/indicator/{code}/{year}
# ---------------------------------------------------------------------------

YEAR_TEMPLATES_EN: dict[str, str] = {
    "title_annual_current": "{name} in {year} — latest annual value",
    "title_annual": "{name} in {year} — value and dynamics",
    "title_ytd": "{name} in {year} — year-to-date data",
    "title_single": "{name} in {year} — value and dynamics",
    "title_quarterly": "{name} in {year} — quarterly data and totals",
    "title_weekly": "{name} in {year} — weekly data and totals",
    "title_daily": "{name} in {year} — daily data and totals",
    "title_monthly": "{name} in {year} — monthly data and totals",
    "desc_single": (
        "{name} in {year}{period_note}: {summary_label} — {summary_bit}. "
        "Comparison with the previous year and position in the series history. "
        "Official data — {source}."
    ),
    "desc_multi": (
        "{name} in {year}{period_note}: {n} values, "
        "{summary_label} — {summary_bit}. Official data — {source}."
    ),
    "period_note_ytd": " (year-to-date through {date})",
    "summary_as_of": "{label} (as of {date})",
    "summary_annual_value": "Annual value",
    "summary_value": "Value",
    "summary_chain": "Price growth over the year",
    "summary_sum": "Annual total (sum)",
    "summary_last": "Year-end value",
    "summary_avg": "Annual average",
    "h2_single": "{name} in {year}",
    "h2_single_as_of": "{name} in {year}: data as of {date}",
    "h2_ytd": "{name} in {year}: year-to-date data",
    "h2_totals": "{year} totals",
    "h2_neighbors": "Dynamics over neighbouring years",
    "h2_all_values": "All values for {year}",
    "h2_chart": "Chart and forecast",
    "h2_other_years": "Other years",
    "chart_p": (
        "Full history, interactive chart and forecast — on the {_link} page."
    ),
    "year_link": "{name} in {year}",
    "chart_alt_single": (
        "{name} in {year} — neighbouring years chart, "
        "{summary_label} {summary_text}, source {source}"
    ),
    "chart_alt_multi": (
        "{name} in {year} — chart, "
        "{summary_label} {summary_text}, source {source}"
    ),
    "chart_caption_single": (
        "{name} in {year} — value in the context of neighbouring years. "
        "Source: {source}. forecasteconomy.com"
    ),
    "chart_caption_multi": (
        "{name} in {year} — dynamics chart. "
        "Source: {source}. forecasteconomy.com"
    ),
    "image_caption_single": "{name} in {year} — value and dynamics",
    "image_caption_multi": "{name} in {year} — chart and totals",
    "jsonld_name": "{name} — {year}",
    "keywords": "{name} {year}, {name} {year} year, {seo_keywords}",
    "th_year": "Year",
    "th_date": "Date",
    "th_value": "Value",
    "th_value_unit": "Value, {unit}",
    "th_cpi_change": "Price change, %",
    "li_value_date": "Value date: {date}",
    "li_source": "Source: {source}",
    "li_summary": "{label}: {text}",
    "li_year_start": "Value at start of year: {value} ({date})",
    "li_year_end": "Value at end of year: {value} ({date})",
    "li_latest": "Latest value: {value} ({date})",
    "li_range": "{label}: {vmin} … {vmax}",
    "li_obs": "Number of observations: {n}",
    "range_minmax": "Minimum and maximum",
    "range_cpi": "Minimum and maximum price change over the period",
    "change_value": "Value: {value}",
    "change_no_prev": "Change vs previous year: no comparable value",
    "change_no_data": "Change vs {prev_year}: no data",
    "change_vs": "Change vs {prev_year}: {abs}{unit} ({pct})",
    "change_zero_base": "not calculated (base is zero)",
    "hist_insufficient": "Position in history: not enough neighbouring years to compare",
    "hist_no_data": "Position in history: no data",
    "hist_above": "above the {n}-year average",
    "hist_below": "below the {n}-year average",
    "hist_at": "at the {n}-year average",
    "hist_position": "Position in history: {vs_mean} (average — {mean})",
    "hist_max_sole": "This is the maximum over the available series history ({n} years)",
    "hist_max_tie": "This is one of the series maxima ({value})",
    "hist_max_other": "Series maximum — {value} in {peak_year}{gap}",
    "hist_min_sole": "This is the minimum over the available series history ({n} years)",
    "hist_min_tie": "This is one of the series minima ({value})",
    "hist_min_other": "Series minimum — {value} in {floor_year}{gap}",
    "gap_ago": " ({n} years ago)",
}

# ---------------------------------------------------------------------------
# Macro indicator card SSR / API title templates (overlay name + shell)
# ---------------------------------------------------------------------------

INDICATOR_TEMPLATES_EN: dict[str, str] = {
    "title": "{name} — data and chart",
    "description_fallback": (
        "{name}: dynamics, official source, methodology and latest values."
    ),
    "intro_fallback": (
        "{name}: official economic indicator with historical values and a chart."
    ),
    "chart_caption": "{name} — dynamics chart from {source}. Source: forecasteconomy.com",
    "chart_alt": (
        "{name} — dynamics chart, latest value {value}, source {source}"
    ),
    "image_name": "{name} — dynamics chart ({source})",
    "forecast_image_name": (
        "{name} — dynamics chart and forecast, forecasteconomy.com"
    ),
    "methodology_fallback": (
        "Methodology follows the official publisher and is used to interpret the series."
    ),
    "block_what": "What it shows",
    "block_why": "Why it matters",
    "block_read": "How to read the chart",
    "block_freq": "How often it updates",
    "block_method": "Methodology",
    "block_source": "Source",
    "block_why_body": (
        "{name} is a reference series for analysis of the Russian economy, "
        "comparisons over time, and interpretation alongside related indicators "
        "on Forecast Economy."
    ),
    "block_read_body": (
        "The chart shows the selected view of the series. Switch modes above the "
        "plot to change period-to-period, year-on-year or level presentation. "
        "The latest reading and date are on the telemetry cards."
    ),
    "block_freq_body": (
        "The series updates when the official publisher releases new figures "
        "({frequency}). The date of the latest point is shown on the chart and in the table."
    ),
    "block_source_body": (
        "Values on this page come from {source}. Chart modes reuse the same "
        "official readings under the rules described in the methodology panel."
    ),
    "freq_daily": "daily",
    "freq_weekly": "weekly",
    "freq_monthly": "monthly",
    "freq_quarterly": "quarterly",
    "freq_annual": "annual",
    "section_current": "Latest value",
    "section_methodology": "Methodology",
    "section_latest": "Latest data",
    "section_related": "Related indicators",
    "section_years": "{name} by year",
    "year_link": "{name} in {year}",
    "li_latest": "Latest value: {value}",
    "li_date": "Date of latest value: {date}",
    "li_frequency": "Frequency: {frequency}",
    "li_source": "Source: {source}",
    "li_points": "Number of observations: {count}",
    "li_period": "Data period: {first} — {last}",
    "th_date": "Date",
    "th_value": "Value",
    "th_value_unit": "Value, {unit}",
    "th_cpi_change": "Price change, %",
    "forecast_desc_tail": (
        "Latest figures and a model forecast for the near term."
    ),
    "forecast_chart_note": (
        "The chart shows the official series and our model forecast (dashed). "
        "Methodology — "
    ),
    "forecast_link": "how the forecast is calculated",
}
