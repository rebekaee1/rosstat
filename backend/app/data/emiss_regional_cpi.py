"""Цены потребителей по регионам помесячно: ЕМИСС 31074, 31052, 31481 (19.11.2026).

До 19.11.2026 индекс потребительских цен региона на сайте был годовым и заканчивался 2024 годом
(сборник «Регионы России», раздел 20). При этом это самый просматриваемый региональный показатель,
а в Яндексе ищут «ИПЦ по липецкой области в июле 2026». Росстат публикует его помесячно в ЕМИСС:

- 31074 «Индексы потребительских цен на товары и услуги» — 119 территорий, с 2002 года, 1105 групп и
  товаров, 9 видов индекса. Берём ходовое: все товары и услуги, базовый индекс (он есть в этом же наборе,
  поэтому отдельный набор 33568 не нужен), продовольственные и непродовольственные товары, услуги — по
  трём видам (к прошлому месяцу, к декабрю, к тому же месяцу год назад) и 20 групп только «за год»;
- 31052 «Стоимость фиксированного набора потребительских товаров и услуг», рубли, с 2002 года;
- 31481 «Стоимость условного (минимального) набора продуктов питания», рубли, с 2001 года.

Набор 40532 («изменение стоимости фиксированного набора», %) не берём: это та же величина, что 31052,
в процентах — страница показателя сама считает изменения от рублёвого ряда.

Слой помесячный (``region_monthly_data``), раздел 20 «Цены и тарифы». Коды ``ipc-…`` и ``nabor-…``;
table_code ``20.c{N}`` — отдельный от цен товаров ``20.m{N}`` (их порядок и подача цены там свои).
Значения ИПЦ — индекс в процентах, как у Росстата (106,35 значит «цены выросли на 6,35 %»).
"""

from __future__ import annotations

from dataclasses import dataclass

CPI_DATASET = 31074
FIXED_SET_DATASET = 31052
FOOD_SET_DATASET = 31481

# 57937 «Виды показателя» набора 31074.
KIND_MONTH = "1704142"      # к предыдущему месяцу
KIND_DECEMBER = "1707674"   # к декабрю предыдущего года
KIND_YEAR = "1704140"       # к соответствующему периоду предыдущего года

KIND_SUFFIX = {KIND_MONTH: "k-mesyacu", KIND_DECEMBER: "k-dekabryu", KIND_YEAR: "za-god"}
KIND_UNIT = {
    KIND_MONTH: "% к предыдущему месяцу",
    KIND_DECEMBER: "% к декабрю предыдущего года",
    KIND_YEAR: "% к тому же месяцу прошлого года",
}
KIND_UNIT_EN = {
    KIND_MONTH: "% of previous month",
    KIND_DECEMBER: "% of December of previous year",
    KIND_YEAR: "% of same month a year earlier",
}
KIND_NAME = {
    KIND_MONTH: "за месяц",
    KIND_DECEMBER: "с начала года",
    KIND_YEAR: "за год",
}
KIND_NAME_EN = {KIND_MONTH: "month on month", KIND_DECEMBER: "year to date", KIND_YEAR: "year on year"}

PERCENT = "950473"
RUBLE = "950351"
FIRST_YEAR = 2002           # 31074 и 31052 начинаются с 2002 года
FOOD_SET_FIRST_YEAR = 2001  # 31481 — с 2001 года


@dataclass(frozen=True)
class CpiGroup:
    oid: str          # значение измерения 58273 «Виды товаров и услуг»
    slug: str         # часть кода ряда
    label: str        # как называет Росстат (так приходит в ответе)
    name: str         # по-человечески
    name_en: str


# Главные индексы: три вида каждый.
HEADLINE: tuple[CpiGroup, ...] = (
    CpiGroup("1707675", "vse", "Все товары и услуги", "все товары и услуги", "all goods and services"),
    CpiGroup("1788790", "bazovyy", "Базовый индекс потребительских цен",
             "базовый (без сезонных и регулируемых цен)", "core (excluding seasonal and regulated prices)"),
    CpiGroup("1748984", "prodovolstvennye", "Продовольственные товары", "продукты", "food"),
    CpiGroup("1744144", "neprodovolstvennye", "Непродовольственные товары", "непродовольственные товары",
             "non-food goods"),
    CpiGroup("1744147", "uslugi", "Услуги", "услуги", "services"),
)

