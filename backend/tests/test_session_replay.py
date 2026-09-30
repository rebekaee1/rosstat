"""Bounded replay ingestion, privacy, reconstruction gaps and late revisions."""
import asyncio
import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from app.api import session_replay as api
from app.config import settings
from app.database import get_analytics_db, get_db
from app.models import SessionAnalysisReport, SessionReplayChunk
from app.services import session_replay as replay

UA = "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/149.0.0.0 Mobile Safari/537.36"


def batch(events=None, **kwargs):
    if events is None:
        events = [{"type": 2, "timestamp": 1000, "data": {"node": {"id": 1, "type": 0, "childNodes": []}}},
                  {"type": 3, "timestamp": 1500, "data": {"source": 3, "id": 1, "x": 0, "y": 20}}]
    return json.dumps({"events": events, **kwargs}, ensure_ascii=False)


def fragment(**kwargs):
    result = {"session_id": "session-a", "visitor_id": "visitor-a", "recording_id": "recording-a",
              "page": "/", "sequence": 0, "part": 0, "parts": 1, "data": batch(), "ended": True}
    result.update(kwargs)
    return result


def chunk(data, **kwargs):
    raw = data.encode()
    result = {"recording_id": "recording-a", "sequence": 0, "part": 0, "parts": 1, "ended": True,
              "page": "/", "payload_gzip": gzip.compress(raw), "payload_hash": hashlib.sha256(raw).hexdigest(),
              "raw_bytes": len(raw)}
    result.update(kwargs)
    return SimpleNamespace(**result)


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / "replay.sqlite"
    sync = create_engine(f"sqlite:///{path}")
    SessionReplayChunk.__table__.create(sync)
    SessionAnalysisReport.__table__.create(sync)
    sync.dispose()
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1")

    async def analytics_db():
        async with maker() as db:
            yield db

    async def no_public_db():
        raise AssertionError("replay must never retain the public DB pool")
        yield  # pragma: no cover

    app.dependency_overrides[get_analytics_db] = analytics_db
    app.dependency_overrides[get_db] = no_public_db
    monkeypatch.setattr(settings, "session_replay_enabled", True)
    monkeypatch.setattr(settings, "behavior_events_enabled", True)
    monkeypatch.setattr(settings, "session_replay_max_recording_bytes", 8_000_000)
    with TestClient(app, headers={"user-agent": UA}) as client:
        yield {"client": client, "app": app, "maker": maker}
    asyncio.run(engine.dispose())


def post(env, payload):
    return env["client"].post("/api/v1/analytics/replay", content=json.dumps(payload, ensure_ascii=True), headers={"content-type": "application/json"})


def read(env):
    env["app"].dependency_overrides[api.require_admin] = lambda: None
    sid = hashlib.sha256(b"session-a").hexdigest()
    return env["client"].get(f"/api/v1/admin/bi/session-analysis/sessions/{sid}/replay")


def db_run(env, callback):
    async def run():
        async with env["maker"]() as db:
            return await callback(db)
    return asyncio.run(run())


def test_idempotent_delivery_and_late_chunk_requeues_analysis(env):
    payload = fragment(ended=False)
    assert post(env, payload).json() == {"accepted": True}
    assert post(env, payload).json() == {"accepted": True, "duplicate": True}
    sid = hashlib.sha256(b"session-a").hexdigest()

    async def mark_complete(db):
        assert await db.scalar(select(func.count()).select_from(SessionReplayChunk)) == 1
        row = await db.get(SessionAnalysisReport, sid)
        assert row.status == "pending"
        row.status = "complete"
        row.latest_event_id = 20
        await db.commit()
    db_run(env, mark_complete)
    assert post(env, fragment(sequence=1, data=batch([]), ended=True)).json()["accepted"] is True

    async def check(db):
        row = await db.get(SessionAnalysisReport, sid)
        assert row.status == "pending"
        assert row.latest_event_id == 20
    db_run(env, check)
    result = read(env).json()
    assert result["incomplete"] is False
    assert result["event_count"] == 2
    assert result["pixel_reviewed"] is False and result["pixel_complete"] is False
    assert "canvas_content_not_recorded" in result["fidelity_limitations"]


def test_sequence_metadata_and_identity_cannot_change(env):
    assert post(env, fragment(part=0, parts=2, ended=False, data="{" )).status_code == 200
    for conflict in (fragment(part=1, parts=3, ended=False, data="}"),
                     fragment(part=1, parts=2, ended=True, data="}"),
                     fragment(part=0, parts=2, ended=False, data="changed"),
                     fragment(visitor_id="another-visitor", part=1, parts=2, ended=False, data="}"),
                     fragment(session_id="another-session", part=1, parts=2, ended=False, data="}")):
        assert post(env, conflict).status_code == 409
    assert post(env, fragment(part=1, parts=2, ended=False, data="}" )).json()["accepted"] is True


