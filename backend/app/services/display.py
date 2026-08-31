"""Display-adapter: storage-значение → пользовательское представление.

Единая точка истины для серверных поверхностей (SSR, OG-картинки, RSS,
embed-виджеты). Закрывает класс инцидентов «Инфляция — 100,2%»: CPI-семейство
хранит месячный/недельный ИНДЕКС (~100.xx), а людям показывается изменение
цен в процентах (индекс − 100) — ровно так же, как React-слой
(`frontend/src/lib/format.js::adjustCpiDisplay`). Плюс locale-типографика
чисел (RU: запятая/узкий пробел; EN: point/comma thousands) и дат
(«1 мая 2026» / «1 May 2026»).

Зеркалить изменения: список CPI-кодов обязан совпадать с
`CPI_INDEX_CODES` в `frontend/src/lib/format.js` (тест
`test_display_adapter.py` держит их в синхроне через фикстуру-копию).
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

_MSK = ZoneInfo("Europe/Moscow")


def today_msk() -> date:
    """«Сегодня» для публичных поверхностей — по Москве, не по TZ контейнера.

    Контейнеры живут в UTC: около полуночи `date.today()` отстаёт от Москвы
    на 3 часа, и страницы «X сегодня» / календарь показывают вчерашнюю дату
    (В-5, CTO-аудит 2026-07-06).
    """
    return datetime.now(_MSK).date()

# Коды, хранящие индекс ~100.xx, который показывается людям как изменение в %.
# Синхронно с frontend/src/lib/format.js::CPI_INDEX_CODES.
CPI_INDEX_CODES = frozenset({
    "cpi",
    "cpi-food",
    "cpi-nonfood",
    "cpi-services",
    "inflation-quarterly",
    "cpi-food-quarterly",
    "cpi-nonfood-quarterly",
    "cpi-services-quarterly",
    "inflation-weekly",
    "inflation-weekly-food",
    "inflation-weekly-nonfood",
    "inflation-weekly-services",
})

# Подпись периода изменения для CPI-кодов: «+0,17 % за месяц».
_PERIOD_LABEL = {
    "weekly": "за неделю",
    "monthly": "за месяц",
    "quarterly": "за квартал",
    "annual": "за год",
}
_PERIOD_LABEL_EN = {
    "weekly": "over the week",
    "monthly": "over the month",
    "quarterly": "over the quarter",
    "annual": "over the year",
}

# Locale-facing money units (storage stays Russian abbreviations).
_UNIT_EN = {
    "руб.": "RUB",
    "руб": "RUB",
    "млн руб.": "mln RUB",
    "млн руб": "mln RUB",
    "млрд руб.": "bln RUB",
    "млрд руб": "bln RUB",
    "трлн руб.": "trln RUB",
    "трлн руб": "trln RUB",
    "руб./л": "RUB/l",
    "руб./г": "RUB/g",
    "тыс. руб.": "ths RUB",
    "тыс. руб": "ths RUB",
    "км²": "km²",
    "км2": "km²",
    "человек": "people",
    "чел. на км²": "people per km²",
    "п.п.": "pp",
    "п.п": "pp",
    "п. п.": "pp",
    "пункт": "point",
    "пункты": "points",
    "пунктов": "points",
    "изменение за месяц, п.п.": "monthly change, pp",
    "изменение за месяц": "monthly change",
    "изменение за квартал, п.п.": "quarterly change, pp",
    "изменение за год, п.п.": "annual change, pp",
    "% ВВП": "% of GDP",
    "млн евро": "million EUR",
    "в текущих ценах, млн евро": "million EUR, current prices",
    "в постоянных ценах 2015 года, млн евро": "million EUR, 2015 constant prices",
    "в постоянных ценах 2010 года, млн евро": "million EUR, 2010 constant prices",
    "ППС на душу населения": "PPS per capita",
    "тысяча рублей": "thousand RUB",
    "тысяч рублей": "thousand RUB",
    "тысяч тонн": "thousand tonnes",
    "рублей за литр": "RUB per litre",
    # Eurostat units (unit_ru storage → EN display).
    "тыс. тонн": "thousand tonnes",
    "тыс. т н. э.": "thousand tonnes of oil equivalent",
    "кг н. э.": "kg of oil equivalent",
    "евро за кг н. э.": "EUR per kg of oil equivalent",
    "евро": "EUR",
    "тыс. евро": "thousand EUR",
    "млн евро, с сезонной корректировкой": "million EUR, seasonally adjusted",
    "млн евро, в постоянных ценах": "million EUR, constant prices",
    "в постоянных ценах 2020 года, евро на душу населения": (
        "EUR per capita, 2020 constant prices"
    ),
    "на душу населения, евро": "EUR per capita",
    "% экономически активного населения": "% of the labour force",
    "% населения": "% of population",
    "% населения ЕС": "% of EU population",
    "% занятости": "% of employment",
    "% от итога": "% of total",
    "% к ожидаемому уровню": "% of expected level",
    "изменение к предыдущему периоду": "change vs previous period",
    "изменение к тому же периоду прошлого года": "change vs same period previous year",
    "темп изменения к предыдущему периоду": "rate of change vs previous period",
    "темп изменения, с сезонной корректировкой": "rate of change, seasonally adjusted",
    "изменение, %": "change, %",
    "изменение за год": "annual change",
    "изменение за год, %": "annual change, %",
    "среднее изменение за 12 месяцев": "average change over 12 months",
    "сальдо": "balance",
    "ГВт·ч": "GWh",
    "МВт": "MW",
    "ТДж": "TJ",
    "млн м³": "million m³",
    "тыс. м²": "thousand m²",
    "км": "km",
    "тыс. баррелей": "thousand barrels",
    "лет": "years",
    "часов в неделю": "hours per week",
    "штук": "units",
    "тыс. единиц": "thousand units",
    "автомобилей": "vehicles",
    "койко-мест": "bed places",
    "сделок": "transactions",
    "дней запаса": "days of supply",
    "градусо-сутки": "degree days",
    "балл индекса": "index points",
    "пунктов индекса Джини": "Gini index points",
    "раз": "ratio",
    "индекс": "index",
    "индекс, среднегодовой": "index, annual average",
    "вероятность / лет": "probability / years",
    "детей на женщину": "children per woman",
    "на 1000 женщин соответствующего возраста": "per 1,000 women of the relevant age",
    "на 1000 человек населения": "per 1,000 population",
    "на 1000 человек соответствующего возраста": "per 1,000 people of the relevant age",
    "на 1000 живорождённых": "per 1,000 live births",
    "на 1000 жителей": "per 1,000 inhabitants",
    "на одного жителя": "per inhabitant",
    "на одну женщину": "per woman",
    "на одного мужчину": "per man",
    "‰ от суммарных весов стран ЕС": "‰ of total EU country weights",
    "‰ от суммарных весов категорий": "‰ of total category weights",
    # Index bases (full unit, shown in the unit field / table header).
    "индекс (2015 = 100)": "index (2015 = 100)",
    "индекс (2015 = 100), с сезонной корректировкой": "index (2015 = 100), seasonally adjusted",
    "индекс (2015 = 100), среднегодовой": "index (2015 = 100), annual average",
    "индекс (2021 = 100)": "index (2021 = 100)",
    "индекс (2020 = 100)": "index (2020 = 100)",
    "индекс (2025 = 100)": "index (2025 = 100)",
    "индекс (2005 = 100)": "index (2005 = 100)",
    "индекс (2017 = 100)": "index (2017 = 100)",
    "индекс (1982–84 = 100)": "index (1982–84 = 100)",
    "индекс (2011–12 = 100)": "index (2011–12 = 100)",
    "индекс (2012 = 100)": "index (2012 = 100)",
    "индекс (2002 = 100)": "index (2002 = 100)",
    "индекс (2-я половина июля 2018 = 100)": "index (second half of July 2018 = 100)",
    "индекс (среднее 1995 = 100)": "index (1995 average = 100)",
    "индекс (тот же месяц прошлого года = 100)": "index (same month previous year = 100)",
    # National-core units (US/CA/UK/AU/JP/CN/KR/IN/BR/MX passports).
    "тыс. человек": "thousand people",
    "тысяч человек": "thousand people",
    "млн долларов США": "million USD",
    "млрд долларов США (цены 2017)": "billion USD (2017 prices)",
    "тыс. долларов США": "thousand USD",
    "млрд $": "billion $",
    "$ на человека": "$ per person",
    "иены": "JPY",
    "млрд иен": "billion JPY",
    "иен за 1 доллар США": "JPY per USD",
    "юаней за 1 доллар США": "CNY per USD",
    "100 млн юаней": "100 million CNY",
    "тыс. канадских долларов": "thousand CAD",
    "млн канадских долларов": "million CAD",
    "млн канадских долларов (цены 2017)": "million CAD (2017 prices)",
    "канадских долларов за 1 доллар США": "CAD per USD",
    "млн австралийских долларов": "million AUD",
    "млн австралийских долларов (цепные объёмы)": "million AUD (chain-linked volumes)",
    "долларов США за 1 австралийский доллар": "USD per AUD",
    "млн фунтов стерлингов": "million GBP",
    "млн фунтов стерлингов (цепные объёмы)": "million GBP (chain-linked volumes)",
    "долларов США за 1 фунт стерлингов": "USD per GBP",
    "долларов США за 1 евро": "USD per EUR",
    "вон за 1 доллар США": "KRW per USD",
    "млрд вон": "billion KRW",
    "млрд вон (цены 2020)": "billion KRW (2020 prices)",
    "мексиканских песо за 1 доллар США": "MXN per USD",
    "млн мексиканских песо (постоянные цены 2018)": "million MXN (2018 constant prices)",
    "бразильских реалов за 1 доллар США": "BRL per USD",
    "крор рупий": "crore INR",
    "рупий за 1 доллар США": "INR per USD",
}

_RU_MONTHS_GEN = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
_RU_MONTHS_NOM = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)


def is_cpi_index(code: str | None) -> bool:
    return code in CPI_INDEX_CODES


def display_value(code: str | None, value) -> float | None:
    """Storage-значение → показываемое людям (CPI-индекс → изменение в %)."""
    if value is None:
        return None
    number = float(value)
    if is_cpi_index(code):
        return round(number - 100.0, 2)
    return number


def display_sign(code: str | None) -> bool:
    """Нужен ли явный знак «+» (для рядов-изменений, каким становится CPI)."""
    return is_cpi_index(code)


def period_label(
    code: str | None,
    frequency: str | None,
    *,
    locale: str | None = None,
) -> str:
    """Суффикс «за месяц»/«за неделю» для CPI-изменений; пусто для уровней."""
    if not is_cpi_index(code):
        return ""
    loc = locale
    if loc is None:
        from app.services.locale import get_locale

        loc = get_locale()
    table = _PERIOD_LABEL_EN if loc == "en" else _PERIOD_LABEL
    return table.get((frequency or "").lower(), "")


def localize_unit(unit: str | None, *, locale: str | None = None) -> str:
    """``руб.`` / ``млрд руб.`` → ``RUB`` / ``bln RUB`` on EN; RU unchanged.

    Составные Eurostat-единицы («в постоянных ценах 2015 года, млн евро»)
    разбираются по сегментам: точное совпадение — потом перевод сегментов
    через «, ». Ничего не нашли и в тексте есть кириллица — фолбэк пустой
    строкой невозможен (вызывающая сторона вернёт RU), поэтому возвращаем
    исходник только если он уже латиницей; иначе отдаём как есть — EN
    проверяется аудит-скриптом на поверхностях, где фолбэк недопустим.
    """
    if not unit:
        return ""
    text = unit.strip()
    if not text:
        return ""
    loc = locale
    if loc is None:
        from app.services.locale import get_locale

        loc = get_locale()
    if loc != "en":
        return text
    exact = _UNIT_EN.get(text) or _UNIT_EN.get(text.rstrip("."))
    if exact:
        return exact
    segments = [s.strip() for s in text.split(",")]
    if len(segments) > 1:
        translated = [localize_unit(s, locale="en") for s in segments]
        return ", ".join(translated)
    return text


def format_number_ru(
    value,
    *,
    signed: bool = False,
    locale: str | None = None,
) -> str:
    """Locale typography for public numbers (SSR / API / OG).

    RU: narrow no-break space in thousands, comma decimal (``17 624,3``).
    EN: comma thousands, period decimal (``17,624.3``) — economist English.
    Precision matches the former SSR format (up to 4 places, no trailing zeros).
    Empty → ``нет данных`` / ``no data`` by locale.
    """
    loc = locale
    if loc is None:
        from app.services.locale import get_locale

        loc = get_locale()
    if value is None:
        return "no data" if loc == "en" else "нет данных"
    number = float(value)
    negative = number < 0
    magnitude = abs(number)
    if magnitude >= 1000:
        # Счётные величины (население, число организаций) целые по природе:
        # «85 664 944,00 человек» выглядит как ошибка округления.
        digits = 0 if magnitude.is_integer() else 2
        text = f"{magnitude:,.{digits}f}"
        if digits:
            # «1 222,40 тыс. чел.» — хвостовой ноль читается как ложная точность.
            text = text.rstrip("0").rstrip(".")
        if loc != "en":
            text = text.replace(",", "\u202f").replace(".", ",")
    else:
        text = f"{magnitude:.4f}".rstrip("0").rstrip(".")
        if loc != "en":
            text = text.replace(".", ",")
    if signed and not negative:
        text = f"+{text}"
    # Типографский минус (−), не дефис: публичные числа читаются как в печати.
    if negative:
        text = f"\u2212{text}"
    return text


def display_value_text(
    code: str | None,
    value,
    unit: str | None,
    frequency: str | None = None,
    *,
    locale: str | None = None,
) -> str:
    """Готовая строка значения: «+0,17 % за месяц» / «17,624.3 bln RUB» on EN."""
    loc = locale
    if loc is None:
        from app.services.locale import get_locale

        loc = get_locale()
    shown = display_value(code, value)
    if shown is None:
        return "no data" if loc == "en" else "нет данных"
    number = format_number_ru(shown, signed=display_sign(code), locale=loc)
    unit_text = localize_unit(unit, locale=loc) if unit else ""
    unit_part = f" {unit_text}" if unit_text else ""
    label = period_label(code, frequency, locale=loc)
    label_part = f" {label}" if label else ""
    return f"{number}{unit_part}{label_part}"


def format_date_ru(value: date | None) -> str:
    """«1 мая 2026» — вместо ISO `2026-05-01` в русской выдаче."""
    if value is None:
        return "нет данных"
    return f"{value.day} {_RU_MONTHS_GEN[value.month - 1]} {value.year}"


_EN_MONTHS_NOM = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def value_period_phrase(
    value: date | None,
    frequency: str | None,
    *,
    locale: str | None = None,
) -> str:
    """Подпись периода с предлогом: «за июль 2026», «на 11 августа 2026».

    Месячное и годовое значение относится к периоду целиком: «на 1 июля 2026»
    у месячного ряда читается как замер конкретного дня, а «на 1 января 2024»
    у годового — как данные на начало года вместо итога за год.
    """
    loc = locale
    if loc is None:
        from app.services.locale import get_locale

        loc = get_locale()
    if value is None:
        return "no data" if loc == "en" else "нет данных"
    freq = (frequency or "").lower()
    if loc == "en":
        if freq.startswith("annual") or freq.startswith("year"):
            return f"for {value.year}"
        if freq.startswith("quarter"):
            q = (value.month - 1) // 3 + 1
            return f"in Q{q} {value.year}"
        if freq.startswith("month"):
            return f"for {_EN_MONTHS_NOM[value.month]} {value.year}"
        return f"as of {format_date_locale(value, locale='en')}"
    if freq.startswith("annual") or freq.startswith("year"):
        return f"за {value.year} год"
    if freq.startswith("quarter"):
        return f"за {(value.month - 1) // 3 + 1} квартал {value.year}"
    if freq.startswith("month"):
        return f"за {_RU_MONTHS_NOM[value.month - 1]} {value.year}"
    return f"на {format_date_ru(value)}"


def format_month_ru(value: date | None) -> str:
    """«май 2026» — компактная подпись периода (embed, OG)."""
    if value is None:
        return ""
    return f"{_RU_MONTHS_NOM[value.month - 1]} {value.year}"


def format_month_year(value: date | None, locale: str | None = None) -> str:
    """Compact period label: «май 2026» / «May 2026» by locale."""
    if value is None:
        return ""
    loc = locale
    if loc is None:
        from app.services.locale import get_locale

        loc = get_locale()
    if loc == "en":
        return f"{_EN_MONTHS_NOM[value.month]} {value.year}"
    return format_month_ru(value)


def format_date_locale(value: date | None, locale: str | None = None) -> str:
    """Full date: «1 мая 2026» / «1 May 2026» by locale."""
    if value is None:
        loc = locale
        if loc is None:
            from app.services.locale import get_locale

            loc = get_locale()
        return "no data" if loc == "en" else "нет данных"
    loc = locale
    if loc is None:
        from app.services.locale import get_locale

        loc = get_locale()
    if loc == "en":
        return f"{value.day} {_EN_MONTHS_NOM[value.month]} {value.year}"
    return format_date_ru(value)


# --- Годовой итог (landing /indicator/{code}/{year}, годовой OG) -------------
#
# «Среднее за год» осмысленно не для всех рядов: для потоков (экспорт, ВВП,
# бюджет) годовой итог — СУММА, для запасов (резервы, долг) — значение на
# конец года, для CPI-индексов — цепной рост цен за год. Природа ряда берётся
# из шаблона generic-семьи (T1…T12); CPI — по своему списку кодов.

_TEMPLATE_ANNUAL_KIND = {
    "T3": "last", "T4": "last", "T5": "last",           # запасы/уровни на дату
    "T6": "sum", "T7": "sum", "T9": "sum", "T9s": "sum",  # потоки
}


def annual_summary_kind(code: str | None) -> str:
    """sum | last | avg | chain — как сворачивать год для показа людям."""
    if is_cpi_index(code):
        return "chain"
    try:
        from app.data.view_model_families import FAMILY_BY_BASE
        fam = FAMILY_BY_BASE.get(code or "")
    except Exception:
        fam = None
    if fam is not None:
        return _TEMPLATE_ANNUAL_KIND.get(fam.template, "avg")
    return "avg"


def annual_summary(code: str | None, values: list[float], unit: str | None) -> tuple[str, str]:
    """(подпись, значение) годового итога: «Итог за год», «1 234,5 млрд руб.»."""
    kind = annual_summary_kind(code)
    if not values:
        return "Итог за год", "нет данных"
    unit_part = f" {unit.strip()}" if unit and unit.strip() else ""
    if kind == "chain":
        # Цепной рост цен: произведение месячных/недельных индексов.
        growth = 1.0
        for v in values:
            growth *= float(v) / 100.0
        pct = round((growth - 1.0) * 100.0, 2)
        return "Рост цен за год", f"{format_number_ru(pct, signed=True)} %"
    if kind == "sum":
        return "Итог за год (сумма)", f"{format_number_ru(round(sum(values), 2))}{unit_part}"
    if kind == "last":
        return "Значение на конец года", f"{format_number_ru(values[-1])}{unit_part}"
    return "Среднее за год", f"{format_number_ru(round(sum(values) / len(values), 2))}{unit_part}"
