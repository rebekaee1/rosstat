"""R7-B: качество названий, групп и единиц 881 позиции цен (глазами закупщика)."""

from __future__ import annotations

import re
from collections import Counter

from app.data.emiss_price_goods import (
    ALL_PRICE_GOODS,
    PRICE_GROUPS,
    PRICE_GOODS_BY_CODE,
    classify_price_group,
    price_meta,
    unit_phrase,
)


def _group(label: str, per: str = "шт.") -> str:
    return classify_price_group(label.lower(), per)


def test_every_short_name_is_complete_and_unique():
    names = Counter()
    for g in ALL_PRICE_GOODS:
        meta = price_meta(g.code)
        assert meta["price_group"] in PRICE_GROUPS
        name = meta["short_name"]
        assert "…" not in name, (g.code, name)
        assert len(name) <= 66, (g.code, name)
        assert not name.endswith(", шт."), (g.code, name)
        names[name] += 1
    assert [n for n, c in names.items() if c > 1] == []


def test_non_medicines_leave_medicine_group():
    assert _group("молоко питьевое цельное пастеризованное более 3,2% жирности", "л") == "Продукты"
    assert _group("шампунь", "250 мл") == "Одежда и товары"
    assert _group("духи импортные", "10 мл") == "Одежда и товары"
    assert _group("паста зубная импортная", "100 мл") == "Одежда и товары"
    assert _group("поливитамины", "10 шт.") == "Лекарства"
    assert _group("энтеросгель", "225 г") == "Лекарства"


def test_services_and_utilities_are_not_goods():
    for label, per in (("изготовление гроба", "шт."), ("лечение кариеса", "пломба"),
                       ("выполнение малярных работ", "10 м2"), ("установка пластиковых окон", "м2"),
                       ("общий анализ крови", "анализ"), ("пошив брюк", "шт.")):
        assert _group(label, per) == "Услуги", label
    assert _group("газ сжиженный", "месяц с человека") == "ЖКХ"
    assert _group("плата за пересылку простой посылки внутри России массой 1-2 кг", "шт.") == "Связь"
    assert _group("полет в салоне экономического класса самолета", "в расчете на 1000 км пути") == "Транспорт"
    assert _group("речной круиз на территории России", "поездка") == "Отдых"
    assert _group("компримированный природный газ", "м3") == "Топливо"


def test_units_read_like_a_person():
    assert unit_phrase("руб.") == "рублей"
    assert unit_phrase("т") == "рублей за тонну"
    assert unit_phrase("м") == "рублей за метр"
    assert unit_phrase("пломба") == "рублей за пломбу"
    g = PRICE_GOODS_BY_CODE["ceni-benzin-avtomobilnyy"]
    assert g.unit == "рублей за литр"
    for g in ALL_PRICE_GOODS:
        assert "рублей за руб" not in g.unit
        assert "(" not in g.per_en


def test_known_short_names():
    cases = {
        "ceni-vodka-krepostyu-40-ob-spirta-i-vyshe-obyknovennogo-kachestva": "Водка обыкновенная, л",
        "ceni-muzhskie-trusy": None,
    }
    assert price_meta("ceni-vodka-krepostyu-40-ob-spirta-i-vyshe-obyknovennogo-kachestva")["short_name"] == cases[
        "ceni-vodka-krepostyu-40-ob-spirta-i-vyshe-obyknovennogo-kachestva"]
    for g in ALL_PRICE_GOODS:
        if "Распутин" in price_meta(g.code)["short_name"]:
            break
    else:
        raise AssertionError("нет понятного имени у водки типа «Распутин»")


def test_english_units_have_no_ambiguity():
    for g in ALL_PRICE_GOODS:
        assert not re.search(r"\b10 items\b", g.per_en), g.code
    assert PRICE_GOODS_BY_CODE["ceni-polivitaminy"].per_en == "10 tablets"
