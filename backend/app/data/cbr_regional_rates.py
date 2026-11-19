"""Ставки по вкладам и кредитам по регионам: Банк России, DataService «В территориальном разрезе» (19.11.2026).

Спрос (боевая БД, 20.10–19.11.2026): `deposit-rate` — 179 входов людей, фразы Яндекса про вклады — 180 человек,
ипотека в Google — 74 показа («ставка по ипотеке по годам»); страницы регионов — 1 266 входов. На сайте ставки были
только по России в целом.

Что отдаёт DataService (живой запрос 19.11.2026, ``/dataservice/measures?datasetId=…``):

- pub 15, ds 34 «Ставки по ипотечным жилищным кредитам» — 96 территорий: Россия, 8 округов, все субъекты (и
  отдельно автономные округа и «области без АО»). Берём рубли (element 36), с января 2019 года;
- pub 19, ds 39 «Ставки по вкладам физических лиц в рублях» — только 8 федеральных округов (ни России, ни
  субъектов): до 1 года включая «до востребования» (element 7) и свыше 1 года (element 11);
- pub 15, ds 32 «Ставки по кредитам физическим лицам в рублях» и ds 33 «по автокредитам» — 8 округов, «по всем
  срокам» (element 110).

Ставки по кредитам организациям и МСП (ds 30, 31) и по вкладам организаций (ds 40) не взяты: людям нужны ставки
для себя, а не для компаний.

Слой помесячный (``region_monthly_data``), раздел 19 «Финансы», table_code ``19.s{N}`` (s — ставки; ``19.N`` —
годовые ряды сборника). Объём всей истории: ипотека 96 × 93 мес. ≈ 8,9 тыс. строк, округа 4 × 8 × 93 ≈ 3 тыс.
строк — около 12 тыс. строк, меньше 2 МБ.
"""

from __future__ import annotations

from dataclasses import dataclass

FIRST_YEAR = 2019
SOURCE_URL = "https://www.cbr.ru/statistics/bank_sector/int_rat/"
UNIT = "% годовых"
UNIT_EN = "% per annum"

# Названия территорий DataService, которых нет в справочнике сайта дословно (живой ответ 19.11.2026).
# «Архангельская область, в том числе НАО» — строка самого НАО («в том числе:»), а не области с округом:
# сентябрь 2026 — область 6,23 %, «в том числе НАО» 6,76 %, «без НАО» 6,20 %. Так же у Тюменской области.
MEASURE_ALIASES: dict[str, str] = {
    "Архангельская область, в том числе Ненецкий автономный округ": "nenetskiy-ao",
    "Архангельская область без данных по Ненецкому автономному округу": "arhangelskaya-oblast-bez-ao",
    "Республика Северная Осетия - Алания": "respublika-severnaya-osetiya",
    "Тюменская область, в том числе Ханты-Мансийский автономный округ - Югра": "hanty-mansiyskiy-ao",
    "Тюменская область, в том числе Ямало-Ненецкий автономный округ": "yamalo-nenetskiy-ao",
    "Тюменская область без данных по Ханты-Мансийскому автономному округу - Югре и Ямало-Ненецкому автономному "
    "округу": "tyumenskaya-oblast-bez-ao",
}


@dataclass(frozen=True)
class RateSeries:
    code: str
    table_code: str
    publication: int
    dataset: int
    element: int
    name: str
    name_en: str
    note: str


SERIES: tuple[RateSeries, ...] = (
    RateSeries(
        "stavka-ipoteki", "19.s1", 15, 34, 36,
        "Средняя ставка по ипотеке в рублях", "Average mortgage rate in roubles",
        "Средневзвешенная ставка по ипотечным кредитам в рублях, выданным жителям региона за месяц, включая "
        "льготные программы. Банк России, с января 2019 года.",
    ),
    RateSeries(
        "stavka-vkladov-do-1-goda", "19.s2", 19, 39, 7,
        "Средняя ставка по вкладам до 1 года (по федеральным округам)",
        "Average deposit rate up to 1 year (by federal district)",
        "Средневзвешенная ставка по новым рублёвым вкладам людей сроком до года, включая «до востребования». "
        "Банк России публикует её только по федеральным округам, без отдельных регионов. С января 2019 года.",
    ),
    RateSeries(
        "stavka-vkladov-svyshe-1-goda", "19.s3", 19, 39, 11,
        "Средняя ставка по вкладам свыше 1 года (по федеральным округам)",
        "Average deposit rate over 1 year (by federal district)",
        "Средневзвешенная ставка по новым рублёвым вкладам людей сроком больше года. Банк России публикует её "
        "только по федеральным округам. С января 2019 года.",
    ),
    RateSeries(
        "stavka-kreditov-fizlitsam", "19.s4", 15, 32, 110,
        "Средняя ставка по кредитам людям (по федеральным округам)",
        "Average loan rate for individuals (by federal district)",
        "Средневзвешенная ставка по новым рублёвым кредитам людям на любой срок. Банк России публикует её "
        "только по федеральным округам. С января 2019 года.",
    ),
    RateSeries(
        "stavka-avtokreditov", "19.s5", 15, 33, 110,
        "Средняя ставка по автокредитам (по федеральным округам)",
        "Average car loan rate (by federal district)",
        "Средневзвешенная ставка по новым рублёвым автокредитам на любой срок. Банк России публикует её только по "
        "федеральным округам. С января 2019 года.",
    ),
)

BY_CODE = {s.code: s for s in SERIES}

NOTES_EN: dict[str, str] = {
    "stavka-ipoteki": (
        "Weighted average rate on rouble mortgage loans issued to residents of the region during the month, "
        "including subsidised programmes. Bank of Russia, from January 2019."
    ),
    "stavka-vkladov-do-1-goda": (
        "Weighted average rate on new rouble deposits of individuals for up to one year, including demand deposits. "
        "The Bank of Russia publishes it by federal district only. From January 2019."
    ),
    "stavka-vkladov-svyshe-1-goda": (
        "Weighted average rate on new rouble deposits of individuals for more than one year. The Bank of Russia "
        "publishes it by federal district only. From January 2019."
    ),
    "stavka-kreditov-fizlitsam": (
        "Weighted average rate on new rouble loans to individuals, all maturities. The Bank of Russia publishes it "
        "by federal district only. From January 2019."
    ),
    "stavka-avtokreditov": (
        "Weighted average rate on new rouble car loans, all maturities. The Bank of Russia publishes it by federal "
        "district only. From January 2019."
    ),
}


def copy_en(s: RateSeries) -> dict:
    return {"name": s.name_en, "unit": UNIT_EN, "note": NOTES_EN[s.code], "section": "Finance"}


def datasets() -> dict[tuple[int, int], tuple[RateSeries, ...]]:
    """(publication, dataset) → ряды набора: один запрос на территорию обслуживает все элементы набора."""
    out: dict[tuple[int, int], list[RateSeries]] = {}
    for s in SERIES:
        out.setdefault((s.publication, s.dataset), []).append(s)
    return {k: tuple(v) for k, v in out.items()}


def indicator_rows() -> list[dict]:
    """Строки ``regional/indicators.json`` (их пишет seed_regional при старте)."""
    return [
        {
            "code": s.code,
            "table_code": s.table_code,
            "section_num": 19,
            "section_name": "Финансы",
            "name": s.name,
            "unit": UNIT,
            "note": s.note,
            "source_sheet": f"Банк России, DataService {s.publication}/{s.dataset}",
            "frequency": "monthly",
        }
        for s in SERIES
    ]
