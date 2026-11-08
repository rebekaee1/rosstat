"""Тесты разбора ЕМИСС-ответов. Фикстуры — урезанные срезы реальных ответов dataGrid.do
(30925 индексы цен на жильё: кварталы; 57824 зарплата: месяцы + нарастающий итог;
31517 суммарный коэффициент рождаемости: годы; 31548 население мужчин по возрасту: срез «на 1 января»).

    python3 -m pytest scripts/emiss/test_grid_to_series.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grid_to_series import build_series, parse_period, parse_ru_float, period_key, series_code  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures"


def series_of(iid):
    d = json.loads((FX / f"{iid}.json").read_text(encoding="utf-8"))
    return build_series(d["grid"], d["page"])


def test_parse_period_kinds():
    assert parse_period("март") == ("M", 3)
    assert parse_period("III квартал") == ("Q", 3)
    assert parse_period("IV квартал (предварительные данные)") == ("Q", 4)
    assert parse_period("значение показателя за год") == ("A", 0)
    assert parse_period("на 31 декабря") == ("AE", 12)
    assert parse_period("на 1 января") == ("AS", 1)
    assert parse_period("январь-март") == ("C", 3)
    assert parse_period("9 месяцев") == ("C", 9)
    assert parse_period("на 30 июня") == ("QE", 2)
    assert parse_period("16 мая") == ("D", 5)
    assert parse_period("что-то новое") == ("?", 0)


def test_values_and_keys():
    assert parse_ru_float("1 234,5") == 1234.5
    assert parse_ru_float("-") is None and parse_ru_float("") is None and parse_ru_float(None) is None
    assert period_key("monthly", 2026, 8) == 202608
    assert period_key("quarterly", 2026, 3) == 20263
    assert period_key("annual", 2025, 0) == 2025
    code = series_code("31517", ["Все население"], "annual")
    assert code == series_code("31517", ["Все население"], "annual") and len(code) <= 96
    assert series_code("1", ["a"], "annual") != series_code("1", ["b"], "annual")


def test_quarterly_housing_prices_30925():
    ss = series_of("30925")
    assert ss and all(s.layer == "quarterly" and s.unit == "процент" for s in ss)
    assert {"Виды показателя", "Рынок жилья", "Типы квартир"} <= set(ss[0].qualifiers)
    slugs = {k[0] for s in ss for k in s.points}
    assert {"russia", "belgorodskaya-oblast", "respublika-tatarstan"} <= slugs
    assert all(20221 <= k[1] <= 20254 and k[1] % 10 in (1, 2, 3, 4) for s in ss for k in s.points)
    assert all(s.code.endswith("-q") for s in ss)


def test_monthly_wages_57824_drops_cumulative():
    ss = series_of("57824")
    assert ss and all(s.unit == "рубль" for s in ss)
    assert {s.layer for s in ss} <= {"monthly", "annual"} and "monthly" in {s.layer for s in ss}
    keys = {k[1] for s in ss if s.layer == "monthly" for k in s.points}
    assert keys and all(202500 < k < 202613 and 1 <= k % 100 <= 12 for k in keys)
    # «январь-март» и т.п. (нарастающим итогом) в месячный слой не попадают: у месяца ровно одно значение на регион
    assert not any(s.layer == "other" for s in ss)
    # Россия: с 2023 берётся строка «без учёта новых субъектов», старая отбрасывается — дублей нет, всё под одним slug
    assert "russia" in {k[0] for s in ss for k in s.points}


def test_annual_birth_rate_31517():
    ss = series_of("31517")
    assert {s.qualifiers["Категории населения"] for s in ss} == {"Все население", "Городское население", "Сельское население"}
    all_ = next(s for s in ss if s.qualifiers["Категории населения"] == "Все население")
    assert all_.layer == "annual"
    assert 1.0 < all_.points[("russia", 2023)] < 2.0
    assert all(2022 <= k[1] <= 2025 for k in all_.points)


def test_snapshot_on_january_first_31548():
    ss = series_of("31548")
    assert ss and all(s.layer == "annual" and s.code.endswith("-1jan") for s in ss)
    assert all(k[1] in (2024, 2025) for s in ss for k in s.points)
    # возраст-«0» и общее число — разные ряды: у ряда один набор квалификаторов
    assert len({s.code for s in ss}) == len(ss)


def test_unknown_territories_are_reported_not_loaded():
    d = json.loads((FX / "31517.json").read_text(encoding="utf-8"))
    row = dict(d["grid"]["payloads"][0]["results"][0])
    row["dim57831"] = "Неведомая территория"
    d["grid"]["payloads"][0]["results"].append(row)
    ss = build_series(d["grid"], d["page"])
    assert any("Неведомая территория" in s.skipped_regions for s in ss)
    assert "unknown" not in {k[0] for s in ss for k in s.points}
