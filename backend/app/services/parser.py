"""
Rosstat CPI Excel parser.
Verified structure (spike 2026-02-24):
- Sheet '01': all CPI, '02': food, '03': non-food, '04': services
- Row 3: year headers (1991-2026+) in columns 1-N
- Rows 5-16: Jan-Dec data, column 0 = month name (Russian)
- Each file contains FULL history from 1991
"""

import io
import logging
from dataclasses import dataclass
from datetime import date
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}


@dataclass
class DataPoint:
    date: date
    value: float


def parse_cpi_sheet(content: bytes, sheet: str = "01") -> List[DataPoint]:
    """Parse a single CPI sheet from Rosstat Excel pivot matrix.

    Args:
        content: raw xlsx bytes
        sheet: sheet name ('01'=all, '02'=food, '03'=non-food, '04'=services)

    Returns:
        Sorted list of DataPoint(date, value)
    """
    df = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=None)

    years: dict[int, int] = {}
    for col in range(1, df.shape[1]):
        val = df.iloc[3, col]
        if pd.notna(val):
            years[col] = int(float(val))

    if not years:
        raise ValueError(f"No year headers in row 3 of sheet '{sheet}'")

    points: list[DataPoint] = []

    for row_idx in range(5, 17):
        month_name = str(df.iloc[row_idx, 0]).strip().lower() if pd.notna(df.iloc[row_idx, 0]) else ""
        expected_month = row_idx - 4

        if month_name in MONTH_MAP and MONTH_MAP[month_name] != expected_month:
            logger.warning(
                "Month mismatch at row %d: expected %d, got '%s' (%d)",
                row_idx, expected_month, month_name, MONTH_MAP[month_name],
            )
            continue

        for col_idx, year in years.items():
            val = df.iloc[row_idx, col_idx]
            if pd.notna(val):
                try:
                    fval = float(val)
                except (ValueError, TypeError):
                    continue

                if 50 <= fval <= 1000:
                    points.append(DataPoint(
                        date=date(year, expected_month, 1),
                        value=round(fval, 4),
                    ))

    points.sort(key=lambda p: p.date)
    logger.info("Parsed %d data points from sheet '%s' (%s - %s)",
                len(points), sheet,
                points[0].date if points else "?",
                points[-1].date if points else "?")
    return points
