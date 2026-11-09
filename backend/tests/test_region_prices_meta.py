"""Подача цен ЕМИСС для человека: короткие имена, группы, «Росстат больше не публикует» (Z1)."""

from __future__ import annotations

from app.data.emiss_price_goods import (
    ALL_PRICE_GOODS,
    HEADLINE_PRICE_CODES,
    MARKET_LAST_MONTH,
    PRICE_GOODS,
    PRICE_GROUPS,
    classify_price_group,
    price_meta,
)
from app.services.seo_regional import _month_label_nom


def test_every_position_has_meta_in_known_group():
    for g in ALL_PRICE_GOODS:
        m = price_meta(g.code)
        assert m and m["short_name"] and m["price_group"] in PRICE_GROUPS
        assert isinstance(m["is_discontinued"], bool) and m["last_month"] > 199912
        assert len(m["short_name"]) <= 80


def test_manual_items_have_hand_written_short_names():
    assert price_meta("ceni-yaytsa")["short_name"] == "Яйца куриные, 10 шт."
    assert price_meta("ceni-hleb-rzhanoy")["short_name"] == "Хлеб ржаной, кг"
    assert price_meta("ceni-arenda-1k")["short_name"] == "Аренда 1-комнатной квартиры, месяц"
    for g in PRICE_GOODS:
        assert not price_meta(g.code)["short_name"].startswith("Средняя цена")
        assert price_meta(g.code)["is_discontinued"] is False


def test_fuel_codes_are_covered_and_headline_codes_exist():
    for code in ("ceni-ai92", "ceni-ai95", "ceni-dt"):
        assert price_meta(code)["price_group"] == "Топливо"
    known = {g.code for g in ALL_PRICE_GOODS} | {"ceni-ai95"}
    assert all(c in known for c in HEADLINE_PRICE_CODES)
    assert price_meta("ceni-kakogo-net") is None


def test_auto_groups_by_keywords_and_forms():
    assert classify_price_group("амлодипин", "10 таблеток") == "Лекарства"
    assert classify_price_group("йод", "10 мл") == "Лекарства"
    assert classify_price_group("водоснабжение холодное", "месяц с человека") == "ЖКХ"
    assert classify_price_group("проезд в городском автобусе", "поездка") == "Транспорт"
    assert classify_price_group("абонентская плата за телевизионную антенну", "месяц") == "Связь"
    assert classify_price_group("баранина (кроме бескостного мяса)", "кг") == "Продукты"
    assert classify_price_group("блузка женская", "шт.") == "Одежда и товары"
    assert classify_price_group("мёд пчелиный натуральный", "кг") == "Продукты"
    assert classify_price_group("восстановление зуба пломбой", "услуга") == "Услуги"


def test_discontinued_is_older_than_twelve_months_from_market_last():
    old = [g for g in ALL_PRICE_GOODS if price_meta(g.code)["is_discontinued"]]
    live = [g for g in ALL_PRICE_GOODS if not price_meta(g.code)["is_discontinued"]]
    assert old and live
    for g in old:
        last = price_meta(g.code)["last_month"]
        assert (MARKET_LAST_MONTH // 100 - last // 100) * 12 + MARKET_LAST_MONTH % 100 - last % 100 > 12


def test_title_month_is_nominative():
    assert _month_label_nom(202609) == "сентябрь 2026"
    assert _month_label_nom(202605) == "май 2026"
