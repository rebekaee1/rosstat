"""Малый и средний бизнес по регионам помесячно — Единый реестр субъектов МСП ФНС России (19.11.2026).

У регионов малый бизнес был только в годовых итогах выборочных и сплошных наблюдений Росстата (раздел 11,
«Организации», последний сплошной — 2020 год). Люди ищут «средний бизнес» (гипотеза Пульса 165), «число ИП по
годам» по городам, «занятых на малых предприятиях» (пустой поиск). ФНС ведёт реестр МСП и 10-го числа каждого месяца
публикует сводку по субъектам на странице `rmsp.nalog.ru/statistics.html`: число юрлиц и ИП по категориям (микро,
малые, средние), вновь созданных, и численность работников. Открытые данные ФНС, отдаются и боевому серверу (200 на
19.11.2026).

Сводка за дату — POST `statistics-proc.json` с полем `statDate=ДД.ММ.ГГГГ` (так делает сама страница); список дат —
выпадающий список `#statDate` на странице (124 даты с 01.08.2016 по 10.11.2026). Ответ — массив строк: Россия
(`cnt_level` 2), федеральные округа (1), субъекты (0). Даты сводки хранятся месяцем (10.11.2026 → 202611), первая
сводка 01.08.2016 — августом.

Россия у ФНС — по всем субъектам, включая присоединённые в 2022 году; на сайте их нет, строки пропускаются, и сумма
субъектов сайта чуть меньше строки России. Округ «Юго-Западные субъекты» (ФО9) — те же четыре субъекта, пропуск.

Объём: 7 рядов × 87 территорий (Россия, 8 округов, 78–85 субъектов) × 124 месяца ≈ 75 тысяч строк
`region_monthly_data` на всю историю, около 6 МБ с индексами.
"""

from __future__ import annotations

from dataclasses import dataclass

STAT_PAGE = "https://rmsp.nalog.ru/statistics.html"
STAT_JSON = "https://rmsp.nalog.ru/statistics-proc.json"
SOURCE_SHEET = "ФНС России, реестр МСП"

# Названия ФНС, которых нет в общем справочнике emiss_dimnames.json (ответ 10.11.2025 и 10.11.2026).
TERRITORY_ALIASES = {
    "г.Москва": "moskva",
    "г.Санкт-Петербург": "sankt-peterburg",
    "г.Севастополь": "sevastopol",
    "Кемеровская область": "kemerovskaya-oblast",
    "Ненецкий автономный округ": "nenetskiy-ao",
    "Республика Северная Осетия - Алания": "respublika-severnaya-osetiya",
    "Ханты-Мансийский автономный округ - Югра": "hanty-mansiyskiy-ao",
    "Ямало-Ненецкий автономный округ": "yamalo-nenetskiy-ao",
}
# Субъекты, которых нет на сайте, и их округ у ФНС; Крымский федеральный округ (упразднён 28.07.2016) — в сводке
# 01.08.2016, Крым и Севастополь в ней есть отдельными строками.
TERRITORY_SKIP = frozenset({
    "Донецкая Народная Республика", "Луганская Народная Республика", "Запорожская область", "Херсонская область",
    "Юго-Западные субъекты Российской Федерации", "Крымский федеральный округ",
})

_SECTION, _SECTION_EN = "Организации", "Organisations"


@dataclass(frozen=True)
class MspSeries:
    code: str
    fields: tuple[str, ...]     # поля ответа ФНС, значения складываются
    table_code: str
    name: str
    name_en: str
    unit: str
    unit_en: str


