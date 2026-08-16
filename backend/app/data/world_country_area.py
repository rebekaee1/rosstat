"""Курируемая площадь территории по странам мирового блока (км²).

Цифры только из официальных источников: национальное статистическое ведомство,
картография/кадастр или (для ЕС/ЕАСТ/кандидатов) Евростат `reg_area3`,
мера Total area (`landuse=TOTAL`). Агрегаторные значения не допускаются:
нет проверенной цифры у ведомства — страны нет в словаре. Единственное
округление — Китай: ведомство публикует территорию как «около 9,6 млн км²»,
более точной официальной величины нет.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CountryArea:
    """Площадь территории одной страны."""

    km2: float
    as_of_year: int
    source: str
    source_url: str


# ISO alpha-2 как в world_countries.code (Греция — EL, Великобритания — UK).
WORLD_COUNTRY_AREA: Mapping[str, CountryArea] = {
    # --- Евростат reg_area3, Total area, км² (API 2026-08-16) ---
    "AL": CountryArea(
        28791, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "AT": CountryArea(
        83882, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "BE": CountryArea(
        30667, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "BG": CountryArea(
        110996, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "CH": CountryArea(
        41287, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "CY": CountryArea(
        9253, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "CZ": CountryArea(
        78871, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "DE": CountryArea(
        357569, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "DK": CountryArea(
        42925, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "EE": CountryArea(
        45336, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "EL": CountryArea(
        131694, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "ES": CountryArea(
        505983, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "FI": CountryArea(
        338363, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "FR": CountryArea(
        638475, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "HR": CountryArea(
        56594, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "HU": CountryArea(
        93012, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "IE": CountryArea(
        69947, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "IS": CountryArea(
        102679, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "IT": CountryArea(
        302073, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "LT": CountryArea(
        65284, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "LU": CountryArea(
        2595, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "LV": CountryArea(
        64594, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "ME": CountryArea(
        13882, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "MK": CountryArea(
        25437, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "MT": CountryArea(
        316, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "NL": CountryArea(
        37391, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "NO": CountryArea(
        384482, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "PL": CountryArea(
        311928, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "PT": CountryArea(
        92226, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "RO": CountryArea(
        238398, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "SE": CountryArea(
        447424, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "SI": CountryArea(
        20273, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "SK": CountryArea(
        49035, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "TR": CountryArea(
        780270, 2026, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    "UK": CountryArea(
        244423, 2023, "Евростат",
        "https://ec.europa.eu/eurostat/databrowser/view/reg_area3/default/table?lang=en",
    ),
    # --- Национальные ведомства ---
    "RS": CountryArea(
        88499, 2025,
        "Республиканское статистическое управление Сербии",
        "https://publikacije.stat.gov.rs/G2025/pdf/G20252058.pdf",
    ),
    "BA": CountryArea(
        51209.2, 2024,
        "Агентство статистики Боснии и Герцеговины",
        "https://bhas.gov.ba/data/Publikacije/Bilteni/2025/NUM_00_2024_TB_1_EN.pdf",
    ),
    "MD": CountryArea(
        33849, 2024,
        "Национальное бюро статистики Молдовы",
        "https://statistica.gov.md/files/files/publicatii_electronice/Mediu/Resursele_naturale_editia_2023.pdf",
    ),
    "GE": CountryArea(
        69700, 2022,
        "Национальная служба статистики Грузии",
        "https://www.geostat.ge/media/58572/Garemo_2022_eng.pdf",
    ),
    "US": CountryArea(
        9833517, 2010,
        "Бюро переписи населения США",
        "https://www.census.gov/geographies/reference-files/2010/geo/state-area.html",
    ),
    "CA": CountryArea(
        9984670, 2001,
        "Статистическая служба Канады (по данным Атласа Канады)",
        "https://www150.statcan.gc.ca/n1/pub/11-402-x/2012000/pdf/geography-geographie-eng.pdf",
    ),
    "JP": CountryArea(
        377976, 2025,
        "Геопространственное управление Японии (публикация Статистического бюро)",
        "https://www.stat.go.jp/english/data/handbook/pdf/2025all.pdf",
    ),
    "CN": CountryArea(
        9600000, 2014,
        "Национальное статистическое управление Китая",
        "https://www.stats.gov.cn/zt_18555/ztsj/hjtjzl/2014/202303/t20230303_1924182.html",
    ),
    "IN": CountryArea(
        3287263, 2022,
        "Правительство Индии (официальный портал)",
        "https://knowindia.india.gov.in/profile/india-at-a-glance.php",
    ),
    "BR": CountryArea(
        8509360.85, 2025,
        "Бразильский институт географии и статистики (IBGE)",
        "https://www.ibge.gov.br/geociencias/organizacao-do-territorio/estrutura-territorial/15761-areas-dos-municipios.html",
    ),
    # Замер территории 1998 года, публикация ведомства 2014: 1 959 248 км²
    # континентальной части + 5 127 км² островов.
    "MX": CountryArea(
        1964375, 2014,
        "Национальный институт статистики и географии Мексики (INEGI)",
        "https://en.www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol"
        "/bvinegi/productos/nueva_estruc/702825064105.pdf",
    ),
    "AU": CountryArea(
        7688287, 2004,
        "Геологическая служба Австралии",
        "https://www.ga.gov.au/scientific-topics/national-location-information/dimensions/area-of-australia-states-and-territories",
    ),
}


def area_for_country(code: str | None) -> CountryArea | None:
    """Площадь по ISO-коду страны или None, если в справочнике нет."""
    if not code:
        return None
    return WORLD_COUNTRY_AREA.get(str(code).strip().upper())


def area_payload(code: str | None) -> dict | None:
    """Публичный фрагмент API: value / unit / year / source / source_url."""
    entry = area_for_country(code)
    if entry is None:
        return None
    value = entry.km2
    if float(value).is_integer():
        value = int(value)
    return {
        "value": value,
        "unit": "км²",
        "year": entry.as_of_year,
        "source": entry.source,
        "source_url": entry.source_url,
    }
