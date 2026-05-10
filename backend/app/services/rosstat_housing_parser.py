"""ETL: Росстат housing price indices → IndicatorData (canonical русский Rosstat).

Источник — официальный ежемесячный бюллетень `osn-{MM}-{YYYY}.pdf` от Росстата
(rosstat.gov.ru/folder/210), раздел "ИНДЕКСЫ ЦЕН НА РЫНКЕ ЖИЛЬЯ":

  «На первичном и вторичном рынках жилья ... составили соответственно
   <QoQ-primary>% и <QoQ-secondary>%»

Plus табличный заголовок "I квартал YYYY г. в % к IV кварталу YYYY-1 г."
определяет reference-quarter.

ADR-0004 path P (compat — DB хранит quarterly cumulative chained 2010=100,
frontend не меняется): парсер читает последнюю quarterly-точку индикатора в DB,
умножает её на свежий QoQ% / 100 → новая cumulative-точка.

Trade-off: один новый datapoint per ETL run per indicator (housing-price-primary,
housing-price-secondary). Полный исторический ряд 2014+ остаётся в DB от прошлой
SDDS-этапы. Когда rosstat опубликует quarterly housing XLSX — расширим парсер.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from PyPDF2 import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.data_validator import validate_points
from app.services.rosstat_sdds_fetcher import fetch_latest_socioeconomic_report_pdf

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    date: date
    value: float


_ROMAN_TO_QUARTER = {"I": 1, "II": 2, "III": 3, "IV": 4}
_QUARTER_END_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}

_QOQ_PAIR_RE = re.compile(
    r"составили\s+соответственно[^\d]{0,40}"
    r"(\d{2,3}[,.]\d)\s*[%][^\d]{1,40}?(\d{2,3}[,.]\d)\s*[%]",
    re.IGNORECASE | re.DOTALL,
)
_QUARTER_HEADER_RE = re.compile(
    r"(I{1,3}|IV)\s*квартал[а-я]?\s+(\d{4})\s*г",
    re.IGNORECASE,
)


def _parse_float_ru(value: str) -> float:
    return float(value.replace("\u00a0", "").replace(" ", "").replace(",", "."))


def _normalize_year_text(text: str) -> str:
    """Rosstat PDF extraction sometimes splits year digits: '202 6' → '2026',
    '20 26' → '2026', даже '2 0 2 6'. Collapse spaces в 4-digit год starting with 20."""
    return re.sub(r"\b20\s*\d\s*\d\b", lambda m: m.group(0).replace(" ", ""), text)


_HOUSING_SECTION_RE = re.compile(r"4\.2\.\s*РЫНОК\s+ЖИЛЬЯ")


def parse_housing_qoq_pair(text: str) -> tuple[float, float] | None:
    """Извлекает (primary_QoQ%, secondary_QoQ%) из summary-строки PDF report.

    Шаблон: «На первичном и вторичном рынках жилья ... составили соответственно
    <P>% и <S>%». Возвращает (P, S) или None.

    Поиск ограничен подсекцией "РЫНОК ЖИЛЬЯ" (4.2 в socioeconomic report),
    чтобы не схватить случайное "составили соответственно" из других секций.
    """
    text_norm = _normalize_year_text(text)
    section = _HOUSING_SECTION_RE.search(text_norm)
    if not section:
        return None
    snippet = text_norm[section.end():section.end() + 1500]
    m = _QOQ_PAIR_RE.search(snippet)
    if not m:
        return None
    try:
        primary = _parse_float_ru(m.group(1))
        secondary = _parse_float_ru(m.group(2))
        if 50 <= primary <= 200 and 50 <= secondary <= 200:
            return (primary, secondary)
    except ValueError:
        pass
    return None


def parse_housing_reference_quarter(text: str) -> date | None:
    """Извлекает reference-quarter из табличного заголовка
    «I квартал YYYY г. в % к IV кварталу YYYY-1 г.»

    Берёт первый квартал, упомянутый в контексте после "ИНДЕКСЫ ЦЕН НА РЫНКЕ ЖИЛЬЯ".
    Возвращает дату конца квартала (e.g. Q1 2026 → 2026-03-01).
    """
    text_norm = _normalize_year_text(text)
    section_match = re.search(
        r"ИНДЕКСЫ\s+ЦЕН\s+НА\s+РЫНКЕ\s+ЖИЛЬЯ", text_norm, re.IGNORECASE
    )
    if not section_match:
        return None

    snippet = text_norm[section_match.end():section_match.end() + 2000]
    m = _QUARTER_HEADER_RE.search(snippet)
    if not m:
        return None
    try:
        roman = m.group(1).upper()
        quarter = _ROMAN_TO_QUARTER.get(roman)
        year = int(m.group(2))
        if quarter is None or not (1990 <= year <= 2100):
            return None
        return date(year, _QUARTER_END_MONTH[quarter], 1)
    except (ValueError, KeyError):
        return None


def parse_housing_report_pdf(content: bytes) -> tuple[date | None, tuple[float, float] | None]:
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return (parse_housing_reference_quarter(text), parse_housing_qoq_pair(text))


_INDICATOR_TO_PAIR_INDEX = {
    "housing-price-primary": 0,
    "housing-price-secondary": 1,
}


class RosstatHousingParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_housing"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        report_content, report_url = await asyncio.to_thread(fetch_latest_socioeconomic_report_pdf)
        ref_quarter, qoq_pair = await asyncio.to_thread(parse_housing_report_pdf, report_content)

        if qoq_pair is None:
            logger.warning("Housing: QoQ pair not found in PDF socioeconomic report")
            return [], report_url
        if ref_quarter is None:
            logger.warning("Housing: reference quarter not found in PDF")
            return [], report_url

        pair_idx = _INDICATOR_TO_PAIR_INDEX.get(indicator.code)
        if pair_idx is None:
            raise ValueError(f"Housing: no pair-index mapping for code '{indicator.code}'")
        qoq = qoq_pair[pair_idx]

        result = await db.execute(
            select(IndicatorData)
            .where(IndicatorData.indicator_id == indicator.id)
            .where(IndicatorData.date < ref_quarter)
            .order_by(IndicatorData.date.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            logger.warning(
                "Housing %s: no existing DB data to chain from. Skipping.",
                indicator.code,
            )
            return [], report_url

        new_cumulative = float(last.value) * qoq / 100.0
        new_point = DataPoint(date=ref_quarter, value=round(new_cumulative, 2))
        logger.info(
            "Housing %s chain: %s=%.2f, QoQ=%.1f%%, new %s=%.2f",
            indicator.code, last.date, float(last.value), qoq,
            ref_quarter, new_cumulative,
        )
        return [new_point], report_url

    def _validate(self, points: list, cfg: dict) -> list:
        return validate_points(points, cfg)
