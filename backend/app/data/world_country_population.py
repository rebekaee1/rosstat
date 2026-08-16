"""Курируемая численность населения по странам мирового блока.

Цифры только из официальных источников: национальное статистическое ведомство
или (для ЕС/ЕАСТ/кандидатов) ряд населения в Eurostat. Агрегаторные оценки
не допускаются: нет проверенной цифры у ведомства — страны нет в словаре.

Европейские страны с живым рядом населения в БД получают population из API
через concept/national crosswalk; этот словарь закрывает крупные экономики
вне Eurostat-демографии (и служит запасным источником).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CountryPopulation:
    """Численность населения одной страны."""

    people: int
    as_of_year: int
    source: str
    source_url: str


# ISO alpha-2 как в world_countries.code (Греция — EL, Великобритания — UK).
WORLD_COUNTRY_POPULATION: Mapping[str, CountryPopulation] = {
    # --- Национальные ведомства (крупные экономики вне Eurostat-демографии) ---
    "US": CountryPopulation(
        341_784_857, 2025,
        "Бюро переписи населения США",
        "https://www.census.gov/data/tables/time-series/demo/popest/2020s-national-total.html",
    ),
    "JP": CountryPopulation(
        123_049_524, 2025,
        "Статистическое бюро Японии (перепись населения, предварительные итоги)",
        "https://www.stat.go.jp/english/data/kokusei/2025/summary.html",
    ),
    "CN": CountryPopulation(
        1_408_280_000, 2024,
        "Национальное статистическое управление Китая",
        "https://www.stats.gov.cn/sj/zxfb/202502/t20250228_1958817.html",
    ),
    # Индия не публикует перепись с 2011 года; ведомство статистики приводит
    # оценку на середину финансового года в национальных счетах — 1395 млн
    # относится к 2023–24 финансовому году, а не к календарному 2024-му.
    "IN": CountryPopulation(
        1_395_000_000, 2023,
        "Министерство статистики и реализации программ Индии "
        "(оценка на середину 2023–24 финансового года)",
        "https://www.mospi.gov.in/sites/default/files/press_release/PressNoteGDP31052024.pdf",
    ),
    "BR": CountryPopulation(
        212_583_750, 2024,
        "Бразильский институт географии и статистики (IBGE)",
        "https://www.ibge.gov.br/estatisticas/sociais/populacao/9103-estimativas-de-populacao.html",
    ),
    # Итоги промежуточного обследования 2025 года ведомство опубликует
    # в сентябре 2026-го; до тех пор измеренная величина — перепись 2020 года.
    "MX": CountryPopulation(
        126_014_024, 2020,
        "Национальный институт статистики и географии Мексики "
        "(перепись населения и жилищного фонда)",
        "https://en.www.inegi.org.mx/programas/ccpv/2020/",
    ),
    "AU": CountryPopulation(
        27_614_411, 2025,
        "Австралийское бюро статистики",
        "https://www.abs.gov.au/statistics/people/population/national-state-and-territory-population/jun-2025",
    ),
}


def population_for_country(code: str | None) -> CountryPopulation | None:
    """Население по ISO-коду страны или None, если в справочнике нет."""
    if not code:
        return None
    return WORLD_COUNTRY_POPULATION.get(str(code).strip().upper())


def population_payload(code: str | None) -> dict | None:
    """Публичный фрагмент API: value / unit / year / source / source_url."""
    entry = population_for_country(code)
    if entry is None:
        return None
    return {
        "value": int(entry.people),
        "unit": "человек",
        "year": entry.as_of_year,
        "source": entry.source,
        "source_url": entry.source_url,
    }