# Группы, которые ищут и смотрят: только «за год» (так понятнее и меньше строк в базе).
GROUPS: tuple[CpiGroup, ...] = (
    CpiGroup("1788777", "myaso", "Мясо и птица", "мясо и птица", "meat and poultry"),
    CpiGroup("1750671", "moloko", "Молоко и молочная продукция", "молоко и молочные продукты", "milk and dairy"),
    CpiGroup("1788866", "hleb", "Хлеб и хлебобулочные изделия", "хлеб и выпечка", "bread and bakery"),
    CpiGroup("1788767", "yaytsa", "Яйца", "яйца", "eggs"),
    CpiGroup("1750667", "sahar", "Сахар", "сахар", "sugar"),
    CpiGroup("1788850", "ovoshchi-frukty", "Плодоовощная продукция, включая картофель",
             "овощи, фрукты и картофель", "fruit, vegetables and potatoes"),
    CpiGroup("1788771", "alkogol", "Алкогольные напитки", "алкогольные напитки", "alcoholic drinks"),
    CpiGroup("1788733", "tabak", "Табачные изделия", "табачные изделия", "tobacco"),
    CpiGroup("1788812", "odezhda", "Одежда", "одежда", "clothing"),
    CpiGroup("1788823", "medikamenty", "Медикаменты", "лекарства", "medicines"),
    CpiGroup("1755210", "benzin", "Бензин автомобильный", "бензин", "petrol"),
    CpiGroup("1788753", "stroymaterialy", "Строительные материалы", "строительные материалы",
             "building materials"),
    # «Жилищно-коммунальные услуги» (1788749) и «Услуги связи» (1788722) Росстат перестал публиковать (в 2024 и
    # 2026 пусто, живой запрос 19.11.2026): берём «Коммунальные услуги» (непрерывно с 2002) и «Услуги
    # телекоммуникационные» (новая группа, ряд короче). Старую и новую группу связи не сшиваем — состав разный.
    CpiGroup("1788723", "kommunalnye", "Коммунальные услуги", "коммунальные услуги (вода, тепло, свет, газ)",
             "utilities"),
    CpiGroup("1788843", "transport", "Услуги пассажирского транспорта", "проезд (пассажирский транспорт)",
             "passenger transport"),
    CpiGroup("1848536", "svyaz", "Услуги телекоммуникационные", "связь и интернет", "telecom and internet"),
    CpiGroup("1788721", "medicina", "Медицинские услуги", "медицинские услуги", "medical services"),
    CpiGroup("1788810", "obrazovanie", "Услуги образования", "образование", "education"),
    CpiGroup("1788775", "detskiy-sad", "Услуги дошкольного воспитания", "детский сад", "kindergarten"),
    CpiGroup("1788880", "turizm-zarubezhnyy", "Услуги в сфере зарубежного туризма", "поездки за границу",
             "travel abroad"),
    CpiGroup("1788818", "bytovye-uslugi", "Бытовые услуги", "бытовые услуги", "personal services"),
)


@dataclass(frozen=True)
class RegionalSeries:
    code: str
    dataset: int
    item: str | None   # oid 58273 (только 31074)
    kind: str | None   # oid 57937 (только 31074)
    name: str
    unit: str
    name_en: str
    unit_en: str
    note: str
    note_en: str


def cpi_code(group: CpiGroup, kind: str) -> str:
    return f"ipc-{group.slug}-{KIND_SUFFIX[kind]}"


_CPI_NOTE = ("Индекс потребительских цен по субъекту, помесячно. 106 % значит, что цены выросли на 6 %, "
             "99,8 % — снизились на 0,2 %.")
