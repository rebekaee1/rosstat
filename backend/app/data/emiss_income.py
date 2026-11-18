"""Распределение доходов населения и заработных плат России из ЕМИСС (18.11.2026).

Разбор пустых поисков Пульса за 17.11.2026: «распределение зарплат», «зарплата распределение россия», «распределение
дохода россия», «джини», «доля доходов 10% самых богатых» — таких рядов в каталоге России не было. Здесь — официальные
годовые ряды Росстата, которые ЕМИСС отдаёт по России целиком с самого начала наблюдения:

- коэффициент Джини (индекс концентрации доходов), 31165, с 1992 года;
- коэффициент фондов — во сколько раз доходы 10 % самых обеспеченных выше доходов 10 % наименее обеспеченных, 31170;
- доли пяти 20-процентных групп населения в общем объёме денежных доходов, 31400, с 1992 года;
- доли 10 % самых и наименее обеспеченных в общем объёме денежных доходов, 60756, с 2013 года;
- медианная заработная плата, 61773, с 2019 года;
- средняя зарплата десяти 10-процентных групп работников, 58031, — обследование за апрель раз в два года, с 2017.

Не взяты: распределение населения по интервалам дохода (31399) и работников по интервалам зарплаты (58033) — границы
интервалов Росстат меняет от года к году, и один ряд «доля с доходом 10–14 тыс.» не сопоставим во времени.
"""

from dataclasses import dataclass

# Строки территории. С 2023 года Росстат публикует Россию без учёта новых субъектов отдельной строкой.
RUSSIA = "1688487"
RUSSIA_WITHOUT_NEW = "1849012"
YEAR_PERIOD = "1558883"     # значение показателя за год
APRIL = "1540229"           # апрель — месяц обследования заработной платы
NO_UNIT, PERCENT, RUBLE = "1341910", "950473", "950351"


@dataclass(frozen=True)
class IncomeSeries:
    dataset: int
    name: str
    name_en: str
    unit: str
    unit_oid: str
    first_year: int
    explanation: str
    explanation_en: str
    group: tuple[str, str] | None = None   # (измерение ЕМИСС, значение)
    period: str = YEAR_PERIOD
    all_industries: bool = False          # строка «Всего по обследуемым видам экономической деятельности»
    every_two_years: bool = False
    topic: str = "income"

    @property
    def source_url(self) -> str:
        return f"https://www.fedstat.ru/indicator/{self.dataset}"

    @property
    def coverage(self) -> tuple[str, str]:
        base = ("С 2023 года данные приведены без учёта новых субъектов Российской Федерации.",
                "From 2023, the data exclude the territories identified by Rosstat as new constituent entities.")
        if self.every_two_years:
            return ("Обследование заработной платы проводится за апрель раз в два года. " + base[0],
                    "The earnings survey covers April and is held every two years. " + base[1])
        return base


