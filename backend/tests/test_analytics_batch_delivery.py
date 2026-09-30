"""A replayed behavior batch is acknowledged only after its DB commit."""
import asyncio
import hashlib
from datetime import datetime, timezone

import pytest
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import analytics
from app.database import get_db
from app.models import BehaviorEvent


@pytest.fixture
def delivery_client(auth_env, monkeypatch):
    from app.config import settings
    from app.services import analytics_alerts

    monkeypatch.setattr(settings, "behavior_events_enabled", True)

    async def no_alert(_):
        return None

    monkeypatch.setattr(analytics_alerts, "note_behavior_ingest", no_alert)

    async def db():
        async with auth_env["session_maker"]() as session:
            yield session

    app = FastAPI()
    app.include_router(analytics.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def payload(batch_id="commit-retry-batch"):
    return {"session_id": "synthetic-delivery-probe", "batch_id": batch_id,
            "events": [{"t": "dwell", "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "url": "/russia/indicator/fuel-ai95/2022", "ms": 1000}]}


def stored(auth_env):
    async def count():
        async with auth_env["session_maker"]() as db:
            return await db.scalar(select(func.count()).select_from(BehaviorEvent).where(
                BehaviorEvent.session_id_hash == hashlib.sha256(b"synthetic-delivery-probe").hexdigest()))
    return asyncio.run(count())


def test_failed_commit_releases_claim_and_same_batch_is_stored_on_retry(delivery_client, auth_env, monkeypatch):
    original = AsyncSession.commit
    attempts = 0

    async def fail_first_commit(self):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("injected commit failure")
        await original(self)

    monkeypatch.setattr(AsyncSession, "commit", fail_first_commit)
    body = payload()
    first = delivery_client.post("/api/v1/analytics/behavior", json=body)
    assert first.status_code == 500 and stored(auth_env) == 0
    retry = delivery_client.post("/api/v1/analytics/behavior", json=body)
    assert retry.status_code == 200 and retry.json()["stored"] == 1
    assert not retry.json().get("duplicate") and stored(auth_env) == 1
    committed_duplicate = delivery_client.post("/api/v1/analytics/behavior", json=body)
    assert committed_duplicate.json() == {"accepted": True, "stored": 0, "duplicate": True}
    assert stored(auth_env) == 1


def test_concurrent_pending_batch_is_retryable_until_the_owner_commits(delivery_client, auth_env, monkeypatch):
    original = AsyncSession.commit

    async def probe():
        entered, release = asyncio.Event(), asyncio.Event()

        async def wait_before_commit(self):
            entered.set()
            await release.wait()
            await original(self)

        monkeypatch.setattr(AsyncSession, "commit", wait_before_commit)
        body = payload("concurrent-batch")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=delivery_client.app), base_url="http://testserver") as client:
            first = asyncio.create_task(client.post("/api/v1/analytics/behavior", json=body))
            try:
                await asyncio.wait_for(entered.wait(), 2)
                marker = await auth_env["state_redis"].get("fe:beh:batch:v2:concurrent-batch")
                assert marker.startswith("pending:")
                pending = await client.post("/api/v1/analytics/behavior", json=body)
                assert pending.status_code == 503 and pending.headers["retry-after"] == "1"
                assert not pending.json().get("accepted") and not pending.json().get("duplicate")
            finally:
                release.set()
                committed = await first
            assert committed.status_code == 200 and committed.json()["stored"] == 1
            assert await auth_env["state_redis"].get("fe:beh:batch:v2:concurrent-batch") == "done"
            duplicate = await client.post("/api/v1/analytics/behavior", json=body)
            assert duplicate.json() == {"accepted": True, "stored": 0, "duplicate": True}

    asyncio.run(probe())
    assert stored(auth_env) == 1


def test_stale_owner_cannot_release_or_finalize_another_claim(auth_env):
    async def probe():
        claim = await analytics._claim_behavior_batch("replaced-lease")
        assert claim.state == "claimed"
        await auth_env["state_redis"].set(claim.key, "pending:another-request", ex=120)
        await analytics._finish_behavior_batch(claim, committed=False)
        assert await auth_env["state_redis"].get(claim.key) == "pending:another-request"
        await analytics._finish_behavior_batch(claim, committed=True)
        assert await auth_env["state_redis"].get(claim.key) == "pending:another-request"
    asyncio.run(probe())


def test_redis_unavailable_still_accepts_only_after_a_real_db_commit(delivery_client, auth_env, monkeypatch):
    import app.core.cache as cache

    async def unavailable():
        raise RuntimeError("injected Redis outage")

    monkeypatch.setattr(cache, "get_state_redis", unavailable)
    response = delivery_client.post("/api/v1/analytics/behavior", json=payload("redis-outage"))
    assert response.status_code == 200 and response.json() == {"accepted": True, "stored": 1}
    assert stored(auth_env) == 1


def test_legacy_precommit_marker_is_not_a_confirmed_duplicate(delivery_client, auth_env):
    asyncio.run(auth_env["state_redis"].set("fe:beh:batch:legacy-batch", "1", ex=3600))
    response = delivery_client.post("/api/v1/analytics/behavior", json=payload("legacy-batch"))
    assert response.status_code == 200 and response.json() == {"accepted": True, "stored": 1}
    assert stored(auth_env) == 1