_CPI_NOTE_EN = "consumer price index by region, monthly; 106% means prices rose by 6%"


def _cpi(group: CpiGroup, kind: str) -> RegionalSeries:
    return RegionalSeries(
        code=cpi_code(group, kind), dataset=CPI_DATASET, item=group.oid, kind=kind,
        name=f"Индекс потребительских цен {KIND_NAME[kind]}: {group.name}",
        unit=KIND_UNIT[kind],
        name_en=f"Consumer price index, {KIND_NAME_EN[kind]}: {group.name_en}",
        unit_en=KIND_UNIT_EN[kind], note=_CPI_NOTE, note_en=_CPI_NOTE_EN,
    )


SERIES: tuple[RegionalSeries, ...] = (
    *(_cpi(g, k) for g in HEADLINE for k in (KIND_YEAR, KIND_MONTH, KIND_DECEMBER)),
    *(_cpi(g, KIND_YEAR) for g in GROUPS),
    RegionalSeries(
        code="nabor-fiksirovannyy", dataset=FIXED_SET_DATASET, item=None, kind=None,
        name="Стоимость фиксированного набора товаров и услуг на человека в месяц",
        unit="рублей",
        name_en="Cost of the fixed basket of goods and services",
        unit_en="roubles",
        note=("Сколько стоит в регионе один и тот же набор из 83 товаров и услуг (продукты, одежда, ЖКХ, "
              "проезд, лечение) на конец месяца. Набор одинаковый для всех регионов, поэтому по нему "
              "сравнивают стоимость жизни."),
        note_en=("cost of the same basket of 83 goods and services at the end of the month; the basket is "
                 "the same everywhere, so it compares the cost of living between regions"),
    ),
    RegionalSeries(
        code="nabor-minimalnyy-produktov", dataset=FOOD_SET_DATASET, item=None, kind=None,
        name="Стоимость минимального набора продуктов питания на человека в месяц",
        unit="рублей",
        name_en="Cost of the minimum food basket",
        unit_en="roubles",
        note=("Сколько стоит в регионе минимальный набор продуктов на одного человека в месяц (33 продукта: хлеб, "
              "крупы, картофель, овощи, мясо, молоко, яйца и другие), на конец месяца."),
        note_en="cost of a minimum monthly food basket of 33 items for one person, end of month",
    ),
)

SERIES_BY_CODE: dict[str, RegionalSeries] = {s.code: s for s in SERIES}

# Мост «регион ↔ Россия» (seo_regional.MACRO_BY_TABLE): table_code → код федеральной карточки.
_MACRO_BY_GROUP = {"vse": "cpi", "prodovolstvennye": "cpi-food", "neprodovolstvennye": "cpi-nonfood",
                   "uslugi": "cpi-services"}

SECTION_NUM = 20
SECTION_NAME = "Цены и тарифы"


def table_code(series: RegionalSeries) -> str:
    return f"20.c{SERIES.index(series) + 1}"


def macro_by_table() -> dict[str, str]:
    out = {}
    for s in SERIES:
        if s.dataset == CPI_DATASET:
            group = s.code.removeprefix("ipc-")
            for suffix in KIND_SUFFIX.values():
                group = group.removesuffix(f"-{suffix}")
            if group in _MACRO_BY_GROUP:
                out[table_code(s)] = _MACRO_BY_GROUP[group]
    return out


def artifact_rows() -> list[dict]:
    """Строки для ``app/data/regional/indicators.json`` (метаданные пишет seed_regional при старте)."""
    return [{
        "code": s.code,
        "table_code": table_code(s),
        "section_num": SECTION_NUM,
        "section_name": SECTION_NAME,
        "name": s.name,
        "unit": s.unit,
        "note": s.note,
        "source_sheet": f"ЕМИСС, витрина {s.dataset}",
        "frequency": "monthly",
    } for s in SERIES]


def copy_en(s: RegionalSeries) -> dict:
    return {"name": s.name_en, "unit": s.unit_en, "note": s.note_en, "section": "Prices"}
