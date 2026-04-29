from __future__ import annotations

import logging
from datetime import date, timedelta

from app.config import settings
from app.database import async_session
from app.services.analytics_ingestion import (
    finish_sync_run,
    start_sync_run,
    store_counter_snapshot,
    store_metrika_report_snapshot,
)
from app.services.yandex_metrika_management import MetrikaManagementClient
from app.services.yandex_metrika_reporting import MetrikaReportingClient

logger = logging.getLogger(__name__)


def _primary_counter_id() -> str:
    return settings.analytics_allowed_counter_ids.split(",")[0].strip()


async def analytics_hourly_job() -> None:
    if not settings.analytics_enabled:
        logger.info("Analytics hourly sync skipped: analytics disabled")
        return
    counter_id = _primary_counter_id()
    yesterday = date.today() - timedelta(days=1)
    async with async_session() as db:
        run = await start_sync_run(
            db,
            source="yandex_metrika",
            job_type="hourly_reporting_top_pages",
            date_from=yesterday,
            date_to=yesterday,
            metadata={"counter_id": counter_id},
        )
        await db.commit()
        try:
            client = MetrikaReportingClient()
            response = await client.table(
                counter_id=counter_id,
                metrics=["ym:s:visits", "ym:s:users", "ym:s:pageviews"],
                dimensions=["ym:s:startURL"],
                date_from=yesterday,
                date_to=yesterday,
                limit=100,
            )
            await store_metrika_report_snapshot(
                db,
                counter_id=counter_id,
                report_type="top_pages",
                query={"metrics": ["ym:s:visits", "ym:s:users", "ym:s:pageviews"], "dimensions": ["ym:s:startURL"]},
                response=response,
                date_from=yesterday,
                date_to=yesterday,
            )
            rows = len(response.data.get("data", [])) if isinstance(response.data, dict) else 0
            await finish_sync_run(db, run, records_processed=rows, request_hash=response.request_hash)
            await db.commit()
        except Exception as exc:
            logger.exception("Analytics hourly sync failed")
            await db.rollback()
            await finish_sync_run(db, run, status="failed", error_message=str(exc)[:500])
            await db.commit()


async def analytics_daily_job() -> None:
    if not settings.analytics_enabled:
        logger.info("Analytics daily sync skipped: analytics disabled")
        return
    counter_id = _primary_counter_id()
    async with async_session() as db:
        run = await start_sync_run(
            db,
            source="yandex_metrika",
            job_type="daily_management_snapshot",
            metadata={"counter_id": counter_id},
        )
        await db.commit()
        try:
            client = MetrikaManagementClient()
            response = await client.counter(counter_id, field=["goals", "filters", "operations", "grants"])
            await store_counter_snapshot(db, counter_id=counter_id, response=response)
            await finish_sync_run(db, run, records_processed=1, request_hash=response.request_hash)
            await db.commit()
        except Exception as exc:
            logger.exception("Analytics daily sync failed")
            await db.rollback()
            await finish_sync_run(db, run, status="failed", error_message=str(exc)[:500])
            await db.commit()
