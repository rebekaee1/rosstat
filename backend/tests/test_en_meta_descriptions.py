"""Английский хост: description ≤ 160 знаков, в нём место и (у годовых) год — по типам страниц (14.11.2026).

Аудит шаблонов: годовая страница страны мира теряла страну («Inflation … in 2023»), годовая
страница региона мира писала «Official state gdp overview … observations», описания были 167–294
знаков и обрезались Google посреди фразы. `fit_meta` держит целые предложения с начала и не
режет на точке сокращения («St. Louis», «U.S.»).
"""

from __future__ import annotations

import html
import re

import pytest

from app.services.seo_renderer import META_DESCRIPTION_LIMIT_EN, fit_meta
from tests.test_seo_world_year import CODE_ANNUAL, CODE_MONTHLY, world_year_client  # noqa: F401
from tests.test_world_compare_frequency import frequency_client  # noqa: F401
from tests.test_world_subnational import subnational_client  # noqa: F401

EN = {"Host": "forecasteconomy.com", "X-FE-Locale": "en"}


def _desc(page: str) -> str:
    return html.unescape(re.search(r'<meta name="description" content="([^"]*)"', page).group(1))


def test_fit_meta_keeps_whole_sentences_and_abbreviations():
    text = (
        "Producer Price Index in United States: 287.93 as of August 2026. Dynamics over 1913–2026, "
        "chart and table. Source: Federal Reserve Bank of St. Louis."
    )
    assert fit_meta(text, 130) == text[: text.index(" Source")]
    assert fit_meta(text, 160) == text  # «St. Louis» не режется на точке сокращения
    assert fit_meta("Value: 5 %. Source: U.S. Bureau of Labor Statistics.", 60) == (
        "Value: 5 %. Source: U.S. Bureau of Labor Statistics."
    )
    assert fit_meta("Value: 5 %. Source: U.S. Bureau of Labor Statistics.", 30) == "Value: 5 %."
    long_word = fit_meta("word " * 60, 160)
    assert len(long_word) <= 160 and long_word.endswith("…")
    assert fit_meta("short", 160) == "short"


@pytest.mark.parametrize("path, place, year", [
    (f"/seo/world/germany/{CODE_ANNUAL}", "Germany", None),
    (f"/seo/world-indicator-year/germany/{CODE_ANNUAL}/2023", "Germany", "2023"),
    (f"/seo/world-indicator-year/germany/{CODE_MONTHLY}/2024", "Germany", "2024"),
    ("/seo/world/germany", "Germany", None),
])
def test_world_country_pages(world_year_client, path, place, year):  # noqa: F811
    desc = _desc(world_year_client.get(path, headers=EN).text)
    assert len(desc) <= META_DESCRIPTION_LIMIT_EN, desc
    assert place in desc, desc
    if year:
        assert year in desc, desc


def test_world_compare_page(frequency_client):  # noqa: F811
    desc = _desc(frequency_client.get("/seo/world-vs/germany-vs-japan/hicp-index", headers=EN).text)
    assert len(desc) <= META_DESCRIPTION_LIMIT_EN and "Germany" in desc and "Japan" in desc, desc


@pytest.mark.parametrize("path, year", [
    ("/seo/world/united-states/region/california/unemployment-rate", None),
    ("/seo/world/united-states/region/california/unemployment-rate/2024", "2024"),
    ("/seo/world/united-states/region/california", None),
])
def test_world_region_pages(subnational_client, path, year):  # noqa: F811
    response = subnational_client.get(path, headers=EN)
    assert response.status_code == 200
    desc = _desc(response.text)
    assert len(desc) <= META_DESCRIPTION_LIMIT_EN and "California" in desc, desc
    if year:
        assert year in desc and "United States" in desc, desc
        assert "observations for" not in desc  # прежний шаблон со строчным названием


def test_russian_host_keeps_longer_descriptions(world_year_client):  # noqa: F811
    """Русский хост не меняется: описание годовой страницы — прежний русский шаблон."""
    desc = _desc(world_year_client.get(
        f"/seo/world-indicator-year/germany/{CODE_ANNUAL}/2023",
        headers={"Host": "ru.forecasteconomy.com", "X-FE-Locale": "ru"},
    ).text)
    assert "Сравнение с прошлым годом" in desc
