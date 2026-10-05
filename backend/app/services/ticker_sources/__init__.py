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

    source_kind — откуда число по смыслу: `market` (биржевая котировка),
                  `central_bank` (официальный курс ЦБ), `ecb` (справочный курс ЕЦБ),
                  `official` (дневной ряд официального источника). Выводится из `source`.
    as_of       — момент значения: метка времени для живых котировок, календарная
                  дата для дневных рядов. Страница курса и лента сравнивают числа по ней.
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
            "source_kind": source_kind(self.source),
        }
        if self.as_of_date is not None:
            out["as_of_date"] = self.as_of_date.isoformat()
        out["as_of"] = out.get("as_of_date") or out["fetched_at"]
        return out


def source_kind(source: str | None) -> str:
    """Тип источника по его короткой метке: биржа, ЦБ, ЕЦБ или прочий официальный ряд."""
    text = str(source or "").strip().lower()
    if "moex" in text or "мосбирж" in text or "binance" in text:
        return "market"
    if "банк россии" in text or "цб" in text.split() or text in {"cbr", "цб рф", "цб"} or "cbr" in text:
        return "central_bank"
    if "ецб" in text or "ecb" in text:
        return "ecb"
    return "official"


# Подпись над ценой: (русская, английская). Для прочих официальных рядов подписью служит название источника.
SOURCE_KIND_LABELS: dict[str, tuple[str, str]] = {
    "market": ("Биржа", "Exchange"),
    "central_bank": ("ЦБ", "Central bank"),
    "ecb": ("ЕЦБ", "ECB"),
}


def source_label(kind: str, source: str | None, locale: str) -> str:
    """Короткая подпись источника для ленты: «Биржа» или «ЦБ»; иначе название источника как есть."""
    pair = SOURCE_KIND_LABELS.get(kind)
    if pair is None:
        return str(source or "")
    return pair[1] if locale == "en" else pair[0]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
