"""Листы недельных файлов Росстата: годом считается только правдоподобный год (инцидент 05.11.2026).

В nedel_sred_cen.xlsx пришёл лист «1»; парсер взял `int("1")` за год и записал 31 неделю цен на топливо
датами 0001-…, а годовые страницы /russia/indicator/fuel-*/{год} отвечали 500 (`bad public year: 1`).
"""
import io
from datetime import date

import openpyxl
import pytest

from app.services.rosstat_weekly_inflation_parser import _sheet_year
from app.services.rosstat_weekly_price_parser import parse_weekly_price_xlsx

LABEL = "Бензин автомобильный марки АИ-92, л"


@pytest.mark.parametrize("name, expected", [
    ("2026", 2026), (" 2022 ", 2022), ("1", None), ("12", None), ("Содержание", None),
    ("2026 (испр.)", None), ("1897", None), (str(date.today().year + 5), None),
])
def test_sheet_year(name, expected):
    assert _sheet_year(name) == expected


def _sheet(wb, title, value):
    ws = wb.create_sheet(title)
    ws.append(["К содержанию"])
    ws.append([])
    ws.append([])
    ws.append(["", "на 12 января", "на 19 января"])
    ws.append([LABEL, value, value + 0.1])


def test_numbered_non_year_sheet_is_ignored():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    _sheet(wb, "2026", 60.0)
    _sheet(wb, "1", 47.4)  # лист не годовой: раньше давал даты 0001-01-12, 0001-01-19
    buf = io.BytesIO()
    wb.save(buf)

    points = parse_weekly_price_xlsx(buf.getvalue(), LABEL)

    assert {p.date for p in points} == {date(2026, 1, 12), date(2026, 1, 19)}
    assert all(p.date.year >= 1990 for p in points)
