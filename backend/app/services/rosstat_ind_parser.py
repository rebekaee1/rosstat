"""
Parser for Rosstat monthly indicator compilation: ind_MM-YYYY.xlsx.

Source: rosstat.gov.ru/storage/mediabank/ind_MM-YYYY.xlsx
Sheets used:
  - "1.12 " → Retail trade turnover (млрд руб.)
  - "1.8 "  → Housing commissioned (млн кв.м)

Structure:
  Row 0-1: headers (Year, Quarters, Months)
  Row 2-3: section title
  Row 4+: data (Year | Annual | Q1-Q4 | Jan-Dec)
  Months in cols G-R (indices 6-17)
"""

from __future__ import annotations

import io
import logging
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import ClassVar

import openpyxl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Indicator, IndicatorData, FetchLog
from app.services.http_client import create_session
from app.services.base_parser import BaseParser
from app.services.upsert import upsert_indicator_data
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)

BASE_URL = "https://rosstat.gov.ru/storage/mediabank/"


@dataclass
class DataPoint:
    date: date
    value: float


def _to_float(cell) -> float | None:
    if cell is None:
        return None
    s = str(cell).strip().replace("\u2212", "-").replace(",", ".").replace("\xa0", "").replace(" ", "")
    if s in ("", "…", "-", "..."):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _extract_year(cell) -> int | None:
    if cell is None:
        return None
    s = str(cell).strip()
    m = re.match(r"(\d{4})", s)
    if m:
        y = int(m.group(1))
        if 1990 <= y <= 2100:
            return y
    return None


def parse_ind_sheet(content: bytes, sheet_name: str) -> list[DataPoint]:
    """Parse a sheet from ind_MM-YYYY.xlsx → monthly DataPoints."""
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        ws = None
        for name in wb.sheetnames:
            if sheet_name.strip() in name.strip():
                ws = wb[name]
                break
        if ws is None:
            raise ValueError(f"Sheet '{sheet_name}' not found in {wb.sheetnames[:10]}")

        rows_data = [list(row) for row in ws.iter_rows(values_only=True)]
    finally:
        wb.close()

    points = []
    seen: set[tuple[int, int]] = set()
    data_started = False

    for row in rows_data:
        if not row or len(row) < 3:
            continue

        first_cell = str(row[0] or "").strip().lower()
        if data_started and ("в %" in first_cell or "percent" in first_cell):
            break

        year = _extract_year(row[0])
        if year is None:
            continue

        data_started = True

        for month_idx in range(12):
            col = 6 + month_idx
            if col >= len(row):
                break
            key = (year, month_idx + 1)
            if key in seen:
                continue
            val = _to_float(row[col])
            if val is not None and val > 0:
                seen.add(key)
                points.append(DataPoint(
                    date=date(year, month_idx + 1, 1),
                    value=round(val, 2),
                ))

    return sorted(points, key=lambda p: p.date)


def _fetch_latest_ind(session) -> tuple[bytes, str]:
    """Try to download the latest ind_MM-YYYY.xlsx by trying recent months."""
    now = datetime.now()
    candidates = []
    for offset in range(6):
        m = now.month - offset
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        candidates.append(f"ind_{m:02d}-{y}.xlsx")

    for fn in candidates:
        url = BASE_URL + fn
        try:
            resp = session.get(url, timeout=90)
            ct = resp.headers.get("content-type", "")
            if "html" in ct.lower() and resp.status_code == 200:
                logger.warning("Got HTML instead of XLSX from %s", url)
                continue
            if resp.status_code == 200 and resp.content[:4] == b"PK\x03\x04":
                logger.info("Downloaded %s (%d KB)", fn, len(resp.content) // 1024)
                return resp.content, url
        except Exception as e:
            logger.debug("Download failed for %s: %s", url, e)
            continue

    raise ValueError(f"ind XLSX not found (tried {candidates})")


SHEET_MAP = {
    "retail-trade": "1.12 ",
    "housing-commissioned": "1.8 ",
    "construction-work": "1.7 ",
    "capital-investment": "1.6 ",
}


class RosstatIndParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_ind_monthly"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            cfg = indicator.model_config_json or {}
            sheet_name = cfg.get("ind_sheet", SHEET_MAP.get(code, ""))

            if not sheet_name:
                raise ValueError(f"No sheet mapping for indicator {code}")

            session = create_session()
            try:
                session.verify = settings.rosstat_ca_cert
                content, url = _fetch_latest_ind(session)
            finally:
                session.close()

            fetch_log.source_url = url
            points = parse_ind_sheet(content, sheet_name)

            if not points:
                logger.warning("No points parsed for %s", code)
                fetch_log.status = "no_new_data"
                fetch_log.records_added = 0
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.commit()
                return

            valid_points = [
                p for p in points
                if isinstance(p.value, (int, float)) and not math.isnan(p.value)
            ]
            if len(valid_points) < len(points):
                logger.warning("%s: filtered out %d invalid values", code, len(points) - len(valid_points))
            points = valid_points

            count_before = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            for p in points:
                await db.execute(upsert_indicator_data(indicator.id, p.date, p.value))
            await db.flush()

            count_after = (await db.execute(
                select(func.count(IndicatorData.id))
                .where(IndicatorData.indicator_id == indicator.id)
            )).scalar() or 0

            records_added = count_after - count_before
            fetch_log.status = "success"
            fetch_log.records_added = records_added
            fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()
            await cache_invalidate_indicator(code)
            logger.info("%s: upserted %d new monthly points (of %d) from ind XLSX", code, records_added, len(points))
        except Exception as exc:
            await db.rollback()
            fetch_log.status = "failed"
            fetch_log.error_message = str(exc)[:500]
            fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(fetch_log)
            await db.commit()
            raise
