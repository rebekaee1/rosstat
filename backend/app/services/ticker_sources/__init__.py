"""Live ticker sources — MOEX ISS for FX, Binance public API for BTC.

Нефть Brent и золото в ленту идут не отсюда, а из рядов карточек
(`brent`, `gold-price`) через `ticker_worker` — иначе бегущая строка
противоречит карточкам на главной.

Все источники — HTTP-pull (без WSS), синхронные запросы из APScheduler-worker
раз в 5 секунд. Результат — dict {ticker_code: TickerSnapshot}, кладётся в
Redis с TTL 90 секунд под ключом `ticker:<code>`. Endpoint `/api/v1/ticker/live`
читает из Redis и отдаёт JSON клиенту.

Поставка обновлений в frontend — через polling (React Query), а не WebSocket
(см. решение «Вариант A» из звонка 2026-05-22).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass(frozen=True)
class TickerSnapshot:
    """Один снимок live-котировки.

    code        — стабильный идентификатор инструмента в нашей системе
                  (`usd-rub-live`, `btc-usd`, `brent`, ...).
    price       — last traded price в собственной валюте инструмента.
    change_pct  — % изменение относительно эталона (для FX — PREVPRICE;
                  для BTC — 24h ago; для дневных рядов карточек — к
                  предыдущей точке ряда).
    market_open — True если торги активны прямо сейчас (для крипты — всегда;
                  для дневных рядов карточек — всегда False).
    fetched_at  — UTC timestamp момента pull'а.
    source      — короткая метка источника для атрибуции в UI tooltip.
    as_of_date  — календарная дата значения (для не-внутридневных рядов);
                  None у живых котировок.
    """

    code: str
    price: float
    change_pct: float | None
    market_open: bool
    fetched_at: datetime
    source: str
    as_of_date: date | None = None

    def as_dict(self) -> dict:
        out = {
            "code": self.code,
            "price": self.price,
            "change_pct": self.change_pct,
            "market_open": self.market_open,
            "fetched_at": self.fetched_at.isoformat(),
            "source": self.source,
        }
        if self.as_of_date is not None:
            out["as_of_date"] = self.as_of_date.isoformat()
        return out


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
