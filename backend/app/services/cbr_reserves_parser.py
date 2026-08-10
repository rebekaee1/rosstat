"""ETL: ЦБ РФ — международные резервы (еженедельные) → IndicatorData.

Источник: https://www.cbr.ru/hd_base/mrrf/mrrf_7d/
HTML-таблица UniDbQuery: дата DD.MM.YYYY | значение (млрд $, запятая как разделитель).

Trap (2026-08): фильтр периода на странице — monthpicker, параметры
``UniDbQuery.From`` / ``To`` принимают ``MM.YYYY`` (например ``05.1998``),
не ``DD.MM.YYYY``. Старый формат сайт молча игнорировал и отдавал
дефолтное окно ~последний год → в БД оставался огрызок с ~июля 2025.
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
# Пол источника на странице ЦБ: «Данные доступны с 29.05.1998».
DEFAULT_BACKFILL_FROM = date(1998, 5, 1)
CHUNK_DAYS = 365


def _parse_ru_float(s: str) -> float:
    t = s.strip().replace("\u2212", "-").replace(" ", "").replace("\xa0", "").replace(",", ".")
    return float(t)


def format_unidb_month(d: date) -> str:
    """Формат периода для monthpicker UniDbQuery: MM.YYYY."""
    return f"{d.month:02d}.{d.year}"


def fetch_reserves_html(date_from: date, date_to: date) -> tuple[str, str]:
    url = f"{settings.cbr_base_url.rstrip('/')}/hd_base/mrrf/mrrf_7d/"
    params = {
        "UniDbQuery.Posted": "True",
        "UniDbQuery.From": format_unidb_month(date_from),
        "UniDbQuery.To": format_unidb_month(date_to),
    }
    session = create_session()
    try:
        resp = session.get(url, params=params, timeout=settings.cbr_request_timeout)
        resp.raise_for_status()
        return resp.text, str(resp.url)
    finally:
        session.close()


def parse_reserves_html(html: str) -> list[tuple[date, float]]:
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
            results.append((date(y, mo, d), round(val, 2)))
        except (ValueError, TypeError):
            continue

    results.sort(key=lambda x: x[0])
    return results


class CbrReservesParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_reserves_html"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        date_to = date.today()

        floor = DEFAULT_BACKFILL_FROM
        raw_from = cfg.get("backfill_from")
        if raw_from:
            try:
                floor = date.fromisoformat(str(raw_from))
            except ValueError:
                logger.warning(
                    "%s: bad backfill_from %r — использую %s",
                    indicator.code, raw_from, DEFAULT_BACKFILL_FROM,
                )

        earliest = (await db.execute(
            select(func.min(IndicatorData.date)).where(
                IndicatorData.indicator_id == indicator.id
            )
        )).scalar_one_or_none()

        windows: list[tuple[date, date]] = []
        if earliest is None:
            windows.append((floor, date_to))
        else:
            # Self-healing: если в БД огрызок (формат дат раньше был сломан),
            # дозапрашиваем [floor, earliest) одним проходом вместе с хвостом.
            if earliest > floor:
                windows.append((floor, earliest - timedelta(days=1)))
            win = int(cfg.get("incremental_fetch_days", 90))
            windows.append((max(floor, date_to - timedelta(days=win)), date_to))

        all_points: list[tuple[date, float]] = []
        chunk_errors: list[str] = []
        final_url = ""
        for win_start, win_end in windows:
            if win_start > win_end:
                continue
            chunk_start = win_start
            while chunk_start <= win_end:
                chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), win_end)
                try:
                    html, final_url = await asyncio.to_thread(
                        fetch_reserves_html, chunk_start, chunk_end,
                    )
                    chunk_points = await asyncio.to_thread(parse_reserves_html, html)
                    all_points.extend(chunk_points)
                    logger.debug(
                        "Reserves chunk %s–%s: %d points",
                        format_unidb_month(chunk_start),
                        format_unidb_month(chunk_end),
                        len(chunk_points),
                    )
                except Exception as chunk_exc:
                    logger.warning(
                        "Reserves chunk %s–%s failed, skipping",
                        chunk_start, chunk_end, exc_info=True,
                    )
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