def test_recording_byte_limit_and_duplicate_at_limit(env, monkeypatch):
    payload = fragment(data=batch([], note="Привет"))
    size = len(payload["data"].encode())
    monkeypatch.setattr(settings, "session_replay_max_recording_bytes", size)
    assert post(env, payload).json()["accepted"] is True
    assert post(env, payload).json()["duplicate"] is True
    assert post(env, fragment(sequence=1)).json() == {"accepted": False, "reason": "recording_limit"}


def test_recording_row_cap(env, monkeypatch):
    monkeypatch.setattr(api, "MAX_RECORDING_ROWS", 1)
    assert post(env, fragment()).json()["accepted"] is True
    assert post(env, fragment(sequence=1)).json() == {"accepted": False, "reason": "recording_limit"}


def test_hourly_row_budget_spans_recordings_and_expires(env, monkeypatch):
    monkeypatch.setattr(api, "MAX_VISITOR_HOUR_ROWS", 2)
    for recording in ("recording-a", "recording-b"):
        assert post(env, fragment(recording_id=recording)).json()["accepted"] is True
    assert post(env, fragment(recording_id="recording-c")).json() == {"accepted": False, "reason": "visitor_hour_limit"}

    async def expire(db):
        await db.execute(update(SessionReplayChunk).values(created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)))
        await db.commit()
    db_run(env, expire)
    assert post(env, fragment(recording_id="recording-c")).json()["accepted"] is True


def test_hourly_byte_budget_spans_recordings(env, monkeypatch):
    payload = fragment()
    monkeypatch.setattr(api, "MAX_VISITOR_HOUR_BYTES", len(payload["data"].encode()))
    assert post(env, payload).json()["accepted"] is True
    assert post(env, fragment(recording_id="recording-b")).json() == {"accepted": False, "reason": "visitor_hour_limit"}
    assert post(env, fragment(recording_id="recording-b", visitor_id="visitor-b")).json()["accepted"] is True


@pytest.mark.parametrize("change", [
    {"data": ""}, {"data": "  "}, {"data": "\ud800"}, {"visitor_id": "\ud800"},
    {"page": "/account"}, {"page": "/%61ccount"}, {"page": "/%2561ccount"},
    {"page": "/%61ccount%3Fsecret"},
    {"page": "/public/../auth/login"}, {"page": "/public\\..\\admin"},
])
def test_invalid_fragments_are_generic_and_do_not_echo_input(env, change):
    response = post(env, fragment(**change))
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid replay fragment"}


def test_body_is_capped_before_json_or_model_validation(monkeypatch):
    received = 0

    async def receive():
        nonlocal received
        received += 1
        return {"type": "http.request", "body": b"private-data" * 2000, "more_body": True}

    def no_parse(_):
        raise AssertionError("oversized data reached validation")
    monkeypatch.setattr(api.ReplayFragment, "model_validate", no_parse)
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [(b"content-type", b"application/json")]}, receive)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api._read_fragment(request))
    assert exc.value.status_code == 413
    assert "private-data" not in str(exc.value.detail)
    assert received == 3


def test_oversized_declared_body_and_cross_origin_are_rejected(env):
    response = env["client"].post("/api/v1/analytics/replay", content="private-data", headers={"content-type": "application/json", "content-length": str(api.MAX_BODY_BYTES + 1)})
    assert response.status_code == 413 and "private-data" not in response.text
    assert env["client"].post("/api/v1/analytics/replay", json=fragment(), headers={"origin": "https://elsewhere.example"}).status_code == 403


@pytest.mark.parametrize("payload", ["[]", '"not an object"', '{"events":null}',
    '{"events":[{"type":2,"timestamp":1e309}]}', '{"events":[{"type":2,"timestamp":NaN}]}',
    '{"events":[{"type":2,"timestamp":true}]}', '{"events":[],"dropped":"bad"}',
    '{"events":[],"states":[{"state_id":"a","original_time_ms":Infinity}]}'])
def test_malformed_batches_are_coverage_gaps_not_server_errors(payload):
    result = replay.assemble_recordings([chunk(payload)])
    assert result["incomplete"] is True
    assert result["event_count"] == 0
    assert any(g["reason"] == "invalid_payload" for g in result["gaps"])
    json.dumps(result, allow_nan=False)