SERIES: tuple[MspSeries, ...] = (
    MspSeries("msp-chislo", ("cnt_total",), "11.m1.1", "Число субъектов малого и среднего бизнеса",
              "Number of small and medium-sized businesses", "единиц", "units"),
    MspSeries("msp-yurlica", ("cnt_ul_total",), "11.m1.2", "Малый и средний бизнес: юридические лица",
              "Small and medium-sized businesses: companies", "единиц", "units"),
    MspSeries("msp-ip", ("cnt_ip_total",), "11.m1.3", "Малый и средний бизнес: индивидуальные предприниматели",
              "Small and medium-sized businesses: sole proprietors", "единиц", "units"),
    MspSeries("msp-mikro", ("cnt_ul_micro", "cnt_ip_micro"), "11.m1.4", "Число микропредприятий",
              "Number of micro-enterprises", "единиц", "units"),
    MspSeries("msp-malye", ("cnt_ul_mini", "cnt_ip_mini"), "11.m1.5", "Число малых предприятий",
              "Number of small enterprises", "единиц", "units"),
    MspSeries("msp-srednie", ("cnt_ul_normal", "cnt_ip_normal"), "11.m1.6", "Число средних предприятий",
              "Number of medium-sized enterprises", "единиц", "units"),
    MspSeries("msp-rabotniki", ("cnt_worker_total",), "11.m1.7", "Работники малого и среднего бизнеса",
              "Employees of small and medium-sized businesses", "человек", "people"),
)
SERIES_BY_CODE: dict[str, MspSeries] = {s.code: s for s in SERIES}

NOTE = (
    "Число организаций и индивидуальных предпринимателей из Единого реестра субъектов малого и среднего "
    "предпринимательства ФНС России на 10-е число месяца (точка «ноябрь» — на 10 ноября). Микропредприятия — до 15 "
    "работников и до 120 млн ₽ выручки в год, малые — до 100 работников и 800 млн ₽, средние — до 250 работников и "
    "2 млрд ₽. Строка России — по всем субъектам."
)
NOTE_EN = (
    "Companies and sole proprietors in the Federal Tax Service's Unified Register of Small and Medium-Sized "
    "Businesses on the 10th of the month (the November point is as of 10 November). Micro: up to 15 employees and "
    "RUB 120m annual revenue; small: up to 100 employees and RUB 800m; medium: up to 250 employees and RUB 2bn. The "
    "Russia row covers all constituent entities."
)
WORKERS_NOTE = (
    "Среднесписочная численность работников организаций и предпринимателей из реестра МСП ФНС России за прошлый год, "
    "на 10-е число месяца. Сами предприниматели и совместители в число не входят."
)
WORKERS_NOTE_EN = (
    "Average headcount of employees at companies and sole proprietors in the Federal Tax Service's SME register for "
    "the previous year, on the 10th of the month. Proprietors themselves and part-timers are not counted."
)


def _note(series: MspSeries, en: bool = False) -> str:
    if series.code == "msp-rabotniki":
        return WORKERS_NOTE_EN if en else WORKERS_NOTE
    return NOTE_EN if en else NOTE


def indicator_rows() -> list[dict]:
    """Строки для ``app/data/regional/indicators.json``."""
    return [
        {
            "code": s.code, "table_code": s.table_code, "section_num": 11, "section_name": _SECTION,
            "name": s.name, "unit": s.unit, "note": _note(s), "source_sheet": SOURCE_SHEET, "frequency": "monthly",
        }
        for s in SERIES
    ]


def copy_en(series: MspSeries) -> dict[str, str | None]:
    return {"name": series.name_en, "unit": series.unit_en, "note": _note(series, en=True), "section": _SECTION_EN}


def is_msp_code(code: str) -> bool:
    return code in SERIES_BY_CODE


