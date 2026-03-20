"""Pytest fixtures: отключаем планировщик ETL, чтобы тесты не трогали cron."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    from app.config import settings

    monkeypatch.setattr(settings, "scheduler_enabled", False)
    from app.main import app

    with TestClient(app) as tc:
        yield tc
