import pytest

from app.database import get_db


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _ScalarsResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _FakeSession:
    def __init__(self):
        self.added = []

    async def execute(self, statement):
        text = str(statement)
        if "count" in text.lower():
            return _ScalarResult(0)
        return _ScalarsResult([])

    def add(self, item):
        self.added.append(item)
        if getattr(item, "id", None) is None:
            item.id = 1

    async def commit(self):
        return None

    async def refresh(self, item):
        if getattr(item, "id", None) is None:
            item.id = 1


@pytest.fixture
def fake_db(client):
    async def override_get_db():
        yield _FakeSession()

    client.app.dependency_overrides[get_db] = override_get_db
    yield
    client.app.dependency_overrides.pop(get_db, None)


def test_analytics_health_requires_token(client):
    response = client.get("/api/v1/analytics/health")
    assert response.status_code == 403


def test_analytics_health_with_token(client, monkeypatch, fake_db):
    from app.config import settings

    monkeypatch.setattr(settings, "analytics_api_token", "test-token")
    response = client.get("/api/v1/analytics/health", headers={"X-Analytics-Token": "test-token"})
    assert response.status_code == 200
    body = response.json()
    assert body["allowed_counter_ids"] == "107136069"


def test_event_collector_gated_by_own_flag(client, monkeypatch):
    """Приём событий развязан с analytics_enabled: гасится своим флагом."""
    from app.config import settings

    # analytics_enabled=False больше НЕ отключает first-party сбор.
    monkeypatch.setattr(settings, "analytics_enabled", False)
    monkeypatch.setattr(settings, "frontend_events_enabled", False)
    response = client.post(
        "/api/v1/analytics/events",
        json={"event_name": "test_event", "url": "https://forecasteconomy.com/"},
    )
    assert response.status_code == 200
    assert response.json()["accepted"] is False


def test_event_collector_accepts_guest(auth_client, monkeypatch):
    """Гость (без сессии): событие принимается и помечается authed=false."""
    from app.config import settings

    monkeypatch.setattr(settings, "analytics_enabled", False)  # не мешает сбору
    monkeypatch.setattr(settings, "frontend_events_enabled", True)
    r = auth_client.post(
        "/api/v1/analytics/events",
        json={"event_name": "indicator_view", "session_id": "guest-sess",
              "url": "https://forecasteconomy.com/indicator/cpi", "params": {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True and body["authed"] is False


def test_event_collector_attributes_authed_user(auth_client, monkeypatch):
    """Зарегистрированный: сервер резолвит сессию → событие authed=true."""
    from app.config import settings

    monkeypatch.setattr(settings, "frontend_events_enabled", True)
    reg = auth_client.post("/api/v1/auth/register", json={
        "email": "tracker@example.com", "password": "supersecret1", "consent": True,
    })
    assert reg.status_code == 201, reg.text

    # Кука fe_sess уже в auth_client → collect_event атрибутирует пользователя.
    r = auth_client.post(
        "/api/v1/analytics/events",
        json={"event_name": "download_csv", "session_id": "authed-sess",
              "url": "https://forecasteconomy.com/indicator/cpi", "params": {}},
    )
    assert r.status_code == 200
    assert r.json()["authed"] is True


def test_action_proposal_is_audited(client, monkeypatch, fake_db):
    from app.config import settings

    monkeypatch.setattr(settings, "analytics_api_token", "test-token")
    response = client.post(
        "/api/v1/analytics/actions/propose",
        headers={"X-Analytics-Token": "test-token"},
        json={
            "action_type": "webmaster.recrawl.submit",
            "target": {"host": "forecasteconomy.com"},
            "payload": {"url": "https://forecasteconomy.com/"},
            "reason": "Smoke proposal",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_approval"] is True
    assert body["safety_class"] == "low_risk_write"
