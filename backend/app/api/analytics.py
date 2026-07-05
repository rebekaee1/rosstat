from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import AgentActionAudit, AnalyticsSyncRun, BehaviorEvent, Experiment, FrontendEvent
from app.security.auth import current_session
from app.services.action_policy import evaluate_action
from app.services.action_executor import execute_approved_action
from app.services.analytics_features import detect_page_opportunities, sync_run_impact, top_pages, top_search_phrases
from app.services.yandex_metrika_reporting import MetrikaReportingClient

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _require_analytics_token(x_analytics_token: str | None = Header(default=None)) -> None:
    if settings.analytics_api_token and x_analytics_token == settings.analytics_api_token:
        return
    raise HTTPException(status_code=403, detail="Analytics API token required")


class MetrikaQueryRequest(BaseModel):
    counter_id: str = Field(default="107136069")
    report_type: str = Field(default="data")
    metrics: list[str]
    dimensions: list[str] = Field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None
    filters: str | None = None
    limit: int = 100


class ActionProposal(BaseModel):
    action_type: str
    target: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    diff: dict[str, Any] | None = None
    reason: str | None = None


class FrontendEventIn(BaseModel):
    event_name: str
    session_id: str | None = None
    url: str | None = None
    referrer: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class BehaviorBatchIn(BaseModel):
    """Батч сырых поведенческих событий от behavior.js (буфер → sendBeacon)."""
    session_id: str | None = None
    authed: int = 0
    events: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/health", dependencies=[Depends(_require_analytics_token)])
async def analytics_health(db: AsyncSession = Depends(get_db)):
    last_runs_q = await db.execute(
        select(AnalyticsSyncRun).order_by(desc(AnalyticsSyncRun.started_at)).limit(10)
    )
    last_runs = last_runs_q.scalars().all()
    failed_count_q = await db.execute(
        select(func.count()).select_from(AnalyticsSyncRun).where(AnalyticsSyncRun.status == "failed")
    )
    return {
        "enabled": settings.analytics_enabled,
        "scheduler_enabled": settings.analytics_scheduler_enabled,
        "allowed_counter_ids": settings.analytics_allowed_counter_ids,
        "allowed_hosts": settings.analytics_allowed_hosts,
        "failed_sync_runs": failed_count_q.scalar_one(),
        "last_runs": [
            {
                "id": run.id,
                "source": run.source,
                "job_type": run.job_type,
                "status": run.status,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "records_processed": run.records_processed,
                "error_message": run.error_message,
            }
            for run in last_runs
        ],
    }


@router.post("/query/metrika", dependencies=[Depends(_require_analytics_token)])
async def query_metrika(payload: MetrikaQueryRequest):
    client = MetrikaReportingClient()
    response = await client.report(
        payload.report_type,  # type: ignore[arg-type]
        counter_id=payload.counter_id,
        metrics=payload.metrics,
        dimensions=payload.dimensions,
        date_from=payload.date_from,
        date_to=payload.date_to,
        filters=payload.filters,
        limit=payload.limit,
    )
    return {
        "request_hash": response.request_hash,
        "sampled": response.sampled,
        "sample_share": response.sample_share,
        "contains_sensitive_data": response.contains_sensitive_data,
        "data": response.data,
    }


@router.get("/pages", dependencies=[Depends(_require_analytics_token)])
async def analytics_pages(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
):
    return {"pages": await top_pages(db, date_from=date_from, date_to=date_to, limit=limit)}


