"""ETL: Росстат SDDS Population XLSX → IndicatorData.

Файл: SDDS_population_{year}.xlsx
Лист: "Population"
Row 1: заголовки — годы (2010, 2011, ...)
Row 3: Population, Million people — значения

Файл: Popul components_1990+.xlsx (rosstat.gov.ru)
Лист: "1"
Row 5: headers (Годы, Числ.населения, общ.прирост, естеств.прирост, миграц.прирост, ...)
Rows 8+: данные (год, население тыс., приросты тыс.)
"""

from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import ClassVar

import openpyxl
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.upsert import bulk_upsert
from app.services.data_validator import validate_points
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.services.rosstat_sdds_fetcher import fetch_sdds_xlsx, fetch_rosstat_static_xlsx
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    date: date
    value: float


def parse_sdds_population_xlsx(content: bytes) -> list[DataPoint]:
    """Parse SDDS population XLSX → annual population in millions."""
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        ws = wb.worksheets[0]
        rows_data: list[list] = []
        for row in ws.iter_rows(values_only=True):
            rows_data.append(list(row))
    finally:
        wb.close()

    if len(rows_data) < 3:
        raise ValueError(f"Population XLSX: expected >=3 rows, got {len(rows_data)}")

    dates: list[tuple[int, int]] = []
    for col_idx in range(2, len(rows_data[0])):
        header = rows_data[0][col_idx]
        if header is not None:
            try:
                year = int(header)
                if 1990 <= year <= 2100:
                    dates.append((col_idx, year))
            except (ValueError, TypeError):
                pass

    pop_row = rows_data[2]
    points: list[DataPoint] = []
    for col_idx, year in dates:
        val = pop_row[col_idx] if col_idx < len(pop_row) else None
        if val is not None:
            try:
                points.append(DataPoint(date=date(year, 1, 1), value=round(float(val), 2)))
            except (ValueError, TypeError):
                pass

    return sorted(points, key=lambda p: p.date)


def parse_popul_components_xlsx(content: bytes) -> dict[str, list[DataPoint]]:
    """Parse Popul components_1990+.xlsx → population, natural growth, total growth, migration.

    Sheet "1", rows starting from row 8:
    Col A: Year (int)
    Col B: Population Jan 1 (thousands)
    Col C: Total change (thousands)
    Col D: Natural change (thousands)
    Col E: Migration change (thousands)
    """
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        sheets = wb.sheetnames
        ws = wb["1"] if "1" in sheets else wb.worksheets[1]
        rows_data: list[list] = []
        for row in ws.iter_rows(values_only=True):
            rows_data.append(list(row))
    finally:
        wb.close()

    population: list[DataPoint] = []
    total_growth: list[DataPoint] = []
    natural_growth: list[DataPoint] = []
    migration: list[DataPoint] = []

    for row in rows_data[7:]:
        if not row or row[0] is None:
            continue
        try:
            year = int(row[0])
        except (ValueError, TypeError):
            continue
        if year < 1990 or year > 2100:
            continue

        d = date(year, 1, 1)

        if row[1] is not None:
            try:
                pop_thousands = float(row[1])
                population.append(DataPoint(date=d, value=round(pop_thousands / 1000, 2)))
            except (ValueError, TypeError):
                pass

        if row[2] is not None:
            try:
                total_growth.append(DataPoint(date=d, value=round(float(row[2]), 1)))
            except (ValueError, TypeError):
                pass

        if row[3] is not None:
            try:
                natural_growth.append(DataPoint(date=d, value=round(float(row[3]), 1)))
            except (ValueError, TypeError):
                pass

        if row[4] is not None:
            try:
                migration.append(DataPoint(date=d, value=round(float(row[4]), 1)))
            except (ValueError, TypeError):
                pass

    return {
        "population": sorted(population, key=lambda p: p.date),
        "total-growth": sorted(total_growth, key=lambda p: p.date),
        "natural-growth": sorted(natural_growth, key=lambda p: p.date),
        "migration": sorted(migration, key=lambda p: p.date),
    }


INDICATOR_SOURCE_MAP: dict[str, str] = {
    "population": "sdds",
    "population-total-growth": "components",
    "population-natural-growth": "components",
    "population-migration": "components",
}

COMPONENT_SERIES_MAP: dict[str, str] = {
    "population-total-growth": "total-growth",
    "population-natural-growth": "natural-growth",
    "population-migration": "migration",
}


class RosstatPopulationParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_population"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        code = indicator.code
        try:
            source = INDICATOR_SOURCE_MAP.get(code, "sdds")

            if source == "sdds":
                content, final_url = await asyncio.to_thread(fetch_sdds_xlsx, "population")
                fetch_log.source_url = final_url[:500]
                points = await asyncio.to_thread(parse_sdds_population_xlsx, content)
            else:
                content, final_url = await asyncio.to_thread(
                    fetch_rosstat_static_xlsx, "popul_components"
                )
                fetch_log.source_url = final_url[:500]
                all_series = await asyncio.to_thread(parse_popul_components_xlsx, content)
                series_key = COMPONENT_SERIES_MAP.get(code, "population")
                points = all_series.get(series_key, [])

            cfg = indicator.model_config_json or {}
            points = validate_points(points, cfg)

            if not points:
                fetch_log.status = "no_new_data"
                fetch_log.error_message = "Parser returned 0 data points"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.commit()
                return

            records_added, records_updated = await bulk_upsert(db, indicator.id, points)
            logger.info(
                "Upserted %d new, %d updated for '%s'",
                records_added, records_updated, code,
            )
            fetch_log.records_added = records_added

            steps = int(cfg.get("forecast_steps", 0) or 0)
            if steps > 0 and (records_added > 0 or records_updated > 0):
                await retrain_indicator_forecast(db, indicator)

            if records_added > 0 or records_updated > 0:
                await cache_invalidate_indicator(code)

            fetch_log.status = "success" if (records_added > 0 or records_updated > 0) else "no_new_data"
            fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()

        except Exception as e:
            logger.exception("ETL failed for '%s'", code)
            await db.rollback()
            fetch_log.status = "failed"
            fetch_log.error_message = str(e)[:500]
            fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(fetch_log)
            await db.commit()
