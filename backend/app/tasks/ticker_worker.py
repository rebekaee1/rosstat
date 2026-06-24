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
  - The TTL is deliberately much longer (90s) than the polling interval so
    that several consecutive pull failures (flaky MOEX, a slow tick) don't
    black out the ticker — the previous snapshot stays until the next
    successful pull replaces it. Sources are fetched concurrently with a 5s
    per-request timeout (see moex_iss._TIMEOUT), so a healthy tick finishes
    well under the TTL; raising the TTL only widens the safety margin.
"""
from __future__ import annotations

import json
import logging

from app.core.cache import get_redis
from app.services.ticker_sources.binance import fetch_all as binance_fetch_all
from app.services.ticker_sources.moex_iss import fetch_all as moex_fetch_all

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = "ticker:"
REDIS_TTL_SECONDS = 90


async def _brent_db_fallback():
    """Последняя дневная котировка Brent из нашей БД (ряд `brent`).

    Используется, когда MOEX FORTS недоступен. Возвращает `TickerSnapshot`
    с `market_open=False` (значение дневное, не live) или None.
    """
    from sqlalchemy import desc, select

    from app.database import async_session
    from app.models import Indicator, IndicatorData
    from app.services.ticker_sources import TickerSnapshot, utcnow

    try:
        async with async_session() as db:
            ind = (
                await db.execute(select(Indicator).where(Indicator.code == "brent"))
            ).scalar_one_or_none()
            if ind is None:
                return None
            rows = (
                await db.execute(
                    select(IndicatorData.value)
                    .where(IndicatorData.indicator_id == ind.id)
                    .order_by(desc(IndicatorData.date))
                    .limit(2)
                )
            ).scalars().all()
            if not rows:
                return None
            last = float(rows[0])
            chg = None
            if len(rows) >= 2 and float(rows[1]):
                prev = float(rows[1])
                chg = round((last - prev) / prev * 100, 2)
            return TickerSnapshot(
                code="brent",
                price=last,
                change_pct=chg,
                market_open=False,
                fetched_at=utcnow(),
                source="Рыночные котировки",
            )
    except Exception:
        logger.exception("ticker_pull_job: brent DB fallback failed")
        return None


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

    # Brent fallback: MOEX FORTS периодически недоступен с сервера (block по IP,
    # ConnectTimeout). У FX/золота есть fallback на ЦБ, у Brent его нет — без
    # этого инструмент исчезает с бара. Подставляем последнюю дневную котировку
    # из нашего ряда `brent` (ежедневный ETL), чтобы тикер всегда был полным.
    if not any(s.code == "brent" for s in snapshots):
        fb = await _brent_db_fallback()
        if fb is not None:
            snapshots.append(fb)

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
