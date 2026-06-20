"""Срезы E/F/G: управление аккаунтом, 152-ФЗ, хардненинг (ADR-0007)."""

from tests.conftest import csrf_headers
from tests.test_auth_oauth import fake_login


def _register(tc, email="user@example.com", password="supersecret1"):
    r = tc.post("/api/v1/auth/register", json={"email": email, "password": password, "consent": True})
    assert r.status_code == 201, r.text
    return r


# --- Срез E: set-password / unlink / logout-all ---

def test_set_password_for_oauth_only_then_login(oauth_client):
    fake_login(oauth_client, sub="sp1", email="sp1@example.com")
    r = oauth_client.post("/api/v1/auth/set-password",
                          json={"password": "newsecret123"}, headers=csrf_headers(oauth_client))
    assert r.status_code == 200, r.text
    assert r.json()["user"]["has_password"] is True
    oauth_client.post("/api/v1/auth/logout", headers=csrf_headers(oauth_client))
    login = oauth_client.post("/api/v1/auth/login", json={"email": "sp1@example.com", "password": "newsecret123"})
    assert login.status_code == 200


def test_unlink_identity_keeps_password(oauth_client):
    fake_login(oauth_client, sub="ul1", email="ul1@example.com")
    oauth_client.post("/api/v1/auth/set-password",
                      json={"password": "newsecret123"}, headers=csrf_headers(oauth_client))
    me = oauth_client.get("/api/v1/auth/me").json()["user"]
    ident_id = me["identities"][0]["id"]
    r = oauth_client.delete(f"/api/v1/auth/identities/{ident_id}", headers=csrf_headers(oauth_client))
    assert r.status_code == 200, r.text
    assert r.json()["user"]["identities"] == []


def test_cannot_unlink_last_method(oauth_client):
    fake_login(oauth_client, sub="last1", email="last1@example.com")
    me = oauth_client.get("/api/v1/auth/me").json()["user"]
    ident_id = me["identities"][0]["id"]
    r = oauth_client.delete(f"/api/v1/auth/identities/{ident_id}", headers=csrf_headers(oauth_client))
    assert r.status_code == 400


def _me_as(client, sess):
    client.cookies.clear()  # избегаем ambiguous jar; шлём один Cookie явно
    return client.get("/api/v1/auth/me", headers={"Cookie": f"fe_sess={sess}"})


def test_logout_all_kills_other_sessions(auth_client):
    # Имитируем два устройства одним клиентом: токены берём из response.cookies
    # (однозначно). Два одновременных TestClient невозможны — общий fakeredis на
    # одном event-loop.
    reg = _register(auth_client, email="multi@example.com")
    s1 = reg.cookies.get("fe_sess")
    login = auth_client.post("/api/v1/auth/login", json={"email": "multi@example.com", "password": "supersecret1"})
    s2 = login.cookies.get("fe_sess")
    assert s1 and s2 and s1 != s2
    assert _me_as(auth_client, s1).status_code == 200  # обе сессии живы

    # Текущий клиент держит s2 (последний вход). logout-all перевыпускает в s3.
    auth_client.cookies.clear()
    auth_client.cookies.set("fe_sess", s2)
    auth_client.cookies.set("XSRF-TOKEN", login.cookies.get("XSRF-TOKEN"))
    r = auth_client.post("/api/v1/auth/logout-all", headers=csrf_headers(auth_client))
    assert r.status_code == 200
    s3 = r.cookies.get("fe_sess")
    assert s3 and s3 not in (s1, s2)

    assert _me_as(auth_client, s1).status_code == 401  # старая выбита
    assert _me_as(auth_client, s3).status_code == 200  # текущая жива


def test_newsletter_toggle_in_cabinet(auth_client):
    # Регистрация без рассылки → newsletter=False; подписка/отписка из кабинета.
    _register(auth_client, email="nl@example.com")
    me = auth_client.get("/api/v1/auth/me").json()["user"]
    assert me["newsletter"] is False

    on = auth_client.post("/api/v1/auth/account/newsletter",
                          json={"subscribe": True}, headers=csrf_headers(auth_client))
    assert on.status_code == 200, on.text
    assert on.json()["user"]["newsletter"] is True

    off = auth_client.post("/api/v1/auth/account/newsletter",
                           json={"subscribe": False}, headers=csrf_headers(auth_client))
    assert off.status_code == 200
    assert off.json()["user"]["newsletter"] is False


# --- Срез F: 152-ФЗ ---

def test_export_returns_personal_data(auth_client):
    _register(auth_client, email="export@example.com")
    r = auth_client.get("/api/v1/auth/account/export")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.json()
    assert body["user"]["email"] == "export@example.com"
    assert any(c["kind"] == "pd" for c in body["consents"])


def test_delete_account_purges_and_allows_reregister(auth_client):
    _register(auth_client, email="del@example.com")
    r = auth_client.delete("/api/v1/auth/account", headers=csrf_headers(auth_client))
    assert r.status_code == 200
    assert auth_client.get("/api/v1/auth/me").status_code == 401
    # email освобождён → повторная регистрация проходит
    again = auth_client.post("/api/v1/auth/register",
                             json={"email": "del@example.com", "password": "supersecret1", "consent": True})
    assert again.status_code == 201


# --- Срез G: lockout 423 ---

def test_login_lockout_returns_423(auth_client):
    _register(auth_client, email="lock@example.com")
    auth_client.post("/api/v1/auth/logout", headers=csrf_headers(auth_client))
    for _ in range(8):
        r = auth_client.post("/api/v1/auth/login", json={"email": "lock@example.com", "password": "wrongpass1"})
        assert r.status_code == 401
    # Следующая попытка (даже с верным паролем) — заблокирована.
    r = auth_client.post("/api/v1/auth/login", json={"email": "lock@example.com", "password": "supersecret1"})
    assert r.status_code == 423
