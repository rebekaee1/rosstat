"""ETL: курсы валют ЦБ РФ (XML_dynamic) → IndicatorData.

Все валюты ежедневной ведомости Банка России: пять исходных пар (usd-rub,
eur-rub, cny-rub, try-rub, kzt-rub) и 49 пар из справочника
``app.data.cbr_currencies`` (08.11.2026). У мелких валют ряд хранится за 100,
1 000, 10 000 или 1 000 000 единиц (``CBR_QUOTE_UNITS``), как в ведомости ЦБ.
Источник: https://www.cbr.ru/scripts/XML_dynamic.asp

Коды валют (параметр VAL_NM_RQ) сверены 2026-10-08 с официальным справочником
Банка России `XML_valFull.asp` и ежедневной ведомостью `XML_daily.asp`:
  R01700J — турецкая лира (ISO TRY, номинал 10, с 2005-01-01),
  R01335  — тенге (ISO KZT, номинал 100, с 1998-01-01).
Номинал делит `parse_fx_xml`, поэтому в ряду всегда рубли за одну единицу.
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
from app.data.cbr_currencies import CBR_CURRENCY_CODES, CBR_QUOTE_UNITS
from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

CURRENCY_MAP: dict[str, str] = {
    "usd-rub": "R01235",
    "eur-rub": "R01239",
    "cny-rub": "R01375",
    "try-rub": "R01700J",
    "kzt-rub": "R01335",
    **CBR_CURRENCY_CODES,
}

DEFAULT_BACKFILL_FROM = date(2015, 1, 1)


def _parse_ru_float(s: str) -> float:
    return float(s.strip().replace("\u2212", "-").replace(",", ".").replace("\xa0", "").replace(" ", ""))


def fetch_fx_xml(val_code: str, date_from: date, date_to: date) -> tuple[str, str]:
    """GET XML_dynamic for a currency pair."""
    url = f"{settings.cbr_base_url.rstrip('/')}/scripts/XML_dynamic.asp"
    params = {
        "date_req1": date_from.strftime("%d/%m/%Y"),
        "date_req2": date_to.strftime("%d/%m/%Y"),
        "VAL_NM_RQ": val_code,
    }
    session = create_session()
    try:
        resp = session.get(url, params=params, timeout=settings.cbr_request_timeout)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "").lower()
        if "xml" not in ct and resp.status_code == 200:
            logger.warning("FX XML unexpected content-type: %s", resp.headers.get("content-type"))
        return resp.text, str(resp.url)
    finally:
        session.close()


def parse_fx_xml(xml_text: str, quote_units: int = 1) -> list[tuple[date, float]]:
    """Parse XML_dynamic response into (date, value) pairs.

    ``quote_units`` — сколько единиц валюты в одной точке ряда (1 для доллара,
    10 000 для сума). Каждая запись делится на свой номинал ЦБ.
    """
    root = ElementTree.fromstring(xml_text)
    results: list[tuple[date, float]] = []
    for record in root.findall("Record"):
        date_str = record.get("Date", "")
        nominal_el = record.find("Nominal")
        value_el = record.find("Value")
        if not date_str or value_el is None or nominal_el is None:
            continue
        d, m, y = date_str.split(".")
        dt = date(int(y), int(m), int(d))
        nominal = _parse_ru_float(nominal_el.text or "1")
        value = _parse_ru_float(value_el.text or "0")
        rate = round(value / nominal * quote_units, 4) if nominal else value
        results.append((dt, rate))
    results.sort(key=lambda x: x[0])
    return results


class CbrFxParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_fx_xml"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        code = indicator.code
        val_code = CURRENCY_MAP.get(code)
        if not val_code:
            raise ValueError(f"Unknown currency code '{code}'")

        date_to = date.today()

        existing_n, earliest = (await db.execute(
            select(func.count(IndicatorData.id), func.min(IndicatorData.date))
            .where(IndicatorData.indicator_id == indicator.id)
        )).one()
        existing_n = existing_n or 0

        # Полная история — пока ряд пуст или не дотянут до пола backfill_from;
        # дальше ежедневный прогон берёт только окно последних дней (08.11.2026:
        # валют стало 54, ежедневная перекачка истории с 1998 года не нужна).
        backfill_from = date.fromisoformat(cfg["backfill_from"]) if cfg.get("backfill_from") else None
        if earliest is not None and hasattr(earliest, "date"):
            earliest = earliest.date()
        if backfill_from and (existing_n == 0 or earliest is None or earliest > backfill_from + timedelta(days=45)):
            date_from = backfill_from
        elif backfill_from is None and existing_n == 0:
            date_from = DEFAULT_BACKFILL_FROM
        else:
            win = int(cfg.get("incremental_fetch_days", 60))
            date_from = date_to - timedelta(days=win)

        xml_text, final_url = await asyncio.to_thread(fetch_fx_xml, val_code, date_from, date_to)
        points = await asyncio.to_thread(parse_fx_xml, xml_text, CBR_QUOTE_UNITS.get(code, 1))
        return points, final_url
