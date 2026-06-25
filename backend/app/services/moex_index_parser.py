"""ETL parser for MOEX stock-market indices via the public ISS API.

Source: GET https://iss.moex.com/iss/history/engines/stock/markets/index/
            securities/{SECID}.json?iss.meta=off&sort_order=asc&start={N}

Each `history` row carries TRADEDATE and CLOSE; we map (date, close). SECID is
read from `model_config_json.moex_secid` so a single parser serves every index
(IMOEX, MCFTR, RTSI, RGBI, RUCBTRNS, …). Daily series, no forecast.

Биржевой ряд — суб-месячная природа, прогноз для индексов не считается
(forecast_steps=0 в seed). Live-котировка в тикере здесь не трогается — это
только историческая страница /indicator/<code>.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import ClassVar

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser

logger = logging.getLogger(__name__)

_BASE = "https://iss.moex.com/iss/history/engines/stock/markets/index/securities"
_PAGE = 100


def _fetch_page(secid: str, start: int, from_date: str | None) -> tuple[list[tuple[date, float]], int]:
    """Return (parsed (date, close) points, raw row count of the page).

    Pagination must advance on the RAW row count, not the filtered count:
    early history of some indices carries rows with NULL CLOSE, and stopping
    when the filtered list is short would truncate the series.
    """
    params = {"iss.meta": "off", "sort_order": "asc", "start": start}
    if from_date:
        params["from"] = from_date
    url = f"{_BASE}/{secid}.json"
    with httpx.Client(timeout=30.0, headers={"User-Agent": "ForecastEconomy/1.0"}) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        block = r.json().get("history", {})
    cols = block.get("columns", [])
    rows = block.get("data", [])
    try:
        di = cols.index("TRADEDATE")
        ci = cols.index("CLOSE")
    except ValueError:
        return [], len(rows)
    out: list[tuple[date, float]] = []
    for row in rows:
        try:
            d = date.fromisoformat(str(row[di]))
            v = row[ci]
        except (IndexError, ValueError, TypeError):
            continue
        if v is None:
            continue
        try:
            out.append((d, float(v)))
        except (ValueError, TypeError):
            continue
    return out, len(rows)


class MoexIndexParser(BaseParser):
    parser_type: ClassVar[str] = "moex_index_daily"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        secid = str(cfg.get("moex_secid") or "").upper()
        if not secid:
            raise ValueError("moex_index_daily requires model_config_json.moex_secid")

        existing_n = (await db.execute(
            select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
        )).scalar() or 0
        from_date: str | None = None
        if existing_n > 0:
            from_date = (date.today() - timedelta(days=14)).isoformat()

        by_date: dict[date, float] = {}
        start = 0
        for _ in range(400):  # safety bound (~40k rows)
            page, raw_n = await asyncio.to_thread(_fetch_page, secid, start, from_date)
            for d, v in page:
                by_date[d] = v
            if raw_n < _PAGE:
                break
            start += _PAGE

        points = sorted(by_date.items())
        return points, f"{_BASE}/{secid}.json"
