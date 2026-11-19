"""Недельные цены на продукты и бензин АИ-98 по России из файла Росстата `nedel_sred_cen.xlsx` (19.11.2026).

Тот же файл «Еженедельные средние потребительские цены», из которого с 2026 года идут `fuel-ai92`, `fuel-ai95` и
`fuel-diesel` (парсер `rosstat_weekly_price`, листы 2022–текущий год, строка товара — по `product_label`). Росстат
публикует в нём 110 товаров и услуг; топливо — главный вход сайта (1 882 человека за 30 дней на 19.11.2026), а цены
на продукты по России на сайте были только помесячными по регионам (ЕМИСС 31448). Здесь — ходовой набор: продукты,
которые люди покупают каждую неделю и о ценах на которые пишут новости (яйца, сахар, гречка, масло, овощи «борщевого
набора», мясо), и АИ-98 (вопросы «сколько стоит 98 бензин» — гипотезы Пульса 289 и 341).

Не взяты: лекарства, одежда, услуги, гостиницы, автомобили, алкоголь и табак — спроса во фразах Яндекса за 90 дней
нет (один-два захода на тему); их можно добавить строкой в `GOODS`, файл и парсер те же.

Подписи `label` — точные названия строк в файле (19.11.2026, лист 2026). Сыр — с 2023 года: на листе 2022 строка
другая («Сыры сычужные твердые и мягкие», без полутвёрдых), ряды не склеиваются. Объём: 21 ряд, 5 157 недельных
точек на 19.11.2026 (~250 на товар) в `indicator_data`.
"""

from __future__ import annotations

from dataclasses import dataclass

SOURCE_URL = "https://rosstat.gov.ru/statistics/price"


@dataclass(frozen=True)
class WeeklyGood:
    code: str
    label: str            # строка файла Росстата (col 0)
    name: str
    name_en: str
    unit: str
    unit_en: str
    what: str             # что именно измеряется, простыми словами (в описание)
    what_en: str
    keywords: str         # синонимы для SEO и поиска
    max_value: float      # граница здравого смысла (руб.)


def _g(code, label, name, name_en, unit, unit_en, what, what_en, keywords, max_value) -> WeeklyGood:
    return WeeklyGood(code, label, name, name_en, unit, unit_en, what, what_en, keywords, max_value)


GOODS: tuple[WeeklyGood, ...] = (
    _g("price-eggs", "Яйца куриные, 10 шт.", "Цены на яйца", "Egg prices", "руб. за 10 шт.", "RUB per 10",
       "куриных яиц за десяток", "chicken eggs per ten",
       "цена яиц, сколько стоят яйца, цена десятка яиц, яйца куриные", 1000),
    _g("price-sugar", "Сахар-песок, кг", "Цены на сахар", "Sugar prices", "руб./кг", "RUB/kg",
       "сахара-песка за килограмм", "granulated sugar per kilogram",
       "цена сахара, сколько стоит сахар, сахарный песок", 1000),
    _g("price-buckwheat", "Крупа гречневая-ядрица, кг", "Цены на гречку", "Buckwheat prices", "руб./кг", "RUB/kg",
       "гречневой крупы (ядрицы) за килограмм", "buckwheat groats per kilogram",
       "цена гречки, гречка, гречневая крупа, ядрица", 1000),
    _g("price-rice", "Рис шлифованный, кг", "Цены на рис", "Rice prices", "руб./кг", "RUB/kg",
       "шлифованного риса за килограмм", "polished rice per kilogram", "цена риса, рис", 1000),
    _g("price-bread", "Хлеб и булочные изделия из пшеничной муки различных сортов, кг", "Цены на хлеб",
       "Bread prices", "руб./кг", "RUB/kg",
       "хлеба и булочных изделий из пшеничной муки за килограмм", "wheat bread and buns per kilogram",
       "цена хлеба, хлеб, батон, булка", 1000),
    _g("price-milk", "Молоко питьевое цельное пастеризованное 2,5-3,2% жирности, л", "Цены на молоко",
       "Milk prices", "руб./л", "RUB/l",
       "пастеризованного молока жирностью 2,5–3,2% за литр", "pasteurised milk, 2.5–3.2% fat, per litre",
       "цена молока, молоко, литр молока", 1000),
    _g("price-butter", "Масло сливочное, кг", "Цены на сливочное масло", "Butter prices", "руб./кг", "RUB/kg",
       "сливочного масла за килограмм", "butter per kilogram", "цена сливочного масла, масло сливочное", 5000),
    _g("price-sunflower-oil", "Масло подсолнечное, л", "Цены на подсолнечное масло", "Sunflower oil prices",
       "руб./л", "RUB/l", "подсолнечного масла за литр", "sunflower oil per litre",
       "цена подсолнечного масла, растительное масло, масло подсолнечное", 1000),
    _g("price-cheese", "Сыры твердые, полутвердые и мягкие, кг", "Цены на сыр", "Cheese prices", "руб./кг",
       "RUB/kg", "сыра за килограмм", "cheese per kilogram", "цена сыра, сыр", 5000),
    _g("price-chicken", "Куры охлажденные и мороженые, кг", "Цены на курицу", "Chicken prices", "руб./кг",
       "RUB/kg", "охлаждённых и мороженых кур за килограмм", "chilled and frozen chicken per kilogram",
       "цена курицы, курица, куры, мясо птицы", 2000),
    _g("price-beef", "Говядина (кроме бескостного мяса), кг", "Цены на говядину", "Beef prices", "руб./кг",
       "RUB/kg", "говядины на кости за килограмм", "bone-in beef per kilogram", "цена говядины, говядина, мясо",
       5000),
    _g("price-pork", "Свинина (кроме бескостного мяса), кг", "Цены на свинину", "Pork prices", "руб./кг",
       "RUB/kg", "свинины на кости за килограмм", "bone-in pork per kilogram", "цена свинины, свинина, мясо",
       5000),
    _g("price-potatoes", "Картофель, кг", "Цены на картофель", "Potato prices", "руб./кг", "RUB/kg",
       "картофеля за килограмм", "potatoes per kilogram", "цена картофеля, картошка, картофель", 500),
    _g("price-cabbage", "Капуста белокочанная свежая, кг", "Цены на капусту", "Cabbage prices", "руб./кг",
       "RUB/kg", "свежей белокочанной капусты за килограмм", "fresh white cabbage per kilogram",
       "цена капусты, капуста", 500),
    _g("price-onions", "Лук репчатый, кг", "Цены на лук", "Onion prices", "руб./кг", "RUB/kg",
       "репчатого лука за килограмм", "onions per kilogram", "цена лука, лук репчатый", 500),
    _g("price-carrots", "Морковь, кг", "Цены на морковь", "Carrot prices", "руб./кг", "RUB/kg",
       "моркови за килограмм", "carrots per kilogram", "цена моркови, морковь", 500),
    _g("price-cucumbers", "Огурцы свежие, кг", "Цены на огурцы", "Cucumber prices", "руб./кг", "RUB/kg",
       "свежих огурцов за килограмм", "fresh cucumbers per kilogram", "цена огурцов, огурцы", 1000),
    _g("price-tomatoes", "Помидоры свежие, кг", "Цены на помидоры", "Tomato prices", "руб./кг", "RUB/kg",
       "свежих помидоров за килограмм", "fresh tomatoes per kilogram", "цена помидоров, помидоры, томаты", 1000),
    _g("price-bananas", "Бананы, кг", "Цены на бананы", "Banana prices", "руб./кг", "RUB/kg",
       "бананов за килограмм", "bananas per kilogram", "цена бананов, бананы", 1000),
    _g("price-apples", "Яблоки, кг", "Цены на яблоки", "Apple prices", "руб./кг", "RUB/kg",
       "яблок за килограмм", "apples per kilogram", "цена яблок, яблоки", 1000),
    _g("fuel-ai98", "Бензин автомобильный марки АИ-98 и выше, л", "Цены на бензин АИ-98", "Gasoline AI-98",
       "руб./л", "RUB/l", "бензина марки АИ-98 и выше за литр", "AI-98 and higher grade gasoline per litre",
       "цена бензина АИ-98, бензин 98, 98 бензин, АИ-100, бензин 100, цена литра бензина", 300),
)

