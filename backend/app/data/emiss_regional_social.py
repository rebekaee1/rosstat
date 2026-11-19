"""Зарплата, пенсия и рождаемость по регионам помесячно из ЕМИСС (19.11.2026).

До 19.11.2026 у регионов эти темы были только годовыми и заканчивались 2024 годом (сборник «Регионы России»),
хотя средняя зарплата, суммарный коэффициент рождаемости и пенсия — одни из самых просматриваемых региональных
показателей. Здесь — свежие помесячные ряды Росстата и Социального фонда, слой ``region_monthly_data``
(тот же, что у цен ЕМИСС 31448):

- 57824 — среднемесячная начисленная зарплата по региону: всего и по 19 разделам ОКВЭД2 (с января 2017);
- 61699 — средний размер назначенной пенсии на 1-е число месяца: все пенсионеры, работающие, неработающие (с 2021);
- 61698 — численность пенсионеров на 1-е число месяца: всего и работающие, тысяч человек (с 2021);
- 62852, 62853 — суммарный коэффициент рождаемости и его часть «третьи и последующие дети» (с января 2025).

Не взяты: 62164 (пенсия по видам — по старости, по инвалидности) — данные раз в квартал, месячный график рвёт ряд на
точки, нужен квартальный слой; 348 подробных видов деятельности 57824 — нужен отдельный экран выбора; строки
«январь–…» (нарастающим итогом) 57824 и значение «за год» 62852/62853.

Даты: зарплата и рождаемость — за отчётный месяц; пенсия и число пенсионеров — на 1-е число, точка «на 1 сентября»
хранится как сентябрь (так месяц и показывается, пометка — в примечании ряда).
"""

from __future__ import annotations

from dataclasses import dataclass

# Периоды «месяц» измерения 33560 (у 61699/61698 своё измерение — «на 1-е число»).
MONTHS_ON_FIRST_DAY = {
    "1594468": 1, "1594792": 2, "1594659": 3, "1594617": 4, "1594529": 5, "1594487": 6,
    "1594766": 7, "1594724": 8, "1594682": 9, "1594594": 10, "1594552": 11, "1594830": 12,
}

# Названия территорий, которых нет в общем справочнике emiss_dimnames.json (ответы 57824, 61699, 61698, 62852):
# межведомственный ОКАТО Соцфонда пишет «г. Москва » с пробелом, «Республика Северная Осетия - Алания» и т. п.
TERRITORY_ALIASES = {
    "Архангельская область (кроме Ненецкого автономного округа)": "arhangelskaya-oblast-bez-ao",
    "Тюменская область (кроме Ханты-Мансийского автономного округа-Югры и Ямало-Ненецкого автономного округа)":
        "tyumenskaya-oblast-bez-ao",
    "Республика Северная Осетия - Алания": "respublika-severnaya-osetiya",
    "г. Санкт-Петербург": "sankt-peterburg",
    "г. Москва": "moskva",
    "Кемеровская область": "kemerovskaya-oblast",
    "г. Севастополь": "sevastopol",
    "Дальневосточный федеральный округ": "dfo",
    "Республика Адыгея": "respublika-adygeya",
    "Северо-Кавказский федеральный округ": "skfo",
    # С 2026 года Росстат ведёт край вместе с федеральной территорией «Сириус» (57824): продолжение того же ряда.
    "Краснодарский край (с учетом ФТ «Сириус»)": "krasnodarskiy-kray",
}
# Строки, которые сайт не показывает: Байконур и округа в старых границах (до 03.11.2018).
TERRITORY_SKIP = frozenset({
    "г. Байконур",
    "Сибирский федеральный округ (до 03.11.2018)",
    "Дальневосточный федеральный окру (до 03.11.2018)",
    "Дальневосточный федеральный округ (до 03.11.2018)",
})

RUSSIA = "Российская Федерация"
RUSSIA_WITHOUT_NEW = "Российская Федерация без учета новых субъектов (с 01.01.2023)"


@dataclass(frozen=True)
class Dataset:
    id: int
    territory_dim: str          # 57831 (ОКАТО Росстата) или 30628 (межведомственный ОКАТО)
    unit_oid: str               # 30611
    first_year: int
    months: dict[str, int]      # oid периода → месяц
    series_dim: str | None = None   # измерение, по которому различаются ряды (ОКВЭД, признак работы)
    fixed: tuple[tuple[str, str], ...] = ()   # прочие обязательные фильтры (измерение, oid)
    scale: float = 1.0          # множитель значения: человек → тысяч человек
    min_value: float = 0.0      # граница здравого смысла: значение вне неё — сбой источника, а не данные
    max_value: float = float("inf")


