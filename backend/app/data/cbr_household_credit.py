"""Кредиты населению и ипотека из DataService Банка России: Россия и регионы помесячно (19.11.2026).

До 19.11.2026 на сайте были только остаток кредитов физлицам (`consumer-credit`) и ставка по ипотеке
(`mortgage-rate`); по регионам — годовая задолженность из сборника «Регионы России» (раздел 19, до 2025 года).
Люди искали «задолженность домохозяйств», «закредитованность», «сведения о задолженности по кредитам физическим
лицам», «ипотека по годам» — и не находили. Здесь — то, что ЦБ публикует помесячно по России и по каждому субъекту
(«Статистика → Банковский сектор», DataService, публикации 20 и 21, с января 2019 года):

- кредиты физическим лицам: выдано за месяц (набор 41), просроченная задолженность (43); остаток (42) — это
  уже действующий `consumer-credit`, по регионам — новый ряд;
- ипотечные жилищные кредиты: число выданных (44), выдано рублей (45), задолженность (46), просроченная
  задолженность (47), средневзвешенный срок новых кредитов (48).

Разреза «новостройки / вторичное жильё» DataService не даёт (живой запрос 19.11.2026: у наборов 44–48 столбцы только
«всего / в рублях / в иностранной валюте»). Сезонно скорректированный долг (55, 56) не взят: на карточке уже есть
изменения к прошлому году, второй вариант того же долга путал бы.

Значения в DataService — в миллионах рублей и в единицах; столбец 35 — «всего» (рубли и валюта вместе), у срока
(48) «всего» нет — берётся 36 «в рублях» (валютных ипотек почти нет, их срок — нули).

Регион — «measure» набора (96 позиций: Россия, 8 округов, субъекты и «в том числе» автономные округа). Даты: у выдач
«date» = первое число следующего месяца, у остатков — дата «на 1-е число»; как у `consumer-credit`, обе сдвигаются
на месяц назад (остаток на 01.10 — конец сентября).
"""

from __future__ import annotations

from dataclasses import dataclass

SOURCE_URL = "https://www.cbr.ru/statistics/bank_sector/sors/"
FIRST_YEAR = 2019
SECTION_NUM = 19
SECTION_NAME, SECTION_EN = "Финансы", "Finance"
RUSSIA_MEASURE = 22
TOTAL, RUBLES = 35, 36

# Позиции, чьё название не совпадает со справочником регионов или двусмысленно (живой список 19.11.2026).
# 46 «Архангельская область, в том числе Ненецкий АО» и 91/92 «Тюменская область, в том числе ХМАО / ЯНАО» —
# это строки самих автономных округов (сумма 91 + 92 + 93 = 90).
MEASURE_SLUGS: dict[int, str] = {
    46: "nenetskiy-ao",
    47: "arhangelskaya-oblast-bez-ao",
    69: "respublika-severnaya-osetiya",
    91: "hanty-mansiyskiy-ao",
    92: "yamalo-nenetskiy-ao",
    93: "tyumenskaya-oblast-bez-ao",
}


@dataclass(frozen=True)
class CreditSeries:
    dataset: int
    publication: int
    element: int
    federal_code: str          # карточка России (PARSER_REGISTRY, cbr_dataservice_json)
    regional_code: str | None  # ряд регионов (region_monthly_data); None — только Россия
    name: str
    name_en: str
    unit: str                  # единица карточки России
    unit_en: str
    divisor: float             # из единиц источника в единицу карточки России
    regional_unit: str
    regional_unit_en: str
    regional_divisor: float
    flow: bool                 # за месяц (выдачи, срок) или остаток на конец месяца
    description: str
    description_en: str
    keywords: str
    federal_new: bool = True   # False — карточка России уже есть (consumer-credit)


_MLN = "млн руб."
_MLN_EN = "RUB million"

