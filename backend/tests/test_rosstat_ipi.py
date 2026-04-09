"""Tests for Rosstat SDDS IPI (Industrial Production Index) parser."""

import io
from datetime import date

import openpyxl

from app.services.rosstat_ipi_parser import parse_ipi_xlsx


def _make_ipi_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "IPI"

    ws.append(["SDDS", None, "01.2024", "02.2024", "03.2024"])
    ws.append(["IPI (2023=100)", None, 98.5, 101.2, 103.7])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseIpiXlsx:
    def test_basic(self):
        content = _make_ipi_xlsx()
        result = parse_ipi_xlsx(content)
        assert len(result) == 3
        assert result[0].date == date(2024, 1, 1)
        assert result[0].value == 98.5
        assert result[2].value == 103.7

    def test_sorted(self):
        content = _make_ipi_xlsx()
        result = parse_ipi_xlsx(content)
        dates = [p.date for p in result]
        assert dates == sorted(dates)
