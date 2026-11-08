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
# Английского перевода у них пока нет — EN-страницы показывают русское название.
def _load_auto() -> tuple[PriceGood, ...]:
    if not _AUTO_PATH.exists():
        return ()
    rows = json.loads(_AUTO_PATH.read_text(encoding="utf-8"))
    return tuple(PriceGood(r["oid"], r["code"], r["label"], r["per"], "Прочее", "", "") for r in rows)


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
        "unit": f"roubles per {g.per_en}",
        "note": "average consumer price; end of month",
        "section": "Prices",
    }
