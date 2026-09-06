"""Срез B: OAuth-флоу через fake-провайдер + матрица резолва идентичности (ADR-0007)."""

from urllib.parse import urlsplit, parse_qs

from tests.conftest import csrf_headers


def _path_q(location: str) -> str:
    parts = urlsplit(location)
    return parts.path + (("?" + parts.query) if parts.query else "")


def fake_login(tc, sub="u1", email="u1@example.com", verified=True, next="/account"):
    """Пройти весь fake OAuth-флоу login и вернуть финальный 302-ответ callback."""
    r1 = tc.get("/api/v1/auth/oauth/fake/start",
                params={"intent": "login", "next": next}, follow_redirects=False)
    assert r1.status_code == 302, r1.text
    authorize = urlsplit(r1.headers["location"])
    q = {k: v[0] for k, v in parse_qs(authorize.query).items()}
    q.update({"sub": sub, "email": email or "", "email_verified": "true" if verified else "false"})
    if not email:
        q["email"] = ""
    r2 = tc.get(authorize.path, params=q, follow_redirects=False)
    assert r2.status_code == 302, r2.text
    r3 = tc.get(_path_q(r2.headers["location"]), follow_redirects=False)
    assert r3.status_code == 302, r3.text
    return r3


def test_oauth_newsletter_consent_recorded(oauth_client):
    # Согласие на рассылку из всплывающего окна → newsletter=1 в start → Consent.
    r1 = oauth_client.get("/api/v1/auth/oauth/fake/start",
                          params={"intent": "login", "next": "/account", "newsletter": "1"},
                          follow_redirects=False)
    assert r1.status_code == 302, r1.text
    authorize = urlsplit(r1.headers["location"])
    q = {k: v[0] for k, v in parse_qs(authorize.query).items()}
    q.update({"sub": "nl-oauth", "email": "nloauth@example.com", "email_verified": "true"})
    r2 = oauth_client.get(authorize.path, params=q, follow_redirects=False)
    assert r2.status_code == 302
    r3 = oauth_client.get(_path_q(r2.headers["location"]), follow_redirects=False)
    assert r3.status_code == 302
    me = oauth_client.get("/api/v1/auth/me").json()["user"]
    assert me["newsletter"] is True


def _clear_oauth(monkeypatch):
    from app.config import settings
    for attr in ("oauth_yandex_client_id", "oauth_yandex_client_secret", "oauth_vk_client_id"):
        monkeypatch.setattr(settings, attr, "")


def test_providers_endpoint_empty_when_unconfigured(auth_client, monkeypatch):
    _clear_oauth(monkeypatch)
    r = auth_client.get("/api/v1/auth/oauth/providers")
    assert r.status_code == 200
    assert r.json()["providers"] == []


def test_providers_endpoint_lists_configured(auth_client, monkeypatch):
    from app.config import settings
    _clear_oauth(monkeypatch)
    monkeypatch.setattr(settings, "oauth_yandex_client_id", "cid")
    monkeypatch.setattr(settings, "oauth_yandex_client_secret", "sec")
    r = auth_client.get("/api/v1/auth/oauth/providers")
    assert r.json()["providers"] == ["yandex"]


def test_fake_login_new_user(oauth_client):
    fake_login(oauth_client, sub="new1", email="new1@example.com")
    me = oauth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()["user"]
    assert body["email"] == "new1@example.com"
    assert body["has_password"] is False
    assert body["identities"][0]["provider"] == "fake"


def test_fake_login_returning_same_sub_is_one_user(oauth_client):
    fake_login(oauth_client, sub="ret1", email="ret1@example.com")
    uid1 = oauth_client.get("/api/v1/auth/me").json()["user"]["id"]
    oauth_client.post("/api/v1/auth/logout", headers=csrf_headers(oauth_client))
    fake_login(oauth_client, sub="ret1", email="ret1@example.com")
    uid2 = oauth_client.get("/api/v1/auth/me").json()["user"]["id"]
    assert uid1 == uid2


def test_autolink_same_verified_email(oauth_client):
    fake_login(oauth_client, sub="link-a", email="shared@example.com", verified=True)
    uid1 = oauth_client.get("/api/v1/auth/me").json()["user"]["id"]
    oauth_client.post("/api/v1/auth/logout", headers=csrf_headers(oauth_client))
    # Другой sub, тот же ВЕРИФИЦИРОВАННЫЙ email → должен примкнуть к тому же User.
    fake_login(oauth_client, sub="link-b", email="shared@example.com", verified=True)
    uid2 = oauth_client.get("/api/v1/auth/me").json()["user"]["id"]
    assert uid1 == uid2
    assert len(oauth_client.get("/api/v1/auth/me").json()["user"]["identities"]) == 2


def test_no_autolink_unverified_email(oauth_client):
    fake_login(oauth_client, sub="nv-a", email="nv@example.com", verified=False)
    uid1 = oauth_client.get("/api/v1/auth/me").json()["user"]["id"]
    oauth_client.post("/api/v1/auth/logout", headers=csrf_headers(oauth_client))
    fake_login(oauth_client, sub="nv-b", email="nv@example.com", verified=False)
    uid2 = oauth_client.get("/api/v1/auth/me").json()["user"]["id"]
    assert uid1 != uid2  # неверифицированный email не мерджит аккаунты


