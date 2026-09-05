"""Гео-блок (аварийный) + bind-cookie: поисковики проходят, чужой /24 — 403."""
from datetime import datetime, timedelta, timezone

from starlette.responses import Response

from app.services import scrape_guard


def test_search_bot_ua_not_blocked(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", False)
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
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", False)
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
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", False)
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "SG")
    monkeypatch.setattr(
        scrape_guard, "geo_lookup", lambda ip: {"country_code": "SG"}
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4", ua="Chrome", path="/api/v1/health/ready"
    ) is None


def test_empty_setting_disables_block(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", False)
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "")
    monkeypatch.setattr(
        scrape_guard, "geo_lookup", lambda ip: {"country_code": "SG"}
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4", ua="Chrome", path="/"
    ) is None


def test_russia_not_blocked(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", False)
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "SG")
    monkeypatch.setattr(
        scrape_guard, "geo_lookup", lambda ip: {"country_code": "RU"}
    )
    assert scrape_guard.should_block(
        ip="5.6.7.8", ua="Chrome", path="/"
    ) is None


def test_poland_chrome_is_blocked_with_default_list(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", False)
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
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", False)
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
    monkeypatch.setattr(scrape_guard.settings, "scrape_challenge_enabled", False)
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
    monkeypatch.setattr(scrape_guard.settings, "scrape_challenge_enabled", False)
    d = scrape_guard.bind_decision(
        ip="8.8.8.10",
        ua="Mozilla/5.0 Chrome/145",
        path="/russia/region/moskva",
        cookie=None,
    )
    assert d.block is False
    assert d.set_cookie is True
    assert d.challenge is False


def test_html_without_cookie_is_challenge(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_challenge_enabled", True)
    d = scrape_guard.bind_decision(
        ip="8.8.8.10",
        ua="Mozilla/5.0 Chrome/145",
        path="/russia/indicator/cpi",
        cookie=None,
    )
    assert d.challenge is True
    assert d.block is False
    assert d.set_cookie is False


def test_api_without_cookie_blocked_when_challenge_on(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_challenge_enabled", True)
    d = scrape_guard.bind_decision(
        ip="8.8.8.10",
        ua="Mozilla/5.0 Chrome/145",
        path="/api/v1/ticker/live",
        cookie=None,
    )
    assert d.block is True
    assert d.challenge is False


def test_challenge_endpoint_exempt(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_challenge_enabled", True)
    d = scrape_guard.bind_decision(
        ip="8.8.8.10",
        ua="Mozilla/5.0 Chrome/145",
        path="/api/v1/scrape-challenge",
        cookie=None,
    )
    assert d.block is False
    assert d.challenge is False
    assert d.set_cookie is False


def test_search_bot_skips_challenge(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_challenge_enabled", True)
    d = scrape_guard.bind_decision(
        ip="8.8.8.10",
        ua="Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
        path="/russia/indicator/cpi",
        cookie=None,
    )
    assert d.challenge is False
    assert d.block is False


def test_automation_reason_cores_and_webgl():
    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    )
    assert scrape_guard.automation_reason({"hc": 8, "wd": 0, "plat": "MacIntel"}, ua) is None
    assert scrape_guard.automation_reason({"hc": 177, "wd": 0, "plat": "MacIntel"}, ua) == "CORES"
    assert scrape_guard.automation_reason({"hc": 8, "wd": 1, "plat": "MacIntel"}, ua) == "WEBDRIVER"
    assert scrape_guard.automation_reason(
        {"hc": 8, "webgl": "Google SwiftShader", "plat": "MacIntel"}, ua
    ) == "WEBGL"
    assert scrape_guard.automation_reason(
        {"hc": 8, "plat": "Linux x86_64"}, ua
    ) == "PLATFORM"


def test_bind_mismatch_html_is_challenge_again(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_challenge_enabled", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_secret", "test-secret")
    token = scrape_guard.issue_token("8.8.8.10")
    d = scrape_guard.bind_decision(
        ip="1.1.1.1",
        ua="Mozilla/5.0 Chrome/145",
        path="/russia/indicator/cpi",
        cookie=token,
    )
    assert d.challenge is True
    assert d.block is False
    assert d.set_cookie is False


def test_challenge_html_reloads_not_replace():
    html = scrape_guard.CHALLENGE_HTML
    assert "location.reload()" in html
    assert "location.replace" not in html
    assert "utm_referrer" in html
    assert "ysclid" in html
    assert "fe:attr:q" in html
    assert "mc.yandex.ru/metrika/tag.js" in html
    assert "107136069" in html
    assert "consent.js" not in html


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


def test_reduced_chrome_ua_is_not_blocked(monkeypatch):
    """Chrome 101+ шлёт Chrome/N.0.0.0 — это не признак Playwright."""
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", False)
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "")
    reduced = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    )
    cursor = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Cursor/3.18.25 Chrome/144.0.7559.236 "
        "Electron/40.10.3 Safari/537.36"
    )
    assert scrape_guard.should_block(ip="8.8.8.8", ua=reduced, path="/") is None
    assert scrape_guard.should_block(ip="8.8.8.8", ua=cursor, path="/") is None
    assert scrape_guard.should_block(
        ip="8.8.8.8",
        ua="Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
        path="/",
    ) is None


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


def test_hosting_asn_blocks_chrome(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "")
    monkeypatch.setattr(
        scrape_guard,
        "lookup_asn",
        lambda ip: {"asn": 24940, "org": "Hetzner Online GmbH"},
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4",
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0",
        path="/russia/indicator/cpi",
    ) == "HOSTING"


def test_hosting_org_blocks_without_known_asn(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "")
    monkeypatch.setattr(
        scrape_guard,
        "lookup_asn",
        lambda ip: {"asn": 999999, "org": "Alibaba Cloud LLC"},
    )
    assert scrape_guard.should_block(
        ip="47.82.201.239",
        ua="Mozilla/5.0 Chrome/145",
        path="/",
    ) == "HOSTING"


def test_hosting_skips_search_bot(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", True)
    monkeypatch.setattr(
        scrape_guard,
        "lookup_asn",
        lambda ip: {"asn": 24940, "org": "Hetzner Online GmbH"},
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4",
        ua="Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
        path="/",
    ) is None


def test_hosting_flag_off(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", False)
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "")
    monkeypatch.setattr(
        scrape_guard,
        "lookup_asn",
        lambda ip: {"asn": 24940, "org": "Hetzner Online GmbH"},
    )
    assert scrape_guard.should_block(
        ip="1.2.3.4", ua="Chrome", path="/"
    ) is None


def test_hosting_fail_open_without_asn(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "")
    monkeypatch.setattr(
        scrape_guard, "lookup_asn", lambda ip: {"asn": None, "org": None}
    )
    assert scrape_guard.should_block(ip="8.8.8.8", ua="Chrome", path="/") is None


def test_is_hosting_network_google_asn_not_listed():
    assert scrape_guard.is_hosting_network(15169, "GOOGLE") is False
    assert scrape_guard.is_hosting_network(24940, "Hetzner Online GmbH") is True
    assert scrape_guard.is_hosting_network(None, None) is False


def test_scrape_challenge_http_rejects_farm_cores(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "scrape_challenge_enabled", True)
    monkeypatch.setattr(settings, "scrape_block_hosting", False)
    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    )
    r = client.post(
        "/api/v1/scrape-challenge",
        json={"hc": 177, "plat": "MacIntel", "wd": 0},
        headers={"User-Agent": ua, "X-Forwarded-For": "8.8.8.8"},
    )
    assert r.status_code == 403
    assert "fe_bind" not in (r.headers.get("set-cookie") or "").lower()


def test_scrape_challenge_http_accepts_laptop(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "scrape_challenge_enabled", True)
    monkeypatch.setattr(settings, "scrape_block_hosting", False)
    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    )
    r = client.post(
        "/api/v1/scrape-challenge",
        json={"hc": 8, "plat": "MacIntel", "wd": 0, "webgl": "Apple M1"},
        headers={"User-Agent": ua, "X-Forwarded-For": "8.8.8.8"},
    )
    assert r.status_code == 204
