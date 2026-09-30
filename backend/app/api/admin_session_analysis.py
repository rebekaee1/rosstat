"""Admin-only session evidence, revisioned analyses and honest coverage."""
from __future__ import annotations

import base64
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_bi import require_admin
from app.database import get_analytics_db
from app.models import BehaviorEvent, BehaviorSession, FrontendEvent, SessionAnalysisReport, SessionReplayChunk, User
from app.services.analytics_period import resolve_period
from app.services.session_analysis import (
    SCHEMA_VERSION, add_optional_narrative, event_evidence, load_session_report,
    persist_report, public_path,
)
from app.session_analysis_schema import VisualReview

router = APIRouter(prefix="/admin/bi/session-analysis", tags=["admin-session-analysis"])


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _encode(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")


def _decode(cursor):
    try:
        if len(cursor) > 2000:
            raise ValueError("Oversized cursor")
        return json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except Exception as exc:
        raise HTTPException(422, "Invalid cursor") from exc


def _active_sessions(p, snapshot_id, frontend_snapshot_id, replay_snapshot_id):
    # Indexed period scan for a requested aggregate, never a scheduler scan.
    behavior = (select(BehaviorEvent.session_id_hash.label("session_id"), BehaviorEvent.occurred_at.label("at"),
                       BehaviorEvent.id.label("behavior_id"), literal(0).label("frontend_id"),
                       literal(0).label("replay_id"), literal(1).label("event_units"), literal(0).label("chunk_units"))
            .where(BehaviorEvent.session_id_hash.is_not(None), BehaviorEvent.id <= snapshot_id,
                   BehaviorEvent.occurred_at >= p.start, BehaviorEvent.occurred_at < p.end))
    frontend = (select(FrontendEvent.session_id_hash.label("session_id"), FrontendEvent.occurred_at.label("at"),
                       literal(0).label("behavior_id"), FrontendEvent.id.label("frontend_id"),
                       literal(0).label("replay_id"), literal(1).label("event_units"), literal(0).label("chunk_units"))
                .where(FrontendEvent.session_id_hash.is_not(None), FrontendEvent.id <= frontend_snapshot_id,
                       FrontendEvent.occurred_at >= p.start, FrontendEvent.occurred_at < p.end))
    # Replay-only coverage uses server receipt time, because original rrweb
    # timestamps live inside compressed payloads and are not a SQL period key.
    replay = (select(SessionReplayChunk.session_id_hash.label("session_id"), SessionReplayChunk.created_at.label("at"),
                     literal(0).label("behavior_id"), literal(0).label("frontend_id"), SessionReplayChunk.id.label("replay_id"),
                     literal(0).label("event_units"), literal(1).label("chunk_units"))
              .where(SessionReplayChunk.id <= replay_snapshot_id,
                     SessionReplayChunk.created_at >= p.start, SessionReplayChunk.created_at < p.end))
    source = union_all(behavior, frontend, replay).subquery()
    return (select(source.c.session_id, func.min(source.c.at).label("first_at"),
                   func.max(source.c.behavior_id).label("latest_event_id"),
                   func.max(source.c.frontend_id).label("latest_frontend_event_id"),
                   func.max(source.c.replay_id).label("latest_replay_chunk_id"),
                   func.sum(source.c.event_units).label("event_count"),
                   func.sum(source.c.chunk_units).label("replay_chunk_count")).group_by(source.c.session_id).subquery())


@router.get("/sessions")
async def sessions(period: str = "today", date_from: str | None = Query(None, alias="from"),
                   date_to: str | None = Query(None, alias="to"), limit: int = Query(50, ge=1, le=200),
                   cursor: str | None = None, _admin: User = Depends(require_admin),
                   db: AsyncSession = Depends(get_analytics_db)):
    p = resolve_period(period, date_from, date_to)
    if p.days > 90:
        raise HTTPException(422, "Session window cannot exceed 90 days")
    state = _decode(cursor) if cursor else None
    if state:
        try:
            if state["start"] != p.start.isoformat() or state["period"] != period:
                raise ValueError("Cursor belongs to another period")
            end = datetime.fromisoformat(state["end"])
            if end > p.end:
                raise ValueError("Cursor snapshot lies in the future")
            p = type(p)(p.start, end, p.preset, p.start_date, p.end_date)
            snapshot_id = int(state["snapshot_id"])
            frontend_snapshot_id = int(state["frontend_snapshot_id"])
            replay_snapshot_id = int(state["replay_snapshot_id"])
            if min(snapshot_id, frontend_snapshot_id, replay_snapshot_id) < 0 or state["from"] != p.start_date.isoformat() or state["to"] != p.end_date.isoformat():
                raise ValueError("Cursor bounds do not match the requested dates")
            last_time, last_id = datetime.fromisoformat(state["last_time"]), str(state["last_id"])
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, "Invalid cursor scope") from exc
    else:
        snapshot_id = await db.scalar(select(func.max(BehaviorEvent.id))) or 0
        frontend_snapshot_id = await db.scalar(select(func.max(FrontendEvent.id))) or 0
        replay_snapshot_id = await db.scalar(select(func.max(SessionReplayChunk.id))) or 0
        last_time = last_id = None
    active = _active_sessions(p, snapshot_id, frontend_snapshot_id, replay_snapshot_id)
    total = await db.scalar(select(func.count()).select_from(active)) or 0
    query = (select(active, BehaviorSession.browser, BehaviorSession.os, BehaviorSession.device_type,
                    SessionAnalysisReport.status.label("analysis_status"))
             .outerjoin(BehaviorSession, BehaviorSession.session_id_hash == active.c.session_id)
             .outerjoin(SessionAnalysisReport, SessionAnalysisReport.session_id_hash == active.c.session_id))
    if last_time is not None:
        query = query.where(or_(active.c.first_at > last_time, and_(active.c.first_at == last_time, active.c.session_id > last_id)))
    records = (await db.execute(query.order_by(active.c.first_at, active.c.session_id).limit(limit + 1))).mappings().all()
    has_more = len(records) > limit
    records = records[:limit]
    next_cursor = None
    if has_more:
        tail = records[-1]
        next_cursor = _encode({"start": p.start.isoformat(), "end": p.end.isoformat(), "period": period,
                               "from": p.start_date.isoformat(), "to": p.end_date.isoformat(),
                               "snapshot_id": snapshot_id, "frontend_snapshot_id": frontend_snapshot_id, "replay_snapshot_id": replay_snapshot_id,
                               "last_time": tail["first_at"].isoformat(), "last_id": tail["session_id"]})
    return {"items": [{**dict(r), "first_at": r["first_at"].isoformat() + "Z"} for r in records],
            "total_captured_sessions": total, "has_more": has_more, "next_cursor": next_cursor,
            "coverage": {"selection": "all_captured_sessions_via_pagination", "sampled": False,
                         "unit": "first_party_browser_session", "snapshot_event_id": snapshot_id,
                         "frontend_snapshot_event_id": frontend_snapshot_id, "replay_snapshot_chunk_id": replay_snapshot_id,
                         "period_clocks": {"events": "occurred_at_utc", "replay": "server_receipt_created_at_utc"}}, "period": p.to_meta()}