SERIES: tuple[CreditSeries, ...] = (
    CreditSeries(
        41, 20, TOTAL, "consumer-loans-issued", "kredity-fizlicam-vydano-mes",
        "Выдано кредитов физическим лицам", "Loans issued to individuals",
        "млрд руб.", "RUB billion", 1_000, _MLN, _MLN_EN, 1, True,
        "Сколько рублей банки выдали населению новыми кредитами за месяц: потребительские кредиты, ипотека, "
        "автокредиты и кредитные карты вместе.",
        "How much banks lent to households in new loans during the month: consumer loans, mortgages, car loans and "
        "credit cards together.",
        "выдачи кредитов, выдано кредитов, кредитование населения, новые кредиты, потребительское кредитование",
    ),
    CreditSeries(
        42, 20, TOTAL, "consumer-credit", "kredity-fizlicam-dolg-mes",
        "Задолженность по кредитам физическим лицам", "Household loan debt",
        "трлн руб.", "RUB trillion", 1_000_000, _MLN, _MLN_EN, 1, False,
        "Сколько население должно банкам по всем кредитам на конец месяца: ипотека, потребительские кредиты, "
        "автокредиты и карты.",
        "How much households owe banks on all loans at the end of the month: mortgages, consumer loans, car loans "
        "and cards.",
        "задолженность населения, долг населения, задолженность домохозяйств, долги по кредитам, закредитованность, "
        "кредитный портфель физлиц",
        federal_new=False,
    ),
    CreditSeries(
        43, 20, TOTAL, "consumer-credit-overdue", "kredity-fizlicam-prosrochka-mes",
        "Просроченная задолженность по кредитам физическим лицам", "Overdue household loan debt",
        "млрд руб.", "RUB billion", 1_000, _MLN, _MLN_EN, 1, False,
        "Часть долга населения перед банками, которую заёмщики не вернули в срок, на конец месяца.",
        "The part of household debt to banks that borrowers have not repaid on time, at the end of the month.",
        "просрочка, просроченные кредиты, просроченная задолженность, неплатежи по кредитам, долги населения",
    ),
    CreditSeries(
        44, 21, TOTAL, "mortgage-issued-count", "ipoteka-chislo-mes",
        "Число выданных ипотечных кредитов", "Number of mortgages issued",
        "тыс.", "thousand", 1_000, "кредитов", "loans", 1, True,
        "Сколько ипотечных жилищных кредитов банки выдали за месяц.",
        "How many residential mortgage loans banks issued during the month.",
        "количество ипотек, число ипотек, сколько выдали ипотек, ипотечные сделки",
    ),
    CreditSeries(
        45, 21, TOTAL, "mortgage-issued", "ipoteka-vydano-mes",
        "Выдано ипотечных кредитов", "Mortgage lending",
        "млрд руб.", "RUB billion", 1_000, _MLN, _MLN_EN, 1, True,
        "Сколько рублей банки выдали за месяц ипотечными жилищными кредитами — льготными и рыночными вместе.",
        "How much banks lent in residential mortgages during the month, subsidised and market-rate loans together.",
        "выдачи ипотеки, выдано ипотеки, объём ипотеки, ипотека по годам, ипотечное кредитование, рынок ипотеки",
    ),
    CreditSeries(
        46, 21, TOTAL, "mortgage-debt", "ipoteka-dolg-mes",
        "Задолженность по ипотеке", "Mortgage debt outstanding",
        "трлн руб.", "RUB trillion", 1_000_000, _MLN, _MLN_EN, 1, False,
        "Сколько население должно банкам по ипотечным жилищным кредитам на конец месяца.",
        "How much households owe banks on residential mortgages at the end of the month.",
        "ипотечный портфель, долг по ипотеке, задолженность по ипотечным кредитам",
    ),
    CreditSeries(
        47, 21, TOTAL, "mortgage-overdue", "ipoteka-prosrochka-mes",
        "Просроченная задолженность по ипотеке", "Overdue mortgage debt",
        "млрд руб.", "RUB billion", 1_000, _MLN, _MLN_EN, 1, False,
        "Часть ипотечного долга, которую заёмщики не вернули в срок, на конец месяца.",
        "The part of mortgage debt that borrowers have not repaid on time, at the end of the month.",
        "просрочка по ипотеке, просроченная ипотека, неплатежи по ипотеке",
    ),
    CreditSeries(
        48, 21, RUBLES, "mortgage-term", "ipoteka-srok-mes",
        "Средний срок ипотеки", "Average mortgage term",
        "мес.", "months", 1, "мес.", "months", 1, True,
        "Средневзвешенный срок ипотечных кредитов в рублях, выданных за месяц, в месяцах (300 месяцев — 25 лет).",
        "Weighted average term of rouble mortgages issued during the month, in months (300 months is 25 years).",
        "срок ипотеки, на сколько лет берут ипотеку, средний срок ипотечного кредита",
    ),
)

