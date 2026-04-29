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
from app.models import AgentActionAudit, AnalyticsSyncRun, Experiment, FrontendEvent
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
    if not settings.analytics_enabled:
        return {"accepted": False, "reason": "analytics disabled"}
    session_hash = hashlib.sha256(payload.session_id.encode("utf-8")).hexdigest() if payload.session_id else None
    event = FrontendEvent(
        event_name=payload.event_name,
        session_id_hash=session_hash,
        url=payload.url,
        referrer=payload.referrer or request.headers.get("referer"),
        params_json=payload.params,
        occurred_at=(payload.occurred_at or datetime.now(timezone.utc)).replace(tzinfo=None),
        ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(event)
    await db.commit()
    return {"accepted": True}