@dataclass(frozen=True)
class SocialSeries:
    code: str
    dataset: int
    member: str | None          # oid в series_dim (None — у набора один ряд)
    table_code: str
    section_num: int
    section_name: str
    name: str
    unit: str
    note: str
    name_en: str
    unit_en: str
    note_en: str
    section_en: str


_MONTHS = {
    "1540283": 1, "1540282": 2, "1540236": 3, "1540229": 4, "1540235": 5, "1540234": 6,
    "1540233": 7, "1540228": 8, "1540276": 9, "1540273": 10, "1540272": 11, "1540230": 12,
}

DATASETS: dict[int, Dataset] = {
    57824: Dataset(57824, "57831", "950351", 2017, _MONTHS, series_dim="57940",
                   min_value=3_000.0, max_value=2_000_000.0),
    61699: Dataset(61699, "30628", "950351", 2021, MONTHS_ON_FIRST_DAY, series_dim="61609",
                   min_value=3_000.0, max_value=200_000.0),
    61698: Dataset(61698, "30628", "950458", 2021, MONTHS_ON_FIRST_DAY, series_dim="61609",
                   scale=0.001, min_value=0.1, max_value=60_000.0),
    62852: Dataset(62852, "57831", "950475", 2025, _MONTHS, min_value=0.3, max_value=5.0),
    62853: Dataset(62853, "57831", "950475", 2025, _MONTHS, min_value=0.0, max_value=3.0),
}

_LIVING, _LIVING_EN = "Уровень жизни населения", "Living standards"
_POP, _POP_EN = "Население", "Population"

_WAGE_NOTE = (
    "Начисленная зарплата за месяц до вычета налога, в среднем на одного работника, включая премии. "
    "Помесячно, данные Росстата (ЕМИСС). С 2023 года строка России — без учёта новых субъектов."
)
_WAGE_NOTE_EN = (
    "Gross accrued monthly pay per employee, before income tax and including bonuses. Monthly Rosstat data "
    "(EMISS). From 2023 the Russia row excludes the territories identified by Rosstat as new constituent entities."
)

# Разделы ОКВЭД2: oid → (хвост кода, как назвать в строке «Средняя зарплата: …», английское название).
WAGE_SECTIONS: tuple[tuple[str, str, str, str], ...] = (
    ("1692933", "", "все отрасли", "all industries"),
    ("1692751", "selskoe-hozyaystvo", "сельское и лесное хозяйство, рыболовство", "agriculture, forestry and fishing"),
    ("1692320", "dobycha", "добыча полезных ископаемых", "mining and quarrying"),
    ("1692321", "obrabatyvayuschie-proizvodstva", "обрабатывающие производства", "manufacturing"),
    ("1692750", "energetika", "электроэнергия, газ и пар", "electricity, gas and steam supply"),
    ("1692748", "vodosnabzhenie", "водоснабжение и вывоз отходов", "water supply and waste management"),
    ("1692322", "stroitelstvo", "строительство", "construction"),
    ("1692323", "torgovlya", "торговля и ремонт автомобилей", "wholesale and retail trade"),
    ("1692324", "transport", "транспорт и склады", "transportation and storage"),
    ("1692325", "gostinitsy-i-obschepit", "гостиницы и общепит", "hotels and catering"),
    ("1692326", "svyaz-i-it", "связь и ИТ", "information and communication"),
    ("1695572", "finansy", "финансы и страхование", "finance and insurance"),
    ("1692327", "nedvizhimost", "операции с недвижимостью", "real estate"),
    ("1692749", "nauka-i-professionalnye-uslugi", "наука и профессиональные услуги",
     "professional, scientific and technical activities"),
    ("1692328", "administrativnye-uslugi", "административные и вспомогательные услуги",
     "administrative and support services"),
    ("1692329", "gosupravlenie", "госуправление и оборона", "public administration and defence"),
    ("1692330", "obrazovanie", "образование", "education"),
    ("1692331", "zdravoohranenie", "здравоохранение и социальные услуги", "health and social work"),
    ("1695397", "kultura-i-sport", "культура, спорт и досуг", "arts, sports and recreation"),
    ("1692332", "prochie-uslugi", "прочие услуги", "other services"),
)


def _wage_series() -> list[SocialSeries]:
    out = []
    for n, (oid, tail, label, label_en) in enumerate(WAGE_SECTIONS):
        code = "zarplata-mesyachnaya" + (f"-{tail}" if tail else "")
        if tail:
            name, name_en = f"Средняя зарплата по месяцам: {label}", f"Average monthly wage: {label_en}"
        else:
            name, name_en = "Средняя зарплата по месяцам", "Average monthly wage, monthly data"
        out.append(SocialSeries(
            code, 57824, oid, f"3.m4.{n}", 3, _LIVING, name, "рублей", _WAGE_NOTE,
            name_en, "roubles", _WAGE_NOTE_EN, _LIVING_EN,
        ))
    return out


