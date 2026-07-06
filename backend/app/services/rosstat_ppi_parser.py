"""ETL: Росстат PPI → IndicatorData (canonical русский Rosstat, без SDDS).

Источник — официальный ежемесячный бюллетень `osn-{MM}-{YYYY}.pdf` от Росстата
(rosstat.gov.ru/folder/210), summary-блок (стр. 6) с строкой:

  Индекс цен производителей промышленных товаров   <MoM>  <YoY>  <YTD>  ...

Первое значение — индекс цен в % к предыдущему месяцу (MoM%) для
reference-месяца PDF (обычно T-1).

ADR-0004 path P (compat — DB хранит cumulative chained 2010=100 формат, frontend
не меняется): парсер читает последнюю точку индикатора в DB, умножает её на
свежий MoM% / 100, получает новую cumulative-точку для нового месяца.

Trade-off: один новый datapoint per ETL run. Полный исторический ряд 2010+ не
рефрешится автоматически — остаётся в DB от прошлой SDDS-этапы (idempotent
bulk_upsert). Когда rosstat опубликует monthly PPI XLSX — расширим парсер.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.data_validator import validate_points
from app.services.rosstat_labor_parser import parse_report_month_from_url
from app.services.rosstat_sdds_fetcher import fetch_latest_socioeconomic_report_pdf

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    date: date
    value: float


_PPI_LINE_RE = re.compile(
    r"Индекс\s+цен\s+производителей\s+промышленных\s+товаров[^0-9]+"
    r"(\d+(?:[,.]\d+)?)\s+",
    re.IGNORECASE,
)


def _parse_float_ru(value: str) -> float:
    return float(value.replace("\u00a0", "").replace(" ", "").replace(",", "."))


def parse_ppi_mom_from_report(text: str) -> float | None:
    """Извлекает PPI MoM% (первое число в строке) из текста PDF socioeconomic
    report. Возвращает None если строка не найдена или значение out-of-range.
    """
    m = _PPI_LINE_RE.search(text)
    if not m:
        return None
    try:
        val = _parse_float_ru(m.group(1))
        if 50 <= val <= 250:
            return val
    except ValueError:
        pass
    return None


def parse_ppi_report_pdf(content: bytes) -> float | None:
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return parse_ppi_mom_from_report(text)


class RosstatPpiParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_ppi"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        report_content, report_url = await asyncio.to_thread(fetch_latest_socioeconomic_report_pdf)
        mom_pct = await asyncio.to_thread(parse_ppi_report_pdf, report_content)

        if mom_pct is None:
            logger.warning("PPI: 'Индекс цен производителей' line not found in PDF")
            return [], report_url

        reference_month = parse_report_month_from_url(report_url)
        if reference_month is None:
            logger.warning("PPI: cannot determine reference month from URL %s", report_url)
            return [], report_url

        result = await db.execute(
            select(IndicatorData)
            .where(IndicatorData.indicator_id == indicator.id)
            .where(IndicatorData.date < reference_month)
            .order_by(IndicatorData.date.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            logger.warning(
                "PPI: no existing DB data to chain from. Skipping (run a one-time "
                "historical seed first).",
            )
            return [], report_url

        new_cumulative = float(last.value) * mom_pct / 100.0
        new_point = DataPoint(date=reference_month, value=round(new_cumulative, 2))
        logger.info(
            "PPI chain: %s=%.2f, MoM=%.1f%%, new %s=%.2f",
            last.date, float(last.value), mom_pct, reference_month, new_cumulative,
        )
        return [new_point], report_url

    def _validate(self, points: list, cfg: dict) -> list:
        return validate_points(points, cfg)
