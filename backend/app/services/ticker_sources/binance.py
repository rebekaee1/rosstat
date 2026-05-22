"""Binance public API live source: BTC/USD.

API documentation: https://binance-docs.github.io/apidocs/spot/en/#24hr-ticker-price-change-statistics
Public, без ключа. Лимит на /api/v3/ticker/24hr — 1 weight = 1200 weights/min,
для одного запроса в 5 сек используется 12 weights/min, с большим запасом.

`priceChangePercent` уже посчитан Binance относительно цены 24 часа назад.
Это и есть то, что показываем пользователю — стандарт для крипты, у которой
нет «закрытия торгов».
"""
from __future__ import annotations

import logging

import httpx

from . import TickerSnapshot, utcnow

logger = logging.getLogger(__name__)

_URL = "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"


async def fetch_all() -> list[TickerSnapshot]:
    """Pull BTC/USD live snapshot."""
    try:
        async with httpx.AsyncClient(headers={"User-Agent": "ForecastEconomy/1.0 (+ticker)"}) as client:
            r = await client.get(_URL, timeout=10.0)
            r.raise_for_status()
            d = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Binance BTC: fetch failed: %s", e)
        return []

    try:
        price = float(d["lastPrice"])
        chgp = float(d["priceChangePercent"])
    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Binance BTC: unexpected payload: %s", e)
        return []

    return [TickerSnapshot(
        code="btc-usd",
        price=price,
        change_pct=chgp,
        market_open=True,  # crypto trades 24/7
        fetched_at=utcnow(),
        source="Binance",
    )]