# Тексты SSR-карточки месячного ряда (ключи — как у `_MONTHLY_RU` в seo_regional): без ценовых фраз и без ЕМИСС.
MONTHLY_TEXT_RU = {
    "p2": "Наблюдение ведётся с {month_gen}, сводка ФНС выходит 10-го числа каждого месяца.",
    "p3": "По России в {month_prep} — {value}{unit}.",
    "faq_value_q": "Какое последнее значение показателя «{short}» в регионе {region}?",
    "faq_value_a": "В {month_prep} — {value}{unit}. Источник — реестр МСП ФНС России.",
    "faq_change_q": "Как изменилось значение за последний месяц?",
    "faq_source_q": "Откуда взяты данные и как часто они обновляются?",
    "faq_source_a": (
        "Источник — Единый реестр субъектов малого и среднего предпринимательства ФНС России. Сводка по регионам "
        "публикуется 10-го числа каждого месяца."
    ),
    "description": (
        "{indicator} в регионе {region}: {value} {unit} в {month_prep}. Динамика с {first_year} года, график и "
        "таблица по месяцам. Данные реестра МСП ФНС, обновление ежемесячное."
    ),
    "source_p": (
        "Единый реестр субъектов МСП ФНС России. Значения приведены в единицах: {unit}. "
        "Период наблюдений: {first} — {last}, обновление ежемесячное."
    ),
    "keywords": "{indicator} {region}, малый бизнес {region}, число ИП {region}, реестр МСП",
    "caption": "{indicator} в регионе {region}, {first_year}–{last_year}. Источник: реестр МСП ФНС России.",
    "dataset_description": (
        "{indicator} ({unit}), {region}, {first_year}–{last_year}, помесячно. Источник: реестр МСП ФНС России."
    ),
}
MONTHLY_TEXT_EN = {
    "p2": "Observations start in {month_gen}; the tax service publishes the summary on the 10th of each month.",
    "p3": "The Russia figure in {month_prep} is {value}{unit}.",
    "faq_value_q": "What is the latest value of “{short}” in {region}?",
    "faq_value_a": "In {month_prep}: {value}{unit}. Source: Federal Tax Service SME register.",
    "faq_change_q": "How did the value change over the last month?",
    "faq_source_q": "Where do the data come from and how often are they updated?",
    "faq_source_a": (
        "Source: the Federal Tax Service's Unified Register of Small and Medium-Sized Businesses. The regional "
        "summary is published on the 10th of each month."
    ),
    "description": (
        "{indicator} in {region}: {value} {unit} in {month_prep}. Monthly chart and table since {first_year}. "
        "Federal Tax Service SME register data, updated monthly."
    ),
    "source_p": (
        "Federal Tax Service SME register. Values in {unit}. Observation period: {first} — {last}, updated monthly."
    ),
    "keywords": "{indicator} {region}, small business {region}, SME register",
    "caption": "{indicator} in {region}, {first_year}–{last_year}. Source: Federal Tax Service SME register.",
    "dataset_description": (
        "{indicator} ({unit}), {region}, {first_year}–{last_year}, monthly. Source: Federal Tax Service SME register."
    ),
}

# Поиск (19.11.2026): «средний бизнес», «малый бизнес», «количество ИП», «занятых на малых предприятиях».
SEARCH_CONCEPTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("средний бизнес", "средних предприятий", "средние предприятия", "число средних предприятий",
      "medium-sized enterprises", "medium businesses"), ("msp-srednie", "средних предприятий")),
    (("количество ип", "число ип", "индивидуальные предприниматели", "индивидуальных предпринимателей",
      "сколько ип", "sole proprietors"), ("msp-ip", "индивидуальные предприниматели")),
    (("микропредприятия", "микропредприятий", "микробизнес", "micro-enterprises"),
     ("msp-mikro", "микропредприятий")),
    (("занятых на малых предприятиях", "занятые в мсп", "работники мсп", "занятость в малом бизнесе",
      "работников малого бизнеса", "sme employment"), ("msp-rabotniki", "работники малого")),
    (("малый и средний бизнес", "малый бизнес", "мсп", "субъекты мсп", "реестр мсп", "число мсп",
      "малое предпринимательство", "sme", "small business", "small businesses"),
     ("msp-chislo", "малого и среднего бизнеса")),
)
