"""Русские заголовки наборов Eurostat: curated + композитор со слотами.

Заголовок принадлежит НАБОРУ (dataset_id), не индикатору/стране.
Страна живёт в world_countries.name_ru и в name_ru индикатора НЕ входит.

Качество имени (name_quality):
  curated  — точный перевод из словаря переопределений
  composed — собран композитором, без латиницы, все токены закрыты словарём,
             шаблон распознан
  raw      — всё остальное → is_listed=false (предохранитель витрины)

Публичные тексты — без кодов наборов, SDMX, имён измерений
(см. .cursor/rules/methodology-language.mdc). Источник в описаниях — «Евростат».
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# ---------------------------------------------------------------------------
# Категории по префиксу dataset_id
# ---------------------------------------------------------------------------

CATEGORY_BY_PREFIX: list[tuple[str, str]] = [
    ("prc_", "Цены"),
    ("ei_cphi", "Цены"),
    ("ei_hppi", "Цены"),
    ("namq_", "ВВП"),
    ("nama_", "ВВП"),
    ("naid", "ВВП"),
    ("une_", "Рынок труда"),
    ("lfsi_", "Рынок труда"),
    ("lfsq_", "Рынок труда"),
    ("lfs_", "Рынок труда"),
    ("ei_lm", "Рынок труда"),
    ("sts_", "Бизнес"),
    ("ei_is", "Бизнес"),
    ("ei_bs", "Бизнес"),
    ("irt_", "Финансы"),
    ("ert_", "Финансы"),
    ("gov_", "Финансы"),
    ("ei_mf", "Финансы"),
    ("ext_", "Торговля"),
    ("bop_", "Торговля"),
    ("ei_et", "Торговля"),
    ("ei_bpm", "Торговля"),
    ("demo_", "Население"),
    ("nrg_", "Товарные рынки"),
    ("road_", "Товарные рынки"),
    ("tour_", "Общество"),
    ("educ_", "Общество"),
    ("hlth_", "Общество"),
    ("ilc_", "Общество"),
    ("isoc_", "Общество"),
    ("sdg_", "Общество"),
    ("tec", "Бизнес"),
    ("tei", "Бизнес"),
    ("tin", "Бизнес"),
    ("tps", "Общество"),
    ("ei_", "Бизнес"),
]

UNIT_RU: dict[str, str] = {
    # Индексы (база явно — содержательная экономическая информация)
    "I15": "индекс (2015 = 100)",
    "I15_Q": "индекс (2015 = 100)",
    "I15_A_AVG": "индекс (2015 = 100), среднегодовой",
    "I10": "индекс (2010 = 100)",
    "I05": "индекс (2005 = 100)",
    "I96": "индекс (1996 = 100)",
    "I2015": "индекс (2015 = 100)",
    "I2021": "индекс (2021 = 100)",
    "I21": "индекс (2021 = 100)",
    "I21_SCA": "индекс (2021 = 100), с сезонной корректировкой",
    "I25": "индекс (2025 = 100)",
    "I25_NSA": "индекс (2025 = 100)",
    "INX": "индекс",
    "INX_A_AVG": "индекс, среднегодовой",
    "INDEX": "индекс",
    # Темпы / изменения
    "RCH_A": "изменение за год",
    "RCH_M": "изменение за месяц",
    "RCH_MV12MAVR": "среднее изменение за 12 месяцев",
    "RT1": "темп изменения",
    "RT1-SCA": "темп изменения, с сезонной корректировкой",
    "RT_M_DIF": "изменение за месяц, п.п.",
    "PCH_SM": "изменение к прошлому месяцу",
    "PCH_PRE": "изменение к предыдущему периоду",
    "PCH_SAME": "изменение к тому же периоду прошлого года",
    # Доли / проценты
    "PC": "%",
    "PC_ACT": "% экономически активного населения",
    "PC_POP": "% населения",
    "PC_GDP": "% ВВП",
    "PC_EU27_2020_HAB_MEUR_CP": "на душу населения, % от среднего по ЕС",
    "PM": "промилле",
    "BAL": "сальдо",
    "RT": "%",
    "YR": "лет",
    "PER_KM2": "чел. на км²",
    # Уровни / объёмы
    "MIO_EUR": "млн евро",
    "MIO_EUR_SCA": "млн евро, с сезонной корректировкой",
    "MIO-EUR-SA": "млн евро, с сезонной корректировкой",
    "MIO_NAC": "млн национальной валюты",
    "CLV15_MEUR": "в постоянных ценах 2015 года, млн евро",
    "CLV10_MEUR": "в постоянных ценах 2010 года, млн евро",
    "CP_MEUR": "в текущих ценах, млн евро",
    "CP_EUR_HAB": "на душу населения, евро",
    "THS_PER": "тысяч человек",
    "THS": "тысяч единиц",
    "THS_EUR": "тыс. евро",
    "NR": "человек",
    "EUR": "евро",
}

# Единицы, которые считаем «уровнем / индексом» (предпочтительнее производных
# мер при выборе единственной листингуемой карточки среди неразличимых).
_LEVEL_UNITS = frozenset({
    "I15", "I15_Q", "I15_A_AVG", "I10", "I05", "I96", "I2015", "I2021", "I21",
    "I21_SCA", "I25", "I25_NSA", "INX", "INX_A_AVG", "INDEX",
    "MIO_EUR", "MIO_EUR_SCA", "MIO-EUR-SA", "MIO_NAC",
    "CLV15_MEUR", "CLV10_MEUR", "CP_MEUR", "CP_EUR_HAB",
    "THS_PER", "THS", "THS_EUR", "NR", "EUR",
})
_DERIVED_UNITS = frozenset({
    "RCH_A", "RCH_M", "RCH_MV12MAVR", "RT1", "RT1-SCA", "RT_M_DIF",
    "PCH_SM", "PCH_PRE", "PCH_SAME",
})

_FREQ_TAIL_RE = re.compile(
    r",\s*(помесячно|поквартально|за год|понедельно|по дням)$"
)

_AGE_RU: dict[str, str] = {
    "Y15-24": "15–24 лет",
    "Y_LT25": "15–24 лет",
    "Y25-74": "25–74 лет",
    "Y15-64": "15–64 лет",
    "Y20-64": "20–64 лет",
    "Y18-64": "18–64 лет",
    "Y18-24": "18–24 лет",
    "Y16-19": "16–19 лет",
    "Y0-29": "0–29 лет",
    "Y18": "18 лет",
    "Y_LT6": "младше 6 лет",
    "Y_GE15": "15 лет и старше",
    "Y_GE25": "25 лет и старше",
    "Y_LT1": "младше 1 года",
    "Y_LT5": "младше 5 лет",
    "D0": "младше 1 дня",
    "D1": "1 день",
    "D1-6": "1–6 дней",
    "D7-27": "7–27 дней",
    "D28-364": "28–364 дня",
    "Y1": "1 год",
    "Y_LT15": "младше 15 лет",
    "Y15-74": "15–74 лет",
}

_SEX_RU: dict[str, str] = {
    "M": "мужчины",
    "F": "женщины",
}

# Измерения, сужающие смысл ряда и обязанные быть в name_ru.
# TOTAL-коды не требуют отражения. Прочие SDMX-измерения (indic, nace…)
# разделяют card_key через extra_dims; имя для них — зона курации, не авто-unlist.
_NARROWING_NAME_DIMS = frozenset({"age", "sex"})
_NARROWING_DIM_TOTALS: dict[str, frozenset[str]] = {
    "age": frozenset({"", "TOTAL", "T", "Y15-74"}),
    "sex": frozenset({"", "T", "TOTAL"}),
}

# ---------------------------------------------------------------------------
# Словарь терминов: nom (подлежащее) / prep (слот «по …»)
# ---------------------------------------------------------------------------

Term = dict[str, str]  # {"nom": "...", "prep": "..."} optional prep


def _t(nom: str, prep: str | None = None) -> Term:
    d: Term = {"nom": nom}
    if prep is not None:
        d["prep"] = prep
    return d


# Многословные фразы — длинные раньше коротких при матчинге.
SUBJECT_TERMS: list[tuple[str, Term]] = [
    ("harmonised index of consumer prices", _t("гармонизированный индекс потребительских цен")),
    ("gross domestic product", _t("валовой внутренний продукт")),
    ("production in industry", _t("производство в промышленности")),
    ("production in construction", _t("производство в строительстве")),
    ("production in services", _t("производство в сфере услуг")),
    ("producer prices in industry", _t("цены производителей в промышленности")),
    ("import prices in industry", _t("цены на импорт в промышленности")),
    ("labour input in construction", _t("затраты труда в строительстве")),
    ("labour input in industry", _t("затраты труда в промышленности")),
    ("labour input in services", _t("затраты труда в сфере услуг")),
    ("young persons neither in employment nor in education and training", _t("незанятая и не обучающаяся молодёжь")),
    ("labour force participation rates", _t("уровень участия в рабочей силе")),
    ("labour market slack", _t("недоиспользование рабочей силы")),
    ("part-time employment and temporary contracts", _t("частичная занятость и временные трудовые договоры")),
    ("persons outside the labour force", _t("лица вне рабочей силы")),
    ("persons having a second job", _t("занятые на второй работе")),
    ("persons in full-time/part-time employment", _t("занятые полное и неполное время")),
    ("persons in part-time employment", _t("частично занятые")),
    ("self-employed persons", _t("самозанятые")),
    ("temporary employees", _t("временно занятые")),
    ("employed persons", _t("занятые")),
    ("unemployed persons", _t("безработные")),
    ("labour force", _t("рабочая сила")),
    ("labour productivity and unit labour costs", _t("производительность труда и удельные затраты на рабочую силу")),
    ("owner-occupied housing price index", _t("индекс цен жилья, занимаемого владельцами")),
    ("volume of retail trade", _t("объём розничной торговли")),
    ("turnover in industry", _t("оборот в промышленности")),
    ("turnover in services", _t("оборот в сфере услуг")),
    ("unemployment rate", _t("уровень безработицы")),
    ("current account", _t("счёт текущих операций")),
    ("financial account", _t("финансовый счёт")),
    ("balance of payments", _t("платёжный баланс")),
    ("international investment position", _t("международная инвестиционная позиция")),
    ("house price index", _t("индекс цен на жильё")),
    ("job vacancy rate", _t("доля вакансий")),
    ("interest rates", _t("процентные ставки")),
    ("exchange rates", _t("обменные курсы")),
    ("industrial production", _t("промышленное производство")),
    ("retail trade", _t("розничная торговля")),
    ("building permits", _t("разрешения на строительство")),
    ("population on 1 january", _t("население на 1 января")),
    ("usually resident population", _t("постоянно проживающее население")),
    ("population structure indicators", _t("показатели возрастной структуры населения")),
    ("population change", _t("изменение численности населения")),
    ("old-age-dependency ratio", _t("коэффициент демографической нагрузки пожилыми")),
    ("total fertility rate", _t("суммарный коэффициент рождаемости")),
    ("fertility indicators", _t("показатели рождаемости")),
    ("fertility rates", _t("коэффициенты рождаемости")),
    ("infant mortality rates", _t("коэффициенты младенческой смертности")),
    ("infant mortality rate", _t("коэффициент младенческой смертности")),
    ("infant mortality", _t("младенческая смертность")),
    ("life expectancy", _t("ожидаемая продолжительность жизни")),
    ("life table", _t("таблица смертности")),
    ("excess mortality", _t("избыточная смертность")),
    ("crude birth rate", _t("общий коэффициент рождаемости")),
    ("crude death rate", _t("общий коэффициент смертности")),
    ("crude marriage rate", _t("общий коэффициент брачности")),
    ("live births", _t("число родившихся")),
    ("marriage indicators", _t("показатели брачности")),
    ("divorce indicators", _t("показатели разводимости")),
    ("at-risk-of-poverty rate", _t("доля населения под риском бедности")),
    ("at risk of poverty or social exclusion", _t("риск бедности или социальной исключённости")),
    ("final energy consumption", _t("конечное потребление энергии")),
    ("energy import dependency", _t("зависимость от импорта энергоресурсов")),
    ("pupils and students enrolled", _t("численность учащихся и студентов")),
    ("pupils and students", _t("учащиеся и студенты")),
    ("passenger cars", _t("легковые автомобили")),
    ("unemployment", _t("безработица")),
    ("employment", _t("занятость")),
    ("employees", _t("наёмные работники")),
    ("population", _t("население")),
    ("inflation", _t("инфляция")),
    ("construction", _t("строительство")),
    ("industry", _t("промышленность")),
    ("energy", _t("энергетика")),
    ("services", _t("услуги")),
    ("exports", _t("экспорт")),
    ("imports", _t("импорт")),
    ("wages", _t("заработная плата")),
    ("debt", _t("долг")),
    ("deficit", _t("дефицит")),
    ("revenue", _t("доходы")),
    ("expenditure", _t("расходы")),
    ("investment", _t("инвестиции")),
    ("tourism", _t("туризм")),
    ("education", _t("образование")),
    ("health", _t("здравоохранение")),
    ("transport", _t("транспорт")),
    ("marriages", _t("браки")),
    ("divorces", _t("разводы")),
    ("deaths", _t("число умерших")),
    ("births", _t("число рождений")),
    ("households", _t("домохозяйства")),
    ("household", _t("домохозяйство")),
    ("index", _t("индекс")),
    ("indicator", _t("показатель")),
    ("indicators", _t("показатели")),
    ("prices", _t("цены")),
    ("price", _t("цена")),
    ("trade", _t("торговля")),
    ("growth", _t("рост")),
    ("rate", _t("ставка")),
    ("rates", _t("ставки")),
    ("volume", _t("объём")),
    ("total", _t("всего")),
]

DIM_TERMS: list[tuple[str, Term]] = [
    ("sex and age", _t("пол и возраст", "полу и возрасту")),
    ("age and sex", _t("возраст и пол", "возрасту и полу")),
    ("type of building", _t("тип здания", "типам зданий")),
    ("nace rev. 2 activity", _t("вид деятельности", "видам экономической деятельности")),
    ("nace rev 2 activity", _t("вид деятельности", "видам экономической деятельности")),
    ("detailed economic activity", _t("детализированный вид экономической деятельности", "детализированным видам экономической деятельности")),
    ("economic activity", _t("вид экономической деятельности", "видам экономической деятельности")),
    ("educational attainment level", _t("уровень образования", "уровню образования")),
    ("professional status and occupation", _t("статус занятости и занятие", "статусу занятости и занятию")),
    ("professional status", _t("статус занятости", "статусу занятости")),
    ("occupation", _t("занятие", "занятию")),
    ("duration of unemployment", _t("продолжительность безработицы", "продолжительности безработицы")),
    ("duration of the employment contract", _t("срок трудового договора", "сроку трудового договора")),
    ("country of birth", _t("страна рождения", "стране рождения")),
    ("citizenship", _t("гражданство", "гражданству")),
    ("broad age group", _t("укрупнённая возрастная группа", "укрупнённым возрастным группам")),
    ("age group", _t("возрастная группа", "возрастным группам")),
    ("age groups", _t("возрастные группы", "возрастным группам")),
    ("legal marital status", _t("семейное положение", "семейному положению")),
    ("marital status", _t("семейное положение", "семейному положению")),
    ("partner country", _t("страна-партнёр", "странам-партнёрам")),
    ("product group", _t("товарная группа", "товарным группам")),
    ("bec product group", _t("группа товаров", "группам товаров")),
    ("sitc product group", _t("товарная группа", "товарным группам")),
    ("type of motor energy", _t("вид топлива", "виду топлива")),
    ("type of plant", _t("тип станции", "типу станции")),
    ("type of institution", _t("тип учреждения", "типу учреждения")),
    ("nuts 2 region", _t("регион", "регионам")),
    ("nuts 3 region", _t("регион", "регионам")),
    ("partner", _t("партнёр", "партнёрам")),
    ("sector", _t("сектор", "секторам")),
    ("size class", _t("размер предприятия", "размеру предприятий")),
    ("enterprise size class", _t("размер предприятия", "размеру предприятий")),
    ("mother's age", _t("возраст матери", "возрасту матери")),
    ("age", _t("возраст", "возрасту")),
    ("sex", _t("пол", "полу")),
    ("country", _t("страна", "странам")),
    ("activity", _t("деятельность", "видам деятельности")),
    ("region", _t("регион", "регионам")),
]

# Однословные токены (для проверки покрытия / фолбэка composed).
WORD_TERMS: dict[str, Term] = {
    "and": _t("и"),
    "of": _t(""),
    "in": _t("в"),
    "by": _t("по"),
    "for": _t("для"),
    "the": _t(""),
    "a": _t(""),
    "an": _t(""),
    "to": _t(""),
    "from": _t("из"),
    "with": _t("с"),
    "without": _t("без"),
    "on": _t("по"),
    "at": _t(""),
    "or": _t("или"),
    "vs": _t("к"),
    "new": _t("новые"),
    "total": _t("всего"),
    "domestic": _t("внутренний"),
    "market": _t("рынок"),
    "monthly": _t("помесячно"),
    "quarterly": _t("поквартально"),
    "annual": _t("за год"),
    "yearly": _t("за год"),
    "weekly": _t("понедельно"),
    "daily": _t("по дням"),
    "data": _t("данные"),
    "index": _t("индекс"),
    "rate": _t("ставка"),
    "rates": _t("ставки"),
    "change": _t("изменение"),
    "average": _t("средний"),
    "main": _t("основные"),
    "components": _t("компоненты"),
    "other": _t("прочие"),
    "all": _t("все"),
    "items": _t("статьи"),
    "area": _t("зона"),
    "euro": _t("евро"),
    "european": _t("европейский"),
    "union": _t("союз"),
    "member": _t("страна"),
    "states": _t("государства"),
    "state": _t("государство"),
    "national": _t("национальный"),
    "international": _t("международный"),
    "external": _t("внешний"),
    "internal": _t("внутренний"),
    "real": _t("реальный"),
    "nominal": _t("номинальный"),
    "seasonally": _t("сезонно"),
    "adjusted": _t("скорректированный"),
    "unadjusted": _t("нескорректированный"),
    "constant": _t("постоянный"),
    "current": _t("текущий"),
    "prices": _t("цены"),
    "price": _t("цена"),
    "consumer": _t("потребительский"),
    "producer": _t("производитель"),
    "industrial": _t("промышленный"),
    "business": _t("деловой"),
    "confidence": _t("уверенность"),
    "sentiment": _t("настроения"),
    "survey": _t("опрос"),
    "results": _t("результаты"),
    "indicator": _t("показатель"),
    "indicators": _t("показатели"),
    "growth": _t("рост"),
    "volume": _t("объём"),
    "value": _t("стоимость"),
    "turnover": _t("оборот"),
    "sales": _t("продажи"),
    "production": _t("производство"),
    "industry": _t("промышленность"),
    "construction": _t("строительство"),
    "services": _t("услуги"),
    "service": _t("услуга"),
    "trade": _t("торговля"),
    "retail": _t("розничная"),
    "wholesale": _t("оптовая"),
    "unemployment": _t("безработица"),
    "employment": _t("занятость"),
    "labour": _t("труд"),
    "labor": _t("труд"),
    "input": _t("затраты"),
    "cost": _t("стоимость"),
    "costs": _t("затраты"),
    "wage": _t("зарплата"),
    "wages": _t("заработная плата"),
    "population": _t("население"),
    "demography": _t("демография"),
    "birth": _t("рождение"),
    "death": _t("смерть"),
    "migration": _t("миграция"),
    "energy": _t("энергетика"),
    "electricity": _t("электроэнергия"),
    "gas": _t("газ"),
    "fuel": _t("топливо"),
    "food": _t("продовольствие"),
    "housing": _t("жильё"),
    "house": _t("жильё"),
    "building": _t("здание"),
    "buildings": _t("здания"),
    "permits": _t("разрешения"),
    "bankruptcy": _t("банкротство"),
    "registration": _t("регистрация"),
    "export": _t("экспорт"),
    "exports": _t("экспорт"),
    "import": _t("импорт"),
    "imports": _t("импорт"),
    "balance": _t("сальдо"),
    "payments": _t("платежи"),
    "payment": _t("платёж"),
    "investment": _t("инвестиции"),
    "investments": _t("инвестиции"),
    "position": _t("позиция"),
    "positions": _t("позиции"),
    "flow": _t("поток"),
    "flows": _t("потоки"),
    "income": _t("доход"),
    "debt": _t("долг"),
    "deficit": _t("дефицит"),
    "surplus": _t("профицит"),
    "revenue": _t("доходы"),
    "expenditure": _t("расходы"),
    "government": _t("государственный"),
    "general": _t("общий"),
    "bond": _t("облигация"),
    "bonds": _t("облигации"),
    "yield": _t("доходность"),
    "yields": _t("доходность"),
    "maturity": _t("срок погашения"),
    "interest": _t("процент"),
    "money": _t("денежный"),
    "market": _t("рынок"),
    "exchange": _t("обменный"),
    "effective": _t("эффективный"),
    "conversion": _t("пересчёт"),
    "factors": _t("коэффициенты"),
    "factor": _t("коэффициент"),
    "currency": _t("валюта"),
    "currencies": _t("валюты"),
    "countries": _t("страны"),
    "country": _t("страна"),
    "partner": _t("партнёр"),
    "partners": _t("партнёры"),
    "product": _t("товар"),
    "products": _t("товары"),
    "group": _t("группа"),
    "groups": _t("группы"),
    "sector": _t("сектор"),
    "sectors": _t("секторы"),
    "activity": _t("деятельность"),
    "activities": _t("виды деятельности"),
    "type": _t("тип"),
    "types": _t("типы"),
    "sex": _t("пол"),
    "age": _t("возраст"),
    "size": _t("размер"),
    "class": _t("класс"),
    "share": _t("доля"),
    "shares": _t("доли"),
    "percent": _t("процент"),
    "percentage": _t("процент"),
    "points": _t("пункты"),
    "point": _t("пункт"),
    "contribution": _t("вклад"),
    "contributions": _t("вклады"),
    "first": _t("первые"),
    "published": _t("опубликованные"),
    "released": _t("опубликованные"),
    "tax": _t("налог"),
    "taxes": _t("налоги"),
    "harmonised": _t("гармонизированный"),
    "detailed": _t("детальный"),
    "geographical": _t("географический"),
    "breakdown": _t("разбивка"),
    "outside": _t("вне"),
    "extra": _t("внешний"),
    "intra": _t("внутренний"),
    "world": _t("мир"),
    "global": _t("глобальный"),
    "unit": _t("удельный"),
    "labour": _t("труд"),
    "hoarding": _t("удержание"),
    "expectations": _t("ожидания"),
    "climate": _t("климат"),
    "consumers": _t("потребители"),
    "consumer": _t("потребительский"),
    "vacancy": _t("вакансия"),
    "job": _t("рабочее место"),
    "persons": _t("человек"),
    "person": _t("человек"),
    "thousand": _t("тысяча"),
    "number": _t("численность"),
    "level": _t("уровень"),
    "levels": _t("уровни"),
    "comparative": _t("сравнительный"),
    "purchasing": _t("покупательный"),
    "power": _t("способность"),
    "parities": _t("паритеты"),
    "parity": _t("паритет"),
    "correction": _t("корректирующий"),
    "coefficients": _t("коэффициенты"),
    "monitoring": _t("мониторинг"),
    "tool": _t("инструмент"),
    "years": _t("лет"),
    "year": _t("год"),
    "month": _t("месяц"),
    "months": _t("месяцы"),
    "quarter": _t("квартал"),
    "day": _t("день"),
    "days": _t("дни"),
    # Аудит-токены и демография / общество / энергия
    "education": _t("образование"),
    "educational": _t("образовательный"),
    "aged": _t("в возрасте"),
    "social": _t("социальный"),
    "status": _t("статус"),
    "region": _t("регион"),
    "regions": _t("регионы"),
    "regional": _t("региональный"),
    "household": _t("домохозяйство"),
    "households": _t("домохозяйства"),
    "poverty": _t("бедность"),
    "pupils": _t("учащиеся"),
    "students": _t("студенты"),
    "enrolled": _t("зачисленные"),
    "attainment": _t("достижение"),
    "intensity": _t("интенсивность"),
    "living": _t("проживающие"),
    "degree": _t("степень"),
    "consumption": _t("потребление"),
    "transport": _t("транспорт"),
    "risk": _t("риск"),
    "accommodation": _t("размещение"),
    "goods": _t("товары"),
    "births": _t("рождения"),
    "deaths": _t("смерти"),
    "mortality": _t("смертность"),
    "fertility": _t("рождаемость"),
    "expectancy": _t("продолжительность"),
    "median": _t("медианный"),
    "crude": _t("общий"),
    "density": _t("плотность"),
    "renewable": _t("возобновляемый"),
    "fossil": _t("ископаемый"),
    "oil": _t("нефть"),
    "petroleum": _t("нефтепродукты"),
    "natural": _t("природный"),
    "solid": _t("твёрдый"),
    "heat": _t("тепло"),
    "capacity": _t("мощность"),
    "capacities": _t("мощности"),
    "motorways": _t("автомагистрали"),
    "roads": _t("дороги"),
    "cars": _t("автомобили"),
    "vehicles": _t("транспортные средства"),
    "physicians": _t("врачи"),
    "hospital": _t("больничный"),
    "beds": _t("койки"),
    "medical": _t("медицинский"),
    "examination": _t("обследование"),
    "corruption": _t("коррупция"),
    "research": _t("исследования"),
    "development": _t("разработки"),
    "capita": _t("на душу населения"),
    "relative": _t("относительный"),
    "gap": _t("разрыв"),
    "transfers": _t("трансферты"),
    "monetary": _t("денежный"),
    "elderly": _t("пожилые"),
    "older": _t("старше"),
    "gender": _t("гендерный"),
    "exclusion": _t("исключённость"),
    "deprivation": _t("лишения"),
    "material": _t("материальный"),
    "january": _t("январь"),
    "structure": _t("структура"),
    "broad": _t("укрупнённый"),
    "mother": _t("мать"),
    "infant": _t("младенческий"),
    "marriage": _t("брак"),
    "marriages": _t("браки"),
    "divorce": _t("развод"),
    "divorces": _t("разводы"),
    "duration": _t("продолжительность"),
    "previous": _t("предыдущий"),
    "citizenship": _t("гражданство"),
    "weight": _t("вес"),
    "abortion": _t("аборт"),
    "abortions": _t("аборты"),
    "excess": _t("избыточный"),
    "table": _t("таблица"),
    "life": _t("жизнь"),
    "dependency": _t("нагрузка"),
    "proportion": _t("доля"),
    "mean": _t("средний"),
    "women": _t("женщины"),
    "childbirth": _t("роды"),
    "child": _t("ребёнок"),
    "participation": _t("участие"),
    "institution": _t("учреждение"),
    "programme": _t("программа"),
    "tertiary": _t("высший"),
    "primary": _t("начальный"),
    "secondary": _t("средний"),
    "compulsory": _t("обязательный"),
    "early": _t("ранний"),
    "childhood": _t("детство"),
    "school": _t("школа"),
    "work": _t("труд"),
}

FREQ_SUFFIX = {
    "monthly": ", помесячно",
    "quarterly": ", поквартально",
    "annual": ", за год",
    "yearly": ", за год",
    "weekly": ", понедельно",
    "daily": ", по дням",
}

# Скобочные уточнения: перевод или отброс (None = отбросить).
PAREN_RULES: list[tuple[re.Pattern[str], str | None]] = [
    (re.compile(r"^\d{4}\s*[-–]\s*\d{2,4}$"), None),
    (re.compile(r"^nace rev\.?\s*2$", re.I), None),
    (re.compile(r"^ecoicop", re.I), None),
    (re.compile(r"^bpm6$", re.I), None),
    (re.compile(r"^sitc", re.I), None),
    (re.compile(r"^bec", re.I), None),
    (re.compile(r"^ebops", re.I), None),
    (re.compile(r"^brussels\s*=", re.I), None),
    (re.compile(r"^\d{4}\s*=\s*100$", re.I), None),
    (re.compile(r"^index$", re.I), "индекс"),
    (re.compile(r"^annual rate of change$", re.I), "годовой темп изменения"),
    (re.compile(r"^monthly rate of change$", re.I), "месячный темп изменения"),
    (re.compile(r"^12-month average rate of change$", re.I), "средний темп за 12 месяцев"),
    (re.compile(r"^in percentage points$", re.I), "в процентных пунктах"),
    (re.compile(r"^duty stations$", re.I), None),
    (re.compile(r"^from \d{4}", re.I), None),
    (re.compile(r"^since \d{4}", re.I), None),
]


@dataclass(frozen=True)
class TitleResult:
    name_ru: str
    quality: str  # curated | composed | raw
    uncovered_tokens: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def _load_curated() -> dict[str, str]:
    path = Path(__file__).with_name("eurostat_titles_curated.json")
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def category_for_dataset(dataset_id: str) -> str:
    ds = (dataset_id or "").lower()
    for prefix, cat in CATEGORY_BY_PREFIX:
        if ds.startswith(prefix.lower()):
            return cat
    return "Прочее"


def unit_label_ru(unit_code: str | None) -> str:
    """Устаревший путь: только однозначные метки кодлиста. Без угадывания RT/NR.

    Для полной резолюции используйте ``resolve_public_unit``.
    """
    from app.data.eurostat_units_ru import resolve_public_unit

    ru, _prov = resolve_public_unit(dataset_id="", unit_code=unit_code)
    return ru or ""


def split_freq_suffix(name: str) -> tuple[str, str]:
    """Отделить хвостовой частотный суффикс: ('…', ', помесячно')."""
    m = _FREQ_TAIL_RE.search(name or "")
    if not m:
        return (name or "").rstrip(), ""
    return name[: m.start()].rstrip(), m.group(0)


# Энергобаланс / продукт — чтобы карточки IPRD≠GID_OBS не схлопывались
# в один display_name и не оставляли витрину пустой после unlist константы.
_NRG_BAL_RU: dict[str, str] = {
    "GID_OBS": "внутренние поставки",
    "GID_CAL": "внутренние поставки",
    "AIM": "доступно для внутреннего рынка",
    "ID": "внутренний спрос",
    "IPRD": "добыча",
    "IMP": "импорт",
    "EXP": "экспорт",
    "FC_E": "конечное потребление",
    "GIC": "валовое внутреннее потребление",
    "DL": "потери при распределении",
    "TI_EHG_MAP": "преобразование в электроэнергию и тепло",
}

_SIEC_RU: dict[str, str] = {
    "C0100": "каменный уголь",
    "C0200": "бурый уголь",
    "C0311": "коксовый кокс",
    "E7000": "электроэнергия",
    "H8000": "тепло",
    "G3000": "природный газ",
    "P1100": "торф",
    "S2000": "горючие сланцы",
}


def _slice_qualifiers_ru(slice_json: dict | None) -> list[str]:
    """Человекочитаемые уточнения среза (пол, возраст, энергопоток) — без кодов."""
    if not slice_json:
        return []
    bits: list[str] = []
    age = (slice_json.get("age") or "").strip().upper()
    if age and age not in {"TOTAL", "T", "Y15-74"}:
        label = _AGE_RU.get(age)
        if label:
            bits.append(label)
    sex = (slice_json.get("sex") or "").strip().upper()
    if sex in _SEX_RU:
        bits.append(_SEX_RU[sex])
    nrg = (slice_json.get("nrg_bal") or "").strip().upper()
    if nrg and nrg in _NRG_BAL_RU:
        bits.append(_NRG_BAL_RU[nrg])
    siec = (slice_json.get("siec") or "").strip().upper()
    if siec and siec in _SIEC_RU:
        bits.append(_SIEC_RU[siec])
    return bits


def narrowing_slice_labels(slice_json: dict | None) -> tuple[list[str], list[str]]:
    """Вернуть (известные_лейблы, неизвестные_коды) для age/sex.

    Неизвестный код = срез сужает смысл, но мы не умеем назвать его по-русски
    → карточку нельзя честно листинговать.
    """
    if not slice_json:
        return [], []
    known: list[str] = []
    unknown: list[str] = []
    for dim in _NARROWING_NAME_DIMS:
        totals = _NARROWING_DIM_TOTALS[dim]
        raw = slice_json.get(dim)
        if raw is None:
            continue
        val = str(raw).strip().upper()
        if not val or val in totals:
            continue
        if dim == "age":
            label = _AGE_RU.get(val)
            if label:
                known.append(label)
            else:
                unknown.append(f"age={val}")
        elif dim == "sex":
            label = _SEX_RU.get(val)
            if label:
                known.append(label)
            else:
                unknown.append(f"sex={val}")
    return known, unknown


def slice_reflected_in_name(name_ru: str | None, slice_json: dict | None) -> bool:
    """Инвариант: сужающий срез обязан быть виден в name_ru (или ряд не листить).

    Плюс слой 2: содержательный срез (na_item/indic*) не противоречит имени.
    """
    from app.data.eurostat_substance import slice_concept_matches_name

    if not slice_concept_matches_name(name_ru, slice_json):
        return False
    known, unknown = narrowing_slice_labels(slice_json)
    if unknown:
        return False
    if not known:
        return True
    hay = (name_ru or "").lower()
    for label in known:
        if label.lower() not in hay:
            return False
    return True


def measure_phrase(unit: str | None, slice_json: dict | None = None, *, dataset_id: str = "") -> str:
    """Различающий признак меры: только достоверная единица + пол/возраст."""
    from app.data.eurostat_units_ru import resolve_public_unit

    code = (unit or "").strip()
    if not code and slice_json:
        code = (slice_json.get("unit") or "").strip()
    bits: list[str] = []
    label, _prov = resolve_public_unit(
        dataset_id=dataset_id,
        unit_code=code,
        slice_json=slice_json,
    )
    if label:
        bits.append(label)
    bits.extend(_slice_qualifiers_ru(slice_json))
    return ", ".join(bits)


def build_public_name(
    base_name: str,
    *,
    unit: str | None = None,
    slice_json: dict | None = None,
    frequency: str | None = None,
    dataset_id: str = "",
) -> str:
    """Имя карточки: предмет из среза (если пин) + различающая мера.

    Частота в имя не входит: на карточке её выбирает переключатель
    (месяц / квартал / год), в том числе когда доступна только одна.
    Параметр ``frequency`` сохранён для совместимости вызовов и игнорируется.
    """
    from app.data.eurostat_substance import apply_substance_to_subject

    _ = frequency  # частота — не часть названия показателя
    subject, _freq_suffix = split_freq_suffix(base_name)

    # Слой 1: подлежащее из фактически закреплённого содержательного среза.
    subject = apply_substance_to_subject(subject, slice_json)

    measure = measure_phrase(unit, slice_json, dataset_id=dataset_id)
    if measure:
        subj_l = subject.lower()
        if measure.lower() not in subj_l:
            extra: list[str] = []
            for part in measure.split(", "):
                if part.lower() not in subj_l:
                    extra.append(part)
            if extra:
                subject = f"{subject}, {', '.join(extra)}"

    name = subject
    if name and name[0].islower():
        name = name[0].upper() + name[1:]
    return name


def listing_substance_score(
    *,
    unit: str | None,
    points_count: int,
    dataset_id: str,
    slice_json: dict | None = None,
) -> int:
    """Чем выше — тем предпочтительнее оставить листингуемым при неразличимости."""
    u = (unit or "").strip()
    score = 0
    if u in _LEVEL_UNITS:
        score += 100
    elif u in _DERIVED_UNITS:
        score += 10
    elif u:
        score += 40
    score += min(max(points_count, 0), 400) // 4
    ds = (dataset_id or "").lower()
    # национальные счета / канонические HICP — содержательнее micro-срезов LFS
    if ds.startswith(("nama_", "namq_", "prc_hicp_midx", "prc_hicp_manr", "une_rt_")):
        score += 50
    if "nama_10r" in ds or "namq_10r" in ds or ds.startswith("lfsq_pg"):
        score -= 40
    if ds.startswith("teilm") or ds.startswith("teibp"):
        score += 5
    # демография: канонический infant mortality rate важнее early neonatal и т.п.
    indic = ""
    if slice_json:
        indic = (
            slice_json.get("indic_de")
            or slice_json.get("indic")
            or ""
        ).upper()
    if indic == "INFMORRT":
        score += 80
    elif indic in {"ENEOMORRT", "NEOMORRT", "PERIMORRT", "LFOEMORRT"}:
        score -= 30
    if indic == "TOTFERRT":
        score += 40
    return score


def has_latin(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text or ""))


def _match_longest(text: str, terms: list[tuple[str, Term]]) -> tuple[str, Term] | None:
    low = text.lower().strip()
    for eng, term in sorted(terms, key=lambda x: -len(x[0])):
        if low == eng or low.startswith(eng + " ") or low.startswith(eng + ",") or low.startswith(eng + "-"):
            return eng, term
        if low == eng:
            return eng, term
    return None


def _tokenize_parens(title: str) -> tuple[str, list[str]]:
    """Process (...) segments: translate or drop. Returns (text, kept_ru_bits)."""
    kept: list[str] = []
    uncovered: list[str] = []

    def repl(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        for pat, ru in PAREN_RULES:
            if pat.search(inner):
                if ru:
                    kept.append(ru)
                return ""
            if pat.fullmatch(inner):
                if ru:
                    kept.append(ru)
                return ""
        # unknown paren → drop for public text, but mark uncovered if has latin words
        for w in re.findall(r"[A-Za-z][A-Za-z0-9\-']*", inner):
            uncovered.append(w.lower())
        return ""

    cleaned = re.sub(r"\(([^)]*)\)", repl, title)
    # stash uncovered on function attribute for caller
    _tokenize_parens._uncovered = uncovered  # type: ignore[attr-defined]
    return re.sub(r"\s+", " ", cleaned).strip(" -–,;"), kept


def _extract_freq(title: str) -> tuple[str, str | None]:
    m = re.search(
        r"\s*[-–—,]?\s*(monthly|quarterly|annual|yearly|weekly|daily)\s+data\b.*$",
        title,
        flags=re.I,
    )
    if not m:
        m2 = re.search(r"\s*[-–—]?\s*quarterly and annual data\b.*$", title, flags=re.I)
        if m2:
            return title[: m2.start()].strip(" -–,;"), ", поквартально"
        return title, None
    word = m.group(1).lower()
    return title[: m.start()].strip(" -–,;"), FREQ_SUFFIX.get(word)


def _tokenize_subject(subject: str) -> tuple[str | None, list[str]]:
    """Return (russian_subject, uncovered_tokens). None subject → failed."""
    uncovered: list[str] = []
    low = subject.lower().strip()
    low = re.sub(r"\s+", " ", low)
    if not low:
        return None, ["<empty>"]

    # Pattern: <Subject> by <dimA> [and <dimB>]
    m = re.match(r"^(.+?)\s+by\s+(.+)$", low)
    if m:
        head, dims = m.group(1).strip(), m.group(2).strip()
        head_hit = _match_longest(head, SUBJECT_TERMS)
        dim_hit = _match_longest(dims, DIM_TERMS)
        if head_hit and dim_hit:
            # check leftover tokens in head/dims beyond matched phrases
            head_rest = head[len(head_hit[0]) :].strip(" ,;-")
            dim_rest = dims[len(dim_hit[0]) :].strip(" ,;-")
            for rest, bag in ((head_rest, head), (dim_rest, dims)):
                if rest:
                    for w in re.findall(r"[a-z][a-z0-9\-']*", rest):
                        if w not in WORD_TERMS and w not in ("rev", "2"):
                            uncovered.append(w)
            if uncovered:
                return None, uncovered
            prep = dim_hit[1].get("prep") or dim_hit[1]["nom"]
            return f"{head_hit[1]['nom']} по {prep}", []
        # partial → collect uncovered
        if not head_hit:
            for w in re.findall(r"[a-z][a-z0-9\-']*", head):
                if w not in WORD_TERMS:
                    uncovered.append(w)
        if not dim_hit:
            for w in re.findall(r"[a-z][a-z0-9\-']*", dims):
                if w not in WORD_TERMS:
                    uncovered.append(w)
        return None, uncovered or ["by-template-miss"]

    # Plain subject phrase
    hit = _match_longest(low, SUBJECT_TERMS)
    if hit:
        rest = low[len(hit[0]) :].strip(" ,;-")
        # allow trailing adjectives covered by WORD_TERMS
        if rest:
            tokens = re.findall(r"[a-z][a-z0-9\-']*", rest)
            for w in tokens:
                if w not in WORD_TERMS and w not in {t[0].split()[0] for t in SUBJECT_TERMS}:
                    # try multi-word remainder against subjects again
                    rem_hit = _match_longest(rest, SUBJECT_TERMS)
                    if rem_hit:
                        continue
                    uncovered.append(w)
            if uncovered:
                return None, uncovered
            # compose: subject + covered trailing words in nom
            bits = [hit[1]["nom"]]
            for w in tokens:
                term = WORD_TERMS.get(w)
                if term and term["nom"]:
                    bits.append(term["nom"])
            return " ".join(bits), []
        return hit[1]["nom"], []

    # Token-cover attempt (emergency — not a recognized template → raw)
    tokens = re.findall(r"[a-z][a-z0-9\-']*", low)
    for w in tokens:
        if w not in WORD_TERMS and not any(w in phr for phr, _ in SUBJECT_TERMS + DIM_TERMS):
            uncovered.append(w)
    return None, uncovered or tokens or ["no-template"]


def compose_title(english_title: str, dataset_id: str = "") -> TitleResult:
    """Трёхуровневый перевод заголовка набора.

    Частотный хвост («, помесячно» и т.п.) из имени всегда снимается:
    периодичность — свойство ряда/режима карточки, не часть названия.
    """
    ds = (dataset_id or "").lower()
    curated = _load_curated()
    if ds in curated:
        name, _ = split_freq_suffix(curated[ds])
        if has_latin(name):
            return TitleResult(name, "raw", ("curated-has-latin",))
        return TitleResult(name, "curated")

    title = (english_title or "").strip()
    if not title:
        return TitleResult("Экономический показатель", "raw", ("empty-title",))

    cleaned, paren_bits = _tokenize_parens(title)
    paren_uncovered = getattr(_tokenize_parens, "_uncovered", [])
    body, _freq_ru = _extract_freq(cleaned)

    subject_ru, uncovered = _tokenize_subject(body)
    uncovered = list(uncovered) + list(paren_uncovered)

    if subject_ru is None or uncovered:
        fallback, _ = split_freq_suffix(curated.get(ds) or "Экономический показатель")
        return TitleResult(fallback, "raw", tuple(dict.fromkeys(uncovered)))

    parts = [subject_ru]
    parts.extend(paren_bits)
    name = ", ".join(parts) if paren_bits else subject_ru
    name, _ = split_freq_suffix(name)
    name = name[0].upper() + name[1:] if name else name

    if has_latin(name):
        return TitleResult(name, "raw", tuple(dict.fromkeys(list(uncovered) + ["latin-in-result"])))

    return TitleResult(name, "composed", ())


def resolve_dataset_title(dataset_id: str, english_title: str) -> TitleResult:
    """Единая точка: один перевод на набор."""
    return compose_title(english_title, dataset_id)


def is_listed_for_quality(quality: str) -> bool:
    return quality in ("curated", "composed")


# Предложный падеж для фраз «X в Германии» (поиск / seo_title / описание).
# Ключ — slug страны; фолбэк — именительный из БД.
COUNTRY_PREPOSITIONAL: dict[str, str] = {
    "austria": "Австрии",
    "belgium": "Бельгии",
    "bulgaria": "Болгарии",
    "croatia": "Хорватии",
    "cyprus": "Кипре",
    "czechia": "Чехии",
    "denmark": "Дании",
    "estonia": "Эстонии",
    "finland": "Финляндии",
    "france": "Франции",
    "germany": "Германии",
    "greece": "Греции",
    "hungary": "Венгрии",
    "ireland": "Ирландии",
    "italy": "Италии",
    "latvia": "Латвии",
    "lithuania": "Литве",
    "luxembourg": "Люксембурге",
    "malta": "Мальте",
    "netherlands": "Нидерландах",
    "poland": "Польше",
    "portugal": "Португалии",
    "romania": "Румынии",
    "slovakia": "Словакии",
    "slovenia": "Словении",
    "spain": "Испании",
    "sweden": "Швеции",
    "iceland": "Исландии",
    "norway": "Норвегии",
    "switzerland": "Швейцарии",
    "united-kingdom": "Великобритании",
    "turkey": "Турции",
    "serbia": "Сербии",
    "montenegro": "Черногории",
    "north-macedonia": "Северной Македонии",
    "albania": "Албании",
    "bosnia": "Боснии и Герцеговине",
    "kosovo": "Косово",
    "ukraine": "Украине",
    "moldova": "Молдове",
    "georgia": "Грузии",
    "armenia": "Армении",
    "azerbaijan": "Азербайджане",
    "united-states": "США",
    "canada": "Канаде",
    "japan": "Японии",
    "south-korea": "Южной Корее",
    "china": "Китае",
    "india": "Индии",
    "brazil": "Бразилии",
    "mexico": "Мексике",
    "australia": "Австралии",
    "new-zealand": "Новой Зеландии",
    "south-africa": "ЮАР",
    "israel": "Израиле",
}

_MONTH_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

# После «по» — винительный: «с января 1991 по май 2026», не «по мая 2026».
_MONTH_NOMINATIVE = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)

_FREQ_TAIL_MARKERS = (
    ", помесячно",
    ", поквартально",
    ", за год",
    ", понедельно",
    ", по дням",
)

# Трафаретные обороты в публичных описаниях (не путать с «по стране рождения»).
TEMPLATE_STUB_RE = re.compile(
    r"(?:Евростата\s+по\s+стране\b|"
    r"ряд(?:а)?\s+Евростата\s+по\s+стране\b|"
    r"официальный\s+статистический\s+ряд\s+Евростата\s+по\s+стране\b|"
    r"\bпо\s+стране\.(?:\s|$)|"
    r"\bв\s+стране\s+[А-ЯЁA-Z]|"
    r"динамику\s+выбранной\s+величины|"
    r"позволяет\s+сравнивать\s+страны\s+по\s+единой\s+европейской\s+методологии)",
    re.I,
)


def country_prepositional(slug: str | None, name_ru: str | None = None) -> str:
    """«в {prep}» — предложный падеж; фолбэк на именительный из БД."""
    if slug and slug in COUNTRY_PREPOSITIONAL:
        return COUNTRY_PREPOSITIONAL[slug]
    return (name_ru or slug or "").strip()


def _format_history_date(d, case: str = "gen") -> str:
    """date → «января 2020» (gen, после «с») или «январь 2020» (nom, после «по»)."""
    if d is None:
        return ""
    try:
        y, m = int(d.year), int(d.month)
    except AttributeError:
        return str(d)
    if 1 <= m <= 12:
        months = _MONTH_NOMINATIVE if case == "nom" else _MONTH_GENITIVE
        return f"{months[m - 1]} {y}"
    return str(y)


def _normalize_freq_list(frequency: str | None, available: list[str] | tuple[str, ...] | None) -> list[str]:
    raw = list(available) if available else ([frequency] if frequency else [])
    out: list[str] = []
    for f in raw:
        nf = (f or "").strip().lower()
        if nf == "yearly":
            nf = "annual"
        if nf and nf not in out:
            out.append(nf)
    return out


def public_seo_title(
    name_ru: str,
    *,
    country_prep: str,
    country_name_ru: str = "",
) -> str:
    """Заголовок страницы: «Показатель в Германии — график и данные»."""
    subject, _ = split_freq_suffix(name_ru)
    prep = (country_prep or country_name_ru or "").strip()
    if not subject:
        subject = "Экономический показатель"
    if prep:
        title = f"{subject} в {prep} — график и данные"
        if len(title) > 300:
            title = f"{subject} в {prep}"
    else:
        title = f"{subject} — график и данные"
    if len(title) > 300:
        title = title[:297].rstrip(" —,") + "…"
    return title


def public_description(
    name_ru: str,
    frequency: str | None = None,
    unit_ru: str = "",
    *,
    country_name_ru: str = "",
    country_prep: str | None = None,
    history_start=None,
    history_end=None,
    available_frequencies: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Живое описание карточки: показатель × страна × период × источник."""
    subject, _ = split_freq_suffix(name_ru)
    prep = (country_prep or "").strip() or country_name_ru.strip()
    where = f" в {prep}" if prep else ""

    start_s = _format_history_date(history_start, case="gen")
    end_s = _format_history_date(history_end, case="nom")

    # Зачин не копирует seo_title («… — график и данные»).
    if start_s and end_s and start_s != end_s:
        parts: list[str] = [
            f"{subject}{where}: динамика с {start_s} по {end_s}."
        ]
    elif start_s and end_s:
        parts = [f"{subject}{where}: данные за {start_s}."]
    else:
        parts = [f"{subject}{where}: данные Евростата."]

    unit = (unit_ru or "").strip()
    if unit and unit.lower() not in subject.lower():
        parts.append(f"Единица измерения — {unit}.")

    freqs = _normalize_freq_list(frequency, available_frequencies)
    freq_view = {
        "monthly": "по месяцам",
        "quarterly": "по кварталам",
        "annual": "по годам",
        "weekly": "по неделям",
        "daily": "по дням",
    }
    freq_pub = {
        "monthly": "ежемесячно",
        "quarterly": "ежеквартально",
        "annual": "ежегодно",
        "weekly": "еженедельно",
        "daily": "ежедневно",
    }
    if len(freqs) >= 2:
        labels = [freq_view[f] for f in freqs if f in freq_view]
        if labels:
            if len(labels) == 2:
                parts.append(f"На карточке — представления {labels[0]} и {labels[1]}.")
            else:
                parts.append(
                    "На карточке — представления "
                    + ", ".join(labels[:-1])
                    + f" и {labels[-1]}."
                )
    elif len(freqs) == 1 and freqs[0] in freq_pub:
        parts.append(f"Публикация — {freq_pub[freqs[0]]}.")

    parts.append("Источник — Евростат.")
    return " ".join(parts)


