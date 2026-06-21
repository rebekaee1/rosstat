"""Pytest fixtures.

`client` — общий TestClient с выключенным планировщиком (без БД-хитов на startup).
`auth_client` — герметичная среда для личного кабинета (ADR-0007): схема в
временном SQLite, Redis → fakeredis. Без внешних postgres/redis, чтобы CI
(`pytest -q`, без сервисов) оставался зелёным.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _mute_telegram(monkeypatch: pytest.MonkeyPatch):
    """Тесты герметичны: Telegram не дёргаем НИКОГДА.

    Без этого `check-all` слал бы реальные уведомления админу — тесты создают
    десятки пользователей (register/oauth), каждый зовёт `notify_new_user` →
    `send_telegram`. Пустой токен → `send_telegram()` выходит ДО сетевого вызова
    (см. alerting.py). Runtime (реальные регистрации) не затрагивается.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "", raising=False)
    monkeypatch.setattr(settings, "telegram_chat_id", "", raising=False)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    from app.config import settings

    monkeypatch.setattr(settings, "scheduler_enabled", False)
    from app.main import app

    with TestClient(app) as tc:
        yield tc


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch):
    """Герметичное окружение identity: SQLite-схема + fakeredis + overrides."""
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    import fakeredis.aioredis

    from app.config import settings
    from app.models import Base
    from app.database import get_db
    import app.core.cache as cache_mod

    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "auth_cookie_secure", False)

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Схему создаём синхронным движком — независимо от event-loop'а TestClient.
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    async_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    TestSession = async_sessionmaker(async_engine, expire_on_commit=False)

    async def _override_get_db():
        async with TestSession() as session:
            yield session

    from app.main import app
    app.dependency_overrides[get_db] = _override_get_db

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    prev_redis = cache_mod._redis
    cache_mod._redis = fake

    yield {"app": app, "session_maker": TestSession, "redis": fake}

    app.dependency_overrides.pop(get_db, None)
    cache_mod._redis = prev_redis
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def auth_client(auth_env):
    with TestClient(auth_env["app"]) as tc:
        yield tc


@pytest.fixture
def oauth_client(auth_env, monkeypatch: pytest.MonkeyPatch):
    """Как auth_client, но с включённым fake OAuth-провайдером (dev/test)."""
    from app.config import settings

    monkeypatch.setattr(settings, "auth_fake_provider_enabled", True)
    monkeypatch.setattr(settings, "auth_public_base_url", "http://testserver")
    with TestClient(auth_env["app"]) as tc:
        yield tc


def csrf_headers(tc: TestClient) -> dict:
    """Заголовок double-submit из XSRF-TOKEN cookie текущей сессии."""
    token = tc.cookies.get("XSRF-TOKEN")
    return {"X-XSRF-TOKEN": token} if token else {}
