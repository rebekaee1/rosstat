"""Backup freshness must survive cache eviction/FLUSHDB and rolling upgrades."""
import asyncio
import time
from datetime import datetime, timezone

import pytest
from fastapi import Response

from app.api import system


@pytest.mark.parametrize(
    "state_age,cache_age,expected,degraded",
    [(2, None, "2.0", False), (None, 3, "3.0", False),
     (40, 1, "40.0", True), (None, None, "never", False)],
)
def test_backup_state_precedence_and_legacy_fallback(monkeypatch, state_age, cache_age, expected, degraded):
    stamp = time.time()
    class Redis:
        def __init__(self, age):
            self.age = age
        async def ping(self):
            return True
        async def get(self, key):
            assert key == "fe:ops:pg_backup_last_ok"
            return None if self.age is None else str(stamp - self.age * 3600)
    class DB:
        async def execute(self, query):
            return None
        async def scalar(self, query):
            return datetime.now(timezone.utc).replace(tzinfo=None)
    async def cache():
        return Redis(cache_age)
    async def state():
        return Redis(state_age)
    monkeypatch.setattr(system, "get_redis", cache)
    monkeypatch.setattr(system, "get_state_redis", state)
    monkeypatch.setattr(system.settings, "scheduler_enabled", False)
    result = asyncio.run(system.health_ready(Response(), DB()))
    assert result["checks"]["pg_backup_age_hours"] == expected
    assert result["degraded"] is degraded
