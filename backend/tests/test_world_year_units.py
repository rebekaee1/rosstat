"""Годовые страницы стран мира: точность ряда и короткая единица справа от числа (14.11.2026).

Было: «7,7092 изменение за год, %», «−0,9119 изменение за год, % (−10,58 %)», «1 years ago»,
«Дата значения: 1 января 2023» у годового ряда, английская единица «3.58 annual change».
"""

from __future__ import annotations

import re

import pytest

from app.data.eurostat_units_ru import unit_suffix
from app.services.locale import _locale_var
from tests.test_seo_world_year import CODE_ANNUAL, CODE_SIBLING_M, world_year_client  # noqa: F401


@pytest.mark.parametrize("unit, expected", [
    ("annual change, %", "%"),
    ("annual change, pp", "pp"),
    ("annual change", ""),
    ("year-over-year change, %", "%"),
    ("in 2015 prices, million EUR", "million EUR"),
    ("per 1,000 people", "per 1,000 people"),
    ("% of GDP", "% of GDP"),
    ("billion $", "billion $"),
    # Русские единицы — как раньше.
    ("изменение за год, %", "%"),
    ("в постоянных ценах 2015 года, млн евро", "млн евро"),
    ("индекс (2015 = 100), среднегодовой", ""),
    ("% экономически активного населения", "% экономически активного населения"),
])
def test_unit_suffix_english_descriptions_are_not_units(unit, expected):
    assert unit_suffix(unit) == expected


def test_history_lines_use_series_format_and_english_singular():
    from datetime import date

    from app.services.seo_renderer import year_history_position_lines

    series = [(2021, 2.7648, date(2021, 1, 1)), (2022, 8.6211, date(2022, 1, 1)), (2023, 7.7092, date(2023, 1, 1))]
    token = _locale_var.set("en")
    try:
        lines = year_history_position_lines(
            year=2023, value=7.7092, series=series, code=None, unit="%",
            value_fmt=lambda v: f"{v:.2f}",
        )
    finally:
        _locale_var.reset(token)
    text = " ".join(lines)
    assert "8.62 % in 2022 (1 year ago)" in text and "1 years ago" not in text
    assert "7.7092" not in text and "8.6211" not in text


def test_percent_year_page_uses_short_unit_and_series_precision(world_year_client):  # noqa: F811
    html = world_year_client.get(
        f"/seo/world-indicator-year/germany/{CODE_SIBLING_M}/2023",
        headers={"Host": "ru.forecasteconomy.com", "X-FE-Locale": "ru"},
    ).text
    desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
    assert re.search(r"\d,\d{1,2} % экономически активного населения", desc), desc
    assert not re.search(r"\d,\d{3,}", desc), desc


def test_annual_year_page_value_date_is_the_year(world_year_client):  # noqa: F811
    html = world_year_client.get(
        f"/seo/world-indicator-year/germany/{CODE_ANNUAL}/2023",
        headers={"Host": "ru.forecasteconomy.com", "X-FE-Locale": "ru"},
    ).text
    assert "Дата значения: 2023<" in html
    assert "Дата значения: 1 января 2023" not in html
