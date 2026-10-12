"""Живая котировка нефти Brent: ближайший фьючерс BR на Московской бирже (ISS).

ВАЖНО: источник подключается только флагом `RUSTATS_MOEX_BRENT_LIVE_ENABLED` и только после договора с биржей.
Условия Мосбиржи разрешают бесплатные данные ISS «для ознакомления»; показ на сайте с рекламой и подпиской
возможен по договору (docs/data_sources.md, «Brent, дневной источник»). Пока флаг выключен, ни один запрос к
бирже за нефтью не уходит, а в ленте остаётся недельный спот EIA.

Что делает коннектор:
  * раз в `_CONTRACTS_TTL` берёт список контрактов фьючерсной секции и выбирает ближайший BR, у которого
    последний день торгов позже сегодняшнего (контракт меняется накануне экспирации, день экспирации не берём);
  * на каждом тике забирает один контракт (одна небольшая выдача), цена — `LAST`, при её отсутствии `SETTLEPRICE`;
  * изменение за день считается к предыдущей расчётной цене (`PREVSETTLEPRICE`): поле биржи `LASTCHANGEPRCNT`
    считает от предыдущей сделки и дневного изменения не даёт;
  * биржа отдаёт ISS с задержкой (`SYSTIME` − `UPDATETIME`, на 12.10.2026 ровно 15 минут): задержка
    пробрасывается в снимок и подписывается на ленте и странице;
  * если значение биржи старше `_LIVE_MAX_AGE_MINUTES`, торги закрыты: снимок идёт как значение на дату
    сессии (`market_open=False`, `as_of_date`); старше `_CLOSED_MAX_AGE_DAYS` или сбой, пустой ответ, нет
    контракта, `None` — вызывающий берёт резерв (EIA).
Время ISS — московское (UTC+3, без перехода на летнее).
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone

import httpx

from . import TickerSnapshot, utcnow

logger = logging.getLogger(__name__)

TICKER_CODE = "brent"
SOURCE_LABEL = "MOEX"

_TIMEOUT = 5.0
_MSK = timezone(timedelta(hours=3))

_BASE = "https://iss.moex.com/iss/engines/futures/markets/forts/securities"
_CONTRACTS_URL = (
    f"{_BASE}.json?iss.meta=off&iss.only=securities&securities.columns=SECID,ASSETCODE,LASTTRADEDATE"
)
_QUOTE_URL = (
    f"{_BASE}/{{secid}}.json?iss.meta=off&iss.only=securities,marketdata"
    "&securities.columns=SECID,SHORTNAME,LASTTRADEDATE,PREVSETTLEPRICE,DECIMALS"
    "&marketdata.columns=SECID,BOARDID,LAST,SETTLEPRICE,LASTCHANGEPRCNT,UPDATETIME,SYSTIME,TRADEDATE"
)

_ASSET_CODE = "BR"
_CONTRACTS_TTL = 6 * 3600
# Значение биржи считается живым, если его возраст не больше этого (задержка биржи ~15 минут уже внутри возраста).
_LIVE_MAX_AGE_MINUTES = 45
# Последняя сессия старше этого числа суток не показывается: берём резерв.
_CLOSED_MAX_AGE_DAYS = 5

_contracts_cache: tuple[float, list[tuple[str, date]]] | None = None


def _table(payload: dict, name: str) -> list[dict]:
    block = (payload or {}).get(name) or {}
    cols = block.get("columns") or []
    return [dict(zip(cols, row)) for row in (block.get("data") or [])]


def _parse_day(raw) -> date | None:
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def pick_nearest_contract(payload: dict, today: date) -> str | None:
    """Ближайший контракт BR, торгуемый и после сегодняшнего дня. `None`, если такого нет."""
    best: tuple[date, str] | None = None
    for row in _table(payload, "securities"):
        if row.get("ASSETCODE") != _ASSET_CODE:
            continue
        last = _parse_day(row.get("LASTTRADEDATE"))
        secid = row.get("SECID")
        if not secid or last is None or last <= today:
            continue
        if best is None or last < best[0]:
            best = (last, str(secid))
    return best[1] if best else None


def _moscow_dt(day: str | None, clock: str | None) -> datetime | None:
    d = _parse_day(day)
    if d is None or not clock:
        return None
    try:
        hh, mm, ss = (int(x) for x in str(clock).split(":")[:3])
        return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=_MSK)
    except (TypeError, ValueError):
        return None


def _sys_dt(raw) -> datetime | None:
    try:
        return datetime.strptime(str(raw)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=_MSK)
    except (TypeError, ValueError):
        return None


def _num(raw) -> float | None:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def build_snapshot(
    payload: dict, *, now: datetime | None = None, min_delay_minutes: int = 15,
) -> TickerSnapshot | None:
    """Снимок `brent` из выдачи ISS по одному контракту; `None`, если пригодного значения нет."""
    now = now or utcnow()
    sec = (_table(payload, "securities") or [None])[0]
    md_rows = _table(payload, "marketdata")
    if sec is None or not md_rows:
        return None
    md = next((r for r in md_rows if r.get("BOARDID") == "RFUD"), md_rows[0])

    last = _num(md.get("LAST"))
    settle = _num(md.get("SETTLEPRICE"))
    price = last if last is not None else settle
    if price is None:
        return None

    prev_settle = _num(sec.get("PREVSETTLEPRICE"))
    change = round((price - prev_settle) / prev_settle * 100, 2) if prev_settle else None

    quote_at = _moscow_dt(md.get("TRADEDATE"), md.get("UPDATETIME"))
    if quote_at is None:
        return None
    quote_utc = quote_at.astimezone(timezone.utc)
    age = now - quote_utc
    if age < timedelta(minutes=-5) or age > timedelta(days=_CLOSED_MAX_AGE_DAYS):
        return None

    observed = None
    sys_at = _sys_dt(md.get("SYSTIME"))
    if sys_at is not None and sys_at >= quote_at:
        observed = int((sys_at - quote_at).total_seconds() // 60)
    # Показываем не меньше договорной задержки и не меньше фактической, округляя вверх до пяти минут.
    delay = max(int(min_delay_minutes), observed or 0)
    delay = ((delay + 4) // 5) * 5
    contract = str(sec.get("SHORTNAME") or sec.get("SECID") or "") or None

    if age <= timedelta(minutes=_LIVE_MAX_AGE_MINUTES) and last is not None:
        return TickerSnapshot(
            code=TICKER_CODE, price=price, change_pct=change, market_open=True,
            fetched_at=quote_utc, source=SOURCE_LABEL, quote_time=quote_utc,
            delay_minutes=delay, contract=contract,
        )
    # Торги закрыты: значение последней сессии, подписанное датой.
    return TickerSnapshot(
        code=TICKER_CODE, price=price, change_pct=change, market_open=False,
        fetched_at=now, source=SOURCE_LABEL, as_of_date=quote_at.date(),
        delay_minutes=delay, contract=contract,
    )


async def _nearest_contract(client: httpx.AsyncClient, today: date) -> str | None:
    global _contracts_cache
    now_m = time.monotonic()
    if _contracts_cache is not None and now_m - _contracts_cache[0] < _CONTRACTS_TTL:
        payload_rows = _contracts_cache[1]
        live = [(s, d) for s, d in payload_rows if d > today]
        if live:
            return min(live, key=lambda x: x[1])[0]
    r = await client.get(_CONTRACTS_URL, timeout=_TIMEOUT)
    r.raise_for_status()
    payload = r.json()
    rows = [
        (str(row["SECID"]), d)
        for row in _table(payload, "securities")
        if row.get("ASSETCODE") == _ASSET_CODE and (d := _parse_day(row.get("LASTTRADEDATE"))) is not None
    ]
    _contracts_cache = (now_m, rows)
    return pick_nearest_contract(payload, today)


async def fetch_brent(min_delay_minutes: int = 15) -> TickerSnapshot | None:
    """Снимок нефти Brent с биржи или `None` (флаг выключает вызывающий; любой сбой даёт `None`, а не исключение)."""
    try:
        async with httpx.AsyncClient(headers={"User-Agent": "ForecastEconomy/1.0 (+ticker)"}) as client:
            today = utcnow().astimezone(_MSK).date()
            secid = await _nearest_contract(client, today)
            if secid is None:
                logger.warning("MOEX Brent: нет подходящего контракта BR")
                return None
            r = await client.get(_QUOTE_URL.format(secid=secid), timeout=_TIMEOUT)
            r.raise_for_status()
            return build_snapshot(r.json(), min_delay_minutes=min_delay_minutes)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.warning("MOEX Brent: запрос не удался: %s", e)
        return None
