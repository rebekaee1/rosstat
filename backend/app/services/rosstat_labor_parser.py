"""ETL: Росстат labor market → IndicatorData (canonical русский Rosstat).

Источник — официальный ежемесячный бюллетень "Социально-экономическое положение
России" `osn-{MM}-{YYYY}.pdf` от Росстата (rosstat.gov.ru/folder/210). PDF
публикуется к 15-20 числу за предыдущий месяц.

Извлекаются 4 временных ряда:

  1. labor-force, employment, unemployment_rate — из табличного блока
     "ДИНАМИКА ЧИСЛЕННОСТИ РАБОЧЕЙ СИЛЫ" (~24-36 месяцев истории на каждый PDF,
     накопительно через bulk_upsert даёт continuous monthly series).

  2. wages-nominal — из summary-блока на стр. 6-7
     "Среднемесячная начисленная заработная плата работников организаций ...
      номинальная, рублей  XXX XXX". Один new datapoint per ETL run для
      reference-месяца PDF (определяется из URL: `osn-MM-YYYY.pdf`).

  2b. wages-nominal backfill — из Таблицы 3 «Динамика среднемесячной номинальной
     и реальной начисленной заработной платы работников организаций» того же PDF.
     Таблица содержит помесячные значения номинала за прошлый и текущий год,
     включая месяцы, ещё не прошедшие через summary (кейс 2026-08: июльский
     выпуск osn-07-2026 не выложен на сайт, июнь 2026 доступен только строкой
     «Июнь» Таблицы 3 в osn-06-2026.pdf). Значения Таблицы 3 и summary —
     один и тот же официальный ряд; при конфликте приоритет у summary.

ADR-0004 path P (compat) — формат хранения и frontend не меняются. SDDS XLSX
больше не используется.

Trade-off: 4-я серия (`wages-nominal`) обновляется по одному значению с каждым
PDF; полный исторический ряд 2015+ остаётся в DB от прошлой SDDS-этапы (idempotent
bulk_upsert не удаляет существующие точки). Если в будущем найдётся monthly XLSX
с зарплатой за все периоды — расширим парсер.
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
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.data_validator import validate_points
from app.services.rosstat_sdds_fetcher import fetch_latest_socioeconomic_report_pdf

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    date: date
    value: float


MONTHS_RU: dict[str, int] = {
    "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6,
    "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12,
}

_MONTH_NUM_RE = re.compile(r"osn-(\d{2})-(\d{4})\.pdf", re.IGNORECASE)


def _parse_float_ru(value: str) -> float:
    return float(value.replace("\u00a0", "").replace(" ", "").replace(",", "."))


def _normalize_report_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    return (
        line
        .replace("Мар т", "Март")
        .replace("202 6", "2026")
        .replace("202 5", "2025")
        .replace("202 4", "2024")
    )


def parse_report_month_from_url(url: str) -> date | None:
    """Extract reference month from PDF URL like `osn-03-2026.pdf` → date(2026, 2, 1).

    Publication convention: `osn-MM-YYYY.pdf` released in month MM contains data
    for **previous** calendar month (T+1 lag). E.g. osn-03-2026.pdf публикован в
    марте 2026 содержит summary за февраль 2026.
    """
    m = _MONTH_NUM_RE.search(url)
    if not m:
        return None
    try:
        pub_month = int(m.group(1))
        pub_year = int(m.group(2))
        if not (1 <= pub_month <= 12):
            return None
        if pub_month == 1:
            data_month, data_year = 12, pub_year - 1
        else:
            data_month, data_year = pub_month - 1, pub_year
        return date(data_year, data_month, 1)
    except (ValueError, TypeError):
        return None


def _parse_labor_force_table(text: str) -> dict[str, list[DataPoint]]:
    """Извлекает 3 серии (labor-force, employment, unemployment-rate) из табличного
    блока "ДИНАМИКА ЧИСЛЕННОСТИ РАБОЧЕЙ СИЛЫ" в PDF.

    Layout: после заголовка таблицы блоки по годам; каждый блок начинается
    "20XX г.", далее строки "Месяц <values>".
    """
    labor_force: list[DataPoint] = []
    employment: list[DataPoint] = []
    unemployment_rate: list[DataPoint] = []

    in_table = False
    current_year: int | None = None

    for raw_line in text.splitlines():
        line = _normalize_report_line(raw_line)
        if "ДИНАМИКА ЧИСЛЕННОСТИ" in line and "РАБОЧЕЙ СИЛЫ" in line:
            in_table = True
            current_year = None
            continue
        if in_table and "Занятость населения" in line:
            break
        if not in_table:
            continue

        year_match = re.match(r"^(20\d{2})\s*г\.", line)
        if year_match:
            current_year = int(year_match.group(1))
            continue

        row_match = re.match(
            r"^(Январь|Февраль|Март|Апрель|Май|Июнь|Июль|Август|Сентябрь|Октябрь|Ноябрь|Декабрь)\s+(.+)$",
            line,
        )
        if not row_match or current_year is None:
            continue

        month_name, values_text = row_match.groups()
        values = re.findall(r"\d+(?:,\d+)?", values_text)
        if len(values) < 7:
            continue

        d = date(current_year, MONTHS_RU[month_name], 1)
        labor_force.append(DataPoint(date=d, value=round(_parse_float_ru(values[0]), 2)))
        employment.append(DataPoint(date=d, value=round(_parse_float_ru(values[2]), 2)))
        unemployment_rate.append(DataPoint(date=d, value=round(_parse_float_ru(values[6]), 1)))

    return {
        "unemployment_rate": sorted(unemployment_rate, key=lambda p: p.date),
        "labor_force": sorted(labor_force, key=lambda p: p.date),
        "employment": sorted(employment, key=lambda p: p.date),
    }


def _parse_wages_summary(text: str, reference_month: date | None) -> list[DataPoint]:
    """Извлекает single wage point для reference_month из summary секции PDF.

    Pattern (стр. 6-7): после строки "Среднемесячная начисленная заработная плата
    работников организаций:" идёт строка "номинальная, рублей  XXX XXX  ..."
    Первое числовое значение — номинальная зарплата в рублях за reference_month.
    """
    if reference_month is None:
        logger.warning("Labor wages: reference_month unknown, skipping")
        return []

    section_idx = text.find("Среднемесячная начисленная")
    if section_idx < 0:
        logger.warning("Labor wages: 'Среднемесячная начисленная' section not found")
        return []

    snippet = text[section_idx:section_idx + 800]
    nominal_idx = snippet.find("номинальная")
    if nominal_idx < 0:
        return []

    after_nominal = snippet[nominal_idx:nominal_idx + 200]
    # Captures digit-and-space sequence ending right before a number-with-decimal
    # (e.g. "103 900" before "115,0"). Falls back to plain digit run.
    m = re.search(r"номинальная,\s+рублей\s+([\d ]+?)(?=\s+\d+[,.]\d)", after_nominal)
    if not m:
        m = re.search(r"номинальная,\s+рублей\s+([\d ]+?)\b", after_nominal)
    if not m:
        return []

    try:
        value = _parse_float_ru(m.group(1))
        if 10_000 <= value <= 1_000_000:
            return [DataPoint(date=reference_month, value=round(value, 2))]
    except ValueError:
        pass
    return []


_WAGES_TABLE_TITLE = "ДИНАМИКА СРЕДНЕМЕСЯЧНОЙ"
_WAGES_TABLE_STOP = "СРЕДНЕМЕСЯЧНАЯ НАЧИСЛЕННАЯ ЗАРАБОТНАЯ ПЛАТА РАБОТНИКОВ ОРГАНИЗАЦИЙ"
_AGG_ROW_RE = re.compile(r"^(?:I|II|III|IV)\s+квартал|Год\s|Январь-|I\s+полугодие", re.IGNORECASE)
_MONTH_ROW_RE = re.compile(
    r"^(Январь|Февраль|Март|Апрель|Май|Июнь|Июль|Август|Сентябрь|Октябрь|Ноябрь|Декабрь)\s+(\d[\d\s]*?)"
    r"(?=\s+\d+[,.]\d)",
)


def _parse_wages_table(text: str) -> list[DataPoint]:
    """Разобрать Таблицу 3 «Динамика среднемесячной номинальной и реальной
    начисленной заработной платы» → помесячные номинальные значения (руб.).

    Layout (pypdf-экстракция): блок «2025 г.» затем строки-месяцы
    «    Январь 88 981 117,1 106,5» (значение, % к пред. году, % к пред. мес.),
    квартальные/полугодовые/годовые строки (I квартал, Январь-май, Год) —
    не месяцы и пропускаются. Заголовки таблицы повторяются на каждой странице
    PDF-спуска — повторный вход в заголовок просто ресетит парсинг.
    """
    points: list[DataPoint] = []
    current_year: int | None = None

    start = text.find(_WAGES_TABLE_TITLE)
    if start < 0:
        return []
    stop = text.find(_WAGES_TABLE_STOP, start)
    if stop < 0:
        stop = min(start + 200_000, len(text))

    for raw_line in text[start:stop].splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        year_match = re.match(r"^(20\d{2})\s*г\.?\s*$", line)
        if year_match:
            current_year = int(year_match.group(1))
            continue
        if "ДИНАМИКА СРЕДНЕМЕСЯЧНОЙ" in line:
            # Повторный заголовок таблицы на следующей странице — контекст сбрасываем.
            current_year = None
            continue
        if current_year is None:
            continue
        if _AGG_ROW_RE.match(line):
            continue
        row = _MONTH_ROW_RE.match(line)
        if not row:
            continue
        month_name, value_text = row.groups()
        try:
            value = _parse_float_ru(value_text)
        except ValueError:
            continue
        if not 1_000 <= value <= 10_000_000:
            continue
        points.append(DataPoint(
            date=date(current_year, MONTHS_RU[month_name], 1),
            value=round(value, 2),
        ))

    return points


def _merge_wages_points(
    summary_points: list[DataPoint],
    table_points: list[DataPoint],
    reference_month: date | None,
) -> list[DataPoint]:
    """Склеить summary-точку (reference-месяц) с помесячным backfill Таблицы 3.

    Это один и тот же официальный ряд Росстата; приоритет у summary-значения
    при коллизии на reference-месяц, backfill закрывает месяцы, ещё не
    прошедшие через summary (или выпуски, задержавшиеся на сайте).
    """
    by_date: dict[date, float] = {p.date: p.value for p in table_points}
    for p in summary_points:
        by_date[p.date] = p.value
    merged = [DataPoint(date=d, value=v) for d, v in sorted(by_date.items())]
    if reference_month is not None:
        merged = [p for p in merged if p.date <= reference_month]
    return merged


def parse_labor_report_pdf(content: bytes, source_url: str) -> dict[str, list[DataPoint]]:
    """Parse Rosstat socioeconomic report PDF — все 4 labor-серии."""
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    series = _parse_labor_force_table(text)
    reference_month = parse_report_month_from_url(source_url)
    series["wages_nominal"] = _merge_wages_points(
        _parse_wages_summary(text, reference_month),
        _parse_wages_table(text),
        reference_month,
    )
    return series


INDICATOR_SERIES_MAP: dict[str, str] = {
    "unemployment": "unemployment_rate",
    "wages-nominal": "wages_nominal",
    "labor-force": "labor_force",
    "employment": "employment",
}


class RosstatLaborParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_labor"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        code = indicator.code
        report_content, report_url = await asyncio.to_thread(fetch_latest_socioeconomic_report_pdf)
        all_series = await asyncio.to_thread(parse_labor_report_pdf, report_content, report_url)

        series_key = INDICATOR_SERIES_MAP.get(code)
        if not series_key:
            raise ValueError(f"No series mapping for '{code}'")

        return all_series.get(series_key, []), report_url

    def _validate(self, points: list, cfg: dict) -> list:
        return validate_points(points, cfg)
