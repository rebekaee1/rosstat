"""Bounded ingestion cursor → durable pending sessions → inactive analyses.

No top-N session sweep: every captured event passes an ascending ID cursor.
Queue registration commits before its durable Redis checkpoint. Late events
enqueue revisions regardless of the session's original start time. Redis
errors propagate so a lost cursor is never reported as successful coverage.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from app.config import settings
from app.core.cache import get_state_redis
from app.database import analytics_session
from app.models import BehaviorEvent, FrontendEvent, SessionAnalysisReport
from app.services.session_analysis import SCHEMA_VERSION, add_optional_narrative, ensure_report_row, load_session_report, persist_report

logger = logging.getLogger(__name__)
_CURSOR_KEY = "fe:session-analysis:ingested-event-cursor:v1"
_FRONTEND_CURSOR_KEY = "fe:session-analysis:frontend-event-cursor:v1"
_INGEST_BATCH = 2000
_SESSION_BATCH = 100
_INACTIVE = timedelta(minutes=30)
_WORK_BUDGET_SECONDS = 45


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def queue_session_revision(db, session_id, *, at=None, source_event_id=0):
    """Replay ingestion may call this for revisions without a behavior event."""
    row = await ensure_report_row(db, session_id)
    at = at or _now()
    row.pending_event_id = max(row.pending_event_id or 0, source_event_id)
    row.pending_at = max(row.pending_at, at) if row.pending_at else at
    row.due_at = row.pending_at + _INACTIVE
    row.status = "pending"
    return row


async def enqueue_event_batch(db, cursor, *, limit=_INGEST_BATCH, source="behavior"):
    model = FrontendEvent if source == "frontend" else BehaviorEvent
    rows = (await db.execute(select(model.id, model.session_id_hash, model.ingested_at)
                            .where(model.id > cursor).order_by(model.id).limit(limit))).all()
    grouped = {}
    for event in rows:
        if not event.session_id_hash:
            continue
        previous = grouped.get(event.session_id_hash)
        if previous:
            grouped[event.session_id_hash] = (max(previous[0], event.id), max(previous[1], event.ingested_at))
        else:
            grouped[event.session_id_hash] = (event.id, event.ingested_at)
    for sid, (event_id, at) in grouped.items():
        row = await db.get(SessionAnalysisReport, sid)
        reviewed = ((row.report_json or {}).get("freshness", {}).get("latest_frontend_event_id", 0) if source == "frontend" else row.latest_event_id) if row else 0
        if row and reviewed >= event_id:
            continue
        await queue_session_revision(db, sid, at=at, source_event_id=0 if source == "frontend" else event_id)
    return {"cursor": rows[-1].id if rows else cursor, "events_registered": len(rows), "sessions_registered": len(grouped)}


async def analyze_pending_batch(session_maker=analytics_session, *, now=None, limit=_SESSION_BATCH,
                                work_budget_seconds=_WORK_BUDGET_SECONDS):
    now = now or _now()
    deadline = time.monotonic() + work_budget_seconds
    limit = min(_SESSION_BATCH, max(1, limit))
    async with session_maker() as db:
        ids = (await db.execute(select(SessionAnalysisReport.session_id_hash).where(
            or_(SessionAnalysisReport.status.in_(["pending", "failed"]), SessionAnalysisReport.schema_version != SCHEMA_VERSION),
            or_(SessionAnalysisReport.due_at <= now, SessionAnalysisReport.due_at.is_(None)),
        ).order_by(SessionAnalysisReport.due_at, SessionAnalysisReport.session_id_hash).limit(limit))).scalars().all()
    completed = failed = 0
    for sid in ids:
        if time.monotonic() >= deadline:
            break
        try:
            async with session_maker() as db:
                row = await db.get(SessionAnalysisReport, sid)
                report = await load_session_report(db, sid, visual_review=row.visual_json if row else None)
                if report is None:
                    # Raw retention can remove evidence while a queue row survives.
                    row.status = "missing"
                    row.error = "No retained session evidence"
                else:
                    await db.commit()
                    report = await add_optional_narrative(report, enabled=bool(getattr(settings, "session_analysis_ai_enabled", False)))
                    await persist_report(db, report)
                await db.commit()
            completed += 1
        except Exception as exc:
            logger.warning("Session evidence build failed (%s)", type(exc).__name__)
            async with session_maker() as db:
                row = await db.get(SessionAnalysisReport, sid)
                if row:
                    row.status = "failed"
                    row.attempt_count = (row.attempt_count or 0) + 1
                    row.error = type(exc).__name__
                    row.due_at = now + timedelta(minutes=min(120, 5 * row.attempt_count))
                    await db.commit()
            failed += 1
    return {"completed": completed, "failed": failed, "deferred_in_batch": len(ids) - completed - failed,
            "batch_limit": limit}


async def session_analysis_job():
    if not getattr(settings, "session_analysis_enabled", False):
        return {"status": "disabled"}
    redis = await get_state_redis()
    raw = await redis.get(_CURSOR_KEY)
    cursor = int(raw or 0)
    frontend_cursor = int(await redis.get(_FRONTEND_CURSOR_KEY) or 0)
    async with analytics_session() as db:
        registration = await enqueue_event_batch(db, cursor)
        frontend_registration = await enqueue_event_batch(db, frontend_cursor, source="frontend")
        await db.commit()
    # Crash before checkpoint repeats idempotent registration; never skips it.
    await redis.set(_CURSOR_KEY, str(registration["cursor"]))
    await redis.set(_FRONTEND_CURSOR_KEY, str(frontend_registration["cursor"]))
    result = await analyze_pending_batch(analytics_session, limit=getattr(settings, "session_analysis_batch_size", 100))
    return {"status": "ok", **registration, "frontend_registration": frontend_registration, **result}
