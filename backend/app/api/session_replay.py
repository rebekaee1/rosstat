"""Bounded same-origin replay ingestion; recorded content is admin-only."""
from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError

from app.api.admin_bi import require_admin
from app.config import settings
from app.database import get_analytics_db
from app.models import SessionReplayChunk
from app.services.scrape_guard import is_noise_client_ua
from app.services.session_replay import (
    MAX_FRAGMENT_BYTES, MAX_READ_BYTES, load_session_replay, public_page,
)
from app.tasks.session_analysis import queue_session_revision

router = APIRouter(tags=["session-replay"])
MAX_BODY_BYTES = 65_536
MAX_RECORDING_ROWS = 2048
MAX_VISITOR_HOUR_ROWS = 4096
MAX_VISITOR_HOUR_BYTES = 16_000_000


class ReplayFragment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=160)
    visitor_id: str = Field(min_length=1, max_length=160)
    recording_id: str = Field(pattern=r"^[a-zA-Z0-9-]{8,40}$")
    page: str = Field(min_length=1, max_length=500)
    sequence: int = Field(ge=0, le=4999)
    part: int = Field(ge=0, le=1999)
    parts: int = Field(ge=1, le=2000)
    data: str = Field(min_length=1, max_length=8000)
    ended: bool = False

    @model_validator(mode="after")
    def valid_fragment(self):
        self.page = public_page(self.page)
        if self.part >= self.parts or not self.data.strip():
            raise ValueError("invalid fragment")
        try:
            self.session_id.encode("utf-8")
            self.visitor_id.encode("utf-8")
            raw = self.data.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("invalid fragment") from exc
        if len(raw) > MAX_FRAGMENT_BYTES:
            raise ValueError("invalid fragment")
        return self


def _invalid_json_constant(_value):
    raise ValueError("invalid JSON")


async def _read_fragment(request: Request) -> ReplayFragment:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(415, "Invalid replay request")
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) < 0:
                raise ValueError
            if int(length) > MAX_BODY_BYTES:
                raise HTTPException(413, "Replay request too large")
        except ValueError:
            raise HTTPException(400, "Invalid replay request") from None
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise HTTPException(413, "Replay request too large")
        body.extend(chunk)
    try:
        value = json.loads(body, parse_constant=_invalid_json_constant)
        return ReplayFragment.model_validate(value)
    except (ValidationError, ValueError, TypeError, UnicodeError, RecursionError):
        # Pydantic's normal error response includes the rejected input. Never
        # echo a DOM fragment, input value or identifier into an HTTP error.
        raise HTTPException(422, "Invalid replay fragment") from None


def _recording_limit():
    return max(0, min(settings.session_replay_max_recording_bytes, MAX_READ_BYTES))


async def _usage(db, predicate, row_cap):
    # LIMIT bounds the work even if an old recording already exceeds the cap.
    bounded = select(SessionReplayChunk.raw_bytes).where(*predicate).limit(row_cap + 1).subquery()
    count, size = (await db.execute(select(func.count(), func.coalesce(func.sum(bounded.c.raw_bytes), 0)).select_from(bounded))).one()
    return count, size


@router.get("/analytics/replay/config")
async def replay_config():
    return {"enabled": settings.session_replay_enabled and settings.behavior_events_enabled,
            "retention_days": settings.session_replay_retention_days,
            "max_recording_bytes": _recording_limit()}


@router.post("/analytics/replay")
async def collect_replay(request: Request, db=Depends(get_analytics_db)):
    if not settings.session_replay_enabled or not settings.behavior_events_enabled:
        return {"accepted": False, "reason": "disabled"}
    if is_noise_client_ua(request.headers.get("user-agent")):
        return {"accepted": False, "reason": "automation"}
    origin = request.headers.get("origin")
    if origin:
        try:
            parsed = urlsplit(origin)
        except ValueError:
            raise HTTPException(403, "Invalid replay origin") from None
        if parsed.scheme not in ("http", "https") or parsed.netloc != request.url.netloc:
            raise HTTPException(403, "Invalid replay origin")
    payload = await _read_fragment(request)
    sid = hashlib.sha256(payload.session_id.encode()).hexdigest()
    vid = hashlib.sha256(payload.visitor_id.encode()).hexdigest()
    raw = payload.data.encode("utf-8")
    checksum = hashlib.sha256(raw).hexdigest()
    if db.bind.dialect.name == "postgresql":
        # A recording may span workers/tabs. Lock the visitor first so rotating
        # recording IDs cannot race the rolling-hour quota.
        for key in ("replay-visitor:" + vid, "replay-recording:" + payload.recording_id):
            await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})
    scope = SessionReplayChunk.recording_id == payload.recording_id
    existing = (await db.execute(select(SessionReplayChunk).where(scope).limit(1))).scalar_one_or_none()
    if existing and (existing.session_id_hash != sid or existing.visitor_id_hash != vid or existing.page != payload.page):
        raise HTTPException(409, "Replay fragment conflict")
    sequence = (await db.execute(select(SessionReplayChunk).where(scope, SessionReplayChunk.sequence == payload.sequence).limit(1))).scalar_one_or_none()
    if sequence and (sequence.parts != payload.parts or sequence.ended != payload.ended):
        raise HTTPException(409, "Replay fragment conflict")
    duplicate = (await db.execute(select(SessionReplayChunk).where(
        scope, SessionReplayChunk.sequence == payload.sequence, SessionReplayChunk.part == payload.part,
    ))).scalar_one_or_none()
    if duplicate:
        if duplicate.payload_hash != checksum:
            raise HTTPException(409, "Replay fragment conflict")
        return {"accepted": True, "duplicate": True}
    rows, total = await _usage(db, (scope,), MAX_RECORDING_ROWS)
    if rows >= MAX_RECORDING_ROWS or total + len(raw) > _recording_limit():
        return {"accepted": False, "reason": "recording_limit"}
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    rows, total = await _usage(db, (
        SessionReplayChunk.visitor_id_hash == vid, SessionReplayChunk.created_at >= since,
    ), MAX_VISITOR_HOUR_ROWS)
    if rows >= MAX_VISITOR_HOUR_ROWS or total + len(raw) > MAX_VISITOR_HOUR_BYTES:
        return {"accepted": False, "reason": "visitor_hour_limit"}
    db.add(SessionReplayChunk(
        session_id_hash=sid, visitor_id_hash=vid, recording_id=payload.recording_id,
        page=payload.page, sequence=payload.sequence, part=payload.part, parts=payload.parts,
        payload_gzip=gzip.compress(raw), payload_hash=checksum, raw_bytes=len(raw), ended=payload.ended,
    ))
    try:
        await db.flush()
        await queue_session_revision(db, sid)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Replay fragment conflict") from None
    return {"accepted": True}


@router.get("/admin/bi/session-analysis/sessions/{session_id}/replay", dependencies=[Depends(require_admin)])
async def read_replay(session_id: str, db=Depends(get_analytics_db)):
    if len(session_id) != 64 or any(c not in "0123456789abcdef" for c in session_id):
        raise HTTPException(422, "Invalid session identifier")
    return await load_session_replay(db, session_id)


async def replay_retention_job():
    from app.database import analytics_session
    if settings.session_replay_retention_days <= 0:
        return
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=settings.session_replay_retention_days)
    async with analytics_session() as db:
        ids = select(SessionReplayChunk.id).where(SessionReplayChunk.created_at < cutoff).limit(5000)
        await db.execute(delete(SessionReplayChunk).where(SessionReplayChunk.id.in_(ids)))
        await db.commit()