SERIES: dict[str, IncomeSeries] = {
    "income-gini": IncomeSeries(
        31165, "Коэффициент Джини", "Gini coefficient of income", "коэфф.", NO_UNIT, 1992,
        "Неравенство денежных доходов населения: 0 — у всех одинаковый доход, 1 — весь доход у одного человека.",
        "Inequality of money income: 0 means everyone has the same income, 1 means one person receives all income.",
    ),
    "income-funds-ratio": IncomeSeries(
        31170, "Коэффициент фондов", "Income decile ratio", "раз", NO_UNIT, 1992,
        "Во сколько раз денежные доходы 10 % самых обеспеченных выше доходов 10 % наименее обеспеченных.",
        "How many times the money income of the richest 10% exceeds that of the poorest 10%.",
    ),
    **{
        f"income-share-quintile-{number}": IncomeSeries(
            31400, name, name_en, "%", PERCENT, 1992,
            f"Доля {group_ru} в общем объёме денежных доходов. Население разделено на пять равных групп по доходу.",
            f"Share of the {group_en} in total money income. The population is split into five equal income groups.",
            group=("58814", oid),
        )
        for number, oid, name, name_en, group_ru, group_en in (
            (1, "1750935", "Доля доходов 20 % наименее обеспеченных", "Income share of the poorest 20%",
             "20 % наименее обеспеченных", "poorest fifth of the population"),
            (2, "1750934", "Доля доходов второй 20-процентной группы", "Income share of the second quintile",
             "второй снизу пятой части населения", "second fifth from the bottom"),
            (3, "1750933", "Доля доходов средней 20-процентной группы", "Income share of the middle quintile",
             "средней пятой части населения", "middle fifth of the population"),
            (4, "1750932", "Доля доходов четвёртой 20-процентной группы", "Income share of the fourth quintile",
             "второй сверху пятой части населения", "second fifth from the top"),
            (5, "1750931", "Доля доходов 20 % самых обеспеченных", "Income share of the richest 20%",
             "20 % самых обеспеченных", "richest fifth of the population"),
        )
    },
    "income-share-top10": IncomeSeries(
        60756, "Доля доходов 10 % самых обеспеченных", "Income share of the richest 10%", "%", PERCENT, 2013,
        "Доля 10 % самых обеспеченных людей в общем объёме денежных доходов населения.",
        "Share of the richest 10% of people in total money income of the population.",
        group=("58823", "1751146"),
    ),
    "income-share-bottom10": IncomeSeries(
        60756, "Доля доходов 10 % наименее обеспеченных", "Income share of the poorest 10%", "%", PERCENT, 2013,
        "Доля 10 % наименее обеспеченных людей в общем объёме денежных доходов населения.",
        "Share of the poorest 10% of people in total money income of the population.",
        group=("58823", "1751139"),
    ),
    "wages-median": IncomeSeries(
        61773, "Медианная заработная плата", "Median wage", "руб.", RUBLE, 2019,
        "Половина работников получает меньше этой суммы, половина — больше. Начисленная зарплата в месяц, в среднем за год.",
        "Half of employees earn less than this amount and half earn more. Gross monthly earnings, annual average.",
        topic="wages",
    ),
    **{
        f"wages-decile-{number}": IncomeSeries(
            58031,
            {1: "Зарплата 10 % самых низкооплачиваемых работников",
             10: "Зарплата 10 % самых высокооплачиваемых работников"}.get(number, f"Зарплата {number}-й децильной группы работников"),
            {1: "Average wage of the lowest-paid 10% of employees",
             10: "Average wage of the highest-paid 10% of employees"}.get(number, f"Average wage of employee decile {number}"),
            "руб.", RUBLE, 2017,
            f"Работники упорядочены по зарплате и разделены на десять равных групп; {number}-я группа {note}. "
            "Средняя начисленная зарплата группы за апрель.",
            f"Employees are ranked by earnings and split into ten equal groups; group {number} {note_en}. "
            "Average gross earnings of the group for April.",
            group=("58334", oid), period=APRIL, all_industries=True, every_two_years=True, topic="wages",
        )
        for number, oid, note, note_en in (
            (1, "1709526", "получает меньше всех", "earns the least"),
            (2, "1709525", "вторая снизу", "is second from the bottom"),
            (3, "1709523", "третья снизу", "is third from the bottom"),
            (4, "1709521", "четвёртая снизу", "is fourth from the bottom"),
            (5, "1709519", "пятая снизу", "is fifth from the bottom"),
            (6, "1709518", "пятая сверху", "is fifth from the top"),
            (7, "1709520", "четвёртая сверху", "is fourth from the top"),
            (8, "1709522", "третья сверху", "is third from the top"),
            (9, "1709524", "вторая сверху", "is second from the top"),
            (10, "1709528", "получает больше всех", "earns the most"),
        )
    },
}

UNITS_EN = {"коэфф.": "coefficient", "раз": "times", "%": "%", "руб.": "RUB"}

KEYWORDS = {
    "income": ("распределение доходов, неравенство доходов, расслоение по доходам, коэффициент Джини, индекс Джини, "
               "коэффициент фондов, децильный коэффициент, доля доходов богатых, доходы 10% самых богатых, "
               "квинтильные группы, 20-процентные группы населения, бедные и богатые, Росстат"),
    "wages": ("распределение зарплат, распределение заработной платы, медианная зарплата, медианная заработная плата, "
              "зарплата по группам работников, децили зарплаты, высокооплачиваемые и низкооплачиваемые работники, "
              "неравенство зарплат, Росстат"),
}


def seed_indicators():
    for code, series in SERIES.items():
        yield {
            "code": code,
            "name": series.name,
            "name_en": series.name_en,
            "unit": series.unit,
            "frequency": "annual",
            "source": "Росстат",
            "source_url": series.source_url,
            "description": series.explanation,
            "methodology": series.coverage[0],
            "parser_type": "rosstat_emiss_income",
            "model_config_json": {"forecast_steps": 0},
            "is_active": True,
            "category": "Рынок труда",
        }


def seo_keywords() -> dict[str, str]:
    return {code: f"{series.name}, {KEYWORDS[series.topic]}" for code, series in SERIES.items()}
