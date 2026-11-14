"""Блок «все годы» на странице показателя (14.11.2026, ADR-0031, пункт 2 утверждённого списка).

Страница показателя — главная страница ряда для Google: в серверном HTML все годы ряда ссылками на годовые
страницы; у стран мира — таблица «год — значение». До 20 строк целиком, иначе 12 и остаток внутри
``<details class="seo-more">`` (поисковик видит всё, человек — короткий блок). Оба языка.
"""

from __future__ import annotations

import re

import pytest

from app.services.locale import _locale_var
from app.services.seo_year_ui import all_years_block
from tests.test_seo_world_year import CODE_ANNUAL, world_year_client  # noqa: F401


def _rows(n: int):
    return [(2025 - i, f"/germany/indicator/de-gdp/{2025 - i}", f"{i}.5") for i in range(n)]


@pytest.fixture
def en():
    token = _locale_var.set("en")
    yield
    _locale_var.reset(token)


def test_short_series_is_shown_whole(en):
    html = all_years_block(_rows(20), head_year="Year", head_value="Value")
    assert "<details" not in html
    assert html.count("<tr><td><a ") == 20
    assert '<a href="/germany/indicator/de-gdp/2006">2006</a>' in html


def test_long_series_keeps_every_year_in_markup(en):
    html = all_years_block(_rows(46), head_year="Year", head_value="Value")
    visible, hidden = html.split('<details class="seo-more">', 1)
    assert visible.count("<tr><td><a ") == 12
    assert hidden.count("<tr><td><a ") == 34
    assert "<summary>All years: 1980–2013</summary>" in hidden
    assert re.findall(r">(\d{4})</a>", html) == [str(2025 - i) for i in range(46)]


def test_links_only_and_russian_summary():
    token = _locale_var.set("ru")
    try:
        html = all_years_block(_rows(5), head_year="", head_value=None, shown=0, collapse_above=0)
    finally:
        _locale_var.reset(token)
    assert html.startswith('<details class="seo-more"><summary>Все годы: 2021–2025</summary><ul class="seo-years">')
    assert "<table" not in html and html.count("<li>") == 5


def test_empty_rows():
    assert all_years_block([], head_year="Year", head_value="Value") == ""


@pytest.mark.parametrize("host, locale, h2_tail, head_year", [
    ("forecasteconomy.com", "en", " by year</h2>", "<th>Year</th>"),
    ("ru.forecasteconomy.com", "ru", " по годам</h2>", "<th>Год</th>"),
])
def test_world_card_lists_years_with_values(world_year_client, host, locale, h2_tail, head_year):  # noqa: F811
    card = world_year_client.get(
        f"/seo/world/germany/{CODE_ANNUAL}", headers={"Host": host, "X-FE-Locale": locale},
    )
    assert card.status_code == 200
    section = card.text.split(h2_tail, 1)[1].split("</section>", 1)[0]
    assert head_year in section
    years = re.findall(rf'href="/germany/indicator/{CODE_ANNUAL}/(\d{{4}})(?:\?[^"]*)?">\1</a></td><td>([^<]+)</td>', section)
    assert years and all(value.strip() for _year, value in years)
    assert [int(y) for y, _v in years] == sorted((int(y) for y, _v in years), reverse=True)
