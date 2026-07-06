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
import time

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
    for name, src in (("moex", moex), ("binance", binance)):
        if isinstance(src, list):
            snapshots.extend(src)
            if src:
                _source_last_ok[name] = time.monotonic()
        elif isinstance(src, Exception):
            logger.warning("ticker_pull_job: source failed: %s", src)
        _check_source_staleness(name)

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
        _note_write_failure("all sources empty")
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
        global _last_write_ok_ts
        _last_write_ok_ts = time.monotonic()
    except Exception:
        logger.exception("ticker_pull_job: Redis write failed")
        _note_write_failure("Redis write failed")


# --- Н-20: тикер молча протухает по TTL, если запись не проходит -----------
# job интервальная (каждые ~30с); если успешной записи не было дольше
# _STALE_ALERT_SECONDS — один алерт, дальше молчим _ALERT_COOLDOWN.
_STALE_ALERT_SECONDS = 180
_ALERT_COOLDOWN = 1800
_last_write_ok_ts: float | None = None
_last_alert_ts: float = 0.0

# --- Н-30: per-source staleness — частичный сбой (MOEX жив, Binance лежит)
# не ловится глобальным чеком: часть тайлов молча пропадает по TTL.
_SOURCE_STALE_SECONDS = 1800
_source_last_ok: dict[str, float] = {}
_source_alerted: set[str] = set()


def _check_source_staleness(name: str) -> None:
    now = time.monotonic()
    last_ok = _source_last_ok.get(name)
    if last_ok is None:
        return  # источник ещё ни разу не отдавал данные (startup)
    if now - last_ok < _SOURCE_STALE_SECONDS:
        _source_alerted.discard(name)  # восстановился — взводим алерт заново
        return
    if name in _source_alerted:
        return
    _source_alerted.add(name)
    logger.error(
        "ticker source '%s' stale: no data for %.0f min — тайлы источника "
        "пропадут с бара по TTL", name, (now - last_ok) / 60,
    )


def _note_write_failure(reason: str) -> None:
    global _last_alert_ts
    import asyncio

    now = time.monotonic()
    if _last_write_ok_ts is None:
        return  # ещё ни одной успешной записи (startup) — не алертим
    if now - _last_write_ok_ts < _STALE_ALERT_SECONDS:
        return
    if now - _last_alert_ts < _ALERT_COOLDOWN:
        return
    _last_alert_ts = now
    try:
        from app.services.alerting import send_telegram
        asyncio.get_running_loop().create_task(send_telegram(
            "🟡 <b>Live ticker stale</b>\n"
            f"Нет успешной записи снапшотов дольше {_STALE_ALERT_SECONDS // 60} мин "
            f"({reason}) — тикер на сайте протухнет по TTL.",
            kind="ticker_stale",
        ))
    except Exception:
        logger.warning("Ticker stale alert failed", exc_info=True)
