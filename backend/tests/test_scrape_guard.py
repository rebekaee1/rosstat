"""Гео-блок скрейпа: поисковики проходят, SG режется, здоровье — нет."""
from app.services import scrape_guard


def test_search_bot_ua_not_blocked(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "SG")
    monkeypatch.setattr(
        scrape_guard, "geo_lookup", lambda ip: {"country_code": "SG"}
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4",
        ua="Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
        path="/russia/indicator/cpi",
    ) is None


def test_singapore_chrome_is_blocked(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "SG")
    monkeypatch.setattr(
        scrape_guard, "geo_lookup", lambda ip: {"country_code": "SG"}
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4",
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        path="/russia/region/moskva",
    ) == "SG"


def test_health_skip_even_from_sg(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "SG")
    monkeypatch.setattr(
        scrape_guard, "geo_lookup", lambda ip: {"country_code": "SG"}
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4", ua="Chrome", path="/api/v1/health/ready"
    ) is None


def test_empty_setting_disables_block(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "")
    monkeypatch.setattr(
        scrape_guard, "geo_lookup", lambda ip: {"country_code": "SG"}
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4", ua="Chrome", path="/"
    ) is None


def test_russia_not_blocked(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "SG")
    monkeypatch.setattr(
        scrape_guard, "geo_lookup", lambda ip: {"country_code": "RU"}
    )
    assert scrape_guard.should_block(
        ip="5.6.7.8", ua="Chrome", path="/"
    ) is None
