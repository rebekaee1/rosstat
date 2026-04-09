"""Tests for Rosstat SDDS PPI (Producer Price Index) parser."""

import io
from datetime import date

import openpyxl

from app.services.rosstat_ppi_parser import parse_ppi_xlsx


def _make_ppi_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Price indices_2010"

    ws.append(["SDDS", None, "01.2024", "02.2024", "03.2024"])
    ws.append(["CPI", None, 100.73, 100.86, 100.39])
    ws.append(["PPI", None, 185.2, 188.5, 190.1])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParsePpiXlsx:
    def test_basic(self):
        content = _make_ppi_xlsx()
        result = parse_ppi_xlsx(content)
        assert len(result) == 3
        assert result[0].date == date(2024, 1, 1)
        assert result[0].value == 185.2
        assert result[2].value == 190.1

    def test_sorted(self):
        content = _make_ppi_xlsx()
        result = parse_ppi_xlsx(content)
        dates = [p.date for p in result]
        assert dates == sorted(dates)
