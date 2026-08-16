"""ETL parser for legacy Yahoo Finance chart API (daily futures closes).

Historically this parser served the commodities desk via
``model_config_json.yahoo_symbol``. As of 2026-08-16 the live desk moved to
official sources:

  natural-gas  → EIA Henry Hub spot via ``fred_csv`` (``DHHNGSP``)
  coal/copper/silver/wheat/soybean → World Bank Pink Sheet monthly
      (``world_bank_pink_sheet``)
  brent        → EIA Europe Brent spot via ``fred_csv`` (``DCOILBRENTEU``)
  steel        → deactivated (no free redistributable official HRC series)

The class remains registered as ``parser_type = moex_brent_daily`` for
backward-compatible tests and any leftover inactive seed rows. Do not wire
new listed indicators to Yahoo: it is an unofficial aggregator and breaks the
platform promise of official primary sources.

Endpoint format (legacy):
  GET https://query1.finance.yahoo.com/v8/finance/chart/<symbol>
       ?period1=<unix_ts_from>&period2=<unix_ts_to>&interval=1d
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