GOODS_BY_CODE: dict[str, WeeklyGood] = {g.code: g for g in GOODS}

METHODOLOGY = (
    "Средняя потребительская цена по России на конец недели. Росстат регистрирует цены каждую неделю в магазинах и на "
    "заправках городов всех регионов и усредняет их с учётом численности населения. Цена — та, что видит покупатель, "
    "со всеми налогами. Ряд недельный, с 2022 года; новые недели выходят по средам. С 2023 года данные — без "
    "учёта новых субъектов Российской Федерации."
)
METHODOLOGY_EN = (
    "Average consumer price in Russia at the end of the week. Rosstat records prices weekly in shops and petrol "
    "stations in towns across all regions and averages them by population. It is the shelf price paid by buyers, "
    "taxes included. Weekly series since 2022; new weeks are released on Wednesdays. From 2023 the data "
    "exclude the territories identified by Rosstat as new constituent entities."
)


def seed_indicators():
    for g in GOODS:
        yield {
            "code": g.code,
            "name": g.name,
            "name_en": g.name_en,
            "unit": g.unit,
            "frequency": "weekly",
            "source": "Росстат",
            "source_url": SOURCE_URL,
            "description": f"Средняя потребительская цена {g.what} в России. Еженедельные данные Росстата.",
            "methodology": METHODOLOGY,
            "parser_type": "rosstat_weekly_price",
            "model_config_json": {
                "product_label": g.label,
                "forecast_steps": 0,
                "validation": {"min": 0.5, "max": g.max_value},
            },
            "is_active": True,
            "category": "Цены",
        }


def copy_en() -> dict[str, dict[str, str]]:
    return {
        g.code: {
            "name": g.name_en,
            "description": f"Average consumer price of {g.what_en} in Russia. Weekly Rosstat data.",
            "methodology": METHODOLOGY_EN,
            "unit": g.unit_en,
        }
        for g in GOODS
    }


def seo_keywords() -> dict[str, str]:
    return {g.code: f"{g.keywords}, цены на продукты, недельные цены, Росстат" for g in GOODS}


def seo_meta() -> dict[str, dict[str, str]]:
    return {
        g.code: {
            "seo_title": f"{g.name} в России по неделям, {g.unit}",
            "seo_description": (
                f"Средняя цена {g.what} в России: еженедельные данные Росстата с 2022 года, график и таблица."
            ),
        }
        for g in GOODS
    }
