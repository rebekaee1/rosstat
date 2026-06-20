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

_PATH = "/api/v3/ticker/24hr?symbol=BTCUSDT"
# api.binance.com отдаёт 451 (Unavailable For Legal Reasons) с российских IP.
# data-api.binance.vision — публичный market-data домен Binance с тем же
# payload, без гео-ограничений; держим его первым. Дальше — зеркала на случай
# точечной недоступности конкретного хоста.
_HOSTS = [
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api.binance.com",
]


async def fetch_all() -> list[TickerSnapshot]:
    """Pull BTC/USD live snapshot (перебор зеркал до первого успешного)."""
    d = None
    last_err: Exception | None = None
    async with httpx.AsyncClient(headers={"User-Agent": "ForecastEconomy/1.0 (+ticker)"}) as client:
        for host in _HOSTS:
            try:
                r = await client.get(f"{host}{_PATH}", timeout=10.0)
                r.raise_for_status()
                d = r.json()
                break
            except (httpx.HTTPError, ValueError) as e:
                last_err = e
                continue
    if d is None:
        logger.warning("Binance BTC: all mirrors failed: %s", last_err)
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