_PENSION_NOTE = (
    "Средний размер назначенной пенсии на 1-е число месяца (точка «сентябрь» — на 1 сентября), по данным "
    "Социального фонда России. Строка России — по всем субъектам."
)
_PENSION_NOTE_EN = (
    "Average assigned pension on the first day of the month (the September point is as of 1 September), "
    "Social Fund of Russia data. The Russia row covers all constituent entities."
)
_COUNT_NOTE = (
    "Число пенсионеров, которые состоят на учёте в Социальном фонде, на 1-е число месяца, тысяч человек."
)
_COUNT_NOTE_EN = "Pensioners registered with the Social Fund of Russia on the first day of the month, thousands."
_FERT_NOTE = (
    "Сколько детей в среднем родила бы одна женщина за жизнь при рождаемости, как в последние двенадцать месяцев. "
    "Помесячная оценка Росстата с 2025 года; годовой ряд до 2024 года — отдельный показатель. Для смены "
    "поколений нужно около 2,1."
)
_FERT_NOTE_EN = (
    "The average number of children a woman would have over her lifetime at the birth rates of the last twelve "
    "months. Monthly Rosstat estimate from 2025; the annual series up to 2024 is a separate indicator. About 2.1 "
    "is needed to replace generations."
)

SERIES: tuple[SocialSeries, ...] = (
    *_wage_series(),
    SocialSeries("pensiya-srednyaya-mesyachnaya", 61699, "1839064", "3.m6.1", 3, _LIVING,
                 "Средняя пенсия по месяцам", "рублей", _PENSION_NOTE,
                 "Average pension, monthly data", "roubles", _PENSION_NOTE_EN, _LIVING_EN),
    SocialSeries("pensiya-srednyaya-rabotayuschih", 61699, "1839065", "3.m6.2", 3, _LIVING,
                 "Средняя пенсия работающих пенсионеров", "рублей", _PENSION_NOTE,
                 "Average pension of working pensioners", "roubles", _PENSION_NOTE_EN, _LIVING_EN),
    SocialSeries("pensiya-srednyaya-nerabotayuschih", 61699, "1839066", "3.m6.3", 3, _LIVING,
                 "Средняя пенсия неработающих пенсионеров", "рублей", _PENSION_NOTE,
                 "Average pension of non-working pensioners", "roubles", _PENSION_NOTE_EN, _LIVING_EN),
    SocialSeries("chislennost-pensionerov-mesyachnaya", 61698, "1839064", "3.m7.1", 3, _LIVING,
                 "Число пенсионеров по месяцам", "тысяч человек", _COUNT_NOTE,
                 "Number of pensioners, monthly data", "thousand people", _COUNT_NOTE_EN, _LIVING_EN),
    SocialSeries("chislennost-rabotayuschih-pensionerov", 61698, "1839065", "3.m7.2", 3, _LIVING,
                 "Число работающих пенсионеров", "тысяч человек", _COUNT_NOTE,
                 "Number of working pensioners", "thousand people", _COUNT_NOTE_EN, _LIVING_EN),
    SocialSeries("summarnyy-koeffitsient-rozhdaemosti-mesyachnyy", 62852, None, "1.m15.1", 1, _POP,
                 "Суммарный коэффициент рождаемости по месяцам", "детей на 1 женщину", _FERT_NOTE,
                 "Total fertility rate, monthly estimate", "children per woman", _FERT_NOTE_EN, _POP_EN),
    SocialSeries("summarnyy-koeffitsient-rozhdaemosti-tretih-detey", 62853, None, "1.m15.2", 1, _POP,
                 "Суммарный коэффициент рождаемости третьих и последующих детей", "детей на 1 женщину",
                 _FERT_NOTE.replace("Сколько детей", "Сколько третьих и следующих детей"),
                 "Total fertility rate for third and later children", "children per woman",
                 _FERT_NOTE_EN.replace("number of children", "number of third and later children"), _POP_EN),
)

SERIES_BY_CODE: dict[str, SocialSeries] = {s.code: s for s in SERIES}


def series_of(dataset: int) -> list[SocialSeries]:
    return [s for s in SERIES if s.dataset == dataset]


def source_sheet(series: SocialSeries) -> str:
    return f"ЕМИСС, витрина {series.dataset}"


def indicator_rows() -> list[dict]:
    """Строки для ``app/data/regional/indicators.json`` (как у ``ceni-ai92``)."""
    return [
        {
            "code": s.code, "table_code": s.table_code, "section_num": s.section_num,
            "section_name": s.section_name, "name": s.name, "unit": s.unit, "note": s.note,
            "source_sheet": source_sheet(s), "frequency": "monthly",
        }
        for s in SERIES
    ]


