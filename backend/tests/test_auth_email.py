"""Срез A: регистрация/вход по email, сессии, CSRF (ADR-0007)."""

from tests.conftest import csrf_headers


def test_register_creates_session_and_me(auth_client):
    r = auth_client.post("/api/v1/auth/register", json={
        "email": "alice@example.com", "password": "supersecret1", "consent": True,
    })
    assert r.status_code == 201, r.text
    assert r.json()["user"]["email"] == "alice@example.com"
    assert "fe_sess" in auth_client.cookies
    assert "XSRF-TOKEN" in auth_client.cookies

    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "alice@example.com"
    assert me.json()["user"]["has_password"] is True


def test_register_requires_consent(auth_client):
    r = auth_client.post("/api/v1/auth/register", json={
        "email": "noconsent@example.com", "password": "supersecret1", "consent": False,
    })
    assert r.status_code == 422


def test_register_duplicate_email_conflict(auth_client):
    payload = {"email": "dup@example.com", "password": "supersecret1", "consent": True}
    assert auth_client.post("/api/v1/auth/register", json=payload).status_code == 201
    auth_client.post("/api/v1/auth/logout", headers=csrf_headers(auth_client))
    r2 = auth_client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


def test_register_email_normalized(auth_client):
    assert auth_client.post("/api/v1/auth/register", json={
        "email": "Mixed@Example.com", "password": "supersecret1", "consent": True,
    }).status_code == 201
    auth_client.post("/api/v1/auth/logout", headers=csrf_headers(auth_client))
    # Тот же email в другом регистре — это тот же аккаунт → конфликт.
    r = auth_client.post("/api/v1/auth/register", json={
        "email": "mixed@example.com", "password": "supersecret1", "consent": True,
    })
    assert r.status_code == 409
    # И вход проходит по нормализованному адресу.
    login = auth_client.post("/api/v1/auth/login", json={
        "email": "MIXED@EXAMPLE.COM", "password": "supersecret1",
    })
    assert login.status_code == 200


def test_login_wrong_password(auth_client):
    auth_client.post("/api/v1/auth/register", json={
        "email": "bob@example.com", "password": "supersecret1", "consent": True,
    })
    auth_client.post("/api/v1/auth/logout", headers=csrf_headers(auth_client))
    r = auth_client.post("/api/v1/auth/login", json={
        "email": "bob@example.com", "password": "wrongpassword",
    })
    assert r.status_code == 401


def test_login_success_and_session(auth_client):
    auth_client.post("/api/v1/auth/register", json={
        "email": "carol@example.com", "password": "supersecret1", "consent": True,
    })
    auth_client.post("/api/v1/auth/logout", headers=csrf_headers(auth_client))
    assert auth_client.get("/api/v1/auth/me").status_code == 401
    r = auth_client.post("/api/v1/auth/login", json={
        "email": "carol@example.com", "password": "supersecret1",
    })
    assert r.status_code == 200
    assert auth_client.get("/api/v1/auth/me").status_code == 200


def test_logout_invalidates_session(auth_client):
    auth_client.post("/api/v1/auth/register", json={
        "email": "dave@example.com", "password": "supersecret1", "consent": True,
    })
    assert auth_client.get("/api/v1/auth/me").status_code == 200
    r = auth_client.post("/api/v1/auth/logout", headers=csrf_headers(auth_client))
    assert r.status_code == 204
    assert auth_client.get("/api/v1/auth/me").status_code == 401


def test_me_unauthenticated(auth_client):
    assert auth_client.get("/api/v1/auth/me").status_code == 401


def test_logout_requires_csrf(auth_client):
    auth_client.post("/api/v1/auth/register", json={
        "email": "erin@example.com", "password": "supersecret1", "consent": True,
    })
    # Без заголовка X-XSRF-TOKEN → 403
    r = auth_client.post("/api/v1/auth/logout")
    assert r.status_code == 403
    # Сессия жива
    assert auth_client.get("/api/v1/auth/me").status_code == 200
