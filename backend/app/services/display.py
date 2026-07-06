"""Display-adapter: storage-значение → пользовательское представление.

Единая точка истины для серверных поверхностей (SSR, OG-картинки, RSS,
embed-виджеты). Закрывает класс инцидентов «Инфляция — 100,2%»: CPI-семейство
хранит месячный/недельный ИНДЕКС (~100.xx), а людям показывается изменение
цен в процентах (индекс − 100) — ровно так же, как React-слой
(`frontend/src/lib/format.js::adjustCpiDisplay`). Плюс русское форматирование
чисел (запятая в дроби, пробел в тысячах) и дат («1 мая 2026») — вместо
ISO-дат и английской точки в русской выдаче.

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


def period_label(code: str | None, frequency: str | None) -> str:
    """Суффикс «за месяц»/«за неделю» для CPI-изменений; пусто для уровней."""
    if not is_cpi_index(code):
        return ""
    return _PERIOD_LABEL.get((frequency or "").lower(), "")


def format_number_ru(value, *, signed: bool = False) -> str:
    """Русская типографика: пробел в тысячах, запятая в дроби.

    Количество знаков — как у прежнего SSR-формата (до 4, без хвостовых нулей),
    чтобы не менять точность, только разделители.
    """
    if value is None:
        return "нет данных"
    number = float(value)
    if abs(number) >= 1000:
        text = f"{number:,.2f}".replace(",", "\u202f").replace(".", ",")
    else:
        text = f"{number:.4f}".rstrip("0").rstrip(".").replace(".", ",")
    if signed and number > 0:
        text = f"+{text}"
    return text


def display_value_text(code: str | None, value, unit: str | None,
                       frequency: str | None = None) -> str:
    """Готовая строка значения: «+0,17 % за месяц» / «17 624,3 млрд руб.»."""
    shown = display_value(code, value)
    if shown is None:
        return "нет данных"
    number = format_number_ru(shown, signed=display_sign(code))
    unit_part = f" {unit.strip()}" if unit and unit.strip() else ""
    label = period_label(code, frequency)
    label_part = f" {label}" if label else ""
    return f"{number}{unit_part}{label_part}"


def format_date_ru(value: date | None) -> str:
    """«1 мая 2026» — вместо ISO `2026-05-01` в русской выдаче."""
    if value is None:
        return "нет данных"
    return f"{value.day} {_RU_MONTHS_GEN[value.month - 1]} {value.year}"


def format_month_ru(value: date | None) -> str:
    """«май 2026» — компактная подпись периода (embed, OG)."""
    if value is None:
        return ""
    return f"{_RU_MONTHS_NOM[value.month - 1]} {value.year}"


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