@router.get("/sessions/{session_id}/events")
async def events(session_id: str, limit: int = Query(500, ge=1, le=1000), cursor: str | None = None,
                 source: Literal["behavior", "frontend"] = "behavior",
                 _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_analytics_db)):
    if len(session_id) > 80:
        raise HTTPException(422, "Invalid session ID")
    state = _decode(cursor) if cursor else None
    model = FrontendEvent if source == "frontend" else BehaviorEvent
    try:
        if state and (state["session_id"] != session_id or state["source"] != source):
            raise ValueError("Cursor belongs to another session")
        snapshot_id = int(state["snapshot_id"]) if state else await db.scalar(select(func.max(model.id)).where(model.session_id_hash == session_id)) or 0
        after = int(state["after"]) if state else 0
        if after < 0 or snapshot_id < after:
            raise ValueError("Invalid event bounds")
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, "Invalid event cursor") from exc
    scope = (model.session_id_hash == session_id, model.id <= snapshot_id)
    total, origin = (await db.execute(select(func.count(model.id), func.min(model.occurred_at)).where(*scope))).one()
    records = (await db.execute(select(model).where(*scope, model.id > after).order_by(model.id).limit(limit + 1))).scalars().all()
    has_more = len(records) > limit
    records = records[:limit]
    next_cursor = _encode({"session_id": session_id, "source": source, "snapshot_id": snapshot_id, "after": records[-1].id}) if has_more else None
    return {"items": [event_evidence(r, origin) for r in records], "total_captured_events": total,
            "has_more": has_more, "next_cursor": next_cursor,
            "coverage": {"sampled": False, "selection": "all_retained_events_via_pagination", "source": source, "snapshot_event_id": snapshot_id,
                         "timeline_clock": "UTC occurred_at; relative_ms starts at this source's first retained event"}}


@router.get("/sessions/{session_id}/analysis")
async def analysis(session_id: str, ai: bool = False, _admin: User = Depends(require_admin),
                   db: AsyncSession = Depends(get_analytics_db)):
    if len(session_id) > 80:
        raise HTTPException(422, "Invalid session ID")
    stored = await db.get(SessionAnalysisReport, session_id)
    report = await load_session_report(db, session_id, visual_review=stored.visual_json if stored else None)
    if report is None:
        raise HTTPException(404, "Session not found")
    if stored and stored.report_json and stored.source_fingerprint == report["freshness"]["fingerprint"] and not ai:
        return stored.report_json
    # Release the analytics transaction before an optional external wait.
    await db.commit()
    from app.config import settings
    report = await add_optional_narrative(report, enabled=ai and bool(getattr(settings, "session_analysis_ai_enabled", False)))
    await persist_report(db, report)
    await db.commit()
    return report


