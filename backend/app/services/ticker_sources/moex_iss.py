"""Live FX source: MOEX ISS, с fallback на CBR XML_daily.

API documentation: https://iss.moex.com/iss/reference/
Public, не требует ключа. Лимит обращений — ~30 req/sec по IP,
наш ticker_worker делает запросы каждые 5 секунд, с запасом.

FX-инструменты — SELT market валютной секции (CETS), тикеры:
    USD000UTSTOM — USD/RUB tomorrow
    EUR_RUB__TOM — EUR/RUB tomorrow
    CNYRUB_TOM   — CNY/RUB tomorrow

Нефть Brent и золото сюда не входят: в ленте они берутся из рядов
карточек (`brent`, `gold-price`) в `ticker_worker`, чтобы не
противоречить витрине.

Поле LAST в `marketdata` — last traded price; LASTCHANGEPRCNT —
% к PREVPRICE. UPDATETIME = '10:00:00' с LAST=None означает, что
торги ещё не начались — обрабатываем как market_open=False.

ISS отдаёт несколько строк marketdata (по борду: CETS, AUCB, CNGD,
LICU). Реальные сделки идут на CETS — она ОБЯЗАТЕЛЬНО выбирается
первой, прежде чем падать в fallback.

CBR fallback (звонок 2026-05-22): после санкций ЕС март-2024 EUR/RUB
на MOEX **фактически мёртв** — LAST=None все сессии. USD на CETS-борде
ещё ходит, но редко. Если MOEX не отдал цену — берём официальный
курс ЦБ из XML_daily.asp (обновляется до 14:00 МСК). Это даёт
ежедневное значение с пометкой `market_open=False` и source='CBR'.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from . import TickerSnapshot, utcnow

logger = logging.getLogger(__name__)

# Жёсткий таймаут на один HTTP-запрос к источнику. Раньше был 10с и запросы
# шли последовательно — при тормозящем MOEX один тик растягивался на 30-90с,
# превышая TTL ключей в Redis, и тикер «мигал». Держим коротким: тик должен
# укладываться в TTL даже при недоступном MOEX.
_TIMEOUT = 5.0


_FX_INSTRUMENTS = [
    # (our ticker code, MOEX SECID, CBR Valute ID for fallback)
    ("usd-rub-live", "USD000UTSTOM", "R01235"),
    ("eur-rub-live", "EUR_RUB__TOM", "R01239"),
    ("cny-rub-live", "CNYRUB_TOM",  "R01375"),
]

_FX_URL = (
    "https://iss.moex.com/iss/engines/currency/markets/selt/securities/{secid}.json"
    "?iss.meta=off"
    "&securities.columns=SECID"
    "&marketdata.columns=SECID,BOARDID,LAST,LASTCHANGEPRCNT,UPDATETIME"
)

_CBR_DAILY_URL = "https://www.cbr.ru/scripts/XML_daily.asp"


async def _fetch_fx_one(client: httpx.AsyncClient, our_code: str, secid: str) -> tuple[float | None, float | None]:
    """Pull last price + change% for one FX pair from MOEX SELT.

    ISS возвращает 4 строки marketdata (борды AUCB / CETS / CNGD / LICU).
    Реальные сделки идут на **CETS** — она первой проверяется. Если CETS
    отдал None, проходим по остальным. Если на всех — None: возвращаем
    (None, None), вызывающий пойдёт в CBR fallback.
    """
    try:
        r = await client.get(_FX_URL.format(secid=secid), timeout=_TIMEOUT)
        r.raise_for_status()
        d = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("MOEX FX %s: fetch failed: %s", secid, e)
        return None, None

    rows = d.get("marketdata", {}).get("data", [])
    if not rows:
        return None, None
    cols = d["marketdata"]["columns"]
    last_idx = cols.index("LAST")
    chg_idx = cols.index("LASTCHANGEPRCNT")
    board_idx = cols.index("BOARDID") if "BOARDID" in cols else None

    # Сначала CETS — основной борд CBR-fixing-style сделок.
    if board_idx is not None:
        cets = [row for row in rows if row[board_idx] == "CETS"]
        for row in cets:
            if row[last_idx] is not None:
                chg = float(row[chg_idx]) if row[chg_idx] is not None else None
                return float(row[last_idx]), chg

    # Остальные борды — резерв.
    for row in rows:
        if row[last_idx] is not None:
            chg = float(row[chg_idx]) if row[chg_idx] is not None else None
            return float(row[last_idx]), chg

    return None, None


async def _fetch_cbr_daily(client: httpx.AsyncClient) -> dict[str, tuple[float, float | None]]:
    """Fetch ЦБ XML_daily and return {ValuteID: (price_rub, change_pct_vs_prev)}.

    XML отдаёт <Valute ID='R01235'><Value>78.4123</Value><VunitRate>78.4123</VunitRate>...
    Сегодняшний курс — `VunitRate` (значение за 1 единицу с учётом nominal).
    Для % изменения тянем вчерашний курс отдельным запросом — на старте
    ETL дешевле, чем строить дельту на каждом тике.
    """
    from xml.etree import ElementTree
    from datetime import timedelta

    out: dict[str, tuple[float, float | None]] = {}

    # Today + yesterday конкурентно — fallback не должен растягивать тик.
    yest = (utcnow() - timedelta(days=1)).strftime("%d/%m/%Y")
    today_resp, yest_resp = await asyncio.gather(
        client.get(_CBR_DAILY_URL, timeout=_TIMEOUT),
        client.get(_CBR_DAILY_URL, params={"date_req": yest}, timeout=_TIMEOUT),
        return_exceptions=True,
    )

    try:
        if isinstance(today_resp, BaseException):
            raise today_resp
        today_resp.raise_for_status()
        today_root = ElementTree.fromstring(today_resp.content)
    except Exception as e:
        logger.warning("CBR XML_daily today: %s", e)
        return out

    try:
        if isinstance(yest_resp, BaseException):
            raise yest_resp
        yest_resp.raise_for_status()
        yest_root = ElementTree.fromstring(yest_resp.content)
    except Exception:
        yest_root = None

    def _val(root, vid: str) -> float | None:
        node = root.find(f".//Valute[@ID='{vid}']")
        if node is None:
            return None
        txt = (node.findtext("VunitRate") or node.findtext("Value") or "").replace(",", ".")
        try:
            return float(txt)
        except ValueError:
            return None

    for _our_code, _secid, vid in _FX_INSTRUMENTS:
        v_today = _val(today_root, vid)
        if v_today is None:
            continue
        v_yest = _val(yest_root, vid) if yest_root is not None else None
        chg = None
        if v_yest and v_yest > 0:
            chg = round((v_today - v_yest) / v_yest * 100, 2)
        out[vid] = (v_today, chg)
    return out


async def fetch_all() -> list[TickerSnapshot]:
    """Pull 3 FX pairs. MOEX first, CBR fallback.

    Brent/золото — не здесь (ряды карточек в ticker_worker).
    Если MOEX не дал цены ни на один борд — для FX подмешиваем CBR
    (источник 'ЦБ РФ', market_open=False).
    """
    async with httpx.AsyncClient(headers={"User-Agent": "ForecastEconomy/1.0 (+ticker)"}) as client:
        snaps: list[TickerSnapshot] = []

        # Все FX тянем конкурентно: критический путь тика ≈ один таймаут.
        fx_results = await asyncio.gather(
            *[_fetch_fx_one(client, code, secid) for code, secid, _ in _FX_INSTRUMENTS],
            return_exceptions=True,
        )

        normalized: list[tuple[float | None, float | None]] = []
        for pair in fx_results:
            if isinstance(pair, BaseException):
                logger.warning("ticker fetch_all: FX one failed: %s", pair)
                normalized.append((None, None))
            else:
                normalized.append(pair)

        moex_results: list[tuple[str, str, str, float | None, float | None]] = [
            (code, secid, cbr_id, pair[0], pair[1])
            for (code, secid, cbr_id), pair in zip(_FX_INSTRUMENTS, normalized)
        ]

        # Если хоть один FX без цены — тянем CBR один раз и подмешиваем.
        need_cbr = any(p is None for _c, _s, _v, p, _ch in moex_results)
        cbr_map: dict[str, tuple[float, float | None]] = {}
        if need_cbr:
            cbr_map = await _fetch_cbr_daily(client)

        for code, secid, cbr_id, price, chg in moex_results:
            if price is not None:
                snaps.append(TickerSnapshot(
                    code=code, price=price, change_pct=chg,
                    market_open=True, fetched_at=utcnow(), source="MOEX",
                ))
                continue
            cbr = cbr_map.get(cbr_id)
            if cbr is None:
                continue
            cbr_price, cbr_chg = cbr
            snaps.append(TickerSnapshot(
                code=code, price=cbr_price, change_pct=cbr_chg,
                market_open=False, fetched_at=utcnow(), source="ЦБ РФ",
            ))

        return snaps
