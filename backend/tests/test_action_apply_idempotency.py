"""F14: apply «действия аналитики» — намерение в аудит до внешнего вызова,
запрет повторного apply, статус `applying` при потере записи итога.

Внешние клиенты не вызываются: исполнитель подменён. БД — временный SQLite.
"""

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models import AgentActionAudit


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "analytics_api_token", "tok")
    # Политика пускает write только при включённых live writes (по умолчанию
    # выключены); в тесте внешний исполнитель подменён, реальные клиенты не зовутся.
    monkeypatch.setattr(settings, "analytics_live_writes_enabled", True)
    monkeypatch.setattr(settings, "analytics_allowed_counter_ids", "107136069", raising=False)
    monkeypatch.setattr(settings, "analytics_allowed_hosts", "forecasteconomy.com", raising=False)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'audit.db'}")
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: AgentActionAudit.__table__.create(c))

    asyncio.run(setup())
    yield maker
    asyncio.run(engine.dispose())


async def _new_action(maker, status="proposed"):
    async with maker() as db:
        row = AgentActionAudit(
            action_type="finding.create", safety_class="low_risk_write", status=status,
            target_json={}, payload_json={"title": "x"},
        )
        db.add(row)
        await db.commit()
        return row.id


async def _load(maker, action_id):
    async with maker() as db:
        return await db.get(AgentActionAudit, action_id)


def _apply(maker, action_id, token="tok"):
    from app.api.analytics import apply_action

    async def run():
        async with maker() as db:
            return await apply_action(action_id, token, db)

    return run()


def test_intent_committed_before_external_call_and_success_recorded(env, monkeypatch):
    seen = {}

    async def fake_exec(action, *, approval_token):
        # Во время внешнего вызова в БД (другая сессия) уже виден `applying`.
        row = await _load(env, action.id)
        seen["status_during"] = row.status
        seen["note_during"] = row.error_message
        return {"response": {"ok": True}, "request_hash": "h"}

    monkeypatch.setattr("app.api.analytics.execute_approved_action", fake_exec)

    async def scenario():
        aid = await _new_action(env)
        out = await _apply(env, aid)
        return aid, out

    aid, out = asyncio.run(scenario())
    assert out["status"] == "approved"
    assert seen["status_during"] == "applying"
    assert "сверьте" in seen["note_during"]
    row = asyncio.run(_load(env, aid))
    assert row.status == "approved"
    assert row.response_json["response"] == {"ok": True}
    assert row.error_message is None
    assert row.applied_at is not None
    assert row.approval_token_hash


@pytest.mark.parametrize("status", ["approved", "applying"])
def test_repeat_apply_refused_and_executor_not_called(env, monkeypatch, status):
    calls = []

    async def fake_exec(action, *, approval_token):
        calls.append(action.id)
        return {"response": {}, "request_hash": None}

    monkeypatch.setattr("app.api.analytics.execute_approved_action", fake_exec)

    async def scenario():
        aid = await _new_action(env, status=status)
        with pytest.raises(HTTPException) as e:
            await _apply(env, aid)
        return e.value

    exc = asyncio.run(scenario())
    assert exc.status_code == 409
    assert status in exc.detail
    assert calls == []


def test_second_apply_after_success_does_not_execute_twice(env, monkeypatch):
    calls = []

    async def fake_exec(action, *, approval_token):
        calls.append(1)
        return {"response": {}, "request_hash": None}

    monkeypatch.setattr("app.api.analytics.execute_approved_action", fake_exec)

    async def scenario():
        aid = await _new_action(env)
        await _apply(env, aid)
        with pytest.raises(HTTPException) as e:
            await _apply(env, aid)
        return e.value.status_code

    assert asyncio.run(scenario()) == 409
    assert calls == [1]


def test_concurrent_apply_executes_once(env, monkeypatch):
    calls = []

    async def fake_exec(action, *, approval_token):
        calls.append(1)
        await asyncio.sleep(0.05)
        return {"response": {}, "request_hash": None}

    monkeypatch.setattr("app.api.analytics.execute_approved_action", fake_exec)

    async def scenario():
        aid = await _new_action(env)
        return await asyncio.gather(_apply(env, aid), _apply(env, aid), return_exceptions=True)

    results = asyncio.run(scenario())
    assert len(calls) == 1
    assert sum(isinstance(r, HTTPException) and r.status_code == 409 for r in results) == 1


def test_executor_failure_marks_failed_and_allows_retry(env, monkeypatch):
    attempts = {"n": 0}

    async def fake_exec(action, *, approval_token):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("upstream 500")
        return {"response": {"ok": 1}, "request_hash": None}

    monkeypatch.setattr("app.api.analytics.execute_approved_action", fake_exec)

    async def scenario():
        aid = await _new_action(env)
        with pytest.raises(HTTPException) as e:
            await _apply(env, aid)
        failed = await _load(env, aid)
        out = await _apply(env, aid)
        return e.value.status_code, failed.status, failed.error_message, out["status"]

    code, st, msg, final = asyncio.run(scenario())
    assert (code, st, final) == (409, "failed", "approved")
    assert "upstream 500" in msg


def test_outcome_write_failure_leaves_applying_and_blocks_reexecution(env, monkeypatch):
    calls = []

    async def fake_exec(action, *, approval_token):
        calls.append(1)
        return {"response": {"ok": True}, "request_hash": None}

    monkeypatch.setattr("app.api.analytics.execute_approved_action", fake_exec)

    import app.api.analytics as mod

    real = mod._record_apply_outcome

    async def broken(db, action_id, values):
        if values.get("status") == "approved":
            raise ConnectionError("db went away")
        return await real(db, action_id, values)

    monkeypatch.setattr(mod, "_record_apply_outcome", broken)

    async def scenario():
        aid = await _new_action(env)
        with pytest.raises(HTTPException) as e:
            await _apply(env, aid)
        row = await _load(env, aid)
        # Повторный apply не выполняет действие второй раз.
        with pytest.raises(HTTPException) as again:
            await _apply(env, aid)
        return e.value, row, again.value

    first, row, again = asyncio.run(scenario())
    assert first.status_code == 500 and "reconcile" in first.detail
    assert row.status == "applying"
    assert "сверьте" in row.error_message  # пометка для ручной сверки
    assert again.status_code == 409
    assert calls == [1]


def test_invalid_token_does_not_touch_status(env, monkeypatch):
    async def fake_exec(action, *, approval_token):  # pragma: no cover
        raise AssertionError("must not run")

    monkeypatch.setattr("app.api.analytics.execute_approved_action", fake_exec)

    async def scenario():
        aid = await _new_action(env)
        with pytest.raises(HTTPException) as e:
            await _apply(env, aid, token="wrong")
        return e.value.status_code, (await _load(env, aid)).status

    assert asyncio.run(scenario()) == (403, "proposed")
