"""
Parser for Rosstat fixed assets depreciation rate: St_izn_of_YYYY.xlsx.

Source: rosstat.gov.ru/storage/mediabank/St_izn_of_YYYY.xlsx
Structure: Sheet "1", row 4+ = [year, percentage]
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

import openpyxl
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator, IndicatorData, FetchLog
from app.services.http_client import create_session
from app.services.base_parser import BaseParser
from app.services.upsert import upsert_indicator_data

logger = logging.getLogger(__name__)

BASE_URL = "https://rosstat.gov.ru/storage/mediabank/"


@dataclass
class DataPoint:
    date: date
    value: float


def parse_depreciation_xlsx(content: bytes) -> list[DataPoint]:
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = None
    for s in wb.worksheets:
        if s.title != "Содержание":
            ws = s
            break
    if ws is None:
        ws = wb.worksheets[-1]
    rows_data = [list(row) for row in ws.iter_rows(values_only=True)]
    wb.close()

    points = []
    for row in rows_data:
        if not row or len(row) < 2:
            continue
        year_str = str(row[0] or "").strip()
        m = re.match(r"(\d{4})", year_str)
        if not m:
            continue
        year = int(m.group(1))
        if year < 1990 or year > 2100:
            continue
        val_str = str(row[1] or "").strip().replace(",", ".")
        try:
            val = float(val_str)
            if 0 < val < 100:
                points.append(DataPoint(date=date(year, 1, 1), value=round(val, 1)))
        except (ValueError, TypeError):
            continue

    return sorted(points, key=lambda p: p.date)


class RosstatFixedAssetsParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_fixed_assets"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        session = create_session()
        content = None
        used_url = ""
        for year in range(2026, 2020, -1):
            fn = f"St_izn_of_{year}.xlsx"
            url = BASE_URL + fn
            try:
                resp = session.get(url, timeout=60)
                if resp.status_code == 200 and resp.content[:4] == b"PK\x03\x04":
                    content = resp.content
                    used_url = url
                    break
            except Exception:
                continue

        if not content:
            raise ValueError("St_izn_of XLSX not found")

        fetch_log.source_url = used_url
        points = parse_depreciation_xlsx(content)

        if not points:
            fetch_log.status = "no_new_data"
            fetch_log.records_added = 0
            return

        count = await upsert_indicator_data(db, indicator.id, [(p.date, p.value) for p in points])
        fetch_log.status = "success"
        fetch_log.records_added = count
        logger.info("depreciation-rate: upserted %d points", count)
