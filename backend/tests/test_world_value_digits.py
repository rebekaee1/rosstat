"""Точность чисел ряда страны мира на сервере — правило SPA (14.11.2026).

Случаи общие с фронтендом: ``frontend/src/lib/worldValueDigits.cases.json`` читает и
``worldValueDigits.test.js``. Сервер отступает только для рядов меньше единицы по модулю.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services.display import format_fixed, world_series_digits
from tests.test_seo_world_year import CODE_ANNUAL, world_year_client  # noqa: F401

CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "frontend/src/lib/worldValueDigits.cases.json").read_text("utf-8")
)


def _plain(text: str) -> str:
    return text.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2212", "-")


@pytest.mark.parametrize("case", CASES["cases"] + CASES["server_only"], ids=lambda c: str(c["values"]))
def test_same_digits_and_text_as_spa(case):
    digits = world_series_digits(case["values"])
    assert digits == case["digits"]
    assert _plain(format_fixed(case["values"][0], digits, locale="en")) == case["en"]
    assert _plain(format_fixed(case["values"][0], digits, locale="ru")) == case["ru"]


def test_format_fixed_typography_and_rounding():
    assert format_fixed(1234567.891, 2, locale="ru") == "1 234 567,89"
    assert format_fixed(-3.25, 1, locale="ru") == "\u22123,3"  # как toFixed: от нуля при равной близости
    assert format_fixed(2.5, 0, locale="en") == "3"
    assert format_fixed(-0.001, 2, locale="ru") == "0,00"  # округлилось до нуля — без минуса
    assert format_fixed(None, 2, locale="en") == "no data"


def test_digits_edge_cases():
    assert world_series_digits([]) == 2
    assert world_series_digits([None, 3.25]) == 2
    assert world_series_digits([5.0, 6.0]) == 0
    assert world_series_digits([0.5, 0.25, 0.123456]) == 4  # меньше единицы — до четырёх знаков


def test_world_card_uses_series_precision(world_year_client):  # noqa: F811
    """Карточка страны мира: лид, «Последние значения» и «по годам» — одна точность ряда."""
    html = world_year_client.get(
        f"/seo/world/germany/{CODE_ANNUAL}", headers={"Host": "forecasteconomy.com", "X-FE-Locale": "en"},
    ).text
    cells = re.findall(r"<td>([0-9][0-9,.  ]*)</td>", html)
    assert cells and all("." not in cell for cell in cells), cells  # численность — целые числа
