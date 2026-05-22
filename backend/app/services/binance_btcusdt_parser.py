"""ETL parser for BTC/USD daily history from Binance public API.

Source: GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d
Returns OHLCV candles; we take `close_time` (UTC midnight of the day after)
mapped back to the trading day and `close` price as the value.

Live-котировка в тикере (sticky bar над navbar) — отдельный путь через
`ticker_sources/binance.py` + Redis. Этот парсер — для исторической
страницы /indicator/btc-usd: ежедневный snapshot, который ETL добавляет в
БД точно так же, как любой другой daily-индикатор.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import ClassVar

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser

logger = logging.getLogger(__name__)

_URL = "https://api.binance.com/api/v3/klines"
_DEFAULT_BACKFILL_DAYS = 1500  # ~4 years
_LIMIT = 1000


def _fetch_klines(start_ms: int | None, limit: int) -> list[list]:
    params = {"symbol": "BTCUSDT", "interval": "1d", "limit": limit}
    if start_ms is not None:
        params["startTime"] = start_ms
    with httpx.Client(timeout=30.0, headers={"User-Agent": "ForecastEconomy/1.0"}) as c:
        r = c.get(_URL, params=params)
        r.raise_for_status()
        return r.json()


def _klines_to_points(klines: list[list]) -> list[tuple[date, float]]:
    """Map [open_time, open, high, low, close, volume, close_time, ...] → (date, close).

    `close_time` is the last millisecond of the trading day in UTC
    (e.g. 23:59:59.999 of day D). We use the UTC date of close_time as
    the canonical date — same convention BTC indicator pages will show.
    """
    out: list[tuple[date, float]] = []
    for row in klines:
        try:
            close_time_ms = int(row[6])
            close_price = float(row[4])
        except (IndexError, ValueError, TypeError):
            continue
        d = datetime.fromtimestamp(close_time_ms / 1000, tz=timezone.utc).date()
        out.append((d, close_price))
    return out


class BinanceBtcUsdtParser(BaseParser):
    parser_type: ClassVar[str] = "binance_btcusdt_daily"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        existing_n = (await db.execute(
            select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
        )).scalar() or 0
        today = date.today()
        if existing_n == 0:
            start_dt = today - timedelta(days=_DEFAULT_BACKFILL_DAYS)
        else:
            start_dt = today - timedelta(days=14)

        all_points: list[tuple[date, float]] = []
        cursor_ms: int | None = int(datetime(start_dt.year, start_dt.month, start_dt.day, tzinfo=timezone.utc).timestamp() * 1000)

        # Binance limit=1000 daily candles per request; paginate forward.
        for _ in range(20):
            kl = await asyncio.to_thread(_fetch_klines, cursor_ms, _LIMIT)
            if not kl:
                break
            pts = _klines_to_points(kl)
            all_points.extend(pts)
            last_open_ms = int(kl[-1][0])
            if len(kl) < _LIMIT:
                break
            cursor_ms = last_open_ms + 86_400_000  # next day

        by_date: dict[date, float] = {}
        for d, v in all_points:
            by_date[d] = v
        points = sorted(by_date.items())
        return points, _URL