def copy_en(series: SocialSeries) -> dict[str, str | None]:
    return {"name": series.name_en, "unit": series.unit_en, "note": series.note_en, "section": series.section_en}


def is_social_code(code: str) -> bool:
    return code in SERIES_BY_CODE


# Тексты SSR-карточки месячного ряда: у цен — свои («средние потребительские цены», «среднероссийская цена»),
# здесь — для зарплаты, пенсии и рождаемости. Ключи — как у `_MONTHLY_RU` в seo_regional.
MONTHLY_TEXT_RU = {
    "p2": "Наблюдение ведётся с {month_gen}, данные публикуются ежемесячно.",
    "p3": "В среднем по России в {month_prep} — {value}{unit}: регион {rel} среднего по стране.",
    "faq_value_q": "Какое последнее значение показателя «{short}» в регионе {region}?",
    "faq_value_a": "В {month_prep} — {value}{unit}. Источник — Росстат (ЕМИСС).",
    "faq_change_q": "Как изменилось значение за последний месяц?",
    "faq_source_q": "Откуда взяты данные и как часто они обновляются?",
    "faq_source_a": (
        "Источник — система показателей Росстата (ЕМИСС); пенсии и число пенсионеров Росстат публикует по данным "
        "Социального фонда России. Данные месячные, обновляются после очередной публикации."
    ),
    "description": (
        "{indicator} в регионе {region}: {value} {unit} в {month_prep}. Динамика с {first_year} года, график и "
        "таблица по месяцам, сравнение со средним по России. Данные Росстата, обновление ежемесячное."
    ),
    "source_p": (
        "Система показателей Росстата (ЕМИСС). Значения приведены в единицах: {unit}. "
        "Период наблюдений: {first} — {last}, обновление ежемесячное."
    ),
    "keywords": "{indicator} {region}, {indicator} по месяцам, статистика Росстата {region}",
}
MONTHLY_TEXT_EN = {
    "p2": "Observations start in {month_gen}; the data are published monthly.",
    "p3": "The Russian average in {month_prep} is {value}{unit}: the region is {rel} the national average.",
    "faq_value_q": "What is the latest value of “{short}” in {region}?",
    "faq_value_a": "In {month_prep}: {value}{unit}. Source: Rosstat (EMISS).",
    "faq_change_q": "How did the value change over the last month?",
    "faq_source_q": "Where do the data come from and how often are they updated?",
    "faq_source_a": (
        "Source: Rosstat's statistical indicator system (EMISS); pensions and the number of pensioners are "
        "published by Rosstat from Social Fund of Russia data. Monthly data, updated after each release."
    ),
    "description": (
        "{indicator} in {region}: {value} {unit} in {month_prep}. Monthly chart and table since {first_year}, "
        "comparison with the Russian average. Rosstat data, updated monthly."
    ),
    "source_p": (
        "Rosstat's statistical indicator system (EMISS). Values in {unit}. "
        "Observation period: {first} — {last}, updated monthly."
    ),
    "keywords": "{indicator} {region}, {indicator} by month, Rosstat statistics {region}",
}


# Поиск (19.11.2026): «зарплата учителей/врачей» — разделы ОКВЭД2 в помесячном ряду региона. «Работающих
# пенсионеров» находит и так: понятие «пенсионеров» плюс слово «работающих» из названия ряда. Длинная фраза
# перекрывает общее «зарплата» (search_intent берёт самое длинное совпадение). Слово «врачей» отдельно не трогаем:
# у регионов есть «численность врачей».
SEARCH_CONCEPTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("зарплата учителей", "зарплаты учителей", "зарплата учителя", "зарплата педагогов", "зарплаты педагогов",
      "зарплата в образовании", "зарплата воспитателей", "teacher salary", "teachers salary", "teacher pay"),
     ("zarplata-mesyachnaya-obrazovanie", "по месяцам: образование")),
    (("зарплата врачей", "зарплаты врачей", "зарплата врача", "зарплата медиков", "зарплаты медиков",
      "зарплата медсестер", "зарплата в здравоохранении", "зарплата в медицине", "doctor salary", "doctors salary"),
     ("zarplata-mesyachnaya-zdravoohranenie", "по месяцам: здравоохранение")),
    (("зарплата программистов", "зарплата айтишников", "зарплаты айтишников", "зарплата в it", "зарплата в ит",
      "it salary"), ("zarplata-mesyachnaya-svyaz-i-it", "по месяцам: связь и ит")),
    (("зарплата строителей", "зарплаты строителей", "зарплата в строительстве"),
     ("zarplata-mesyachnaya-stroitelstvo", "по месяцам: строительство")),
    (("зарплата полицейских", "зарплата госслужащих", "зарплата чиновников", "зарплата военных"),
     ("zarplata-mesyachnaya-gosupravlenie", "по месяцам: госуправление")),
)
