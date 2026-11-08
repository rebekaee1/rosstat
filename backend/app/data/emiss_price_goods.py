"""Средние потребительские цены на товары и услуги по субъектам РФ (ЕМИСС 31448).

Витрина Росстата «Средние потребительские цены (тарифы) на товары и услуги»:
884 позиции в справочнике, из них 560 опубликованы за сентябрь 2026 года по
94 территориям (проверено живым запросом 08.11.2026). До 08.11.2026 сайт брал
из неё только три вида топлива (``PRICE_FUELS`` в ``emiss_regional_parser``).

Здесь — первая порция: 79 позиций, которые ищут чаще всего (продукты, ЖКХ,
связь, проезд, аренда жилья, бытовые услуги, поездки). Код ряда — ``ceni-…``,
как у топлива; раздел 20 «Цены и тарифы» регионального каталога; слой
помесячный (``region_monthly_data``). История: по России с 2000 года, по
субъектам с 2003 года (так отдаёт источник). Значения — рубли за указанную в
названии единицу, на конец месяца (методология Росстата).

Ключ — oid позиции в измерении 58273 «Виды товаров и услуг». У части позиций
(водка, кефир, творог, сыры, хлеб пшеничный, сигареты, пиво, масло
подсолнечное за литр) Росстат с 2022 года завёл новые oid с новым описанием
товара: ряд по такому oid начинается с даты нового описания, старые описания
другого качества сюда не сшиваются.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# Топливо той же витрины живёт отдельно (PRICE_FUELS в emiss_regional_parser).
PRICE_FUELS_OIDS = ("1709730", "1709750", "1755196")

_AUTO_PATH = Path(__file__).resolve().parent / "regional" / "emiss_price_goods.json"


@dataclass(frozen=True)
class PriceGood:
    oid: str
    code: str
    label: str      # название позиции у Росстата без единицы
    per: str        # единица: «кг», «л», «10 шт.», «месяц» …
    group: str      # для текстов: «Продукты», «ЖКХ» …
    label_en: str
    per_en: str

    @property
    def name(self) -> str:
        return f"Средняя цена: {self.label}, {unit_phrase(self.per)}"

    @property
    def unit(self) -> str:
        return unit_phrase(self.per)


_UNIT_PHRASES = {
    "кг": "рублей за кг",
    "л": "рублей за литр",
    "10 шт.": "рублей за 10 штук",
    "пачка": "рублей за пачку",
    "25 пакетиков": "рублей за 25 пакетиков",
    "200 г": "рублей за 200 г",
    "месяц": "рублей в месяц",
    "месяц с человека": "рублей в месяц с человека",
    "м3": "рублей за м³",
    "Гкал": "рублей за Гкал",
    "м2": "рублей за м² общей площади",
    "100 кВт·ч": "рублей за 100 кВт·ч",
    "поездка": "рублей за поездку",
    "1 км": "рублей за 1 км пути",
    "50 км": "рублей за 50 км пути",
    "100 км": "рублей за 100 км пути",
    "стрижка": "рублей за стрижку",
    "день": "рублей за день",
    "с человека": "рублей в месяц с человека",
}


# Единицы, у которых в «рублей за …» меняется окончание.
_ACCUSATIVE = {
    "пара": "пару", "поездка": "поездку", "услуга": "услугу", "минута": "минуту",
    "пачка": "пачку", "упаковка": "упаковку", "катушка": "катушку", "капсула": "капсулу",
    "стрижка": "стрижку", "таблетка": "таблетку", "ампула": "ампулу", "штука": "штуку",
}


def unit_phrase(per: str) -> str:
    """«кг» → «рублей за кг»; единицы из справочника Росстата — по общему правилу."""
    if per in _UNIT_PHRASES:
        return _UNIT_PHRASES[per]
    per = per.replace("кВт.ч", "кВт·ч").replace("расчете", "расчёте")
    if not per:
        return "рублей"
    if per.startswith(("в расчёте", "на ", "в ")):
        return f"рублей {per}"
    if per in ("месяц", "год", "сутки", "час", "академический час", "семестр", "день", "неделя"):
        return f"рублей за {per}" if per != "месяц" else "рублей в месяц"
    first, _, rest = per.partition(" ")
    first = _ACCUSATIVE.get(first, first)
    return f"рублей за {first}{(' ' + rest) if rest else ''}"


def _g(oid, code, label, per, group, en, per_en):
    return PriceGood(oid, code, label, per, group, en, per_en)


PRICE_GOODS: tuple[PriceGood, ...] = (
    # Хлеб, крупы, бакалея
    _g("1709733", "ceni-hleb-rzhanoy", "хлеб из ржаной и ржано-пшеничной муки", "кг", "Продукты", "Rye and rye-wheat bread", "kg"),
    _g("1846521", "ceni-hleb-pshenichnyy", "хлеб и булочные изделия из пшеничной муки", "кг", "Продукты", "Wheat bread and rolls", "kg"),
    _g("1755145", "ceni-muka", "мука пшеничная", "кг", "Продукты", "Wheat flour", "kg"),
    _g("1755068", "ceni-ris", "рис шлифованный", "кг", "Продукты", "Polished rice", "kg"),
    _g("1755104", "ceni-grechka", "крупа гречневая-ядрица", "кг", "Продукты", "Buckwheat groats", "kg"),
    _g("1754784", "ceni-manka", "крупа манная", "кг", "Продукты", "Semolina", "kg"),
    _g("1709722", "ceni-makarony", "макаронные изделия из муки высшего сорта", "кг", "Продукты", "Pasta", "kg"),
    _g("1709795", "ceni-sahar", "сахар-песок", "кг", "Продукты", "Granulated sugar", "kg"),
    _g("1755092", "ceni-sol", "соль поваренная пищевая", "кг", "Продукты", "Table salt", "kg"),
    _g("1846527", "ceni-maslo-podsolnechnoe", "масло подсолнечное", "л", "Продукты", "Sunflower oil", "litre"),
    _g("1754745", "ceni-maslo-olivkovoe", "масло оливковое", "л", "Продукты", "Olive oil", "litre"),
    # Мясо и рыба
    _g("1709756", "ceni-govyadina", "говядина (кроме бескостного мяса)", "кг", "Продукты", "Beef (bone-in)", "kg"),
    _g("1709713", "ceni-govyadina-beskostnaya", "говядина бескостная", "кг", "Продукты", "Boneless beef", "kg"),
    _g("1709753", "ceni-svinina", "свинина (кроме бескостного мяса)", "кг", "Продукты", "Pork (bone-in)", "kg"),
    _g("1709731", "ceni-svinina-beskostnaya", "свинина бескостная", "кг", "Продукты", "Boneless pork", "kg"),
    _g("1709748", "ceni-kury", "куры охлаждённые и мороженые", "кг", "Продукты", "Chicken, chilled and frozen", "kg"),
    _g("1743476", "ceni-kolbasa-varenaya", "колбаса варёная", "кг", "Продукты", "Boiled sausage", "kg"),
    _g("1709791", "ceni-kolbasa-polukopchenaya", "колбаса полукопчёная и варёно-копчёная", "кг", "Продукты", "Semi-smoked sausage", "kg"),
    _g("1754708", "ceni-kolbasa-syrokopchenaya", "колбаса сырокопчёная", "кг", "Продукты", "Dry-cured sausage", "kg"),
    _g("1754719", "ceni-pelmeni", "пельмени, манты, равиоли", "кг", "Продукты", "Pelmeni and dumplings", "kg"),
    _g("1743472", "ceni-ryba-morozhenaya", "рыба мороженая неразделанная", "кг", "Продукты", "Frozen whole fish", "kg"),
    _g("1754723", "ceni-ryba-lososevaya", "рыба лососёвых пород охлаждённая и мороженая", "кг", "Продукты", "Salmon fish, chilled and frozen", "kg"),
    _g("1709806", "ceni-ryba-solenaya", "рыба солёная, маринованная, копчёная", "кг", "Продукты", "Salted, pickled and smoked fish", "kg"),
    # Молочные продукты и яйца
    _g("1709745", "ceni-moloko", "молоко питьевое пастеризованное 2,5–3,2% жирности", "л", "Продукты", "Pasteurised milk 2.5–3.2% fat", "litre"),
    _g("1853986", "ceni-moloko-ultrapasterizovannoe", "молоко ультрапастеризованное 2,5–3,2% жирности", "л", "Продукты", "UHT milk 2.5–3.2% fat", "litre"),
    _g("1856405", "ceni-kefir", "кефир", "кг", "Продукты", "Kefir", "kg"),
    _g("1709793", "ceni-smetana", "сметана", "кг", "Продукты", "Sour cream", "kg"),
    _g("1846520", "ceni-tvorog", "творог", "кг", "Продукты", "Cottage cheese", "kg"),
    _g("1709734", "ceni-maslo-slivochnoe", "масло сливочное", "кг", "Продукты", "Butter", "kg"),
    _g("1848409", "ceni-syr", "сыры твёрдые, полутвёрдые и мягкие", "кг", "Продукты", "Cheese", "kg"),
    _g("1709749", "ceni-yaytsa", "яйца куриные", "10 шт.", "Продукты", "Chicken eggs", "10 eggs"),
    # Овощи и фрукты
    _g("1743470", "ceni-kartofel", "картофель", "кг", "Продукты", "Potatoes", "kg"),
    _g("1743463", "ceni-kapusta", "капуста белокочанная", "кг", "Продукты", "White cabbage", "kg"),
    _g("1755134", "ceni-luk", "лук репчатый", "кг", "Продукты", "Onions", "kg"),
    _g("1743475", "ceni-morkov", "морковь", "кг", "Продукты", "Carrots", "kg"),
    _g("1743457", "ceni-ogurcy", "огурцы свежие", "кг", "Продукты", "Fresh cucumbers", "kg"),
    _g("1755033", "ceni-pomidory", "помидоры свежие", "кг", "Продукты", "Fresh tomatoes", "kg"),
    _g("1743471", "ceni-yabloki", "яблоки", "кг", "Продукты", "Apples", "kg"),
    _g("1754800", "ceni-banany", "бананы", "кг", "Продукты", "Bananas", "kg"),
    _g("1743453", "ceni-apelsiny", "апельсины", "кг", "Продукты", "Oranges", "kg"),
    # Чай, кофе, сладости, алкоголь, табак
    _g("1755110", "ceni-chay", "чай чёрный байховый", "кг", "Продукты", "Black tea", "kg"),
    _g("1754812", "ceni-kofe-rastvorimyy", "кофе натуральный растворимый", "кг", "Продукты", "Instant coffee", "kg"),
    _g("1754720", "ceni-kofe-zerno", "кофе в зёрнах и молотый", "кг", "Продукты", "Coffee beans and ground coffee", "kg"),
    _g("1754797", "ceni-kofe-navynos", "кофе в заведениях быстрого обслуживания", "200 г", "Услуги", "Coffee in fast-food outlets", "200 g"),
    _g("1754791", "ceni-shokolad", "шоколад", "кг", "Продукты", "Chocolate", "kg"),
    _g("1754792", "ceni-konfety", "конфеты шоколадные", "кг", "Продукты", "Chocolate sweets", "kg"),
    _g("1848408", "ceni-vodka", "водка", "л", "Продукты", "Vodka", "litre"),
    _g("1846562", "ceni-pivo", "пиво", "л", "Продукты", "Beer", "litre"),
    _g("1846523", "ceni-sigarety", "сигареты с фильтром", "пачка", "Продукты", "Filter cigarettes", "pack"),
    # Топливо (АИ-92, АИ-95 и дизель уже есть: ceni-ai92/ai95/dt)
    _g("1755184", "ceni-ai98", "бензин АИ-98 и выше", "л", "Топливо", "AI-98+ gasoline", "litre"),
    # ЖКХ
    _g("1755085", "ceni-elektroenergiya", "электроэнергия в квартирах без электроплит (в пределах нормы)", "100 кВт·ч", "ЖКХ", "Electricity, flats without electric stoves (within norm)", "100 kWh"),
    _g("1755055", "ceni-elektroenergiya-elektroplity", "электроэнергия в квартирах с электроплитами (в пределах нормы)", "100 кВт·ч", "ЖКХ", "Electricity, flats with electric stoves (within norm)", "100 kWh"),
    _g("1755194", "ceni-voda-holodnaya", "водоснабжение холодное", "м3", "ЖКХ", "Cold water supply", "m³"),
    _g("1755208", "ceni-voda-goryachaya", "водоснабжение горячее", "м3", "ЖКХ", "Hot water supply", "m³"),
    _g("1755212", "ceni-vodootvedenie", "водоотведение", "м3", "ЖКХ", "Sewerage", "m³"),
    _g("1755197", "ceni-otoplenie", "отопление", "Гкал", "ЖКХ", "Heating", "Gcal"),
    _g("1755100", "ceni-gaz-setevoy", "газ сетевой", "м3", "ЖКХ", "Piped gas", "m³"),
    _g("1785697", "ceni-vyvoz-musora", "обращение с твёрдыми коммунальными отходами", "с человека", "ЖКХ", "Municipal solid waste handling", "per person per month"),
    _g("1755108", "ceni-soderzhanie-zhilya", "содержание и ремонт жилья для собственников", "м2", "ЖКХ", "Housing maintenance for owners", "m² of floor area"),
    # Связь
    _g("1755188", "ceni-sotovaya-svyaz", "абонентская плата за пакет услуг сотовой связи", "месяц", "Связь", "Mobile service bundle fee", "month"),
    _g("1755165", "ceni-internet", "абонентская плата за доступ в интернет", "месяц", "Связь", "Home internet subscription", "month"),
    _g("1755062", "ceni-telefon-domashniy", "абонентская плата за местную телефонную связь (безлимит)", "месяц", "Связь", "Unlimited landline subscription", "month"),
    # Транспорт
    _g("1785650", "ceni-proezd-avtobus", "проезд в городском автобусе", "поездка", "Транспорт", "City bus fare", "trip"),
    _g("1755193", "ceni-proezd-tramvay", "проезд в трамвае", "поездка", "Транспорт", "Tram fare", "trip"),
    _g("1755209", "ceni-proezd-trolleybus", "проезд в троллейбусе", "поездка", "Транспорт", "Trolleybus fare", "trip"),
    _g("1755200", "ceni-proezd-metro", "проезд в метро", "поездка", "Транспорт", "Metro fare", "trip"),
    _g("1755156", "ceni-proezd-marshrutka", "проезд в маршрутном такси", "поездка", "Транспорт", "Minibus fare", "trip"),
    _g("1755125", "ceni-taksi", "проезд в такси", "1 км", "Транспорт", "Taxi fare", "1 km"),
    _g("1755136", "ceni-elektrichka", "проезд в пригородном поезде", "поездка", "Транспорт", "Suburban train fare", "trip"),
    _g("1755018", "ceni-mezhdugorodniy-avtobus", "проезд в междугородном автобусе", "50 км", "Транспорт", "Intercity bus fare", "50 km"),
    _g("1755041", "ceni-poezd-plackart", "проезд в плацкартном вагоне скорого поезда", "100 км", "Транспорт", "Long-distance train, open-plan sleeper", "100 km"),
    _g("1755049", "ceni-poezd-kupe", "проезд в купейном вагоне скорого поезда", "100 км", "Транспорт", "Long-distance train, compartment", "100 km"),
    # Жильё и бытовые услуги
    _g("1755157", "ceni-arenda-1k", "аренда однокомнатной квартиры у частных лиц", "месяц", "Жильё", "Renting a one-room flat from a private landlord", "month"),
    _g("1755035", "ceni-arenda-2k", "аренда двухкомнатной квартиры у частных лиц", "месяц", "Жильё", "Renting a two-room flat from a private landlord", "month"),
    _g("1754921", "ceni-strizhka-zhenskaya", "стрижка модельная в женском зале", "стрижка", "Услуги", "Women's haircut", "haircut"),
    _g("1754960", "ceni-strizhka-muzhskaya", "стрижка модельная в мужском зале", "стрижка", "Услуги", "Men's haircut", "haircut"),
    _g("1755107", "ceni-detskiy-sad", "посещение детского ясли-сада", "день", "Услуги", "Nursery and kindergarten attendance", "day"),
    # Поездки
    _g("1785693", "ceni-poezdka-turciya", "поездка на отдых в Турцию", "поездка", "Отдых", "Holiday trip to Turkey", "trip"),
    _g("1846545", "ceni-poezdka-egipet", "поездка на отдых в Египет", "поездка", "Отдых", "Holiday trip to Egypt", "trip"),
    _g("1848518", "ceni-poezdka-chernomore", "поездка на Черноморское побережье России", "поездка", "Отдых", "Trip to Russia's Black Sea coast", "trip"),
)

# Все остальные позиции витрины с опубликованными ценами (08.11.2026): артефакт
# собирает scripts/regional/build_price_goods.py по полному проходу истории.
# Английские названия и единицы — в app/data/i18n/price_goods_en.py.
def _load_auto() -> tuple[PriceGood, ...]:
    if not _AUTO_PATH.exists():
        return ()
    rows = json.loads(_AUTO_PATH.read_text(encoding="utf-8"))
    from app.data.i18n.price_goods_en import PRICE_GOODS_EN

    def _en(code: str) -> tuple[str, str]:
        return PRICE_GOODS_EN.get(code, ("", ""))

    return tuple(
        PriceGood(r["oid"], r["code"], r["label"], r["per"], "Прочее", *_en(r["code"]))
        for r in rows
    )


AUTO_PRICE_GOODS: tuple[PriceGood, ...] = _load_auto()
ALL_PRICE_GOODS: tuple[PriceGood, ...] = PRICE_GOODS + AUTO_PRICE_GOODS

PRICE_GOODS_BY_OID: dict[str, str] = {g.oid: g.code for g in ALL_PRICE_GOODS}
PRICE_GOODS_BY_CODE: dict[str, PriceGood] = {g.code: g for g in ALL_PRICE_GOODS}

# Раздел регионального каталога, куда встают позиции.
SECTION_NUM = 20
SECTION_NAME = "Цены и тарифы"


def artifact_rows() -> list[dict]:
    """Строки для ``app/data/regional/indicators.json`` (как у ``ceni-ai92``)."""
    rows = []
    for n, g in enumerate(ALL_PRICE_GOODS, start=1):
        rows.append({
            "code": g.code,
            "table_code": f"20.m{n}",
            "section_num": SECTION_NUM,
            "section_name": SECTION_NAME,
            "name": g.name,
            "unit": g.unit,
            "note": "Средние потребительские цены по субъекту, конец месяца. Частота — месячная.",
            "source_sheet": "ЕМИСС, витрина 31448",
            "frequency": "monthly",
        })
    return rows


def copy_en(g: PriceGood) -> dict:
    return {
        "name": f"Average consumer price: {g.label_en}",
        "unit": f"roubles per {g.per_en}" if g.per_en else "roubles",
        "note": "average consumer price; end of month",
        "section": "Prices",
    }


# --- Подача для человека: короткое имя, группа, «Росстат больше не публикует» ---

# Группы в порядке показа на странице региона.
PRICE_GROUPS: tuple[str, ...] = (
    "Продукты", "ЖКХ", "Транспорт", "Топливо", "Жильё", "Связь", "Услуги",
    "Лекарства", "Одежда и товары", "Отдых", "Прочее",
)
PRICE_GROUPS_EN: dict[str, str] = {
    "Продукты": "Food", "ЖКХ": "Utilities", "Транспорт": "Transport", "Топливо": "Fuel",
    "Жильё": "Housing", "Связь": "Telecom", "Услуги": "Services", "Лекарства": "Medicines",
    "Одежда и товары": "Clothing and goods", "Отдых": "Leisure", "Прочее": "Other",
}

# Короткие имена ручных позиций и топлива (имя уже включает единицу).
_SHORT_MANUAL: dict[str, str] = {
    "ceni-ai92": "Бензин АИ-92, л", "ceni-ai95": "Бензин АИ-95, л", "ceni-dt": "Дизельное топливо, л",
    "ceni-ai98": "Бензин АИ-98 и выше, л",
    "ceni-hleb-rzhanoy": "Хлеб ржаной, кг", "ceni-hleb-pshenichnyy": "Хлеб пшеничный, кг",
    "ceni-muka": "Мука пшеничная, кг", "ceni-ris": "Рис, кг", "ceni-grechka": "Гречка, кг",
    "ceni-manka": "Манка, кг", "ceni-makarony": "Макароны, кг", "ceni-sahar": "Сахар, кг",
    "ceni-sol": "Соль, кг", "ceni-maslo-podsolnechnoe": "Масло подсолнечное, л",
    "ceni-maslo-olivkovoe": "Масло оливковое, л",
    "ceni-govyadina": "Говядина на кости, кг", "ceni-govyadina-beskostnaya": "Говядина без кости, кг",
    "ceni-svinina": "Свинина на кости, кг", "ceni-svinina-beskostnaya": "Свинина без кости, кг",
    "ceni-kury": "Курица, кг", "ceni-kolbasa-varenaya": "Колбаса варёная, кг",
    "ceni-kolbasa-polukopchenaya": "Колбаса полукопчёная, кг",
    "ceni-kolbasa-syrokopchenaya": "Колбаса сырокопчёная, кг", "ceni-pelmeni": "Пельмени, кг",
    "ceni-ryba-morozhenaya": "Рыба мороженая, кг", "ceni-ryba-lososevaya": "Лосось и форель, кг",
    "ceni-ryba-solenaya": "Рыба солёная и копчёная, кг",
    "ceni-moloko": "Молоко пастеризованное, л", "ceni-moloko-ultrapasterizovannoe": "Молоко длительного хранения, л",
    "ceni-kefir": "Кефир, кг", "ceni-smetana": "Сметана, кг", "ceni-tvorog": "Творог, кг",
    "ceni-maslo-slivochnoe": "Масло сливочное, кг", "ceni-syr": "Сыр, кг",
    "ceni-yaytsa": "Яйца куриные, 10 шт.",
    "ceni-kartofel": "Картофель, кг", "ceni-kapusta": "Капуста, кг", "ceni-luk": "Лук репчатый, кг",
    "ceni-morkov": "Морковь, кг", "ceni-ogurcy": "Огурцы, кг", "ceni-pomidory": "Помидоры, кг",
    "ceni-yabloki": "Яблоки, кг", "ceni-banany": "Бананы, кг", "ceni-apelsiny": "Апельсины, кг",
    "ceni-chay": "Чай чёрный, кг", "ceni-kofe-rastvorimyy": "Кофе растворимый, кг",
    "ceni-kofe-zerno": "Кофе в зёрнах и молотый, кг", "ceni-kofe-navynos": "Кофе навынос, 200 г",
    "ceni-shokolad": "Шоколад, кг", "ceni-konfety": "Конфеты шоколадные, кг",
    "ceni-vodka": "Водка, л", "ceni-pivo": "Пиво, л", "ceni-sigarety": "Сигареты, пачка",
    "ceni-elektroenergiya": "Электричество без плиты, 100 кВт·ч",
    "ceni-elektroenergiya-elektroplity": "Электричество с электроплитой, 100 кВт·ч",
    "ceni-voda-holodnaya": "Холодная вода, м³", "ceni-voda-goryachaya": "Горячая вода, м³",
    "ceni-vodootvedenie": "Водоотведение, м³", "ceni-otoplenie": "Отопление, Гкал",
    "ceni-gaz-setevoy": "Газ сетевой, м³", "ceni-vyvoz-musora": "Вывоз мусора, в месяц с человека",
    "ceni-soderzhanie-zhilya": "Содержание и ремонт жилья, м²",
    "ceni-sotovaya-svyaz": "Сотовая связь, месяц", "ceni-internet": "Домашний интернет, месяц",
    "ceni-telefon-domashniy": "Домашний телефон, месяц",
    "ceni-proezd-avtobus": "Проезд в автобусе, поездка", "ceni-proezd-tramvay": "Проезд в трамвае, поездка",
    "ceni-proezd-trolleybus": "Проезд в троллейбусе, поездка", "ceni-proezd-metro": "Проезд в метро, поездка",
    "ceni-proezd-marshrutka": "Проезд в маршрутке, поездка", "ceni-taksi": "Такси, 1 км",
    "ceni-elektrichka": "Электричка, поездка", "ceni-mezhdugorodniy-avtobus": "Междугородный автобус, 50 км",
    "ceni-poezd-plackart": "Поезд, плацкарт, 100 км", "ceni-poezd-kupe": "Поезд, купе, 100 км",
    "ceni-arenda-1k": "Аренда 1-комнатной квартиры, месяц", "ceni-arenda-2k": "Аренда 2-комнатной квартиры, месяц",
    "ceni-strizhka-zhenskaya": "Женская стрижка", "ceni-strizhka-muzhskaya": "Мужская стрижка",
    "ceni-detskiy-sad": "Детский сад, день",
    "ceni-poezdka-turciya": "Поездка в Турцию", "ceni-poezdka-egipet": "Поездка в Египет",
    "ceni-poezdka-chernomore": "Поездка на Чёрное море",
}

_FUEL_EN = {"ceni-ai92": "AI-92 gasoline, litre", "ceni-ai95": "AI-95 gasoline, litre", "ceni-dt": "Diesel, litre"}
_FUEL_CODES = ("ceni-ai92", "ceni-ai95", "ceni-dt")

# Ходовые позиции для блока «Цены в регионе» на первом экране: порядок показа.
HEADLINE_PRICE_CODES: tuple[str, ...] = (
    "ceni-hleb-pshenichnyy", "ceni-moloko", "ceni-yaytsa", "ceni-kury", "ceni-kartofel",
    "ceni-ai95", "ceni-proezd-avtobus", "ceni-arenda-1k", "ceni-elektroenergiya",
    "ceni-sahar", "ceni-govyadina-beskostnaya", "ceni-internet",
)

_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Топливо", ("бензин", "дизельн", "топливо", "газ автомобильный", "газ для заправки")),
    ("Жильё", ("аренда", "наём жилых", "наем жилых", "найм жиль", "наём жилья")),
    ("ЖКХ", ("водоснабжен", "водоотведен", "отоплени", "электроэнерг", "газ сетев", "газ в баллон",
             "сжиженный газ", "коммунальн", "содержание и ремонт жиль", "канализац", "капитальный ремонт",
             "лифт", "домофон", "дрова", "горячая вода", "холодная вода", "теплоснабжен")),
    ("Связь", ("абонентская плата", "связь", "связи", "интернет", "sms", "смс", "почтов", "телеграмм",
               "радиоточк", "антенн", "кабельн", "междугородн", "телефон")),
    ("Транспорт", ("проезд", "такси", "перевозк", "авиабилет", "железнодорож", "автобус", "трамва",
                   "метро", "троллейбус", "парковк", "автомобил", "шиномонтаж", "осаго", "каско")),
    ("Отдых", ("поездка в", "поездки в", "поездка на", "поездки на", "путёвк", "путевк", "санатор",
               "дом отдыха", "гостиниц", "кинотеатр", "театр", "концерт", "музе", "экскурс", "отдых",
               "цирк", "аттракцион", "пансионат", "база отдыха", "зоопарк")),
)
_MED_PER = re.compile(r"(таблет|капсул|драже|ампул|суппозитор|мл\b|доз|пакетик)", re.I)
_MED_LABEL = re.compile(r"(,\s*\d+(?:[.,]\d+)?\s*(мг|мкг|ме|%)|\bмазь\b|\bгель\b|капли|сироп|настойк|"
                        r"таблетки|антибиот|вакцин|бинт|пластырь|вата|шприц|термометр|презерватив|"
                        r"контрацептив|йод|перекис|пероксид|кислота|спрей|раствор)", re.I)
_FOOD_PER = {"кг", "л", "10 шт.", "пачка", "200 г", "100 г", "350 г", "100 г (100 мл)", "1000 шт.", "упаковка"}
_NONFOOD_KG = ("порошок", "мыло", "корм", "краска", "цемент", "гвозд", "удобрен", "семена", "кабель",
               "проволок", "стекл", "обои", "линолеум", "лак", "шпатлёвк", "шпаклёвк", "песок", "щебень",
               "кирпич", "средств", "уголь", "сигарет", "блоки", "строительн")
_SERVICE_PER = ("услуга", "одна операция", "исследование", "один вид работы", "посещение", "час",
                "академический час", "семестр", "минута", "полис", "сеанс", "занятие", "стрижка", "день",
                "сутки", "билет", "сутки с человека")
_SERVICE_KEYS = ("ремонт", "услуг", "химчистк", "стирк", "парикмахер", "бани", "баня", "сауна", "ритуальн",
                 "нотариальн", "оформление", "обучение", "образован", "детский сад", "ясли", "ясел",
                 "страхов", "фотограф", "проживание", "перевод суммы", "вклад", "ксерокопи", "юридич",
                 "стоматолог", "приём врача", "прием врача", "диагностик", "рытье", "похорон", "кремаци",
                 "занятия", "бассейн", "кредит", "доставка", "изготовление", "пошив", "прокат", "массаж", "маникюр")
_PER_SHORT = {"м2": "м²", "м3": "м³", "м2 общей площади": "м²", "10 м2": "10 м²",
              "месяц с человека": "в месяц с человека", "в расчете на 100 км пути": "100 км пути"}


_TOUR = re.compile(r"(^|\W)тур(ы|а|ов|ист|ы)?(\W|$)")
_GOODS_PER = ("шт.", "пара", "кг", "л", "комплект", "10 шт.", "упаковка", "набор")


def _contains(label: str, keys: tuple[str, ...]) -> bool:
    return any(k in label for k in keys)


def classify_price_group(label: str, per: str) -> str:
    """Группа цены по названию и единице Росстата (для позиций вне ручного списка)."""
    low = label.lower()
    for group, keys in _RULES:
        if _contains(low, keys) or (group == "Отдых" and _TOUR.search(low)):
            return group
    if _contains(low, ("общественного питания", "обед в", "столов")):
        return "Продукты"
    if _MED_PER.search(per) or _MED_LABEL.search(low):
        return "Лекарства"
    if per in _SERVICE_PER or (per not in _GOODS_PER and _contains(low, _SERVICE_KEYS)):
        return "Услуги"
    if per in _FOOD_PER and not _contains(low, _NONFOOD_KG):
        return "Продукты"
    if per:
        return "Одежда и товары"
    return "Прочее"


_TAIL_WORDS = {"из", "при", "в", "на", "с", "и", "для", "или", "по", "за", "от", "до", "без", "во", "к"}


def _short_label(label: str) -> str:
    text = label.strip()
    if len(text) > 44 and "(" in text:
        text = re.sub(r"\s*\([^)]*\)", "", text).strip()
    text = text[:1].upper() + text[1:]
    if len(text) > 56:
        cut = text[:56].rsplit(" ", 1)[0].rstrip(" ,;-–")
        for sep in (" из ", " при ", " для ", " с ", " на "):
            at = cut.find(sep)
            if at >= 16:
                cut = cut[:at]
                break
        words = cut.split()
        while words and words[-1].lower() in _TAIL_WORDS:
            words.pop()
        text = " ".join(words).rstrip(" ,;-–") + "…"
    return text


def short_name_for(g: PriceGood) -> str:
    """Короткое имя для карточек и списков: «Яйца куриные, 10 шт.»."""
    manual = _SHORT_MANUAL.get(g.code)
    if manual:
        return manual
    per = _PER_SHORT.get(g.per, g.per).strip()
    base = _short_label(g.label)
    if not per or per.lower() in base.lower().split() or per == "услуга":
        return base
    return f"{base}, {per}"


def _load_auto_last() -> dict[str, int]:
    if not _AUTO_PATH.exists():
        return {}
    rows = json.loads(_AUTO_PATH.read_text(encoding="utf-8"))
    return {r["code"]: int(r.get("last") or 0) for r in rows}


_AUTO_LAST: dict[str, int] = _load_auto_last()
# Последний месяц витрины (по артефакту: самый свежий ряд любой позиции).
MARKET_LAST_MONTH: int = max(_AUTO_LAST.values(), default=0) or 202609


def _months_between(a: int, b: int) -> int:
    return (b // 100 - a // 100) * 12 + (b % 100 - a % 100)


_SKIP_UNIT_EN = ("service", "item", "type of work", "operation", "visit", "procedure", "session", "course")


def _short_en(g: PriceGood) -> str | None:
    """Short English name with the unit: «Chicken eggs, 10 eggs»; no unit when it adds nothing."""
    if not g.label_en:
        return None
    if not g.per_en or g.per_en in _SKIP_UNIT_EN:
        return g.label_en
    return f"{g.label_en}, {g.per_en}"


def price_meta(code: str) -> dict | None:
    """Поля подачи цены для API; None, если код — не из витрины цен."""
    g = PRICE_GOODS_BY_CODE.get(code)
    if g is None:
        if code in _FUEL_CODES:
            return {"short_name": _SHORT_MANUAL[code], "short_name_en": _FUEL_EN[code], "price_group": "Топливо",
                    "is_discontinued": False, "last_month": MARKET_LAST_MONTH}
        return None
    last = _AUTO_LAST.get(code) or MARKET_LAST_MONTH
    group = g.group if g.group != "Прочее" else classify_price_group(g.label, g.per)
    return {
        "short_name": short_name_for(g),
        "short_name_en": _short_en(g),
        "price_group": group,
        "is_discontinued": _months_between(last, MARKET_LAST_MONTH) > 12,
        "last_month": last,
    }
