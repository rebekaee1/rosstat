"""ETL parser for Brent daily history.

Source: Yahoo Finance unofficial API, ticker BZ=F (Brent Crude Oil Futures
front-month, ICE Europe). Public, no API key, no rate limit issues we've
hit so far. Returns daily OHLC for the rolled-forward front contract,
which is the standard reference series used by financial press.

Endpoint format:
  GET https://query1.finance.yahoo.com/v8/finance/chart/BZ=F
       ?period1=<unix_ts_from>&period2=<unix_ts_to>&interval=1d

Response shape:
  result[0].timestamp     — array of unix-seconds for each daily bar
  result[0].indicators.quote[0].close  — close prices (may contain nulls
                                          for non-trading days)

Why Yahoo vs FRED (DCOILBRENTEU spot):
  - We tried FRED first; from the Docker network FRED's HTTPS endpoint
    intermittently times out on multi-year windows (one-shot ad-hoc
    requests succeed; ETL re-runs fail). Yahoo's chart API serves 1300+
    daily points in a single 0.5s call.
  - Yahoo BZ=F is futures, FRED is spot — they track within ~0.5% on a
    daily basis; for a market-overview indicator the choice is
    acceptable and matches the live source (MOEX FORTS BR-X.Y).
  - The class name stays `BrentDailyFredParser` only for git-history
    continuity; rename in a follow-up if it bothers anyone.

Why we keep `parser_type = "moex_brent_daily"` despite using Yahoo:
  - This is the slot in `model_config_json` already wired up for the
    `brent` indicator; switching the actual upstream provider should not
    cascade into a DB migration. The contract is "give me daily Brent
    closes"; the source is an implementation detail.
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

_URL = "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F"
_DEFAULT_BACKFILL_FROM = date(2015, 1, 1)


def _fetch_yahoo(from_date: date, to_date: date) -> dict:
    period1 = int(datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc).timestamp())
    period2 = int(datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc).timestamp()) + 86400
    params = {"period1": period1, "period2": period2, "interval": "1d"}
    with httpx.Client(
        timeout=30.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0)"},
    ) as c:
        r = c.get(_URL, params=params)
        r.raise_for_status()
        return r.json()


def _parse_yahoo(payload: dict) -> list[tuple[date, float]]:
    try:
        result = payload["chart"]["result"][0]
        ts_list = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        return []

    out: list[tuple[date, float]] = []
    for ts, close in zip(ts_list, closes):
        if close is None:
            continue
        try:
            d = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
            out.append((d, round(float(close), 2)))
        except (ValueError, TypeError):
            continue
    return out


class BrentDailyFredParser(BaseParser):
    parser_type: ClassVar[str] = "moex_brent_daily"

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
        date_from = _DEFAULT_BACKFILL_FROM if existing_n == 0 else today - timedelta(days=30)

        try:
            payload = await asyncio.to_thread(_fetch_yahoo, date_from, today)
            points = _parse_yahoo(payload)
        except Exception as e:
            fetch_log.error_message = f"Yahoo BZ=F fetch failed: {e}"[:500]
            return [], _URL

        by_date: dict[date, float] = {}
        for d, v in points:
            by_date[d] = v
        return sorted(by_date.items()), _URL
