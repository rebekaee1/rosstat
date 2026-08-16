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
    "Всемирный банк": "World Bank",
    "Рыночные котировки": "Market quotes",
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
