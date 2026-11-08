"""Средние цены ЕМИСС 31448 по субъектам (08.11.2026): справочник и метаданные."""

from __future__ import annotations

import json
from pathlib import Path

from app.data.emiss_price_goods import ALL_PRICE_GOODS, PRICE_FUELS_OIDS, PRICE_GOODS, artifact_rows, unit_phrase
from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN
from app.services.emiss_regional_parser import PRICE_FUELS, PRICE_SERIES, parse_grid_response

DATA = Path(__file__).resolve().parents[1] / "app" / "data" / "regional"


def test_codes_and_oids_are_unique_and_do_not_touch_fuel():
    codes = [g.code for g in ALL_PRICE_GOODS]
    oids = [g.oid for g in ALL_PRICE_GOODS]
    assert len(codes) == len(set(codes)) and len(oids) == len(set(oids))
    assert not set(oids) & set(PRICE_FUELS) and set(PRICE_FUELS) == set(PRICE_FUELS_OIDS)
    assert not set(codes) & set(PRICE_FUELS.values())
    assert all(c.startswith("ceni-") and len(c) <= 120 for c in codes)
    assert len(PRICE_SERIES) == len(PRICE_FUELS) + len(ALL_PRICE_GOODS)


def test_artifact_rows_fit_the_model_and_are_in_indicators_json():
    rows = artifact_rows()
    assert all(len(r["table_code"]) <= 20 and len(r["name"]) <= 300 and len(r["unit"]) <= 120 for r in rows)
    stored = {r["code"]: r for r in json.loads((DATA / "indicators.json").read_text(encoding="utf-8"))}
    for row in rows:
        assert stored[row["code"]] == row
    assert all(r["section_num"] == 22 for r in rows)


def test_unit_phrases_read_naturally():
    assert unit_phrase("кг") == "рублей за кг"
    assert unit_phrase("10 шт.") == "рублей за 10 штук"
    assert unit_phrase("пара") == "рублей за пару"
    assert unit_phrase("в расчете за 100 кВт.ч") == "рублей в расчёте за 100 кВт·ч"
    assert unit_phrase("месяц") == "рублей в месяц"


def test_hand_picked_items_have_english_names():
    for g in PRICE_GOODS:
        assert REGION_INDICATORS_EN[g.code]["name"].startswith("Average consumer price")


def test_one_month_payload_parses_fuel_and_goods_together():
    payload = {"results": [{
        "dim57831": "Российская Федерация",
        "dim1709730_d1_i1": "45,10",       # АИ-92
        "dim1709749_d2_i1": "98,40",       # яйца
        "dim1755157_d3_i1": "22 345,00",   # аренда 1-комн.
    }]}
    points = parse_grid_response(payload, year=2026, month=9, dimnames={"Российская Федерация": "russia"})
    assert sorted(points) == [
        ("ceni-ai92", "russia", 202609, 45.1),
        ("ceni-arenda-1k", "russia", 202609, 22345.0),
        ("ceni-yaytsa", "russia", 202609, 98.4),
    ]
