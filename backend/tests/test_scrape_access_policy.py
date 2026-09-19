"""Access-policy regressions; nginx checks are structural, not nginx -t."""
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.main import LocaleMiddleware, ScrapeGuardMiddleware, pick_client_ip
from app.services import scrape_guard


NGINX = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"


def nginx_directives():
    return "\n".join(line.split("#", 1)[0] for line in NGINX.read_text().splitlines())


def test_ssr_limits_have_no_ua_exemption_or_sitewide_bucket():
    config = nginx_directives()
    assert "zone=ssrall" not in config
    assert "limit_req_zone $binary_remote_addr zone=ssr:10m rate=5r/s;" in config
    assert "limit_req_zone $binary_remote_addr zone=ssrstrict:10m rate=2r/s;" in config
    assert "$ssr_limit_key" not in config


def test_og_resource_caps_remain_and_cover_direct_api():
    config = nginx_directives()
    assert "limit_req_zone $server_name zone=ogall:1m rate=8r/s;" in config
    assert "limit_conn_zone $server_name zone=ogconn:1m;" in config
    for location in ("location ^~ /og/", "location ^~ /api/v1/og-image/"):
        block = config.split(location, 1)[1].split("\n    }", 1)[0]
        assert "limit_req zone=ssrstrict burst=10 nodelay;" in block
        assert "limit_req zone=ogall burst=16 nodelay;" in block
        assert "limit_conn ogconn 4;" in block
        assert "limit_conn perip 8;" in block


def test_nginx_does_not_deny_browser_variants_by_ua():
    config = nginx_directives()
    assert "$bad_bot" not in config
    assert "real_ip_header X-Forwarded-For;" in config
    assert "real_ip_recursive on;" in config
    assert "set_real_ip_from 0.0.0.0/0;" not in config
    assert "set_real_ip_from ::/0;" not in config
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in config
    assert "$proxy_add_x_forwarded_for" not in config
    assert config.count("proxy_set_header X-Forwarded-For $remote_addr;") == config.count("proxy_set_header X-Forwarded-Host $host;")


@pytest.mark.parametrize("peer", ["8.8.8.8", "2606:4700:4700::1111", "testclient"])
def test_untrusted_socket_peer_cannot_spoof_ip(peer):
    assert pick_client_ip("1.1.1.1, 10.0.0.1", peer) == peer


def test_equivalent_ipv6_spellings_share_one_limit_key():
    assert pick_client_ip("2606:4700:4700:0:0:0:0:1111", "172.18.0.2") == "2606:4700:4700::1111"


@pytest.mark.parametrize("host,locale", [("ru.forecasteconomy.com", "ru"), ("forecasteconomy.com", "en")])
@pytest.mark.parametrize("cookie", [None, "invalid", "other-network"])
@pytest.mark.parametrize("path", ["/russia/indicator/cpi", "/api/v1/indicators/cpi/data"])
def test_first_visit_and_vpn_change_reach_handler(monkeypatch, host, locale, cookie, path):
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_countries", "SG,PL")
    monkeypatch.setattr(scrape_guard.settings, "scrape_block_hosting", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    monkeypatch.setattr(scrape_guard.settings, "scrape_challenge_enabled", True)
    monkeypatch.setattr(scrape_guard.settings, "apex_locale_en", True)
    monkeypatch.setattr(scrape_guard.settings, "geo_locale_redirect_enabled", False)
    monkeypatch.setattr(scrape_guard, "geo_lookup", lambda ip: {"country_code": "SG"}, raising=False)
    app = FastAPI()

    @app.get(path)
    async def page(request: Request):
        return {"path": request.url.path}

    app.add_middleware(ScrapeGuardMiddleware)
    app.add_middleware(LocaleMiddleware)
    headers = {"User-Agent": "Mozilla/5.0 Chrome/145.0.0.0", "X-Forwarded-For": "1.1.1.1"}
    if cookie:
        token = scrape_guard.issue_token("8.8.8.8") if cookie == "other-network" else cookie
        headers["Cookie"] = f"fe_bind={token}"
    async def behind_proxy(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": ("172.18.0.2", 40000)}
        await app(scope, receive, send)

    with TestClient(behind_proxy, base_url=f"https://{host}") as client:
        response = client.get(path, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"path": path}
    assert response.headers["Content-Language"] == locale
    assert "fe_bind=" in response.headers["set-cookie"]


def test_spoofed_search_ua_does_not_change_bind_policy(monkeypatch):
    monkeypatch.setattr(scrape_guard.settings, "scrape_bind_enabled", True)
    normal = scrape_guard.bind_decision(ip="1.1.1.1", ua="Chrome", path="/russia/indicator/cpi", cookie=None)
    spoof = scrape_guard.bind_decision(ip="1.1.1.1", ua="Googlebot", path="/russia/indicator/cpi", cookie=None)
    assert normal == spoof


def test_api_spoof_googlebot_is_limited_without_consuming_other_ip(monkeypatch):
    from app import main

    class Counter:
        def __init__(self):
            self.counts = {}

        async def eval(self, script, numkeys, key, window):
            self.counts[key] = self.counts.get(key, 0) + 1
            return self.counts[key]

    counter = Counter()

    async def redis():
        return counter

    monkeypatch.setattr(main, "get_redis", redis)
    monkeypatch.setattr(main.RateLimitMiddleware, "LIMIT", 2)
    app = FastAPI()

    @app.get("/api/v1/indicators/cpi/data")
    async def data():
        return {"ok": True}

    app.add_middleware(main.RateLimitMiddleware)

    async def behind_proxy(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": ("172.18.0.2", 40000)}
        await app(scope, receive, send)

    with TestClient(behind_proxy) as client:
        bot = {"User-Agent": "Googlebot", "X-Forwarded-For": "8.8.8.8"}
        statuses = [client.get("/api/v1/indicators/cpi/data", headers=bot).status_code for _ in range(3)]
        assert statuses == [200, 200, 429]
        assert client.get("/api/v1/indicators/cpi/data", headers={
            "User-Agent": "Mozilla/5.0 Chrome/145", "X-Forwarded-For": "1.1.1.1",
        }).status_code == 200