def test_missing_fragments_end_and_recordings_are_explicit():
    assert replay.assemble_recordings([])["gaps"] == [{"reason": "not_captured_or_expired"}]
    result = replay.assemble_recordings([chunk("{", part=0, parts=2, ended=False)])
    assert {g["reason"] for g in result["gaps"]} >= {"missing_fragment", "missing_full_snapshot", "end_not_received"}
    result = replay.assemble_recordings([chunk(batch(), sequence=4999)])
    assert any(g["reason"] == "missing_sequence" and g["to_sequence"] == 4998 for g in result["gaps"])
    assert len(result["gaps"]) < 10


def test_chronological_recordings_and_route_gaps_remain_in_original_timeline():
    early = chunk(batch(), recording_id="z-early")
    events = [{"type": 2, "timestamp": 5000, "data": {"node": {"id": 1, "type": 0, "childNodes": []}}},
              {"type": 3, "timestamp": 5500, "data": {"source": 3}}]
    later = chunk(batch(events), recording_id="a-later")
    result = replay.assemble_recordings([later, early])
    assert [r["recording_id"] for r in result["recordings"]] == ["z-early", "a-later"]
    assert [r["timeline_start_ms"] for r in result["recordings"]] == [0, 4000]
    assert result["original_start_ms"] == 1000
    assert result["original_end_ms"] == 5500
    assert result["original_duration_ms"] == 4500
    assert result["source_clock"]["kind"] == "client_epoch_ms"


def test_compressed_bomb_checksum_and_metadata_are_rejected():
    bomb = chunk(batch(), raw_bytes=1000, payload_gzip=gzip.compress(b"x" * 1_000_000))
    for row in (bomb, chunk(batch(), payload_hash="0" * 64), chunk(batch(), raw_bytes=0)):
        result = replay.assemble_recordings([row])
        assert result["incomplete"] is True and result["event_count"] == 0
        assert result["read_bytes"] <= replay.MAX_READ_BYTES


def test_server_sanitizes_input_urls_css_and_state_text():
    snapshot = {"type": 2, "timestamp": 1000, "data": {"node": {"type": 0, "id": 1, "childNodes": [
        {"type": 2, "id": 2, "tagName": "input", "attributes": {"value": "private-phrase", "placeholder": "person@example.test"}, "childNodes": []},
        {"type": 2, "id": 3, "tagName": "img", "attributes": {"src": "https://example.test/a?token=secret#fragment", "srcset": "https://example.test/a?secret=one 1x, https://example.test/b?secret=two 2x", "style": "background:url('/a?secret=three')", "data-email": "person@example.test"}, "childNodes": []},
    ]}}}
    event = {"type": 3, "timestamp": 1200, "data": {"source": 5, "text": "private-phrase", "id": 2}}
    state = {"state_id": "state-a", "original_time_ms": 1100, "page": "/?token=secret", "visible_text": "person@example.test +7 (999) 123-45-67", "boxes": [], "viewport": {"w": 339, "h": 500}}
    result = replay.assemble_recordings([chunk(batch([snapshot, event], states=[state]))])
    serialized = json.dumps(result)
    for private in ("private-phrase", "person@example.test", "token=secret", "secret=", "123-45-67", "#fragment"):
        assert private not in serialized
    assert result["dom_states"][0]["original_timestamp_ms"] == 1100
    assert result["dom_states"][0]["source"] == "dom_snapshot"
    assert result["dom_state_count"] == result["dom_states_returned_count"] == 1
    assert result["dom_states_complete"] is True


@pytest.mark.parametrize("root_id", [None, 1])
def test_blocked_nodes_preserve_rrweb_document_and_element_types(root_id):
    def element(node_id, tag, attrs=None, children=None):
        node = {"type": 2, "id": node_id, "tagName": tag,
                "attributes": attrs or {}, "childNodes": children or []}
        if root_id is not None:
            node["rootId"] = root_id
        return node

    doctype = {"type": 1, "id": 2, "name": "html", "publicId": "", "systemId": ""}
    if root_id is not None:
        doctype["rootId"] = root_id
    document = {"type": 0, "id": 1, "childNodes": [doctype, element(3, "html", children=[
        element(4, "head", children=[element(5, "script", children=[
            {"type": 3, "id": 6, "textContent": "private-script"}])]),
        element(7, "body", children=[
            element(8, "form", children=[element(9, "input", {"value": "private-value"})]),
            element(10, "div", {"data-private": "", "class": "private"}, [
                {"type": 3, "id": 11, "textContent": "private-region"}]),
            element(12, "iframe", {"src": "/account"}),
        ]),
    ])]}
    snapshot = {"type": 2, "timestamp": 1000, "data": {"node": document}}
    result = replay.assemble_recordings([chunk(batch([snapshot]))])
    actual = result["recordings"][0]["events"][0]["data"]["node"]
    assert actual["type"] == 0 and actual["childNodes"][0] == doctype
    html = actual["childNodes"][1]
    assert html["type"] == 2 and html["tagName"] == "html"
    head, body = html["childNodes"]
    placeholders = head["childNodes"] + body["childNodes"]
    assert [node["id"] for node in placeholders] == [5, 8, 10, 12]
    for node in placeholders:
        # Type 1 is DocumentType; inserting it inside HTML raises HierarchyRequestError.
        assert node["type"] == 2 and node["tagName"] == "div"
        assert node["attributes"] == {"class": "rr-block"} and node["childNodes"] == []
        assert node.get("rootId") == root_id
    assert "private-" not in json.dumps(actual)
    assert result["incomplete"] is False