def public_methodology(
    frequency: str | None = None,
    unit_ru: str = "",
    *,
    available_frequencies: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Методология карточки: источник, единица, честная оговорка о частоте."""
    freqs = _normalize_freq_list(frequency, available_frequencies)
    freq_adj = {
        "monthly": "месячная",
        "quarterly": "квартальная",
        "annual": "годовая",
        "weekly": "недельная",
        "daily": "дневная",
    }
    freq_noun = {
        "monthly": "месяц",
        "quarterly": "квартал",
        "annual": "год",
        "weekly": "неделя",
        "daily": "день",
    }
    if len(freqs) >= 2:
        nouns = [freq_noun[f] for f in freqs if f in freq_noun]
        if len(nouns) == 2:
            freq_part = (
                f"На карточке доступны периодичности «{nouns[0]}» и «{nouns[1]}» — "
                f"нужную выбирают переключателем."
            )
        else:
            joined = ", ".join(f"«{n}»" for n in nouns[:-1]) + f" и «{nouns[-1]}»"
            freq_part = (
                f"На карточке доступны периодичности {joined} — "
                f"нужную выбирают переключателем."
            )
    else:
        fr = freq_adj.get(freqs[0], "регулярная") if freqs else "регулярная"
        freq_part = f"Частота публикации — {fr}."

    unit_bit = (
        f" Единица измерения на графике — {unit_ru}."
        if unit_ru
        else ""
    )
    return (
        f"Источник данных — Евростат. Ряд формируется по гармонизированной "
        f"методологии для стран Европы. {freq_part}{unit_bit} "
        f"На графике показан наиболее общий доступный срез показателя."
    )


def has_frequency_suffix(text: str | None) -> bool:
    """True, если в тексте есть хвостовой частотный суффикс названия."""
    if not text:
        return False
    _, suf = split_freq_suffix(text)
    if suf:
        return True
    # суффикс в середине (seo_title: «…, помесячно — Германия»)
    low = text.lower()
    return any(m in low for m in _FREQ_TAIL_MARKERS)


def has_template_stub(text: str | None) -> bool:
    """True при трафаретных оборотах вроде «по стране» / «выбранной величины»."""
    if not text:
        return False
    # «по стране рождения/гражданства» — содержательные уточнения, не заглушка
    cleaned = re.sub(
        r"по\s+стране\s+(?:рождения|гражданства)\b",
        " ",
        text,
        flags=re.I,
    )
    return bool(TEMPLATE_STUB_RE.search(cleaned))


def collect_uncovered_from_titles(pairs: list[tuple[str, str]]) -> dict[str, int]:
    """Для аудита: частота непокрытых английских токенов."""
    counts: dict[str, int] = {}
    for ds, title in pairs:
        res = compose_title(title, ds)
        for tok in res.uncovered_tokens:
            if tok.startswith("<") or tok in ("by-template-miss", "no-template", "empty-title"):
                continue
            counts[tok] = counts.get(tok, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
