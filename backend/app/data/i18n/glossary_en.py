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
