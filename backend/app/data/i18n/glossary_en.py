"""Canonical English glossary skeleton — CONTENT AGENT may extend terms.

Translators MUST reuse these forms. Terms only (not page copy).
Mid-dot « · » is forbidden except unit multiply (ГВт·ч).
"""

from __future__ import annotations

# Russian term → English. Keep stable; do not invent per-page synonyms.
GLOSSARY_EN: dict[str, str] = {
    "Инфляция": "Inflation",
    "ИПЦ": "CPI",
    "Индекс потребительских цен": "Consumer Price Index",
    "Ключевая ставка": "Key rate",
    "Безработица": "Unemployment rate",
    "Уровень безработицы": "Unemployment rate",
    "ВВП": "GDP",
    "Номинальный ВВП": "Nominal GDP",
    "Реальный ВВП": "Real GDP",
    "Заработная плата": "Wages",
    "г/г": "YoY",
    "м/м": "MoM",
    "кв/кв": "QoQ",
    "Росстат": "Rosstat",
    "Банк России": "Bank of Russia",
    "Минфин": "Ministry of Finance",
    "Минфин России": "Ministry of Finance",
    "Московская биржа": "Moscow Exchange",
    "Евростат": "Eurostat",
    "Международный валютный фонд": "International Monetary Fund",
    "Всемирный банк": "World Bank",
    "Банк международных расчётов": "Bank for International Settlements",
    "UN Tourism (Всемирная туристская организация ООН)": "UN Tourism (World Tourism Organization)",
    "ОЭСР": "OECD",
    "Статистическая служба Кипра (CYSTAT)": "Statistical Service of Cyprus (CYSTAT)",
    "Национальная статистическая служба Грузии (Geostat)": "National Statistics Office of Georgia (Geostat)",
    "Министерство культуры и туризма Турции": "Ministry of Culture and Tourism of Türkiye",
    "Статистический комитет Армении": "Statistical Committee of the Republic of Armenia",
    "Государственный комитет по статистике Азербайджана": "State Statistical Committee of the Republic of Azerbaijan",
    "Министерство туризма Индии": "Ministry of Tourism, Government of India",
    "Центральное статистическое бюро Израиля": "Israel Central Bureau of Statistics",
    "Национальная туристическая организация Японии (JNTO)": "Japan National Tourism Organization (JNTO)",
    "Корейская организация туризма": "Korea Tourism Organization",
    "Статистическое управление Черногории (Monstat)": "Statistical Office of Montenegro (Monstat)",
    "Республиканское статистическое управление Сербии": "Statistical Office of the Republic of Serbia",
    "Национальный институт статистики Испании (INE)": "National Statistics Institute of Spain (INE)",
    "Банк международных расчётов (BIS)": "Bank for International Settlements (BIS)",
    "Международная организация труда": "International Labour Organization",
    "Международная организация труда (МОТ)": "International Labour Organization (ILO)",
    "Рыночные котировки": "Market quotes",
    "Статистическое управление Канады": "Statistics Canada",
    "Банк Канады": "Bank of Canada",
    "Австралийское бюро статистики": "Australian Bureau of Statistics",
    "Резервный банк Австралии": "Reserve Bank of Australia",
    "Управление национальной статистики Великобритании": "Office for National Statistics",
    "Банк Англии": "Bank of England",
    "Федеральный резервный банк Сент-Луиса": "Federal Reserve Bank of St. Louis",
    "Бюро трудовой статистики США": "U.S. Bureau of Labor Statistics",
    "Бюро экономического анализа США": "U.S. Bureau of Economic Analysis",
    "Банк Японии": "Bank of Japan",
    "Статистическое бюро Японии": "Statistics Bureau of Japan",
    "Банк Кореи": "Bank of Korea",
    "Банк Бразилии": "Central Bank of Brazil",
    "Банк Мексики": "Bank of Mexico",
    "Национальное статистическое бюро Китая": "National Bureau of Statistics of China",
    "Китайская система валютных торгов": "China Foreign Exchange Trade System",
    "Министерство статистики и программной реализации Индии": (
        "Ministry of Statistics and Programme Implementation"
    ),
    "Резервный банк Индии": "Reserve Bank of India",
    "Бюро переписи населения США": "U.S. Census Bureau",
    "Бразильский институт географии и статистики (IBGE)": (
        "Brazilian Institute of Geography and Statistics (IBGE)"
    ),
    "Управление энергетической информации США (EIA)": "U.S. Energy Information Administration (EIA)",
    "Европейский центральный банк": "European Central Bank",
    "Министерство финансов США": "U.S. Department of the Treasury",
    "Совет управляющих Федеральной резервной системы США": "Board of Governors of the Federal Reserve System",
    # Первоисточники рядов, которые приходят через FRED (14.11.2026): «… (через FRED)» → «… (via FRED)».
    "Министерство труда США": "U.S. Department of Labor",
    "Федеральное агентство по жилищному финансированию США": "Federal Housing Finance Agency",
    "Административно-бюджетное управление США": "U.S. Office of Management and Budget",
    "через FRED": "via FRED",
    "Россия": "Russia",
    "Регионы": "Regions",
    "Регионы России": "Regions of Russia",
    "Сравнение": "Compare",
    "Прогноз": "Forecast",
    "Методология": "Methodology",
    "Источник": "Source",
}


def term(ru: str) -> str:
    """Look up a glossary term; raise if missing so calques do not slip in."""
    try:
        return GLOSSARY_EN[ru]
    except KeyError as exc:
        raise KeyError(f"glossary: missing EN for {ru!r}") from exc
