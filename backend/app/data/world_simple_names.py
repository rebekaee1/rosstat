"""Короткие человеческие названия мировых рядов («простое название»).

Полное название ряда остаётся точным и длинным («Государственный долг сектора
государственного управления»); для чипов, плиток и заголовков нужно слово, которое
человек сам скажет вслух: «Госдолг», «Баланс бюджета», «ВВП на душу».

Название выводится из концепта каталога (`world_concepts`) или из сверенного
соответствия национального ряда концепту (`world_concept_national`), то есть только для
рядов, смысл которых сверен вручную. У остальных рядов `None`: интерфейс показывает
обычное название, а не придуманное.
"""

from __future__ import annotations

from typing import Any

# slug концепта -> (по-русски, по-английски)
SIMPLE_NAMES: dict[str, tuple[str, str]] = {
    "hicp-index": ("Цены", "Consumer prices"),
    "unemployment-rate": ("Безработица", "Unemployment"),
    "gdp-volume-quarterly": ("ВВП без инфляции", "Real GDP"),
    "gdp-volume-annual": ("ВВП без инфляции", "Real GDP"),
    "gdp-usd": ("ВВП в долларах", "GDP in US dollars"),
    "gdp-per-capita-usd": ("ВВП на душу", "GDP per person"),
    "gdp-per-capita-eu": ("ВВП на душу к среднему по ЕС", "GDP per person vs EU average"),
    "budget-balance-gdp": ("Баланс бюджета", "Budget balance"),
    "government-debt-gdp": ("Госдолг", "Government debt"),
    "population": ("Население", "Population"),
    "long-term-interest-rate": ("Доходность гособлигаций", "Government bond yield"),
    "activity-rate": ("Работают или ищут работу", "Working or looking for work"),
}


def simple_name_for_concept(slug: str | None, locale: str) -> str | None:
    pair = SIMPLE_NAMES.get(slug or "")
    if pair is None:
        return None
    return pair[1] if locale == "en" else pair[0]


def simple_indicator_name(indicator: Any, locale: str) -> str | None:
    """Короткое название ряда или None, если смысл ряда не сверен с концептом каталога."""
    from app.data.world_concept_national import concept_slug_for_national_code
    from app.data.world_concepts import concept_for_indicator

    try:
        concept = concept_for_indicator(indicator)
    except ValueError:
        return None
    slug = concept.slug if concept is not None else concept_slug_for_national_code(
        str(getattr(indicator, "code", "") or "")
    )
    return simple_name_for_concept(slug, locale)
