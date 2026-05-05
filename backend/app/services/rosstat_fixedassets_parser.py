"""
Parser for Rosstat fixed assets depreciation rate: St_izn_of_YYYY.xlsx.

Source: rosstat.gov.ru/storage/mediabank/St_izn_of_YYYY.xlsx
Structure: Sheet "1", row 4+ = [year, percentage]
"""

from __future__ import annotations

import io
import logging
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar

import openpyxl
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Indicator, FetchLog
from app.services.http_client import create_session
from app.services.base_parser import BaseParser

logger = logging.getLogger(__name__)

BASE_URL = "https://rosstat.gov.ru/storage/mediabank/"


@dataclass
class DataPoint:
    date: date
    value: float


def parse_depreciation_xlsx(content: bytes) -> list[DataPoint]:
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        ws = None
        for s in wb.worksheets:
            if s.title != "Содержание":
                ws = s
                break
        if ws is None:
            ws = wb.worksheets[-1]
        rows_data = [list(row) for row in ws.iter_rows(values_only=True)]
    finally:
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
        val_str = str(row[1] or "").strip().replace("\u2212", "-").replace(",", ".")
        try:
            val = float(val_str)
            if 0 < val < 100:
                points.append(DataPoint(date=date(year, 1, 1), value=round(val, 1)))
        except (ValueError, TypeError):
            continue

    return sorted(points, key=lambda p: p.date)


class RosstatFixedAssetsParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_fixed_assets"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        current_year = datetime.now().year

        session = create_session()
        try:
            session.verify = settings.rosstat_ca_cert
            content = None
            used_url = ""
            for year in range(current_year + 1, current_year - 7, -1):
                fn = f"St_izn_of_{year}.xlsx"
                url = BASE_URL + fn
                try:
                    resp = session.get(url, timeout=60)
                    ct = resp.headers.get("content-type", "")
                    if "html" in ct.lower() and resp.status_code == 200:
                        logger.warning("Got HTML instead of XLSX from %s", url)
                        continue
                    if resp.status_code == 200 and resp.content[:4] == b"PK\x03\x04":
                        content = resp.content
                        used_url = url
                        break
                except Exception as e:
                    logger.debug("Download failed for %s: %s", url, e)
                    continue
        finally:
            session.close()

        if not content:
            raise ValueError("St_izn_of XLSX not found")

        return parse_depreciation_xlsx(content), used_url

    def _validate(self, points: list, cfg: dict) -> list:
        valid = [
            p for p in points
            if isinstance(p.value, (int, float)) and not math.isnan(p.value)
        ]
        if len(valid) < len(points):
            logger.warning("Filtered out %d invalid (NaN/non-numeric) fixed-asset values", len(points) - len(valid))
        return valid
