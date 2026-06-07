"""ETL: Росстат National Accounts → IndicatorData (canonical русский Rosstat).

Два источника, выбираются через `model_config_json.gdp_source`:

1. `gdp_source: "official_quarterly"` — `VVP_kvartal_s_1995-2026.xlsx` (rosstat.gov.ru):
   Quarter-grid layout (years row 2, quarters row 3, single value row 4).
   `gdp_sheet`: "2" = nominal ОКВЭД2 2011+, "9" = real в ценах 2021 г. (2011+).
   Опциональные `gdp_history_sheet` ("1" nominal ОКВЭД2007 1995-2011 / "3" real
   в ценах 2008 1995-2011) + `gdp_overlap_year` (default 2011) — продлевают
   историю до 1995 через **ratio-splice** на overlap-году (см. `splice_at_overlap`).

2. `gdp_source: "official_use"` — `GDP-quarters-of-use-1995-4kv-2025.xls` (rosstat.gov.ru):
   Quarter-grid layout, multi-row (стек индикаторов на одном sheet).
   `gdp_sheet`: "1" = ОКВЭД2007 (1995-2011), "2" = ОКВЭД2 (2011+).
   `gdp_row_index` (0-based): 4 = ВВП, 7 = домохозяйства, 8 = госуправление, 11 = GFCF.
   Опциональные `gdp_history_sheet` + `gdp_overlap_year` — то же ratio-splice.

Для **history extension** (1995-2010) `splice_at_overlap` калибрует ratio как
`mean(modern points в overlap_year) / mean(history points в overlap_year)`,
умножает все historical-точки (year < overlap_year) на этот ratio. Получаем
непрерывный ряд в base modern-методологии. Стандартная economic-series splice
техника. ADR-0004 «history extension до 1995» — closed.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import ClassVar

import openpyxl
import xlrd
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser
from app.services.data_validator import validate_points
from app.services.rosstat_sdds_fetcher import fetch_rosstat_static_xlsx

logger = logging.getLogger(__name__)

_Q_RE = re.compile(r"^Q(\d)-(\d{4})")
_YEAR_RE = re.compile(r"(\d{4})")


@dataclass
class DataPoint:
    date: date
    value: float


QUARTER_MONTH = {1: 3, 2: 6, 3: 9, 4: 12}


def _parse_quarter_header(header: str) -> date | None:
    """Parse 'Q1-2011' or 'Q3-2025**' to end-of-quarter date."""
    if not header or not isinstance(header, str):
        return None
    m = _Q_RE.match(header.strip())
    if not m:
        return None
    q, y = int(m.group(1)), int(m.group(2))
    if 1 <= q <= 4 and 1990 <= y <= 2100:
        return date(y, QUARTER_MONTH[q], 1)
    return None


_FOOTNOTE_SUFFIX_RE = re.compile(r"\d\)\s*$")


def _parse_ru_number(cell) -> float | None:
    """Parse Rosstat Excel cell to float, обрабатывая Russian decimals и footnotes.

    Rosstat Excel-файлы регулярно содержат значения как СТРОКИ с:
    - запятой как decimal separator («1662,8»)
    - trailing footnote suffix («1662,82)» = 1662.8 + footnote 2)
    - non-breaking spaces в качестве thousands separator
    Чистый `float()` на этом падает. Этот хелпер устойчив к таким артефактам.

    Возвращает None если cell пустая или нечисловая.
    """
    if cell is None or cell == "":
        return None
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        return float(cell)
    s = str(cell).strip().replace("\u00a0", "").replace(" ", "")
    s = _FOOTNOTE_SUFFIX_RE.sub("", s).rstrip()
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _extract_year(cell) -> int | None:
    if cell is None:
        return None
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        year = int(cell)
    else:
        m = _YEAR_RE.match(str(cell).strip())
        if not m:
            return None
        year = int(m.group(1))
    return year if 1990 <= year <= 2100 else None


_QUARTER_NAME_TO_MONTH = {
    "i квартал": 3,
    "ii квартал": 6,
    "iii квартал": 9,
    "iv квартал": 12,
}


def parse_rosstat_gdp_quarter_grid_xlsx(content: bytes, sheet_name: str = "9") -> list[DataPoint]:
    """Parse official Rosstat GDP quarter grid.

    The Russian accounts file has years in row 3, quarters in row 4, values in row 5.
    Sheet 9 is GDP in 2021 constant prices, billion rubles.
    """
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        ws = wb[sheet_name]
        rows_data = [list(row) for row in ws.iter_rows(values_only=True)]
    finally:
        wb.close()

    if len(rows_data) < 5:
        raise ValueError(f"GDP official XLSX sheet {sheet_name}: expected >=5 rows, got {len(rows_data)}")

    year_row = rows_data[2]
    quarter_row = rows_data[3]
    value_row = rows_data[4]

    points: list[DataPoint] = []
    current_year: int | None = None
    for idx, quarter_cell in enumerate(quarter_row):
        maybe_year = _extract_year(year_row[idx] if idx < len(year_row) else None)
        if maybe_year is not None:
            current_year = maybe_year

        if current_year is None:
            continue

        quarter = str(quarter_cell or "").strip().lower()
        month = _QUARTER_NAME_TO_MONTH.get(quarter)
        if month is None:
            continue

        val = value_row[idx] if idx < len(value_row) else None
        parsed = _parse_ru_number(val)
        if parsed is None:
            continue
        points.append(DataPoint(date=date(current_year, month, 1), value=round(parsed, 1)))

    points.sort(key=lambda p: p.date)
    return points


def parse_rosstat_gdp_use_xls(
    content: bytes,
    sheet_name: str = "2",
    value_row_index: int = 4,
) -> list[DataPoint]:
    """Parse legacy .xls `GDP-quarters-of-use-*.xls` (rosstat.gov.ru/statistics/accounts).

    Same year/quarter grid as `parse_rosstat_gdp_quarter_grid_xlsx` but the file is
    OLE2 binary (xlrd, not openpyxl) and the sheet hosts multiple stacked indicators
    (ВВП, конечное потребление, домохозяйства, госуправление, GFCF) — caller selects
    via `value_row_index` (0-based).

    Sheets: "1" = ОКВЭД2007 1995-2010 (methodology break vs sheet 2),
            "2" = ОКВЭД2 2011+ (current canonical for our 2011-onwards series).
    """
    wb = xlrd.open_workbook(file_contents=content)
    ws = wb.sheet_by_name(sheet_name)

    if ws.nrows <= max(4, value_row_index):
        raise ValueError(
            f"GDP use XLS sheet {sheet_name}: expected >= {value_row_index + 1} rows, got {ws.nrows}"
        )

    year_row = ws.row_values(2)
    quarter_row = ws.row_values(3)
    value_row = ws.row_values(value_row_index)

    points: list[DataPoint] = []
    current_year: int | None = None
    for idx, qcell in enumerate(quarter_row):
        maybe_year = _extract_year(year_row[idx] if idx < len(year_row) else None)
        if maybe_year is not None:
            current_year = maybe_year

        if current_year is None:
            continue

        quarter = str(qcell or "").strip().lower()
        month = _QUARTER_NAME_TO_MONTH.get(quarter)
        if month is None:
            continue

        val = value_row[idx] if idx < len(value_row) else None
        parsed = _parse_ru_number(val)
        if parsed is None:
            continue
        points.append(DataPoint(date=date(current_year, month, 1), value=round(parsed, 1)))

    points.sort(key=lambda p: p.date)
    return points


def splice_at_overlap(
    history: list[DataPoint],
    modern: list[DataPoint],
    overlap_year: int,
) -> list[DataPoint]:
    """Ratio-splice двух методологически разных рядов в один continuous ряд.

    Стандартная economic-series splice техника (используется ОЭСР/МВФ при
    re-basing GDP/IPI/CPI рядов). Калибруем ratio через overlap-год — берём
    среднее модерн-значений и среднее historical-значений за этот год,
    умножаем все historical-точки (year < overlap_year) на ratio = modern/history.

    Возвращаем: scaled_history (year < overlap_year) + modern (year >= overlap_year),
    отсортировано по дате. Modern имеет приоритет на overlap-году (без дублей).

    Raises ValueError если overlap_year не покрыт обоими рядами или history-mean
    нулевой (degenerate ratio).
    """
    history_overlap = [p.value for p in history if p.date.year == overlap_year]
    modern_overlap = [p.value for p in modern if p.date.year == overlap_year]

    if not history_overlap:
        raise ValueError(
            f"splice_at_overlap: history не содержит точек за overlap_year={overlap_year}"
        )
    if not modern_overlap:
        raise ValueError(
            f"splice_at_overlap: modern не содержит точек за overlap_year={overlap_year}"
        )

    history_mean = sum(history_overlap) / len(history_overlap)
    modern_mean = sum(modern_overlap) / len(modern_overlap)

    if history_mean == 0:
        raise ValueError(
            f"splice_at_overlap: history mean == 0 за overlap_year={overlap_year}, "
            f"ratio undefined"
        )

    ratio = modern_mean / history_mean

    scaled_history = [
        DataPoint(date=p.date, value=round(p.value * ratio, 1))
        for p in history if p.date.year < overlap_year
    ]
    modern_kept = [p for p in modern if p.date.year >= overlap_year]

    combined = scaled_history + modern_kept
    combined.sort(key=lambda p: p.date)
    return combined


class RosstatGdpParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_gdp"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        gdp_source = cfg.get("gdp_source")
        history_sheet = cfg.get("gdp_history_sheet")
        overlap_year = int(cfg.get("gdp_overlap_year", 2011))

        if gdp_source == "official_quarterly":
            content, final_url = await asyncio.to_thread(fetch_rosstat_static_xlsx, "gdp_quarterly")
            sheet_name = str(cfg.get("gdp_sheet", "9"))
            modern = await asyncio.to_thread(parse_rosstat_gdp_quarter_grid_xlsx, content, sheet_name)
            if history_sheet:
                history = await asyncio.to_thread(
                    parse_rosstat_gdp_quarter_grid_xlsx, content, str(history_sheet)
                )
                points = splice_at_overlap(history, modern, overlap_year)
            else:
                points = modern
        elif gdp_source == "official_use":
            content, final_url = await asyncio.to_thread(fetch_rosstat_static_xlsx, "gdp_use_quarterly")
            sheet_name = str(cfg.get("gdp_sheet", "2"))
            row_index = int(cfg.get("gdp_row_index", 4))
            modern = await asyncio.to_thread(
                parse_rosstat_gdp_use_xls, content, sheet_name, row_index
            )
            if history_sheet:
                history = await asyncio.to_thread(
                    parse_rosstat_gdp_use_xls, content, str(history_sheet), row_index
                )
                points = splice_at_overlap(history, modern, overlap_year)
            else:
                points = modern
        else:
            raise ValueError(
                f"RosstatGdpParser: indicator {indicator.code!r} missing or invalid "
                f"`gdp_source` in model_config_json (got {gdp_source!r}). "
                f"Expected 'official_quarterly' or 'official_use'. SDDS branch removed (ADR-0004)."
            )
        return points, final_url

    def _validate(self, points: list, cfg: dict) -> list:
        return validate_points(points, cfg)