SERIES_BY_FEDERAL: dict[str, CreditSeries] = {s.federal_code: s for s in SERIES}
SERIES_BY_REGIONAL: dict[str, CreditSeries] = {s.regional_code: s for s in SERIES if s.regional_code}

METHODOLOGY = (
    "Данные Банка России по отчётности банков, помесячно с января 2019 года, по России и по каждому субъекту РФ. "
    "«Выдано за месяц» — сумма новых кредитов за "
    "месяц; «задолженность» и «просроченная задолженность» — остаток на конец месяца. В суммы входят кредиты в рублях "
    "и в иностранной валюте, пересчитанные в рубли. Значения могут уточняться задним числом. Месяц публикуется "
    "в начале второго месяца после него."
)
METHODOLOGY_EN = (
    "Bank of Russia data from bank reporting, monthly since January 2019, for Russia and for each region. "
    "“Issued during the month” is the sum of new loans in the month; "
    "“debt” and “overdue debt” are balances at the end of the month. Totals include rouble and foreign-currency "
    "loans converted into roubles. Values may be revised later. A month is published early in the second month after "
    "it."
)
NOTE = "Банк России. Частота — месячная."
NOTE_EN = "Bank of Russia; monthly"
KEYWORDS = "Банк России, ЦБ, кредиты населению, кредиты физическим лицам, статистика кредитования"


def dataservice_cfg(s: CreditSeries) -> dict:
    return {
        "dataservice": {
            "publicationId": s.publication,
            "datasetId": s.dataset,
            "measureId": RUSSIA_MEASURE,
            "element_id": s.element,
            "date_offset_months": -1,
        },
        "backfill_from_year": FIRST_YEAR,
        "forecast_steps": 0,
        "forecast_transform": "absolute",
        "validation": {"min": 0},
        "value_divisor": s.divisor,
    }


def seed_indicators():
    """Новые карточки России (consumer-credit уже заведён в seed_data.py своим блоком)."""
    for s in SERIES:
        if not s.federal_new:
            continue
        yield {
            "code": s.federal_code,
            "name": s.name,
            "name_en": s.name_en,
            "unit": s.unit,
            "frequency": "monthly",
            "source": "Банк России",
            "source_url": SOURCE_URL,
            "description": s.description,
            "methodology": METHODOLOGY,
            "parser_type": "cbr_dataservice_json",
            "model_config_json": dataservice_cfg(s),
            "is_active": True,
            "category": "Финансы",
        }


def copy_en() -> dict[str, dict[str, str]]:
    return {
        s.federal_code: {
            "name": s.name_en, "description": s.description_en, "methodology": METHODOLOGY_EN, "unit": s.unit_en,
        }
        for s in SERIES if s.federal_new
    }


def seo_keywords() -> dict[str, str]:
    return {s.federal_code: f"{s.name}, {s.keywords}, {KEYWORDS}" for s in SERIES if s.federal_new}


def seo_meta() -> dict[str, dict[str, str]]:
    return {
        s.federal_code: {
            "seo_title": f"{s.name} в России — помесячно с 2019 года, данные ЦБ",
            "seo_description": (
                f"{s.name} в России по месяцам с 2019 года, {s.unit}: график, таблица, изменение к прошлому году. "
                "Данные Банка России; по регионам — на страницах субъектов."
            ),
        }
        for s in SERIES if s.federal_new
    }


# ── Регионы ──────────────────────────────────────────────────────────────────

def regional_table_code(s: CreditSeries) -> str:
    return f"{SECTION_NUM}.k{SERIES.index(s) + 1}"


def artifact_rows() -> list[dict]:
    """Строки каталога регионов (формат ``app/data/regional/indicators.json``); дописываются при сиде."""
    return [
        {
            "code": s.regional_code,
            "table_code": regional_table_code(s),
            "section_num": SECTION_NUM,
            "section_name": SECTION_NAME,
            "name": s.name,
            "unit": s.regional_unit,
            "note": NOTE,
            "source_sheet": f"Банк России, DataService, набор {s.dataset}",
            "frequency": "monthly",
        }
        for s in SERIES if s.regional_code
    ]


