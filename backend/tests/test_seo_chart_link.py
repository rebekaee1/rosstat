"""Картинка графика на SEO-страницах — ссылка на живую карточку (пункт 10, 19.11.2026).

Пульс 134/135/141: картинка выглядела интерактивной. Ссылка `.seo-chart-link` уже
стоит у всех семейств; здесь закреплено, что: вся карточка графика нажимается
(подпись тоже), у ссылки есть подсказка на языке страницы, картинка и alt на месте.
"""
from bs4 import BeautifulSoup
import pytest

from app.services.locale import reset_locale, set_locale
from app.services.seo_renderer import (
    SEO_CRITICAL_CSS,
    _responsive_charts,
    _seo_chart_figure,
)


@pytest.mark.parametrize("locale,title", [
    ("ru", "Открыть интерактивный график"),
    ("en", "Open the interactive chart"),
])
def test_chart_link_has_localized_hint_and_keeps_image(locale, title):
    token = set_locale(locale)
    try:
        figure = _seo_chart_figure("/og/russia/cpi/2025.png", "ИПЦ 2025", "2025",
                                   href="/russia/indicator/cpi")
        html, _ = _responsive_charts(figure)
    finally:
        reset_locale(token)
    soup = BeautifulSoup(html, "html.parser")
    link = soup.select_one("figure.seo-chart > a.seo-chart-link")
    assert link["href"] == "/russia/indicator/cpi#chart"
    assert link["title"] == title
    img = link.find("img")
    assert img["alt"] == "ИПЦ 2025" and img["src"] == "/og/russia/cpi/2025.png"


def test_inline_family_figure_gets_hint_too():
    """Семейства со своей разметкой (мир, регионы) проходят тот же разбор."""
    body = ('<figure class="seo-chart"><a class="seo-chart-link" href="/germany/indicator/gdp#chart">'
            '<img src="/og/germany/gdp.png" alt="GDP" width="1200" height="630" loading="eager"></a>'
            '<figcaption>GDP</figcaption></figure>')
    token = set_locale("en")
    try:
        html, _ = _responsive_charts(body)
    finally:
        reset_locale(token)
    assert BeautifulSoup(html, "html.parser").select_one(".seo-chart-link")["title"] == "Open the interactive chart"


def test_figure_without_link_stays_plain():
    html, _ = _responsive_charts(_seo_chart_figure("/og/world/germany.png", "Hub", "Hub"))
    soup = BeautifulSoup(html, "html.parser")
    assert soup.select_one(".seo-chart-link") is None
    assert soup.img["alt"] == "Hub"


def test_whole_chart_card_is_clickable_in_critical_css():
    """Подпись под картинкой — часть ссылки: dead-клики по figcaption (19.11.2026)."""
    assert ".seo-chart-link::after{content:\"\";position:absolute;inset:0}" in SEO_CRITICAL_CSS
    chart_rule = SEO_CRITICAL_CSS.split(".seo-chart{", 1)[1].split("}", 1)[0]
    assert "position:relative" in chart_rule
