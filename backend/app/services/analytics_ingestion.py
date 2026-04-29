from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalyticsSyncRun,
    MetrikaCounterSnapshot,
    MetrikaReportSnapshot,
)
from app.services.yandex_client import YandexResponse


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def start_sync_run(
    db: AsyncSession,
    *,
    source: str,
    job_type: str,
    date_from: date | None = None,
    date_to: date | None = None,
    metadata: dict[str, Any] | None = None,
) -> AnalyticsSyncRun:
    run = AnalyticsSyncRun(
        source=source,
        job_type=job_type,
        status="running",
        date_from=date_from,
        date_to=date_to,
        metadata_json=metadata,
        started_at=utcnow_naive(),
    )
    db.add(run)
    await db.flush()
    return run


async def finish_sync_run(
    db: AsyncSession,
    run: AnalyticsSyncRun,
    *,
    status: str = "success",
    records_processed: int = 0,
    error_message: str | None = None,
    request_hash: str | None = None,
) -> AnalyticsSyncRun:
    run.status = status
    run.records_processed = records_processed
    run.error_message = error_message
    run.request_hash = request_hash
    run.completed_at = utcnow_naive()
    db.add(run)
    await db.flush()
    return run


async def store_metrika_report_snapshot(
    db: AsyncSession,
    *,
    counter_id: str,
    report_type: str,
    query: dict[str, Any],
    response: YandexResponse,
    date_from: date | None = None,
    date_to: date | None = None,
) -> MetrikaReportSnapshot:
    existing_q = await db.execute(
        select(MetrikaReportSnapshot).where(
            MetrikaReportSnapshot.counter_id == counter_id,
            MetrikaReportSnapshot.report_type == report_type,
            MetrikaReportSnapshot.query_hash == response.request_hash,
            MetrikaReportSnapshot.date_from == date_from,
            MetrikaReportSnapshot.date_to == date_to,
        )
    )
    existing = existing_q.scalar_one_or_none()
    if existing:
        existing.sampled = response.sampled
        existing.sample_share = response.sample_share
        existing.contains_sensitive_data = response.contains_sensitive_data
        existing.query_json = query
        existing.response_json = response.data if isinstance(response.data, dict) else {"raw": response.data}
        existing.captured_at = utcnow_naive()
        db.add(existing)
        await db.flush()
        return existing

    snapshot = MetrikaReportSnapshot(
        counter_id=counter_id,
        report_type=report_type,
        query_hash=response.request_hash,
        date_from=date_from,
        date_to=date_to,
        sampled=response.sampled,
        sample_share=response.sample_share,
        contains_sensitive_data=response.contains_sensitive_data,
        query_json=query,
        response_json=response.data if isinstance(response.data, dict) else {"raw": response.data},
        captured_at=utcnow_naive(),
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def store_counter_snapshot(
    db: AsyncSession,
    *,
    counter_id: str,
    response: YandexResponse,
) -> MetrikaCounterSnapshot:
    payload = response.data.get("counter", response.data) if isinstance(response.data, dict) else {}
    code_options = payload.get("code_options") or {}
    webvisor = payload.get("webvisor") or {}
    snapshot = MetrikaCounterSnapshot(
        counter_id=str(counter_id),
        name=payload.get("name"),
        site=payload.get("site") or (payload.get("site2") or {}).get("site"),
        status=payload.get("status"),
        permission=payload.get("permission"),
        webvisor_enabled=bool(code_options.get("visor") or webvisor.get("allow_wv2")) if payload else None,
        ecommerce_enabled=bool(code_options.get("ecommerce")) if payload else None,
        clickmap_enabled=bool(code_options.get("clickmap")) if payload else None,
        raw_json=payload,
        captured_at=utcnow_naive(),
    )
    db.add(snapshot)
    await db.flush()
    return snapshot