def regional_copy_en() -> dict[str, dict[str, str]]:
    return {
        s.regional_code: {"name": s.name_en, "unit": s.regional_unit_en, "note": NOTE_EN, "section": SECTION_EN}
        for s in SERIES if s.regional_code
    }


def macro_by_table() -> dict[str, str]:
    """Мост «регион ↔ Россия» (seo_regional.MACRO_BY_TABLE): ряд региона → карточка России."""
    return {regional_table_code(s): s.federal_code for s in SERIES if s.regional_code}


def is_credit_code(code: str) -> bool:
    return code in SERIES_BY_REGIONAL


# Тексты SSR-карточки месячного ряда региона (ключи — как у `_MONTHLY_RU` в seo_regional): у цен и у рядов
# Росстата источник — ЕМИСС, здесь — Банк России.
MONTHLY_TEXT_RU = {
    "p2": "Наблюдение ведётся с {month_gen}, Банк России публикует данные ежемесячно.",
    "p3": "Россия в целом в {month_prep} — {value}{unit}.",
    "faq_value_q": "Какое последнее значение показателя «{short}» в регионе {region}?",
    "faq_value_a": "В {month_prep} — {value}{unit}. Источник — Банк России.",
    "faq_change_q": "Как изменилось значение за последний месяц?",
    "faq_source_q": "Откуда взяты данные и как часто они обновляются?",
    "faq_source_a": (
        "Источник — статистика Банка России по кредитам физическим лицам и ипотечным жилищным кредитам в разрезе "
        "субъектов РФ, по отчётности банков. Данные месячные, с января 2019 года; месяц выходит в начале второго "
        "месяца после него и может уточняться."
    ),
    "description": (
        "{indicator} в регионе {region}: {value} {unit} в {month_prep}. Помесячно с {first_year} года, график и "
        "таблица, сравнение с Россией. Данные Банка России."
    ),
    "dataset_description": "{indicator} ({unit}), {region}, {first_year}–{last_year}, помесячно. Источник: Банк России.",
    "creator": "Банк России",
    "caption": "{indicator} в регионе {region}, {first_year}–{last_year}. Источник: Банк России.",
    "source_p": (
        "Статистика Банка России по кредитованию физических лиц в разрезе субъектов РФ. Значения в единицах: {unit}. "
        "Период наблюдений: {first} — {last}, обновление ежемесячное."
    ),
    "keywords": "{indicator} {region}, ипотека {region}, кредиты {region}, статистика ЦБ по регионам",
}
MONTHLY_TEXT_EN = {
    "p2": "Observations start in {month_gen}; the Bank of Russia publishes the data monthly.",
    "p3": "Russia as a whole in {month_prep}: {value}{unit}.",
    "faq_value_q": "What is the latest value of “{short}” in {region}?",
    "faq_value_a": "In {month_prep}: {value}{unit}. Source: Bank of Russia.",
    "faq_change_q": "How did the value change over the last month?",
    "faq_source_q": "Where do the data come from and how often are they updated?",
    "faq_source_a": (
        "Source: Bank of Russia statistics on loans to individuals and residential mortgages by region, based on bank "
        "reporting. Monthly data since January 2019; a month is released early in the second month after it and "
        "may be revised."
    ),
    "description": (
        "{indicator} in {region}: {value} {unit} in {month_prep}. Monthly since {first_year}, chart and table, "
        "comparison with Russia. Bank of Russia data."
    ),
    "dataset_description": "{indicator} ({unit}), {region}, {first_year}–{last_year}, monthly. Source: Bank of Russia.",
    "creator": "Bank of Russia",
    "caption": "{indicator} in {region}, {first_year}–{last_year}. Source: Bank of Russia.",
    "source_p": (
        "Bank of Russia statistics on lending to individuals by region of Russia. Values in {unit}. "
        "Observation period: {first} — {last}, updated monthly."
    ),
    "keywords": "{indicator} {region}, mortgage {region}, loans {region}, Bank of Russia regional statistics",
}


def monthly_texts(code: str, locale: str) -> dict[str, str] | None:
    if not is_credit_code(code):
        return None
    return MONTHLY_TEXT_EN if locale == "en" else MONTHLY_TEXT_RU
