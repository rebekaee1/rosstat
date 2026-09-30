"""Real sanitized GOLD evidence and diverse counterexamples to overclaiming."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models import BehaviorEvent, SessionAnalysisReport
from app.services.session_analysis import build_session_report
from app.session_analysis_schema import VisualReview


def event(eid, kind="pageview", *, page="/", params=None, **kw):
    return {"id": eid, "event_type": kind, "page": page, "params_json": params or {},
            "occurred_at": datetime(2026, 9, 30, 13) + timedelta(seconds=eid),
            "ingested_at": datetime(2026, 9, 30, 13) + timedelta(seconds=eid), **kw}


def gold():
    return json.loads((Path(__file__).parent / "fixtures/session_analysis_gold_home.json").read_text())


def review(*, status="partial", method="manual_view", intervals=None):
    return {"status": status, "original_duration_ms": 89000,
            "viewed_intervals": intervals or [], "observations": [{
                "observation_id": "cookie", "original_time_ms": 40000,
                "frame_id": "frame-40", "page": "/", "kind": "pointer_marker",
                "description": "Маркер действия находится в области кнопки; баннер остаётся видимым.",
                "provenance": {"source": "webvisor", "method": method,
                               "replay_id": "fixture-replay", "replay_fingerprint": "a" * 64,
                               "artifact_ref": "fixture://frame-40", "captured_at": "2026-09-30T17:00:00Z",
                               "model_id": "fixture-model" if method.startswith("multimodal") else None}}]}


def test_gold_full_evidence_does_not_turn_scroll_into_success():
    fixture = gold()
    result = build_session_report(fixture["session_id"], fixture["events"], portrait=fixture["portrait"])
    assert len(result["evidence"]) == 23
    assert result["coverage"]["captured_events"] == result["coverage"]["analyzed_events"] == 23
    assert result["coverage"]["event_complete"] is True
    assert result["metrics"]["route"] == ["/russia/indicator/gold-price/2009", "/"]
    assert result["metrics"]["max_scroll_pct"] == 100
    assert result["metrics"]["inp"][-1]["value_ms"] == 3744
    assert result["metrics"]["inp"][-1]["target"] is None
    assert result["coverage"]["satisfaction"] == result["coverage"]["task_outcome"] == "unknown"
    assert result["coverage"]["visual"]["pixel_reviewed"] is False
    assert {u["code"] for u in result["unknowns"]} >= {"inp_target", "block_visibility_legacy", "visual_review"}
    assert {r["issue_code"] for r in result["recommendations"]} == {"slow_inp"}
    assert all(e["occurred_at"].endswith("Z") for e in result["evidence"])
    encoded = json.dumps(result)
    assert "visitor_id_hash" not in encoded and "session_id_hash" not in encoded


def test_event_cap_is_disclosed_and_late_evidence_invalidates_fingerprint():
    rows = [event(1), event(2, "click")]
    full = build_session_report("fixture", rows)
    partial = build_session_report("fixture", rows, captured_count=3, latest_event_id=3)
    assert not partial["coverage"]["event_complete"]
    assert partial["coverage"]["captured_events"] == 3
    assert partial["freshness"]["fingerprint"] != full["freshness"]["fingerprint"]
    earlier_late = event(3, "click", occurred_at=datetime(2026, 9, 30, 12, 59))
    revised = build_session_report("fixture", rows + [earlier_late])
    assert revised["evidence"][0]["event_id"] == 3
    assert revised["freshness"]["latest_event_id"] == 3


def test_heuristics_and_dom_are_not_visual_bug_proof():
    result = build_session_report("fixture", [event(1, "click", is_dead=True, is_rage=True),
        event(2, "block_view", params={"block": "hero", "visibility_version": 3})],
        replay_context={"dom_states": [{"state_id": "s1", "source": "dom_snapshot", "original_time_ms": 1000,
                                        "visible_text": "Принять cookies", "page": "/"}]})
    assert result["analysis_mode"] == "events_and_dom"
    assert result["coverage"]["visual"]["status"] == "dom_only"
    assert result["coverage"]["visual"]["pixel_reviewed"] is False
    assert "block_visibility_legacy" not in {u["code"] for u in result["unknowns"]}
    assert "эвристические" in next(f["text"] for f in result["facts"] if f["id"] == "heuristic_clicks")


def test_visual_observations_require_provenance_and_continuous_coverage():
    incomplete = review(status="reviewed", intervals=[{"start_ms": 0, "end_ms": 5000}])
    with pytest.raises(ValidationError):
        VisualReview.model_validate(incomplete)
    snapshots = review(status="reviewed", method="multimodal_frames", intervals=[{"start_ms": 0, "end_ms": 89000}])
    with pytest.raises(ValidationError):
        VisualReview.model_validate(snapshots)
    invalid = review()
    invalid["observations"][0]["provenance"].pop("replay_fingerprint")
    with pytest.raises(ValidationError):
        VisualReview.model_validate(invalid)
    valid = review(status="reviewed", intervals=[{"start_ms": 0, "end_ms": 89000}])
    result = build_session_report("fixture", [event(1)], visual_review=valid)
    assert result["coverage"]["visual"]["status"] == "reviewed"
    assert result["coverage"]["task_outcome"] == "unknown"
    assert not result["inferences"]


def test_optional_ai_is_off_and_unconfigured_without_any_network(monkeypatch):
    from app.services.session_analysis import add_optional_narrative, settings
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: pytest.fail("No external call expected"))
    result = build_session_report("fixture", [event(1)])
    assert asyncio.run(add_optional_narrative(result))["ai"]["status"] == "disabled"
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    assert asyncio.run(add_optional_narrative(result, enabled=True))["ai"]["status"] == "not_configured"


def test_optional_ai_over_budget_has_no_network_and_keeps_full_local_facts(monkeypatch):
    from app.services import session_analysis as service
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: pytest.fail("Budget skip must not call externally"))
    monkeypatch.setattr(service.settings, "openrouter_api_key", "fixture-key")
    monkeypatch.setattr(service, "MAX_AI_INPUT_BYTES", 1)
    result = build_session_report("fixture", [event(1)])
    original_facts = list(result["facts"])
    result = asyncio.run(service.add_optional_narrative(result, enabled=True))
    assert result["ai"]["status"] == "skipped_input_budget"
    assert result["facts"] == original_facts
    assert result["coverage"]["event_complete"] is True


@pytest.mark.parametrize("invalid_kind", ["unknown_evidence", "invented_success"])
def test_optional_ai_validates_findings_and_retains_facts(monkeypatch, invalid_kind):
    from app.services import session_analysis as service
    import httpx
    content = {"inferences": [{"text": "Вероятно, посетитель изучал историю показателя.", "evidence_ids": ["missing" if invalid_kind == "unknown_evidence" else "e1"]}], "recommendations": []}
    if invalid_kind == "invented_success":
        content["inferences"][0]["text"] = "Посетитель доволен, задача выполнена."
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": json.dumps(content)}}]}
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            payload = kwargs["json"]["messages"][1]["content"]
            assert "session_id" not in payload and "visitor_id" not in payload
            return Response()
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr(service.settings, "openrouter_api_key", "fixture-key")
    result = build_session_report("fixture", [event(1)])
    facts = list(result["facts"])
    result = asyncio.run(service.add_optional_narrative(result, enabled=True))
    assert result["ai"]["status"] == "invalid"
    assert result["facts"] == facts and not result["inferences"]


def test_queue_processes_every_session_and_late_batch_without_starvation(auth_env):
    from sqlalchemy import select
    from app.tasks.session_analysis import enqueue_event_batch, analyze_pending_batch
    maker = auth_env["session_maker"]
    async def run():
        async with maker() as db:
            for i in range(205):
                row = event(i + 1)
                db.add(BehaviorEvent(**row, session_id_hash=f"fixture-{i:03d}"))
            await db.commit()
            first = await enqueue_event_batch(db, 0, limit=100)
            await db.commit()
            second = await enqueue_event_batch(db, first["cursor"], limit=200)
            await db.commit()
        assert first["events_registered"] == 100 and second["events_registered"] == 105
        now = datetime(2026, 10, 1)
        counts = [await analyze_pending_batch(maker, now=now, work_budget_seconds=120) for _ in range(3)]
        assert [r["completed"] for r in counts] == [100, 100, 5]
        async with maker() as db:
            late = event(206, "click", occurred_at=datetime(2026, 9, 30, 12))
            db.add(BehaviorEvent(**late, session_id_hash="fixture-000"))
            await db.commit()
            third = await enqueue_event_batch(db, second["cursor"])
            await db.commit()
            assert third["events_registered"] == 1
            row = await db.get(SessionAnalysisReport, "fixture-000")
            assert row.status == "pending"
        result = await analyze_pending_batch(maker, now=now, work_budget_seconds=120)
        assert result["completed"] == 1
        async with maker() as db:
            row = await db.get(SessionAnalysisReport, "fixture-000")
            assert row.event_count == 2 and row.latest_event_id == 206
    asyncio.run(run())


def test_business_outcome_and_revision_during_external_wait_are_preserved(auth_env):
    from app.models import FrontendEvent
    from app.services.session_analysis import load_session_report, persist_report
    from app.tasks.session_analysis import enqueue_event_batch, queue_session_revision
    maker = auth_env["session_maker"]
    async def run():
        async with maker() as db:
            original = event(1)
            db.add(BehaviorEvent(**original, session_id_hash="fixture-outcome"))
            db.add(FrontendEvent(id=1, event_name="download_csv", session_id_hash="fixture-outcome", url="/russia/indicator/gold-price",
                                 params_json={"indicator": "gold-price"}, occurred_at=original["occurred_at"], ingested_at=original["ingested_at"]))
            await db.commit()
            registration = await enqueue_event_batch(db, 0, source="frontend")
            assert registration["events_registered"] == 1
            await db.commit()
            report = await load_session_report(db, "fixture-outcome")
            assert report["coverage"]["sources"] == {"behavior_event": 1, "frontend_event": 1}
            assert report["outcomes"][0]["code"] == "client_export_dispatched"
            assert report["outcomes"][0]["file_saved"] == "unknown"
            assert report["coverage"]["satisfaction"] == "unknown"
            await db.commit()
            # Simulate a new replay chunk while the optional LLM is outside DB.
            async with maker() as other:
                await queue_session_revision(other, "fixture-outcome", at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=1), source_event_id=99)
                await other.commit()
            await persist_report(db, report)
            await db.commit()
        async with maker() as db:
            stored = await db.get(SessionAnalysisReport, "fixture-outcome")
            assert stored.status == "pending"
            assert stored.pending_event_id == 99
            assert stored.latest_event_id == 1
    asyncio.run(run())


def test_dom_epoch_times_use_a_known_clock_and_never_claim_screenshot():
    origin = datetime(2026, 9, 30, 13, 44, 20)
    from datetime import timezone
    epoch = round(origin.replace(tzinfo=timezone.utc).timestamp() * 1000)
    result = build_session_report("fixture", [event(1, occurred_at=origin)], replay_context={"dom_states": [
        {"state_id": "d1", "source": "dom_snapshot", "original_timestamp_ms": epoch + 4200, "page": "/", "visible_text": "Cookies",
         "viewport": {"w": 390, "h": 844}, "boxes": [{"x": 0, "y": 600, "w": 390, "h": 200,
                                                        "text": "Cookies", "tag": "aside", "block": "consent"}]}]})
    dom = next(e for e in result["evidence"] if e["source"] == "dom_snapshot")
    assert dom["relative_ms"] == 4200
    assert dom["source_clock"] == "epoch_ms"
    assert dom["pixel_verified"] is False
    assert dom["viewport"] == {"w": 390, "h": 844}
    assert dom["boxes"][0]["block"] == "consent"


def test_numeric_collector_flags_and_scroll_geometry_are_preserved():
    result = build_session_report("fixture", [event(1, "dwell", params={
        "scroll_version": 3, "scroll_valid": 1, "scroll_pct": 43,
        "scroll_height": 4000, "scroll_viewport": 800, "scroll_max_y": 1400}),
        event(2, "api_timing", params={"ok": 0, "st": 0, "ms": 2000})])
    assert result["metrics"]["scroll_measurement"] == "validated_geometry"
    assert result["metrics"]["valid_max_scroll_pct"] == 43
    assert result["evidence"][0]["params"]["scroll_viewport"] == 800
    assert result["evidence"][0]["params"]["scroll_max_y"] == 1400
    assert {r["issue_code"] for r in result["recommendations"]} == {"api_error"}


def test_admin_access_and_exact_event_pagination(auth_client, auth_env, monkeypatch):
    from app.api.admin_bi import require_admin
    from app.services import session_analysis as service
    root = "/api/v1/admin/bi/session-analysis"
    assert auth_client.get(root + "/sessions").status_code == 401
    async def admin(): return object()
    auth_client.app.dependency_overrides[require_admin] = admin
    maker = auth_env["session_maker"]
    async def seed():
        async with maker() as db:
            for i in range(1, 7):
                db.add(BehaviorEvent(**event(i), session_id_hash="fixture-pagination"))
            await db.commit()
    asyncio.run(seed())
    try:
        listing = auth_client.get(root + "/sessions", params={"period": "custom", "from": "2026-09-30", "to": "2026-09-30", "limit": 1})
        assert listing.status_code == 200, listing.text
        assert listing.json()["total_captured_sessions"] == 1
        cursor = None
        ids = []
        while True:
            response = auth_client.get(root + "/sessions/fixture-pagination/events", params={"limit": 2, **({"cursor": cursor} if cursor else {})})
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["total_captured_events"] == 6
            ids += [e["event_id"] for e in data["items"]]
            if not data["has_more"]: break
            cursor = data["next_cursor"]
        assert ids == list(range(1, 7))
        monkeypatch.setattr(service, "MAX_REPORT_EVENTS", 2)
        data = auth_client.get(root + "/sessions/fixture-pagination/analysis").json()
        assert data["coverage"]["captured_events"] == 6
        assert data["coverage"]["analyzed_events"] == 2
        assert not data["coverage"]["event_complete"]
        stats = auth_client.get(root + "/summary", params={"period": "custom", "from": "2026-09-30", "to": "2026-09-30"})
        assert stats.status_code == 200, stats.text
        assert stats.json()["total_captured_sessions"] == stats.json()["analyzed_sessions"] == 1
        assert stats.json()["event_complete_sessions"] == 0
        assert auth_client.get(root + "/sessions/fixture-pagination/events?cursor=broken").status_code == 422
    finally:
        auth_client.app.dependency_overrides.pop(require_admin, None)


def test_all_source_session_pagination_and_replay_only_analysis(auth_client, auth_env):
    import gzip
    import hashlib
    from app.api.admin_bi import require_admin
    from app.models import FrontendEvent, SessionReplayChunk
    from app.services.session_analysis import load_session_report
    from app.tasks.session_analysis import analyze_pending_batch, queue_session_revision
    root = "/api/v1/admin/bi/session-analysis"
    maker = auth_env["session_maker"]
    origin = datetime(2026, 9, 30, 13)
    epoch = round(origin.replace(tzinfo=timezone.utc).timestamp() * 1000)
    raw = json.dumps({"events": [{"type": 2, "timestamp": epoch, "data": {"node": {"id": 1, "type": 0, "childNodes": []}}}],
                      "states": [{"state_id": "s1", "original_timestamp_ms": epoch + 500,
                                  "visible_text": "Цена золота", "viewport": {"w": 390, "h": 844}, "overlay": False}]}).encode()
    async def seed():
        async with maker() as db:
            db.add(BehaviorEvent(**event(1), session_id_hash="fixture-behavior-only"))
            db.add(FrontendEvent(id=1, event_name="download_csv", session_id_hash="fixture-business-only", url="/",
                                 occurred_at=origin, ingested_at=origin, params_json={}))
            db.add(SessionReplayChunk(id=1, session_id_hash="fixture-replay-only", visitor_id_hash="fixture-visitor",
                                     recording_id="fixture-replay", page="/russia/indicator/gold-price", sequence=0, part=0, parts=1,
                                     payload_gzip=gzip.compress(raw), payload_hash=hashlib.sha256(raw).hexdigest(), raw_bytes=len(raw),
                                     ended=True, created_at=origin))
            await queue_session_revision(db, "fixture-replay-only", at=origin)
            await db.commit()
    asyncio.run(seed())
    async def admin(): return object()
    auth_client.app.dependency_overrides[require_admin] = admin
    params = {"period": "custom", "from": "2026-09-30", "to": "2026-09-30", "limit": 1}
    try:
        ids, cursor = [], None
        while True:
            response = auth_client.get(root + "/sessions", params={**params, **({"cursor": cursor} if cursor else {})})
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["total_captured_sessions"] == 3
            ids += [s["session_id"] for s in data["items"]]
            if not data["has_more"]: break
            cursor = data["next_cursor"]
        assert sorted(ids) == ["fixture-behavior-only", "fixture-business-only", "fixture-replay-only"]
        result = asyncio.run(analyze_pending_batch(maker, now=datetime(2026, 10, 1), work_budget_seconds=120))
        assert result["completed"] == 1
        report = auth_client.get(root + "/sessions/fixture-replay-only/analysis").json()
        assert report["coverage"]["captured_events"] == 0
        assert report["coverage"]["event_complete"] is False
        assert report["coverage"]["timeline_clock"] == "replay_client_epoch_ms"
        assert report["coverage"]["visual"]["status"] == "dom_only"
        assert report["coverage"]["visual"]["pixel_reviewed"] is False
        assert report["freshness"]["latest_replay_chunk_id"] == 1
        assert "event_stream_missing" in {u["code"] for u in report["unknowns"]}
        assert next(e for e in report["evidence"] if e["source"] == "dom_snapshot")["relative_ms"] == 500
        async def stable():
            async with maker() as db:
                newer = await load_session_report(db, "fixture-replay-only")
                assert newer["freshness"]["fingerprint"] == report["freshness"]["fingerprint"]
        asyncio.run(stable())
        stats = auth_client.get(root + "/summary", params={k: v for k, v in params.items() if k != "limit"}).json()
        assert stats["total_captured_sessions"] == 3
        assert stats["analyzed_sessions"] == stats["dom_only_sessions"] == 1
        assert stats["event_complete_sessions"] == 0
    finally:
        auth_client.app.dependency_overrides.pop(require_admin, None)


def test_absent_replay_is_not_reported_as_truncated_saved_dom_states():
    result = build_session_report('fixture', [event(1)], replay_context={
        'chunk_count': 0, 'dom_state_count': 0, 'dom_states': [], 'dom_states_complete': False,
        'gaps': [{'reason': 'not_captured_or_expired'}],
    })
    assert 'dom_state_budget' not in {u['code'] for u in result['unknowns']}
    assert result['coverage']['visual']['status'] == 'not_reviewed'
    assert result['coverage']['dom']['states_received'] == 0