@router.get("/search-phrases", dependencies=[Depends(_require_analytics_token)])
async def analytics_search_phrases(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    return {"phrases": await top_search_phrases(db, date_from=date_from, date_to=date_to, limit=limit)}


@router.get("/anomalies", dependencies=[Depends(_require_analytics_token)])
async def analytics_anomalies(db: AsyncSession = Depends(get_db)):
    opportunities = await detect_page_opportunities(db)
    return {"opportunities": [item.__dict__ for item in opportunities]}


@router.get("/deploy-impact", dependencies=[Depends(_require_analytics_token)])
async def analytics_deploy_impact(db: AsyncSession = Depends(get_db)):
    return {"recent_sync_runs": await sync_run_impact(db)}


@router.get("/experiments/bootstrap")
async def experiments_bootstrap(db: AsyncSession = Depends(get_db)):
    if not settings.analytics_enabled:
        return {"experiments": [], "flags": {}}
    rows = (
        await db.execute(select(Experiment).where(Experiment.status == "active"))
    ).scalars().all()
    flags: dict[str, Any] = {}
    experiments = []
    for experiment in rows:
        variants = experiment.variants_json or {}
        split = experiment.traffic_split_json or {}
        experiments.append({
            "key": experiment.key,
            "variants": variants,
            "traffic_split": split,
        })
        flags[experiment.key] = variants.get("default") if isinstance(variants, dict) else None
    return {"experiments": experiments, "flags": flags}


@router.post("/actions/propose", dependencies=[Depends(_require_analytics_token)])
async def propose_action(payload: ActionProposal, db: AsyncSession = Depends(get_db)):
    decision = evaluate_action(payload.action_type, {**payload.target, **payload.payload}, approved=False)
    action = AgentActionAudit(
        action_type=payload.action_type,
        safety_class=decision.safety_class.value,
        status="proposed",
        target_json=payload.target,
        payload_json=payload.payload,
        diff_json=payload.diff,
        reason=payload.reason or decision.reason,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return {
        "action_id": action.id,
        "allowed_now": decision.allowed,
        "requires_approval": decision.requires_approval,
        "safety_class": decision.safety_class,
        "reason": decision.reason,
    }


@router.post("/actions/{action_id}/apply", dependencies=[Depends(_require_analytics_token)])
async def apply_action(action_id: int, approval_token: str, db: AsyncSession = Depends(get_db)):
    action = await db.get(AgentActionAudit, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    expected = settings.analytics_api_token
    if not expected or approval_token != expected:
        raise HTTPException(status_code=403, detail="Invalid approval token")
    decision = evaluate_action(action.action_type, {**(action.target_json or {}), **(action.payload_json or {})}, approved=True)
    if not decision.allowed:
        raise HTTPException(status_code=409, detail=decision.reason)
    try:
        result = await execute_approved_action(action, approval_token=approval_token)
    except Exception as exc:
        action.status = "failed"
        action.error_message = str(exc)[:500]
        db.add(action)
        await db.commit()
        raise HTTPException(status_code=409, detail=str(exc))
    action.status = "approved"
    action.approval_token_hash = hashlib.sha256(approval_token.encode("utf-8")).hexdigest()
    action.response_json = result
    action.applied_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(action)
    await db.commit()
    return {"action_id": action.id, "status": action.status, "reason": decision.reason}


@router.post("/events")
async def collect_event(request: Request, payload: FrontendEventIn, db: AsyncSession = Depends(get_db)):
    # First-party телеметрия развязана с внешней Метрика-интеграцией: пишем
    # события всегда (питает «Пульс»), даже если analytics_enabled=false.
    if not settings.frontend_events_enabled:
        return {"accepted": False, "reason": "frontend events disabled"}
    session_hash = hashlib.sha256(payload.session_id.encode("utf-8")).hexdigest() if payload.session_id else None
    # Атрибуция аудитории. Эндпоинт — POST (не кэшируется), поэтому чтение
    # сессионной куки безопасно и не нарушает инвариант «не варьировать кэш по
    # куке». Резолв через state-Redis, без похода в БД: сессия несёт user_id.
    sess = await current_session(request)
    user_id = sess.get("user_id") if sess else None
    event = FrontendEvent(
        event_name=payload.event_name,
        session_id_hash=session_hash,
        user_id=str(user_id) if user_id else None,
        authed=bool(user_id),
        url=payload.url,
        referrer=payload.referrer or request.headers.get("referer"),
        params_json=payload.params,
        occurred_at=(payload.occurred_at or datetime.now(timezone.utc)).replace(tzinfo=None),
        ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(event)
    await db.commit()
    return {"accepted": True, "authed": bool(user_id)}


# Горячие поля батч-события, выносимые в колонки behavior_events; остальное
# уходит в params_json. Ключи совпадают с полями, которые шлёт behavior.js.
_BEHAVIOR_COLUMN_KEYS = {"t", "ts", "url", "pl", "path", "text", "x", "y", "dead", "rage"}
_BEHAVIOR_TYPES = {"pageview", "click", "move", "dwell", "copy"}


def _int_or_none(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


async def _upsert_behavior_session(
    db: AsyncSession, ev: dict, *, session_hash: str, user_id: str | None,
    authed: bool, occurred: datetime,
) -> None:
    """session_start → строка в behavior_sessions (портрет сессии/аудитории).

    Идемпотентно по PK session_id_hash (DO NOTHING) — повторная отправка
    (например, после restore вкладки) не перетирает первый портрет.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models import BehaviorSession
    from app.services.ua_parser import parse_user_agent

    ua = (str(ev.get("ua") or "") or None) and str(ev.get("ua"))[:500]
    parsed = parse_user_agent(ua)
    referrer = (str(ev.get("ref") or "") or None) and str(ev.get("ref"))[:1000]
    ref_host = None
    if referrer:
        try:
            from urllib.parse import urlparse
            ref_host = (urlparse(referrer).hostname or None) and urlparse(referrer).hostname[:200]
        except ValueError:
            ref_host = None

    values = {
        "session_id_hash": session_hash,
        "user_id": user_id,
        "authed": authed,
        "started_at": occurred,
        "entry_page": (str(ev.get("url") or "") or None) and str(ev.get("url"))[:500],
        "referrer": referrer,
        "referrer_host": ref_host,
        "utm_source": (str(ev.get("us") or "") or None) and str(ev.get("us"))[:120],
        "utm_medium": (str(ev.get("um") or "") or None) and str(ev.get("um"))[:120],
        "utm_campaign": (str(ev.get("uc") or "") or None) and str(ev.get("uc"))[:200],
        "ua_raw": ua,
        "browser": parsed["browser"],
        "browser_version": parsed["browser_version"],
        "os": parsed["os"],
        "os_version": parsed["os_version"],
        "device_type": parsed["device_type"],
        "screen_w": _int_or_none(ev.get("sw")),
        "screen_h": _int_or_none(ev.get("sh")),
        "viewport_w": _int_or_none(ev.get("vw")),
        "viewport_h": _int_or_none(ev.get("vh")),
        "dpr": ev.get("dpr") if isinstance(ev.get("dpr"), (int, float)) else None,
        "language": (str(ev.get("lang") or "") or None) and str(ev.get("lang"))[:16],
        "timezone": (str(ev.get("tz") or "") or None) and str(ev.get("tz"))[:60],
        "touch": bool(ev.get("touch")) if ev.get("touch") is not None else None,
    }
    if db.bind.dialect.name == "postgresql":
        stmt = pg_insert(BehaviorSession.__table__).values(**values).on_conflict_do_nothing(
            index_elements=["session_id_hash"]
        )
        await db.execute(stmt)
    else:  # sqlite в тестах
        from sqlalchemy import select as sa_select
        exists = await db.scalar(
            sa_select(BehaviorSession.session_id_hash).where(
                BehaviorSession.session_id_hash == session_hash
            )
        )
        if not exists:
            await db.execute(BehaviorSession.__table__.insert().values(**values))


@router.post("/behavior")
async def collect_behavior_batch(
    request: Request, payload: BehaviorBatchIn, db: AsyncSession = Depends(get_db)
):
    """Приём батча поведенческого потока (behavior.js). Bulk-insert одним
    executemany — при 100k посетителей/день вставка остаётся дешёвой."""
    if not settings.behavior_events_enabled:
        return {"accepted": False, "reason": "behavior events disabled"}
    events = payload.events[: settings.behavior_batch_max_events]
    if not events:
        return {"accepted": True, "stored": 0}

    session_hash = (
        hashlib.sha256(payload.session_id.encode("utf-8")).hexdigest()
        if payload.session_id else None
    )
    sess = await current_session(request)
    user_id = sess.get("user_id") if sess else None
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    rows = []
    sessions_stored = 0
    for ev in events:
        etype = str(ev.get("t") or "")[:20]
        try:
            occurred = datetime.fromtimestamp(int(ev["ts"]) / 1000, tz=timezone.utc).replace(tzinfo=None)
        except (KeyError, TypeError, ValueError, OSError):
            occurred = now
        if etype == "session_start" and session_hash:
            await _upsert_behavior_session(
                db, ev, session_hash=session_hash,
                user_id=str(user_id) if user_id else None,
                authed=bool(user_id) or bool(payload.authed),
                occurred=occurred,
            )
            sessions_stored += 1
            continue
        if etype not in _BEHAVIOR_TYPES:
            continue
        extra = {k: v for k, v in ev.items() if k not in _BEHAVIOR_COLUMN_KEYS}
        rows.append({
            "event_type": etype,
            "session_id_hash": session_hash,
            "page_load_id": (str(ev.get("pl") or "") or None) and str(ev.get("pl"))[:40],
            "user_id": str(user_id) if user_id else None,
            "authed": bool(user_id) or bool(payload.authed),
            "page": (str(ev.get("url") or "") or None) and str(ev.get("url"))[:500],
            "element_path": (str(ev.get("path") or "") or None) and str(ev.get("path"))[:400],
            "element_text": (str(ev.get("text") or "") or None) and str(ev.get("text"))[:120],
            "x": ev.get("x") if isinstance(ev.get("x"), int) else None,
            "y": ev.get("y") if isinstance(ev.get("y"), int) else None,
            "is_dead": bool(ev.get("dead")),
            "is_rage": bool(ev.get("rage")),
            "params_json": extra or None,
            "occurred_at": occurred,
            "ingested_at": now,
        })
    if rows:
        await db.execute(BehaviorEvent.__table__.insert(), rows)
    if rows or sessions_stored:
        await db.commit()
    return {"accepted": True, "stored": len(rows)}