def test_dom_state_limit_reports_the_omitted_semantic_coverage():
    states = [{"state_id": f"state-{i}", "original_time_ms": 2000 + i,
               "page": "/", "visible_text": "Public heading", "boxes": []}
              for i in range(replay.MAX_DOM_STATES + 1)]
    groups = [states[i:i + 200] for i in range(0, len(states), 200)]
    rows = [chunk(batch(states=group), sequence=i, ended=i == len(groups) - 1)
            for i, group in enumerate(groups)]
    result = replay.assemble_recordings(rows)
    assert result["event_count"] == 2 * len(groups)
    assert result["dom_state_count"] == replay.MAX_DOM_STATES + 1
    assert result["dom_states_returned_count"] == len(result["dom_states"]) == replay.MAX_DOM_STATES
    assert result["dom_states_complete"] is False and result["incomplete"] is True
    assert result["gaps"] == [{"reason": "dom_state_read_limit", "count": 1}]


def test_read_budget_applies_across_recordings_and_preserves_context(env, monkeypatch):
    payload = fragment()
    assert post(env, payload).json()["accepted"] is True
    assert post(env, fragment(recording_id="recording-b")).json()["accepted"] is True
    monkeypatch.setattr(replay, "MAX_READ_BYTES", len(payload["data"].encode()) + 1)
    result = read(env).json()
    assert result["read_bytes"] <= replay.MAX_READ_BYTES
    assert result["incomplete"] is True
    assert any(g["reason"] == "server_read_byte_limit" for g in result["gaps"])
    sid = hashlib.sha256(b"session-a").hexdigest()
    context = db_run(env, lambda db: replay.analysis_replay_context(db, sid))
    assert "recordings" not in context
    assert context["pixel_reviewed"] is False
    assert context["fidelity_limitations"] == result["fidelity_limitations"]


def test_svg_local_paint_references_and_numeric_geometry_are_preserved():
    attributes = {"d": "M 130 250 130 270 L 200 270 200 250", "points": "123456789 123456780 123456789 0",
                  "fill": "url(#gradient)", "clip-path": "url(#clip)", "xlink:href": "#shape",
                  "style": "filter:url('#blur');transform:matrix(1,0,0,1,123456789,987654321)",
                  "href": "#ordinary-navigation", "stroke": "url(https://example.test/a?private=secret)"}
    snapshot = {"type": 2, "timestamp": 1000, "data": {"node": {
        "type": 2, "id": 1, "tagName": "path", "attributes": attributes, "childNodes": [],
    }}}
    result = replay.assemble_recordings([chunk(batch([snapshot]))])
    actual = result["recordings"][0]["events"][0]["data"]["node"]["attributes"]
    assert actual["d"] == attributes["d"] and actual["points"] == attributes["points"]
    assert actual["fill"] == 'url("#gradient")' and actual["clip-path"] == 'url("#clip")'
    assert actual["xlink:href"] == "#shape"
    assert 'url("#blur")' in actual["style"]
    assert "123456789,987654321" in actual["style"]
    assert "#ordinary-navigation" not in actual["href"]
    assert "private=secret" not in actual["stroke"]


def test_replay_read_requires_admin_and_collection_uses_analytics_pool(env):
    assert post(env, fragment()).json()["accepted"] is True
    sid = hashlib.sha256(b"session-a").hexdigest()
    url = f"/api/v1/admin/bi/session-analysis/sessions/{sid}/replay"
    assert env["client"].get(url).status_code == 401

    def not_admin():
        raise HTTPException(404, "Not found")
    env["app"].dependency_overrides[api.require_admin] = not_admin
    assert env["client"].get(url).status_code == 404
