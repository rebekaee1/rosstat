"""Быстрые ссылки (чистые SSR-страницы) ведут на платформу: кнопка в первом экране, нажимаемые плитки, плавающая плашка."""
from bs4 import BeautifulSoup

from app.services.locale import reset_locale, set_locale
from app.services.seo_renderer import _prepare_quicklink_body

BODY = (
    '<main class="seo-page"><section class="seo-answer"><h1>Индекс в 2021 году</h1></section>'
    '<div class="seo-tiles"><div class="seo-tile"><span>Минимум</span><b>1</b></div>'
    '<div class="seo-tile"><span>Максимум</span><b>2</b></div></div></main>'
)


def _render(path, locale="ru"):
    token = set_locale(locale)
    try:
        return BeautifulSoup(_prepare_quicklink_body(BODY, path), "html.parser")
    finally:
        reset_locale(token)


def test_year_page_gets_hero_button_clickable_tiles_and_bar_to_the_indicator_card():
    soup = _render("/russia/indicator/housing-affordability/2021")
    target = "/russia/indicator/housing-affordability"
    assert soup.select_one(".seo-answer a.seo-bridge-hero")["href"] == target
    assert "Открыть интерактивный график" in soup.select_one(".seo-bridge-hero").get_text()
    tiles = soup.select("a.seo-tile")
    assert len(tiles) == 2 and all(t["href"] == target for t in tiles)
    assert not soup.select("div.seo-tile")
    assert soup.select_one("aside.seo-bridge-bar a.seo-bridge-go")["href"] == target


def test_page_without_indicator_card_leads_to_platform_home_and_keeps_tiles_plain():
    soup = _render("/russia/calendar/2026/05")
    assert soup.select_one(".seo-bridge-hero")["href"] == "/"
    assert soup.select_one(".seo-bridge-go")["href"] == "/"
    assert len(soup.select("div.seo-tile")) == 2


def test_english_copy_and_single_bar():
    soup = _render("/united-states/indicator/us-weo-ngdpd/2021", locale="en")
    assert "Open the interactive chart" in soup.select_one(".seo-bridge-hero").get_text()
    assert len(soup.select(".seo-bridge-bar")) == 1
