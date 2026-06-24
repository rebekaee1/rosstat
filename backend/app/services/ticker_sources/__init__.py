"""Live ticker sources — MOEX ISS for FX/Brent, Binance public API for BTC.

Все источники — HTTP-pull (без WSS), синхронные запросы из APScheduler-worker
раз в 5 секунд. Результат — dict {ticker_code: TickerSnapshot}, кладётся в
Redis с TTL 90 секунд под ключом `ticker:<code>`. Endpoint `/api/v1/ticker/live`
читает из Redis и отдаёт JSON клиенту.

Поставка обновлений в frontend — через polling (React Query), а не WebSocket
(см. решение «Вариант A» из звонка 2026-05-22).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class TickerSnapshot:
    """Один снимок live-котировки.

    code        — стабильный идентификатор инструмента в нашей системе
                  (`usd-rub-live`, `btc-usd`, `brent`, ...).
    price       — last traded price в собственной валюте инструмента.
    change_pct  — % изменение относительно эталона (для FX/Brent
                  это PREVPRICE; для BTC — 24h ago).
    market_open — True если торги активны прямо сейчас (для крипты — всегда).
    fetched_at  — UTC timestamp момента pull'а.
    source      — короткая метка источника для атрибуции в UI tooltip.
    """

    code: str
    price: float
    change_pct: float | None
    market_open: bool
    fetched_at: datetime
    source: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "price": self.price,
            "change_pct": self.change_pct,
            "market_open": self.market_open,
            "fetched_at": self.fetched_at.isoformat(),
            "source": self.source,
        }


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