def test_no_autolink_to_password_account(oauth_client):
    # Парольный аккаунт (email_verified=false на Phase 1).
    oauth_client.post("/api/v1/auth/register", json={
        "email": "victim@example.com", "password": "supersecret1", "consent": True,
    })
    pwd_uid = oauth_client.get("/api/v1/auth/me").json()["user"]["id"]
    oauth_client.post("/api/v1/auth/logout", headers=csrf_headers(oauth_client))
    # OAuth с тем же email (даже verified) НЕ должен захватить парольный аккаунт.
    fake_login(oauth_client, sub="attacker", email="victim@example.com", verified=True)
    oauth_uid = oauth_client.get("/api/v1/auth/me").json()["user"]["id"]
    assert oauth_uid != pwd_uid  # pre-hijack закрыт


def test_login_without_email_branch(oauth_client):
    fake_login(oauth_client, sub="noemail1", email=None)
    body = oauth_client.get("/api/v1/auth/me").json()["user"]
    assert body["email"] is None
    assert body["identities"][0]["provider"] == "fake"


def test_callback_state_mismatch_rejected(oauth_client):
    r1 = oauth_client.get("/api/v1/auth/oauth/fake/start", follow_redirects=False)
    assert r1.status_code == 302
    # Прямой переход на callback с чужим state (не совпадает с fe_oauth cookie).
    r = oauth_client.get("/api/v1/auth/oauth/fake/callback",
                         params={"code": "x", "state": "forged"}, follow_redirects=False)
    assert r.status_code == 302
    assert "error=oauth_state" in r.headers["location"]


def test_fake_disabled_without_flag(auth_client):
    # auth_client не включает fake → провайдер недоступен.
    r = auth_client.get("/api/v1/auth/oauth/fake/start", follow_redirects=False)
    assert r.status_code == 302
    assert "error=oauth_disabled" in r.headers["location"]


def test_fake_provider_forbidden_in_prod(monkeypatch):
    """ADR-0007: при debug=false включённый fake-провайдер роняет старт."""
    import pytest
    from fastapi.testclient import TestClient
    from app.config import settings

    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "auth_fake_provider_enabled", True)
    from app.main import app

    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass


def test_effective_auth_cookie_domain_shares_apex_and_ru(monkeypatch):
    from app.config import settings
    from app.security.auth import effective_auth_cookie_domain

    monkeypatch.setattr(settings, "auth_cookie_domain", "")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")
    assert effective_auth_cookie_domain() == ".forecasteconomy.com"


def test_effective_auth_cookie_domain_debug_stays_host_only(monkeypatch):
    from app.config import settings
    from app.security.auth import effective_auth_cookie_domain

    monkeypatch.setattr(settings, "auth_cookie_domain", "")
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")
    assert effective_auth_cookie_domain() == ""


def test_oauth_start_cookie_uses_shared_apex_domain(oauth_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_cookie_domain", "")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "public_base_url", "https://forecasteconomy.com")
    r = oauth_client.get("/api/v1/auth/oauth/fake/start", follow_redirects=False)
    assert r.status_code == 302
    header = r.headers.get("set-cookie", "")
    assert "fe_oauth=" in header
    assert "Domain=.forecasteconomy.com" in header


def _vk_start_settings(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "oauth_vk_client_id", "54644188")
    monkeypatch.setattr(
        settings,
        "oauth_vk_redirect_uri",
        "https://forecasteconomy.com/api/auth/vk/callback",
    )
    monkeypatch.setattr(settings, "auth_public_base_url", "https://forecasteconomy.com")


def test_vk_start_from_ru_hops_to_apex_before_vk(auth_client, monkeypatch):
    """VK ID режет Referer ru. как чужой базовый домен — сначала скачок на apex."""
    _vk_start_settings(monkeypatch)
    r = auth_client.get(
        "/api/v1/auth/oauth/vk/start",
        params={"intent": "login", "next": "/register"},
        headers={"X-Forwarded-Host": "ru.forecasteconomy.com"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://forecasteconomy.com/api/v1/auth/oauth/vk/start")
    assert "next=%2Fregister" in loc or "next=/register" in loc
    assert "id.vk.ru" not in loc


def test_vk_start_from_apex_goes_to_vk(auth_client, monkeypatch):
    _vk_start_settings(monkeypatch)
    r = auth_client.get(
        "/api/v1/auth/oauth/vk/start",
        params={"intent": "login", "next": "/register"},
        headers={"X-Forwarded-Host": "forecasteconomy.com"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://id.vk.ru/authorize")
    assert "redirect_uri=https%3A%2F%2Fforecasteconomy.com%2Fapi%2Fauth%2Fvk%2Fcallback" in loc


def test_vk_start_foreign_host_does_not_hop(auth_client, monkeypatch):
    _vk_start_settings(monkeypatch)
    r = auth_client.get(
        "/api/v1/auth/oauth/vk/start",
        headers={"X-Forwarded-Host": "evil.example"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "evil.example" not in r.headers["location"]
    assert r.headers["location"].startswith("https://id.vk.ru/authorize")
