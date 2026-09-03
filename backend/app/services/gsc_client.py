"""Google Search Console Search Analytics — скелет клиента.

Пока нет OAuth-токена владельца (`RUSTATS_GSC_ACCESS_TOKEN` /
service account), джоб тихо выходит. Meta `google-site-verification`
эмитится из `RUSTATS_GOOGLE_SITE_VERIFICATION`.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from app.config import settings
from app.database import analytics_session
from app.models import GscSearchQuery
from app.services.display import today_msk

logger = logging.getLogger(__name__)

GSC_SEARCH_ANALYTICS = (
    "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
)


async def gsc_search_queries_job() -> None:
    token = getattr(settings, "gsc_access_token", "") or ""
    if not token:
        logger.info("GSC sync skipped: RUSTATS_GSC_ACCESS_TOKEN empty")
        return
    try:
        n = await sync_gsc_search_queries(token)
        logger.info("GSC search queries synced: %d rows", n)
    except Exception:
        logger.exception("GSC search queries sync failed")


async def sync_gsc_search_queries(token: str, *, days: int = 7) -> int:
    """Тянет Search Analytics за N дней. Без токена не вызывается."""
    import httpx
    from sqlalchemy.dialects.postgresql import insert

    end = today_msk() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    url = (
        "https://www.googleapis.com/webmasters/v3/sites/"
        f"sc-domain:{settings.public_host}/searchAnalytics/query"
    )
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": ["query", "page", "date"],
        "rowLimit": 25000,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        rows = resp.json().get("rows") or []

    stored = 0
    async with analytics_session() as db:
        for row in rows:
            keys = row.get("keys") or []
            if len(keys) < 3:
                continue
            query, page, day_s = keys[0], keys[1], keys[2]
            try:
                day = date.fromisoformat(day_s)
            except ValueError:
                continue
            stmt = insert(GscSearchQuery).values(
                date=day,
                query=str(query)[:500],
                page=str(page)[:1000] if page else None,
                impressions=int(row.get("impressions") or 0),
                clicks=int(row.get("clicks") or 0),
                ctr=row.get("ctr"),
                position=row.get("position"),
                raw_json=row,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_gsc_search_query",
                set_={
                    "impressions": stmt.excluded.impressions,
                    "clicks": stmt.excluded.clicks,
                    "ctr": stmt.excluded.ctr,
                    "position": stmt.excluded.position,
                    "raw_json": stmt.excluded.raw_json,
                },
            )
            await db.execute(stmt)
            stored += 1
        await db.commit()
    return stored
