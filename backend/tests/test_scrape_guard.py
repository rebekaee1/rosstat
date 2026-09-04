"""Гео-блок (аварийный) + bind-cookie: поисковики проходят, чужой /24 — 403."""
from datetime import datetime, timedelta, timezone

from starlette.responses import Response

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


def test_poland_chrome_is_blocked_with_default_list(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "SG,PL")
    monkeypatch.setattr(
        scrape_guard, "geo_lookup", lambda ip: {"country_code": "PL"}
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4",
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        path="/",
    ) == "PL"


def test_googlebot_from_poland_not_blocked(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "SG,PL")
    monkeypatch.setattr(
        scrape_guard, "geo_lookup", lambda ip: {"country_code": "PL"}
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4",
        ua="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        path="/",
    ) is None


def test_ip_prefix_v4_slash24():
    assert scrape_guard.ip_network_prefix("8.8.8.10") == "8.8.8.0"
    assert scrape_guard.ip_network_prefix("8.8.8.250") == "8.8.8.0"
    assert scrape_guard.ip_network_prefix("8.8.4.1") == "8.8.4.0"


def test_ip_prefix_skips_private():
    assert scrape_guard.ip_network_prefix("10.0.0.5") is None
    assert scrape_guard.ip_network_prefix("127.0.0.1") is None
    assert scrape_guard.ip_network_prefix("testclient") is None


def test_ip_prefix_v6_slash48():
    a = scrape_guard.ip_network_prefix("2a00:1450:4001::1")
    b = scrape_guard.ip_network_prefix("2a00:1450:4001:ffff::9")
    c = scrape_guard.ip_network_prefix("2a00:1450:4002::1")
    assert a == b
    assert a != c


def test_token_same_slash24_different_hosts(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_secret", "test-secret")
    when = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    t1 = scrape_guard.issue_token("8.8.8.10", when=when)
    t2 = scrape_guard.issue_token("8.8.8.99", when=when)
    assert t1 == t2
    assert scrape_guard.verify_token(t1, "8.8.8.50", when=when)
    assert not scrape_guard.verify_token(t1, "1.1.1.1", when=when)


def test_token_accepts_yesterday(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_secret", "test-secret")
    now = datetime(2026, 9, 4, 0, 30, tzinfo=timezone.utc)
    yesterday = now - timedelta(days=1)
    token = scrape_guard.issue_token("8.8.8.10", when=yesterday)
    assert scrape_guard.verify_token(token, "8.8.8.10", when=now)


def test_bind_mismatch_blocks_api(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_secret", "test-secret")
    token = scrape_guard.issue_token("8.8.8.10")
    d = scrape_guard.bind_decision(
        ip="1.1.1.1",
        ua="Mozilla/5.0 Chrome/145",
        path="/api/v1/ticker/live",
        cookie=token,
    )
    assert d.block is True
    assert d.set_cookie is False


def test_bind_missing_cookie_allows_and_sets(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    d = scrape_guard.bind_decision(
        ip="8.8.8.10",
        ua="Mozilla/5.0 Chrome/145",
        path="/api/v1/ticker/live",
        cookie=None,
    )
    assert d.block is False
    assert d.set_cookie is True


def test_bind_search_bot_skips(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    token = scrape_guard.issue_token("8.8.8.10")
    d = scrape_guard.bind_decision(
        ip="1.1.1.1",
        ua="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        path="/api/v1/og-image/today.png",
        cookie=token,
    )
    assert d.block is False
    assert d.set_cookie is False


def test_bind_html_sets_cookie(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    d = scrape_guard.bind_decision(
        ip="8.8.8.10",
        ua="Mozilla/5.0 Chrome/145",
        path="/russia/region/moskva",
        cookie=None,
    )
    assert d.block is False
    assert d.set_cookie is True


def test_bind_private_ip_skips(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    d = scrape_guard.bind_decision(
        ip="127.0.0.1",
        ua="Chrome",
        path="/api/v1/ticker/live",
        cookie="garbage",
    )
    assert d.block is False
    assert d.set_cookie is False


def test_attach_bind_cookie_httponly(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_secret", "test-secret")
    monkeypatch.setattr(scrape_guard.settings, "auth_cookie_secure", False)
    resp = Response(status_code=200)
    scrape_guard.attach_bind_cookie(resp, "8.8.8.10")
    header = resp.headers.get("set-cookie", "")
    assert "fe_bind=" in header
    assert "HttpOnly" in header
    assert "samesite=lax" in header.lower()


def test_noise_ua():
    assert scrape_guard.is_noise_client_ua(
        "Mozilla/5.0 HeadlessChrome/145.0.0.0 Safari/537.36"
    )
    assert scrape_guard.is_noise_client_ua(
        "Mozilla/5.0 (Macintosh) Cursor/3.18.25 Chrome/144.0.7559.236 Electron/40.10.3"
    )
    assert not scrape_guard.is_noise_client_ua(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0"
    )
    assert not scrape_guard.is_noise_client_ua(
        "Mozilla/5.0 (compatible; YandexBot/3.0)"
    )
