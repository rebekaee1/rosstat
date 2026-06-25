"""ETL: ЦБ РФ — учётные цены на драгметаллы → IndicatorData.

Источник: https://www.cbr.ru/scripts/xml_metall.asp
XML API: Record[@Code=1] = Gold, Code=2 = Silver, Code=3 = Platinum, Code=4 = Palladium.
Values in Buy/Sell (руб/грамм).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import ClassVar
from xml.etree import ElementTree

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

DEFAULT_BACKFILL_FROM = date(2015, 1, 1)
CHUNK_DAYS = 365

METAL_CODES = {"gold": "1", "silver": "2", "platinum": "3", "palladium": "4"}

_XML_URL = "https://www.cbr.ru/scripts/xml_metall.asp"


def _parse_ru_float(s: str) -> float:
    return float(s.strip().replace("\u2212", "-").replace("\xa0", "").replace(" ", "").replace(",", "."))


def fetch_gold_xml(date_from: date, date_to: date) -> tuple[bytes, str]:
    url = _XML_URL
    params = {
        "date_req1": date_from.strftime("%d/%m/%Y"),
        "date_req2": date_to.strftime("%d/%m/%Y"),
    }
    session = create_session()
    try:
        resp = session.get(url, params=params, timeout=settings.cbr_request_timeout)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "").lower()
        if "xml" not in ct and resp.status_code == 200:
            logger.warning("Gold XML unexpected content-type: %s", resp.headers.get("content-type"))
        return resp.content, str(resp.url)
    finally:
        session.close()


def parse_gold_xml(xml_data: bytes, metal_code: str = "1") -> list[tuple[date, float]]:
    """Parse CBR metals XML. metal_code: 1=gold, 2=silver, 3=platinum, 4=palladium."""
    root = ElementTree.fromstring(xml_data)
    results: list[tuple[date, float]] = []

    for record in root.findall("Record"):
        code = record.get("Code", "")
        if code != metal_code:
            continue
        date_str = record.get("Date", "")
        buy_elem = record.find("Buy")
        if buy_elem is None or buy_elem.text is None:
            continue
        try:
            d, mo, y = (int(x) for x in date_str.split("."))
            val = _parse_ru_float(buy_elem.text)
            results.append((date(y, mo, d), round(val, 2)))
        except (ValueError, TypeError):
            continue

    results.sort(key=lambda x: x[0])
    return results


class CbrGoldParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_gold_html"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        metal = cfg.get("metal", "gold")
        metal_code = METAL_CODES.get(metal, "1")
        date_to = date.today()

        existing_n = (await db.execute(
            select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
        )).scalar() or 0

        if cfg.get("backfill_from"):
            # Явный исторический бэкфилл (полная история, идемпотентный upsert).
            date_from = date.fromisoformat(cfg["backfill_from"])
        elif existing_n == 0:
            date_from = DEFAULT_BACKFILL_FROM
        else:
            date_from = date_to - timedelta(days=90)

        all_points: list[tuple[date, float]] = []
        chunk_errors: list[str] = []
        chunk_start = date_from
        final_url = ""
        while chunk_start < date_to:
            chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), date_to)
            try:
                xml_data, final_url = await asyncio.to_thread(fetch_gold_xml, chunk_start, chunk_end)
                chunk_points = await asyncio.to_thread(parse_gold_xml, xml_data, metal_code)
                all_points.extend(chunk_points)
            except Exception as chunk_exc:
                logger.warning("Gold chunk %s-%s failed", chunk_start, chunk_end, exc_info=True)
                chunk_errors.append(f"{chunk_start}–{chunk_end}: {chunk_exc}")
            chunk_start = chunk_end + timedelta(days=1)

        by_date: dict[date, float] = {}
        for d, v in all_points:
            by_date[d] = v
        points = sorted(by_date.items())

        if chunk_errors:
            fetch_log.error_message = (
                f"{len(chunk_errors)} chunk errors: {'; '.join(chunk_errors[:3])}"
            )[:500]

        return points, final_url
