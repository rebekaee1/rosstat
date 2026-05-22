"""Live ticker API endpoint.

`GET /api/v1/ticker/live` — returns the most recent snapshots stored by
`ticker_worker` in Redis. Lightweight (Redis read only, no external API
hops), suitable for client polling at 3-5 second cadence.

Response shape:
{
  "snapshots": [
    {
      "code": "usd-rub-live",
      "price": 71.4775,
      "change_pct": 0.04,
      "market_open": true,
      "fetched_at": "2026-05-22T08:40:26+00:00",
      "source": "MOEX"
    },
    ...
  ],
  "server_time": "2026-05-22T08:42:11+00:00"
}

`snapshots` is filtered to the 5 codes the UI currently uses (in fixed
order) so the client doesn't need to re-sort.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.cache import get_redis
from app.tasks.ticker_worker import REDIS_KEY_PREFIX

router = APIRouter(prefix="/ticker", tags=["ticker"])

# Fixed display order for the UI bar. Order = importance for our audience.
TICKER_CODES = [
    "usd-rub-live",
    "eur-rub-live",
    "cny-rub-live",
    "btc-usd",
    "brent",
]


@router.get("/live")
async def get_live_ticker() -> dict:
    snapshots: list[dict] = []
    try:
        r = await get_redis()
        keys = [f"{REDIS_KEY_PREFIX}{c}" for c in TICKER_CODES]
        raw_values = await r.mget(*keys)
        for raw in raw_values:
            if raw is None:
                continue
            try:
                snapshots.append(json.loads(raw))
            except (TypeError, ValueError):
                continue
    except Exception:
        # If Redis is unreachable, return an empty list — the UI shows
        # nothing rather than half-broken state.
        snapshots = []

    return {
        "snapshots": snapshots,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
