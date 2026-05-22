"""Live ticker worker: APScheduler-driven, runs every 5 seconds.

Pulls live FX/Brent quotes from MOEX ISS and BTC/USD from Binance, persists
the result in Redis under `ticker:<code>` with TTL 30 seconds. The frontend
hits `GET /api/v1/ticker/live`, which reads these keys atomically (no per-
request external API call, no rate-limit issues at scale).

Design notes:
  - One worker per backend process. Each tick is bounded by the 10s timeout
    of the underlying httpx clients; we use `coalesce=True` and
    `max_instances=1` in main.py so two concurrent ticks cannot pile up.
  - Failures of one source don't kill the other. If MOEX is down, BTC still
    updates; the missing snapshots in Redis simply expire (TTL = 30s), and
    the API endpoint silently omits them from the response.
  - The TTL is deliberately longer (30s) than the polling interval (5s) so
    that a one-off pull failure doesn't black out the ticker — the previous
    snapshot stays until the next successful pull replaces it.
"""
from __future__ import annotations

import json
import logging

from app.core.cache import get_redis
from app.services.ticker_sources.binance import fetch_all as binance_fetch_all
from app.services.ticker_sources.moex_iss import fetch_all as moex_fetch_all

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = "ticker:"
REDIS_TTL_SECONDS = 30


async def ticker_pull_job() -> None:
    """Fetch all sources concurrently and write snapshots to Redis."""
    import asyncio

    try:
        moex, binance = await asyncio.gather(
            moex_fetch_all(),
            binance_fetch_all(),
            return_exceptions=True,
        )
    except Exception:
        logger.exception("ticker_pull_job: gather() crashed unexpectedly")
        return

    snapshots = []
    for src in (moex, binance):
        if isinstance(src, list):
            snapshots.extend(src)
        elif isinstance(src, Exception):
            logger.warning("ticker_pull_job: source failed: %s", src)

    if not snapshots:
        logger.info("ticker_pull_job: no snapshots fetched, skipping Redis write")
        return

    try:
        r = await get_redis()
        pipe = r.pipeline()
        for snap in snapshots:
            pipe.set(
                f"{REDIS_KEY_PREFIX}{snap.code}",
                json.dumps(snap.as_dict()),
                ex=REDIS_TTL_SECONDS,
            )
        await pipe.execute()
    except Exception:
        logger.exception("ticker_pull_job: Redis write failed")
