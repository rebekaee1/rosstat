"""Live FX/Brent source: MOEX ISS, с fallback на CBR XML_daily для FX.

API documentation: https://iss.moex.com/iss/reference/
Public, не требует ключа. Лимит обращений — ~30 req/sec по IP,
наш ticker_worker делает 2 запроса каждые 5 секунд, с запасом.

FX-инструменты — SELT market валютной секции (CETS), тикеры:
    USD000UTSTOM — USD/RUB tomorrow
    EUR_RUB__TOM — EUR/RUB tomorrow
    CNYRUB_TOM   — CNY/RUB tomorrow

Brent — forts market в futures section. SECID меняется каждый месяц
(BRM6 для июня, BRN6 для июля и т.д.); для тикера выбираем
ближайший контракт по `LASTTRADEDATE`.

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

# Spot gold on MOEX SELT (рубли за грамм), тот же CETS-борд, что и FX.
# Совпадает по единице с учётной ценой ЦБ РФ (руб/грамм) — поэтому при
# неликвиде на MOEX подмешиваем дневную учётную цену из xml_metall.asp.
_GOLD_SECID = "GLDRUB_TOM"
_CBR_METAL_URL = "https://www.cbr.ru/scripts/xml_metall.asp"

_BRENT_URL = (
    "https://iss.moex.com/iss/engines/futures/markets/forts/securities.json"
    "?iss.meta=off"
    "&securities.columns=SECID,SHORTNAME,LASTTRADEDATE"
    "&marketdata.columns=SECID,LAST,LASTCHANGEPRCNT"
)


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


async def _fetch_brent(client: httpx.AsyncClient) -> TickerSnapshot | None:
    """Pull nearest Brent futures from MOEX FORTS.

    Тикер контракта меняется ежемесячно (BR-6.26, BR-7.26 ...). Выбираем
    запись с минимальной `LASTTRADEDATE`, ещё не истекшим.
    """
    try:
        r = await client.get(_BRENT_URL, timeout=_TIMEOUT)
        r.raise_for_status()
        d = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("MOEX Brent: fetch failed: %s", e)
        return None

    sec_cols = d.get("securities", {}).get("columns", [])
    if not sec_cols:
        return None
    sec_data = d["securities"]["data"]
    sn_idx = sec_cols.index("SHORTNAME")
    sid_idx = sec_cols.index("SECID")
    ltd_idx = sec_cols.index("LASTTRADEDATE")

    brent_rows = [r for r in sec_data if (r[sn_idx] or "").startswith("BR-")]
    if not brent_rows:
        return None
    brent_rows.sort(key=lambda r: r[ltd_idx] or "9999-12-31")
    nearest = brent_rows[0]
    nearest_secid = nearest[sid_idx]

    md_cols = d.get("marketdata", {}).get("columns", [])
    md_data = d.get("marketdata", {}).get("data", [])
    md_map = {row[md_cols.index("SECID")]: row for row in md_data}
    md_row = md_map.get(nearest_secid)
    if not md_row:
        return None
    last = md_row[md_cols.index("LAST")]
    chgp = md_row[md_cols.index("LASTCHANGEPRCNT")]

    market_open = last is not None
    return TickerSnapshot(
        code="brent",
        price=float(last) if last is not None else 0.0,
        change_pct=float(chgp) if chgp is not None else None,
        market_open=market_open,
        fetched_at=utcnow(),
        source="MOEX",
    )


async def _fetch_cbr_gold(client: httpx.AsyncClient) -> tuple[float | None, float | None]:
    """Fallback: учётная цена золота ЦБ РФ (руб/грамм, Buy) + % к пред. дню.

    Тянем небольшой диапазон последних дней из xml_metall.asp, берём
    последнюю запись по золоту (Code=1) и предыдущую для дельты.
    """
    from datetime import date as _date, timedelta
    from xml.etree import ElementTree

    now = utcnow()
    params = {
        "date_req1": (now - timedelta(days=10)).strftime("%d/%m/%Y"),
        "date_req2": now.strftime("%d/%m/%Y"),
    }
    try:
        r = await client.get(_CBR_METAL_URL, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        root = ElementTree.fromstring(r.content)
    except Exception as e:  # noqa: BLE001 — fallback, любое падение → нет цены
        logger.warning("CBR xml_metall gold: %s", e)
        return None, None

    vals: list[tuple[_date, float]] = []
    for rec in root.findall("Record"):
        if rec.get("Code") != "1":  # 1 = gold
            continue
        buy = rec.find("Buy")
        ds = rec.get("Date", "")
        if buy is None or buy.text is None:
            continue
        try:
            dd, mm, yy = (int(x) for x in ds.split("."))
            v = float(buy.text.strip().replace("\xa0", "").replace(" ", "").replace(",", "."))
            vals.append((_date(yy, mm, dd), v))
        except (ValueError, TypeError):
            continue

    if not vals:
        return None, None
    vals.sort(key=lambda x: x[0])
    last = vals[-1][1]
    chg = None
    if len(vals) >= 2 and vals[-2][1]:
        chg = round((last - vals[-2][1]) / vals[-2][1] * 100, 2)
    return last, chg


async def _fetch_gold(client: httpx.AsyncClient) -> TickerSnapshot | None:
    """Pull spot gold (руб/грамм): MOEX SELT first, CBR учётная цена fallback."""
    price, chg = await _fetch_fx_one(client, "gold-rub-live", _GOLD_SECID)
    if price is not None:
        return TickerSnapshot(
            code="gold-rub-live", price=price, change_pct=chg,
            market_open=True, fetched_at=utcnow(), source="MOEX",
        )
    cbr_price, cbr_chg = await _fetch_cbr_gold(client)
    if cbr_price is None:
        return None
    return TickerSnapshot(
        code="gold-rub-live", price=cbr_price, change_pct=cbr_chg,
        market_open=False, fetched_at=utcnow(), source="ЦБ РФ",
    )


async def fetch_all() -> list[TickerSnapshot]:
    """Pull 3 FX pairs + Brent + gold. MOEX first, CBR fallback.

    Контракт: всегда возвращаем 4 снапшота для FX+Brent если хотя бы один
    источник ответил. Если MOEX не дал цены ни на один борд — для FX
    подмешиваем CBR (источник 'CBR', market_open=False).
    """
    async with httpx.AsyncClient(headers={"User-Agent": "ForecastEconomy/1.0 (+ticker)"}) as client:
        snaps: list[TickerSnapshot] = []

        # Все источники тянем конкурентно: критический путь тика ≈ один таймаут,
        # а не сумма по всем запросам. Иначе медленный MOEX растягивал тик
        # дольше TTL ключей и тикер «мигал» (см. ticker_worker docstring).
        fx_results, brent, gold = await asyncio.gather(
            asyncio.gather(*[_fetch_fx_one(client, code, secid) for code, secid, _ in _FX_INSTRUMENTS]),
            _fetch_brent(client),
            _fetch_gold(client),
            return_exceptions=True,
        )

        if isinstance(fx_results, BaseException):
            logger.warning("ticker fetch_all: FX gather failed: %s", fx_results)
            fx_results = [(None, None)] * len(_FX_INSTRUMENTS)

        moex_results: list[tuple[str, str, str, float | None, float | None]] = [
            (code, secid, cbr_id, pair[0], pair[1])
            for (code, secid, cbr_id), pair in zip(_FX_INSTRUMENTS, fx_results)
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

        if isinstance(brent, BaseException):
            logger.warning("ticker fetch_all: brent failed: %s", brent)
        elif brent is not None:
            snaps.append(brent)

        if isinstance(gold, BaseException):
            logger.warning("ticker fetch_all: gold failed: %s", gold)
        elif gold is not None:
            snaps.append(gold)

        return snaps