@router.post("/sessions/{session_id}/visual-review")
async def visual_review(session_id: str, review: VisualReview, _admin: User = Depends(require_admin),
                        db: AsyncSession = Depends(get_analytics_db)):
    report = await load_session_report(db, session_id, visual_review=review)
    if report is None:
        raise HTTPException(404, "Session not found")
    own = [o for o in review.observations if o.provenance.source == "own_replay"]
    if own:
        fingerprint = report["coverage"]["replay"].get("fingerprint")
        if not fingerprint or any(o.provenance.replay_fingerprint != fingerprint for o in own):
            raise HTTPException(409, "Visual review does not match the current replay version")
        if review.status == "reviewed" and report["coverage"]["replay"].get("incomplete"):
            raise HTTPException(409, "Incomplete replay cannot establish complete visual coverage")
    await persist_report(db, report, visual_review=review)
    await db.commit()
    return report


@router.get("/summary")
async def summary(period: str = "today", date_from: str | None = Query(None, alias="from"),
                  date_to: str | None = Query(None, alias="to"), _admin: User = Depends(require_admin),
                  db: AsyncSession = Depends(get_analytics_db)):
    p = resolve_period(period, date_from, date_to)
    if p.days > 90:
        raise HTTPException(422, "Session window cannot exceed 90 days")
    snapshot = await db.scalar(select(func.max(BehaviorEvent.id))) or 0
    frontend_snapshot = await db.scalar(select(func.max(FrontendEvent.id))) or 0
    replay_snapshot = await db.scalar(select(func.max(SessionReplayChunk.id))) or 0
    active = _active_sessions(p, snapshot, frontend_snapshot, replay_snapshot)
    captured = await db.scalar(select(func.count()).select_from(active)) or 0
    # SQL selects the exact captured scope; stream all reports without raw events.
    joined = (select(SessionAnalysisReport.session_id_hash, SessionAnalysisReport.status, SessionAnalysisReport.report_json,
                     SessionAnalysisReport.latest_event_id, active.c.latest_event_id.label("source_latest"),
                     active.c.latest_frontend_event_id.label("frontend_source_latest"),
                     active.c.latest_replay_chunk_id.label("replay_source_latest"),
                     SessionAnalysisReport.schema_version)
              .join(active, active.c.session_id == SessionAnalysisReport.session_id_hash))
    counts = Counter()
    issue_counts = Counter()
    # Streaming reports avoids an arbitrary top-N denominator.
    stream = await db.stream(joined.execution_options(yield_per=1))
    async for row in stream:
        report = row.report_json or {}
        fresh = (row.schema_version == SCHEMA_VERSION and row.latest_event_id >= row.source_latest
                 and report.get("freshness", {}).get("latest_frontend_event_id", 0) >= row.frontend_source_latest
                 and report.get("freshness", {}).get("latest_replay_chunk_id", 0) >= row.replay_source_latest)
        counts["stored"] += 1
        if not fresh or row.status not in ("complete", "partial"):
            counts["stale_or_pending"] += 1
            continue
        counts["analyzed"] += 1
        counts["event_complete"] += int(bool(report.get("coverage", {}).get("event_complete")))
        status = report.get("coverage", {}).get("visual", {}).get("status", "not_reviewed")
        counts["visual_reviewed"] += int(status == "reviewed")
        counts["visual_partial"] += int(status == "partial")
        counts["dom_only"] += int(status == "dom_only")
        in_window = {e["id"] for e in report.get("evidence", [])
                     if e.get("occurred_at") and p.start <= datetime.fromisoformat(e["occurred_at"].replace("Z", "+00:00")).replace(tzinfo=None) < p.end}
        issue_counts.update({i["code"] for i in report.get("issues", []) if set(i.get("evidence_ids", [])) & in_window})
    recommendations = {"slow_inp": "Собрать атрибуцию медленных взаимодействий и проверить повторяющиеся target/страницы.",
                       "js_error": "Сопоставить повторяющиеся ошибки с состояниями интерфейса.",
                       "api_error": "Проверить повторяющиеся неуспешные запросы и пользовательский результат.",
                       "click_heuristic": "Проверить визуальные эпизоды с эвристическими флагами кликов.",
                       "block_visibility_legacy": "Переизмерить видимость с учётом перекрытия и фокуса; не считать старые impressions чтением."}
    return {"period": p.to_meta(), "unit": "first_party_browser_session", "total_captured_sessions": captured,
            "analyzed_sessions": counts["analyzed"], "event_complete_sessions": counts["event_complete"],
            "pending_or_missing_sessions": captured - counts["analyzed"], "stale_or_pending_reports": counts["stale_or_pending"],
            "visual_reviewed_sessions": counts["visual_reviewed"], "visual_partial_sessions": counts["visual_partial"],
            "dom_only_sessions": counts["dom_only"], "physical_humans": None, "satisfaction": "unknown",
            "issues": [{"code": code, "affected_analyzed_sessions": count, "denominator_analyzed_sessions": counts["analyzed"],
                        "denominator_captured_sessions": captured, "recommendation": recommendations.get(code)} for code, count in sorted(issue_counts.items())],
            "coverage": {"sampled": False, "collection_completeness": "unknown", "unanalysed_are_not_issue_free": True,
                         "period_clocks": {"events": "occurred_at_utc", "replay": "server_receipt_created_at_utc"}}}
