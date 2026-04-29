from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    AgentFinding,
    AnalyticsSyncRun,
    MetrikaDailyPageMetric,
    MetrikaSearchPhrase,
    SeoPageSnapshot,
)


@dataclass(frozen=True)
class PageOpportunity:
    url: str
    visits: int
    search_visits: int
    bounce_rate: float | None
    internal_links_count: int | None
    score: float


async def top_pages(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    stmt: Select = (
        select(
            MetrikaDailyPageMetric.url,
            func.sum(MetrikaDailyPageMetric.visits).label("visits"),
            func.sum(MetrikaDailyPageMetric.users).label("users"),
            func.avg(MetrikaDailyPageMetric.bounce_rate).label("bounce_rate"),
        )
        .group_by(MetrikaDailyPageMetric.url)
        .order_by(func.sum(MetrikaDailyPageMetric.visits).desc())
        .limit(limit)
    )
    if date_from:
        stmt = stmt.where(MetrikaDailyPageMetric.date >= date_from)
    if date_to:
        stmt = stmt.where(MetrikaDailyPageMetric.date <= date_to)
    rows = (await db.execute(stmt)).mappings().all()
    return [dict(row) for row in rows]


async def top_search_phrases(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt: Select = (
        select(
            MetrikaSearchPhrase.phrase,
            MetrikaSearchPhrase.landing_url,
            func.sum(MetrikaSearchPhrase.visits).label("visits"),
            func.sum(MetrikaSearchPhrase.users).label("users"),
            func.avg(MetrikaSearchPhrase.bounce_rate).label("bounce_rate"),
        )
        .group_by(MetrikaSearchPhrase.phrase, MetrikaSearchPhrase.landing_url)
        .order_by(func.sum(MetrikaSearchPhrase.visits).desc())
        .limit(limit)
    )
    if date_from:
        stmt = stmt.where(MetrikaSearchPhrase.date >= date_from)
    if date_to:
        stmt = stmt.where(MetrikaSearchPhrase.date <= date_to)
    rows = (await db.execute(stmt)).mappings().all()
    return [dict(row) for row in rows]


async def detect_page_opportunities(db: AsyncSession, *, limit: int = 25) -> list[PageOpportunity]:
    page_rows = await top_pages(db, limit=limit * 2)
    opportunities: list[PageOpportunity] = []
    for row in page_rows:
        url = row["url"]
        absolute_url = f"{settings.analytics_base_url.rstrip('/')}{url}" if str(url).startswith("/") else str(url)
        snapshot_q = await db.execute(
            select(SeoPageSnapshot)
            .where(SeoPageSnapshot.url.in_([url, absolute_url]))
            .order_by(SeoPageSnapshot.captured_at.desc())
            .limit(1)
        )
        snapshot = snapshot_q.scalar_one_or_none()
        visits = int(row["visits"] or 0)
        bounce = float(row["bounce_rate"]) if row["bounce_rate"] is not None else None
        links = snapshot.internal_links_count if snapshot else None
        score = visits
        if bounce and bounce > 60:
            score *= 1.2
        if links is not None and links < 3:
            score *= 1.3
        opportunities.append(
            PageOpportunity(
                url=row["url"],
                visits=visits,
                search_visits=0,
                bounce_rate=bounce,
                internal_links_count=links,
                score=round(score, 2),
            )
        )
    return sorted(opportunities, key=lambda item: item.score, reverse=True)[:limit]


async def sync_run_impact(db: AsyncSession, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(AnalyticsSyncRun)
            .where(AnalyticsSyncRun.status.in_(["success", "failed"]))
            .order_by(AnalyticsSyncRun.started_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": run.id,
            "source": run.source,
            "job_type": run.job_type,
            "status": run.status,
            "records_processed": run.records_processed,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "error_message": run.error_message,
        }
        for run in rows
    ]


async def create_finding(
    db: AsyncSession,
    *,
    finding_type: str,
    title: str,
    summary: str,
    evidence: dict[str, Any],
    priority: int = 3,
    confidence: float | None = None,
) -> AgentFinding:
    finding = AgentFinding(
        finding_type=finding_type,
        title=title,
        summary=summary,
        evidence_json=evidence,
        priority=priority,
        confidence=confidence,
        status="open",
    )
    db.add(finding)
    await db.flush()
    return finding
