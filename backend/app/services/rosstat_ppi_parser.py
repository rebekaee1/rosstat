"""ETL: Росстат PPI → IndicatorData (canonical русский Rosstat, без SDDS).

Источник — официальный ежемесячный доклад «Социально-экономическое положение
России» `osn-{MM}-{YYYY}.pdf` (rosstat.gov.ru/folder/210), подраздел
«Индексы и уровни цен производителей промышленных товаров» (номер плавает:
4.2.1 / 4.3.1 / 5.2.1), первое предложение:

  «Индекс цен производителей промышленных товаров в июле 2026 г.
   относительно предыдущего месяца, по предварительным данным, составил 97,5%»

Из него берутся И MoM%, И reference-месяц («в июле 2026 г.»).

Почему не summary-таблица (стр. 6): строка «Индекс цен производителей …
106,6 97,5 102,8 …» начинается с годового индекса (к тому же месяцу прошлого
года), а не с MoM. До 2026-09 парсер брал первое число оттуда → в цепной
индекс с 2026-02 вписывались YoY-коэффициенты (+32% «за полгода» на витрине),
а месяц брался из имени файла со сдвигом на −1. Исправлено 2026-09-26;
данные чинит `backend/scripts/repair_ppi_housing_2026.py`.

pypdf рвёт слова пробелами («п ромышленных», «прои зводителей»), поэтому
матчинг идёт по тексту без пробельных символов (`_compact`).

ADR-0004 path P (compat — DB хранит cumulative chained 2010=100 формат, frontend
не меняется): парсер читает точку индикатора за предыдущий месяц, умножает её
на свежий MoM% / 100, получает новую cumulative-точку. Если точки за
предыдущий месяц нет (пропуск доклада) — прогон падает (failed), а не
перемножает через дыру.
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
from app.services.rosstat_sdds_fetcher import fetch_latest_socioeconomic_report_pdf

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    date: date
    value: float


MONTHS_LOCATIVE_RU: dict[str, int] = {
    "январе": 1, "феврале": 2, "марте": 3, "апреле": 4, "мае": 5, "июне": 6,
    "июле": 7, "августе": 8, "сентябре": 9, "октябре": 10, "ноябре": 11,
    "декабре": 12,
}

# Матчится по `_compact(text)` (все пробельные символы удалены).
_PPI_MOM_COMPACT_RE = re.compile(
    r"Индексценпроизводителейпромышленныхтоваров"
    r"в(" + "|".join(MONTHS_LOCATIVE_RU) + r")(\d{4})г\.?"
    r"относительнопредыдущегомесяца,?(?:попредварительнымданным,?)?"
    r"составил(\d{2,3}(?:[,.]\d+)?)%",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PpiReading:
    reference_month: date
    mom_pct: float


def _parse_float_ru(value: str) -> float:
    return float(value.replace("\u00a0", "").replace(" ", "").replace(",", "."))


def _compact(text: str) -> str:
    """Склейка переносов «произво-\nдителей» + удаление всех пробельных символов."""
    text = re.sub(r"-\s*\n\s*", "", text)
    return re.sub(r"\s+", "", text)


def parse_ppi_reading_from_report(text: str) -> PpiReading | None:
    """MoM% и reference-месяц из подраздела «Индексы и уровни цен производителей».

    Возвращает None, если предложение не найдено или значение вне 50..250.
    """
    m = _PPI_MOM_COMPACT_RE.search(_compact(text))
    if not m:
        return None
    month = MONTHS_LOCATIVE_RU[m.group(1).lower()]
    year = int(m.group(2))
    try:
        val = _parse_float_ru(m.group(3))
    except ValueError:
        return None
    if not (50 <= val <= 250) or not (2000 <= year <= 2100):
        return None
    return PpiReading(reference_month=date(year, month, 1), mom_pct=val)


def parse_ppi_mom_from_report(text: str) -> float | None:
    """Compat-обёртка: только MoM% (см. `parse_ppi_reading_from_report`)."""
    reading = parse_ppi_reading_from_report(text)
    return reading.mom_pct if reading else None


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_ppi_report_pdf(content: bytes) -> PpiReading | None:
    return parse_ppi_reading_from_report(extract_pdf_text(content))


def previous_month(d: date) -> date:
    return date(d.year - 1, 12, 1) if d.month == 1 else date(d.year, d.month - 1, 1)


def chain_ppi_point(prev_value: float, reading: PpiReading) -> DataPoint:
    return DataPoint(
        date=reading.reference_month,
        value=round(prev_value * reading.mom_pct / 100.0, 2),
    )


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
        reading = await asyncio.to_thread(parse_ppi_report_pdf, report_content)

        if reading is None:
            # Пустой результат при живой истории → BaseParser ставит parsed_zero.
            logger.warning(
                "PPI: MoM sentence ('относительно предыдущего месяца … составил X%%') "
                "not found in %s", report_url,
            )
            return [], report_url

        prev_month = previous_month(reading.reference_month)
        result = await db.execute(
            select(IndicatorData)
            .where(IndicatorData.indicator_id == indicator.id)
            .where(IndicatorData.date < reading.reference_month)
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
        if last.date != prev_month:
            raise RuntimeError(
                f"PPI chain gap: report {report_url} gives MoM for "
                f"{reading.reference_month}, but last DB point before it is "
                f"{last.date} (need {prev_month}); backfill the missing month(s) "
                f"from older osn-*.pdf first"
            )

        new_point = chain_ppi_point(float(last.value), reading)
        logger.info(
            "PPI chain: %s=%.2f, MoM=%.1f%%, new %s=%.2f (%s)",
            last.date, float(last.value), reading.mom_pct, reading.reference_month,
            new_point.value, report_url,
        )
        return [new_point], report_url

    def _validate(self, points: list, cfg: dict) -> list:
        return validate_points(points, cfg)
