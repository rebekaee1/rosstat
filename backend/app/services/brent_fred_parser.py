"""ETL parser for daily commodity / market history (Yahoo Finance chart API).

Source: Yahoo Finance unofficial API. The upstream ticker is config-driven
via ``model_config_json.yahoo_symbol`` (default ``BZ=F`` for Brent), so the
same parser serves the whole commodities desk:

  brent        BZ=F   Brent Crude front-month (ICE Europe), USD/bbl
  copper       HG=F   COMEX copper, USD/lb
  silver       SI=F   COMEX silver, USD/troy oz
  wheat        ZW=F   CBOT wheat, US¢/bushel
  natural-gas  NG=F   NYMEX Henry Hub, USD/MMBtu
  coal         MTF=F  ICE Rotterdam coal, USD/t
  steel        HRC=F  CME US Midwest HRC steel, USD/short ton
  soybean      ZS=F   CBOT soybeans, US¢/bushel

Public, no API key. Returns daily OHLC for the rolled-forward front
contract, which is the standard reference series used by financial press.
Backfill start is config-driven via ``model_config_json.backfill_from``
(ISO date, default 2015-01-01).

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

_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
_DEFAULT_SYMBOL = "BZ=F"
_DEFAULT_BACKFILL_FROM = date(2015, 1, 1)


def _fetch_yahoo(symbol: str, from_date: date, to_date: date) -> dict:
    period1 = int(datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc).timestamp())
    period2 = int(datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc).timestamp()) + 86400
    params = {"period1": period1, "period2": period2, "interval": "1d"}
    with httpx.Client(
        timeout=30.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0)"},
    ) as c:
        r = c.get(_BASE_URL + symbol, params=params)
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
        symbol = str(cfg.get("yahoo_symbol") or _DEFAULT_SYMBOL)
        backfill_from = _DEFAULT_BACKFILL_FROM
        raw_from = cfg.get("backfill_from")
        if raw_from:
            try:
                backfill_from = date.fromisoformat(str(raw_from))
            except ValueError:
                pass

        earliest = (await db.execute(
            select(func.min(IndicatorData.date)).where(IndicatorData.indicator_id == indicator.id)
        )).scalar()
        today = date.today()
        url = _BASE_URL + symbol

        # Свежий хвост всегда; глубокая история — при первом прогоне или когда
        # самая ранняя точка БД позже `backfill_from` (self-healing: расширение
        # истории = смена конфига + ETL, без одноразовых скриптов).
        windows: list[tuple[date, date]] = []
        if earliest is None:
            windows.append((backfill_from, today))
        else:
            windows.append((today - timedelta(days=30), today))
            if earliest > backfill_from:
                windows.append((backfill_from, earliest))

        by_date: dict[date, float] = {}
        try:
            for w_start, w_end in windows:
                payload = await asyncio.to_thread(_fetch_yahoo, symbol, w_start, w_end)
                for d, v in _parse_yahoo(payload):
                    by_date[d] = v
        except Exception as e:
            fetch_log.error_message = f"Yahoo {symbol} fetch failed: {e}"[:500]
            return [], url

        return sorted(by_date.items()), url
