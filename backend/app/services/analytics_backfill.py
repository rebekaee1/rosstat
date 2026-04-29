from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any
from urllib.parse import urljoin

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MetrikaDailyPageMetric, MetrikaSearchPhrase
from app.services.analytics_ingestion import finish_sync_run, start_sync_run
from app.services.seo_crawler import crawl_url, store_seo_snapshot
from app.services.yandex_metrika_reporting import MetrikaReportingClient


def daterange(date_from: date, date_to: date):
    current = date_from
    while current <= date_to:
        yield current
        current += timedelta(days=1)


async def _upsert_page_metric(
    db: AsyncSession,
    *,
    counter_id: str,
    metric_date: date,
    url: str,
    source: str | None,
    metrics: list[float],
    metadata: dict[str, Any] | None = None,
) -> None:
    existing_q = await db.execute(
        select(MetrikaDailyPageMetric).where(
            MetrikaDailyPageMetric.counter_id == counter_id,
            MetrikaDailyPageMetric.date == metric_date,
            MetrikaDailyPageMetric.url == url,
            MetrikaDailyPageMetric.source == source,
        )
    )
    item = existing_q.scalar_one_or_none() or MetrikaDailyPageMetric(
        counter_id=counter_id,
        date=metric_date,
        url=url,
        source=source,
    )
    item.visits = int(metrics[0] or 0)
    item.users = int(metrics[1] or 0)
    item.pageviews = int(metrics[2] or 0)
    item.bounce_rate = metrics[3] if len(metrics) > 3 else None
    item.depth = metrics[4] if len(metrics) > 4 else None
    item.avg_duration_seconds = metrics[5] if len(metrics) > 5 else None
    item.metadata_json = metadata
    db.add(item)


async def _upsert_search_phrase(
    db: AsyncSession,
    *,
    counter_id: str,
    metric_date: date,
    phrase: str,
    landing_url: str | None,
    search_engine: str | None,
    metrics: list[float],
    metadata: dict[str, Any] | None = None,
) -> None:
    existing_q = await db.execute(
        select(MetrikaSearchPhrase).where(
            MetrikaSearchPhrase.counter_id == counter_id,
            MetrikaSearchPhrase.date == metric_date,
            MetrikaSearchPhrase.phrase == phrase,
            MetrikaSearchPhrase.landing_url == landing_url,
            MetrikaSearchPhrase.search_engine == search_engine,
        )
    )
    item = existing_q.scalar_one_or_none() or MetrikaSearchPhrase(
        counter_id=counter_id,
        date=metric_date,
        phrase=phrase,
        landing_url=landing_url,
        search_engine=search_engine,
    )
    item.visits = int(metrics[0] or 0)
    item.users = int(metrics[1] or 0)
    item.bounce_rate = metrics[2] if len(metrics) > 2 else None
    item.metadata_json = metadata
    db.add(item)


async def backfill_metrika_daily_pages(db: AsyncSession, *, date_from: date, date_to: date, counter_id: str | None = None) -> int:
    counter_id = counter_id or settings.analytics_allowed_counter_ids.split(",")[0].strip()
    client = MetrikaReportingClient()
    run = await start_sync_run(
        db,
        source="yandex_metrika",
        job_type="backfill_daily_page_metrics",
        date_from=date_from,
        date_to=date_to,
        metadata={"counter_id": counter_id},
    )
    await db.commit()
    processed = 0
    try:
        for day in daterange(date_from, date_to):
            response = await client.table(
                counter_id=counter_id,
                metrics=[
                    "ym:s:visits",
                    "ym:s:users",
                    "ym:s:pageviews",
                    "ym:s:bounceRate",
                    "ym:s:pageDepth",
                    "ym:s:avgVisitDurationSeconds",
                ],
                dimensions=["ym:s:startURLPath"],
                date_from=day,
                date_to=day,
                limit=500,
            )
            for row in response.data.get("data", []):
                url = row["dimensions"][0]["name"]
                await _upsert_page_metric(
                    db,
                    counter_id=counter_id,
                    metric_date=day,
                    url=url,
                    source=None,
                    metrics=row["metrics"],
                    metadata={"sampled": response.sampled, "sample_share": response.sample_share},
                )
                processed += 1
        await finish_sync_run(db, run, records_processed=processed)
        await db.commit()
        return processed
    except Exception as exc:
        await db.rollback()
        await finish_sync_run(db, run, status="failed", error_message=str(exc)[:500])
        await db.commit()
        raise


async def backfill_metrika_search_phrases(db: AsyncSession, *, date_from: date, date_to: date, counter_id: str | None = None) -> int:
    counter_id = counter_id or settings.analytics_allowed_counter_ids.split(",")[0].strip()
    client = MetrikaReportingClient()
    run = await start_sync_run(
        db,
        source="yandex_metrika",
        job_type="backfill_search_phrases",
        date_from=date_from,
        date_to=date_to,
        metadata={"counter_id": counter_id},
    )
    await db.commit()
    processed = 0
    try:
        response = await client.table(
            counter_id=counter_id,
            metrics=["ym:s:visits", "ym:s:users", "ym:s:bounceRate"],
            dimensions=["ym:s:searchPhrase"],
            filters="ym:s:trafficSource=='organic'",
            date_from=date_from,
            date_to=date_to,
            limit=500,
        )
        for row in response.data.get("data", []):
            dims = row["dimensions"]
            await _upsert_search_phrase(
                db,
                counter_id=counter_id,
                metric_date=date_to,
                phrase=dims[0]["name"],
                landing_url=None,
                search_engine=None,
                metrics=row["metrics"],
                metadata={
                    "date_from": str(date_from),
                    "date_to": str(date_to),
                    "sampled": response.sampled,
                    "sample_share": response.sample_share,
                },
            )
            processed += 1
        await finish_sync_run(db, run, records_processed=processed)
        await db.commit()
        return processed
    except Exception as exc:
        await db.rollback()
        await finish_sync_run(db, run, status="failed", error_message=str(exc)[:500])
        await db.commit()
        raise


async def backfill_seo_snapshots(db: AsyncSession, *, base_url: str | None = None, limit: int | None = None) -> int:
    base_url = (base_url or settings.analytics_base_url).rstrip("/")
    run = await start_sync_run(db, source="seo_crawler", job_type="backfill_seo_snapshots", metadata={"base_url": base_url})
    await db.commit()
    processed = 0
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(urljoin(base_url + "/", "sitemap.xml"))
            response.raise_for_status()
        root = ET.fromstring(response.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
        if not urls:
            urls = [loc.text.strip() for loc in root.findall(".//loc") if loc.text]
        if limit:
            urls = urls[:limit]
        for url in urls:
            facts = await crawl_url(url, base_url=base_url)
            await store_seo_snapshot(db, facts)
            processed += 1
        await finish_sync_run(db, run, records_processed=processed)
        await db.commit()
        return processed
    except Exception as exc:
        await db.rollback()
        await finish_sync_run(db, run, status="failed", error_message=str(exc)[:500])
        await db.commit()
        raise
