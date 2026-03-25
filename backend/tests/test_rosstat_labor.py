"""Tests for Rosstat SDDS labor market parser."""

import io
from datetime import date

import openpyxl
import pytest

from app.services.rosstat_labor_parser import (
    _parse_header_date,
    parse_labor_xlsx,
)


def _make_sample_xlsx() -> bytes:
    """Build minimal SDDS labor market XLSX for testing."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "labor market"

    ws.append(["SDDS Data Category", "Unit", "01.2024", "02.2024", "03.2024"])
    ws.append(["Economically active", "Mln", 75.5, 75.6, 75.7])
    ws.append(["Employed", "Mln", 73.5, 73.6, 73.7])
    ws.append(["Unemployed", "Mln", 2.0, 2.0, 2.0])
    ws.append(["Unemployed registered", "Mln", 0.3, 0.3, 0.3])
    ws.append(["Wages", "Rubles", 75000, 78000, 87000])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseHeaderDate:
    def test_valid(self):
        assert _parse_header_date("01.2024") == date(2024, 1, 1)
        assert _parse_header_date("12.2025") == date(2025, 12, 1)

    def test_invalid(self):
        assert _parse_header_date("Q1-2024") is None
        assert _parse_header_date("foo") is None
        assert _parse_header_date("") is None
        assert _parse_header_date(None) is None

    def test_out_of_range(self):
        assert _parse_header_date("13.2024") is None
        assert _parse_header_date("00.2024") is None


class TestParseLaborXlsx:
    def test_basic(self):
        content = _make_sample_xlsx()
        result = parse_labor_xlsx(content)

        assert "unemployment_rate" in result
        assert "wages_nominal" in result

        rates = result["unemployment_rate"]
        assert len(rates) == 3
        assert rates[0].date == date(2024, 1, 1)
        expected_rate = round(2.0 / 75.5 * 100, 2)
        assert rates[0].value == expected_rate

        wages = result["wages_nominal"]
        assert len(wages) == 3
        assert wages[0].value == 75000.0
        assert wages[1].value == 78000.0
        assert wages[2].value == 87000.0

    def test_dates_sorted(self):
        content = _make_sample_xlsx()
        result = parse_labor_xlsx(content)
        dates = [p.date for p in result["unemployment_rate"]]
        assert dates == sorted(dates)
