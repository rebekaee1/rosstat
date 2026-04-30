"""Tests for Rosstat SDDS labor market parser."""

import io
from datetime import date

import openpyxl
import pytest

from app.services.rosstat_labor_parser import (
    DataPoint,
    _parse_header_date,
    _parse_labor_report_text,
    parse_labor_xlsx,
    merge_labor_series,
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
        expected_rate = round(2.0 / 75.5 * 100, 1)
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


class TestParseLaborReportText:
    def test_supplements_sdds_lag_from_official_report(self):
        text = """
        ДИНАМИКА ЧИСЛЕННОСТИ РАБОЧЕЙ СИЛЫ
        2026 г.
        Январь 76,2 101,2 74,5 101,4 1,7 91,8 2,2 0,3 103,3 0,4
        Февраль 76,3 101,0 74,6 101,2 1,6 91,6 2,1 0,3 106,6 0,4
        Мар т 76,2 100,6 74,6 100,7 1,7 96,8 2,2 0,3 107,0 0,4
        Занятость населения.
        """

        result = _parse_labor_report_text(text)

        assert result["labor_force"][-1].date == date(2026, 3, 1)
        assert result["labor_force"][-1].value == 76.2
        assert result["employment"][-1].value == 74.6
        assert result["unemployment_rate"][-1].value == 2.2

    def test_report_values_override_sdds_by_date(self):
        base = {
            "unemployment_rate": [
                DataPoint(date=date(2026, 2, 1), value=2.15),
            ],
            "wages_nominal": [],
            "labor_force": [],
            "employment": [],
        }
        supplement = {
            "unemployment_rate": [
                DataPoint(date=date(2026, 2, 1), value=2.1),
                DataPoint(date=date(2026, 3, 1), value=2.2),
            ],
            "wages_nominal": [],
            "labor_force": [],
            "employment": [],
        }

        merged = merge_labor_series(base, supplement)

        assert [p.value for p in merged["unemployment_rate"]] == [2.1, 2.2]
