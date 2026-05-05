"""ETL: RUONIA (ставка однодневного MBK) с cbr.ru/hd_base/ruonia/dynamics → IndicatorData.

Источник: HTML-таблица https://www.cbr.ru/hd_base/ruonia/dynamics/
Вертикальная таблица: колонки — «Дата ставки», «Ставка RUONIA, % годовых», …
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, timedelta
from typing import ClassVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.http_client import create_session

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")

DEFAULT_BACKFILL_FROM = date(2010, 9, 1)
CHUNK_DAYS = 365


def _parse_ru_float(s: str) -> float:
    t = s.strip().replace("\u2212", "-").replace(" ", "").replace("\xa0", "").replace(",", ".")
    return float(t)


def fetch_ruonia_html(date_from: date, date_to: date) -> tuple[str, str]:
    url = f"{settings.cbr_base_url.rstrip('/')}/hd_base/ruonia/dynamics/"
    params = {
        "UniDbQuery.Posted": "True",
        "UniDbQuery.From": date_from.strftime("%d.%m.%Y"),
        "UniDbQuery.To": date_to.strftime("%d.%m.%Y"),
    }
    session = create_session()
    try:
        resp = session.get(url, params=params, timeout=settings.cbr_request_timeout)
        resp.raise_for_status()
        return resp.text, str(resp.url)
    finally:
        session.close()


def parse_ruonia_html(html: str) -> list[tuple[date, float]]:
    """Parse vertical RUONIA dynamics table: each row = one date."""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    results: list[tuple[date, float]] = []

    for row_html in rows:
        cells = [
            re.sub(r"<[^>]+>", "", td).strip()
            for td in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        ]
        if len(cells) < 2:
            continue
        date_str = cells[0]
        if not _DATE_RE.match(date_str):
            continue
        try:
            d, mo, y = (int(x) for x in date_str.split("."))
            val = _parse_ru_float(cells[1])
            results.append((date(y, mo, d), round(val, 4)))
        except (ValueError, TypeError):
            continue

    results.sort(key=lambda x: x[0])
    return results


class CbrRuoniaParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_ruonia_html"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        date_to = date.today()

        existing_n = (await db.execute(
            select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
        )).scalar() or 0

        if cfg.get("backfill_from"):
            date_from = date.fromisoformat(cfg["backfill_from"])
        elif existing_n == 0:
            date_from = DEFAULT_BACKFILL_FROM
        else:
            win = int(cfg.get("incremental_fetch_days", 60))
            date_from = date_to - timedelta(days=win)

        all_points: list[tuple[date, float]] = []
        chunk_errors: list[str] = []
        chunk_start = date_from
        final_url = ""
        while chunk_start < date_to:
            chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), date_to)
            try:
                html, final_url = await asyncio.to_thread(fetch_ruonia_html, chunk_start, chunk_end)
                chunk_points = await asyncio.to_thread(parse_ruonia_html, html)
                all_points.extend(chunk_points)
                logger.debug("RUONIA chunk %s–%s: %d points", chunk_start, chunk_end, len(chunk_points))
            except Exception as chunk_exc:
                logger.warning("RUONIA chunk %s–%s failed, skipping", chunk_start, chunk_end, exc_info=True)
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
