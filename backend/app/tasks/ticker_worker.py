"""Live ticker worker: APScheduler-driven, runs every 5 seconds.

Pulls live FX quotes from MOEX ISS and BTC/USD from Binance, persists
the result in Redis under `ticker:<code>` with TTL 30 seconds. The frontend
hits `GET /api/v1/ticker/live`, which reads these keys atomically (no per-
request external API call, no rate-limit issues at scale).

Brent and gold always come from the same DB series as their indicator cards
(`brent`, `gold-price`). Live MOEX futures/spot must not appear in the bar —
that contradicted the cards on the home page (P0).

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
from datetime import date

from app.core.cache import get_redis
from app.services.ticker_sources.binance import fetch_all as binance_fetch_all
from app.services.ticker_sources.moex_iss import fetch_all as moex_fetch_all

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = "ticker:"
REDIS_TTL_SECONDS = 90

# Дневные ряды карточек → код в ленте. Не подмешиваем live-биржу.
_SERIES_TICKER_SPECS: tuple[tuple[str, str, str], ...] = (
    # (indicator_code, ticker_code, source_label)
    ("brent", "brent", "EIA"),
    ("gold-price", "gold-rub-live", "Банк России"),
)

# Воркер тикает каждые 5 секунд, а дневной ряд обновляется раз в сутки:
# без памяти это ~17 тысяч одинаковых запросов к БД в день.
_SERIES_CACHE_TTL_SECONDS = 300
_series_cache: dict[str, tuple[float, object]] = {}


async def _series_db_snapshot(
    indicator_code: str,
    ticker_code: str,
    source: str,
):
    """Последняя точка ряда карточки + % к предыдущей точке.

    Возвращает `TickerSnapshot` с `market_open=False` и `as_of_date`, либо None.
    """
    from sqlalchemy import desc, select

    from app.database import async_session
    from app.models import Indicator, IndicatorData
    from app.services.ticker_sources import TickerSnapshot, utcnow

    cached = _series_cache.get(indicator_code)
    if cached is not None and time.monotonic() - cached[0] < _SERIES_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        async with async_session() as db:
            ind = (
                await db.execute(select(Indicator).where(Indicator.code == indicator_code))
            ).scalar_one_or_none()
            if ind is None:
                return None
            rows = (
                await db.execute(
                    select(IndicatorData.date, IndicatorData.value)
                    .where(IndicatorData.indicator_id == ind.id)
                    .order_by(desc(IndicatorData.date))
                    .limit(2)
                )
            ).all()
            if not rows:
                return None
            last_date, last_val = rows[0]
            last = float(last_val)
            chg = None
            if len(rows) >= 2 and float(rows[1][1]):
                prev = float(rows[1][1])
                chg = round((last - prev) / prev * 100, 2)
            as_of: date | None = last_date if isinstance(last_date, date) else None
            snapshot = TickerSnapshot(
                code=ticker_code,
                price=last,
                change_pct=chg,
                market_open=False,
                fetched_at=utcnow(),
                source=source,
                as_of_date=as_of,
            )
            _series_cache[indicator_code] = (time.monotonic(), snapshot)
            return snapshot
    except Exception:
        logger.exception(
            "ticker_pull_job: series DB snapshot failed for %s", indicator_code,
        )
        return None


# Совместимость со старыми тестами / импортами.
async def _brent_db_fallback():
    return await _series_db_snapshot("brent", "brent", "EIA")


async def ticker_pull_job() -> None:
    """Fetch live sources + card series; write snapshots to Redis."""
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
            # На случай легаси-кода, который ещё тянет brent/gold с MOEX —
            # выкидываем: в ленте только ряды карточек.
            snapshots.extend(
                s for s in src
                if s.code not in {"brent", "gold-rub-live"}
            )
            if src:
                _source_last_ok[name] = time.monotonic()
        elif isinstance(src, Exception):
            logger.warning("ticker_pull_job: source failed: %s", src)
        _check_source_staleness(name)

    series_snaps = await asyncio.gather(
        *[_series_db_snapshot(ind, tick, src) for ind, tick, src in _SERIES_TICKER_SPECS],
        return_exceptions=True,
    )
    for spec, snap in zip(_SERIES_TICKER_SPECS, series_snaps):
        if isinstance(snap, Exception):
            logger.warning(
                "ticker_pull_job: series %s failed: %s", spec[0], snap,
            )
            continue
        if snap is not None:
            snapshots.append(snap)

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
