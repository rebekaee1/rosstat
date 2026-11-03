"""National labour series from the Rosstat labour force survey in EMISS."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LaborSeries:
    dataset: int
    name: str
    name_en: str
    unit: str = "%"
    frequency: str = "monthly"
    first_year: int = 2019
    sex: str | None = "1709473"
    age: str | None = None
    education: str | None = None
    explanation: str = ""
    explanation_en: str = ""

    @property
    def coverage(self) -> tuple[str, str]:
        if self.dataset == 43913:
            return REGISTERED_COVERAGE, REGISTERED_COVERAGE_EN
        if self.dataset in {59197, 59302, 59303}:
            return (
                f"До 2021 года охват составлял 15–72 года, с 2021 года — 15 лет и старше. {COVERAGE}",
                f"Through 2020, coverage was ages 15–72. From 2021, it is ages 15 and over. {COVERAGE_EN}",
            )
        return COVERAGE, COVERAGE_EN

    @property
    def source_url(self) -> str:
        return f"https://www.fedstat.ru/indicator/{self.dataset}"


AGES = {
    "1788561": "15 лет и старше",
    "1744169": "15-24 лет",
    "1798986": "25-54 года",
    "1798984": "55-64 года",
}
COVERAGE = "С января 2023 года данные приведены без учёта новых субъектов РФ."
REGISTERED_COVERAGE = "Данные за 2023 год приведены по строке «Российская Федерация». С 2024 года — без учёта новых субъектов РФ."
REGISTERED_COVERAGE_EN = "The 2023 figures use the Russian Federation source row. From 2024, the data exclude the territories identified by Rosstat as new constituent entities."
COVERAGE_EN = "From January 2023, the data exclude the territories identified by Rosstat as new constituent entities."

SERIES = {
    "registered-unemployment-share": LaborSeries(
        43913, "Доля зарегистрированных безработных", "Share of unemployed people registered with employment services",
        frequency="annual", first_year=2013, sex=None,
        explanation="Отношение числа зарегистрированных службой занятости безработных к числу безработных по обследованию рабочей силы. Показатель за год.",
        explanation_en="Registered unemployed people as a percentage of unemployment measured by the labour force survey. Annual figure.",
    ),
    "registered-unemployment-share-quarterly": LaborSeries(
        43913, "Доля зарегистрированных безработных по кварталам",
        "Share of unemployed people registered with employment services, quarterly",
        frequency="quarterly", first_year=2013, sex=None,
        explanation="Отношение числа зарегистрированных службой занятости безработных к числу безработных по обследованию рабочей силы. Показатель за квартал.",
        explanation_en="Registered unemployed people as a percentage of unemployment measured by the labour force survey. Quarterly figure.",
    ),
    "unemployed-higher-education-share": LaborSeries(
        62298, "Доля безработных с высшим образованием",
        "Share of unemployed people with higher education",
        frequency="quarterly", first_year=2023, sex=None, age="1788561", education="1709712",
        explanation="Доля людей с высшим образованием среди всех безработных в возрасте 15 лет и старше.",
        explanation_en="Share of people with higher education among all unemployed people aged 15 and over.",
    ),
    "unemployed-higher-education-share-annual": LaborSeries(
        62298, "Доля безработных с высшим образованием за год",
        "Annual share of unemployed people with higher education",
        frequency="annual", first_year=2022, sex=None, age="1788561", education="1709712",
        explanation="Доля людей с высшим образованием среди всех безработных в возрасте 15 лет и старше за год.",
        explanation_en="Annual share of people with higher education among all unemployed people aged 15 and over.",
    ),
    "part-time-employed": LaborSeries(
        59197, "Неполная занятость", "Part-time employment", unit="тыс. чел.",
        explanation="Численность работающих в условиях неполной занятости по обследованию рабочей силы Росстата.",
        explanation_en="Number of people working part-time, as reported in Rosstat’s labour force survey.",
    ),
    "long-term-unemployed": LaborSeries(
        59303, "Длительная безработица", "Long-term unemployment", unit="тыс. чел.",
        explanation="Число безработных, которые ищут работу 12 месяцев или дольше.",
        explanation_en="Number of unemployed people who have been seeking work for at least 12 months.",
    ),
    "short-term-unemployed": LaborSeries(
        59302, "Краткосрочная безработица", "Short-term unemployment", unit="тыс. чел.",
        explanation="Число безработных, которые ищут работу менее 12 месяцев.",
        explanation_en="Number of unemployed people who have been seeking work for less than 12 months.",
    ),
}

for code, ru, en, age, start in (
    ("youth", "15–24 лет", "ages 15–24", "1744169", 2022),
    ("age-25-54", "25–54 лет", "ages 25–54", "1798986", 2022),
    ("age-55-64", "55–64 лет", "ages 55–64", "1798984", 2022),
    ("all-ages", "", "", "1788561", 2022),
):
    for sex_code, sex_ru, sex_en, sex in (
        ("", "", "", "1709473"),
        ("women", "женщины", "women", "1709472"),
        ("men", "мужчины", "men", "1709471"),
    ):
        if code == "all-ages" and not sex_code:
            continue  # The existing headline rate has its own official source.
        suffix = "-".join(part for part in (code if ru else "", sex_code) if part)
        group_ru = ", ".join(part for part in (ru, sex_ru) if part)
        group_en = ", ".join(part for part in (en, sex_en) if part)
        SERIES[f"unemployment-{suffix}"] = LaborSeries(
            59301, f"Безработица ({group_ru})", f"Unemployment ({group_en})",
            first_year=start, sex=sex, age=age,
            explanation="Доля безработных в рабочей силе этой группы по обследованию Росстата.",
            explanation_en="Unemployed people as a share of the labour force in this group, from Rosstat’s labour force survey.",
        )

    if ru:
        SERIES[f"employment-rate-{code}"] = LaborSeries(
            59194, f"Уровень занятости ({ru})", f"Employment rate ({en})",
            first_year=start, age=age,
            explanation="Доля работающих среди населения этой возрастной группы.",
            explanation_en="Employed people as a share of the population in this age group.",
        )
        SERIES[f"labor-force-{code}"] = LaborSeries(
            59191, f"Рабочая сила ({ru})", f"Labour force ({en})",
            unit="тыс. чел.", first_year=start, age=age,
            explanation="Численность занятых и безработных в этой возрастной группе.",
            explanation_en="Number of employed and unemployed people in this age group.",
        )


def seed_indicators():
    for code, series in SERIES.items():
        yield {
            "code": code,
            "name": series.name,
            "name_en": series.name_en,
            "unit": series.unit,
            "frequency": series.frequency,
            "source": "Росстат",
            "source_url": series.source_url,
            "description": series.explanation,
            "methodology": series.coverage[0],
            "parser_type": "rosstat_emiss_labor",
            "model_config_json": {"forecast_steps": 0},
            "is_active": True,
            "category": "Рынок труда",
        }
