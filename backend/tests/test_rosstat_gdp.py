"""Tests for Rosstat SDDS GDP parser."""

import io
from datetime import date

import openpyxl
import pytest

from app.services.rosstat_gdp_parser import (
    _parse_quarter_header,
    parse_gdp_xlsx,
    parse_rosstat_gdp_quarter_grid_xlsx,
)


def _make_sample_xlsx() -> bytes:
    """Build minimal SDDS national accounts XLSX for testing."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "National Accounts"

    ws.append(["SDDS Data Category", "Unit", "Q1-2024", "Q2-2024", "Q3-2024**"])
    ws.append(["National Accounts", None, None, None, None])
    ws.append(["GDP in current prices", "Billion roubles", 43268.6, 47114.7, 50699.4])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_official_quarter_grid_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "9"
    ws.append(["К содержанию"])
    ws.append(["Валовой внутренний продукт (в ценах 2021г., млрд.руб.)"])
    ws.append([2011, None, None, None, 2012, None, None, None])
    ws.append(["I квартал", "II квартал", "III квартал", "IV квартал", "I квартал", "II квартал", "III квартал", "IV квартал"])
    ws.append([26368.3866, 28407.6171, 29882.9625, 32019.0647, 27871.2704, 29785.6564, 30925.3725, 32790.9561])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseQuarterHeader:
    def test_valid(self):
        assert _parse_quarter_header("Q1-2024") == date(2024, 3, 1)
        assert _parse_quarter_header("Q2-2024") == date(2024, 6, 1)
        assert _parse_quarter_header("Q3-2024**") == date(2024, 9, 1)
        assert _parse_quarter_header("Q4-2023") == date(2023, 12, 1)

    def test_invalid(self):
        assert _parse_quarter_header("01.2024") is None
        assert _parse_quarter_header("foo") is None
        assert _parse_quarter_header("") is None
        assert _parse_quarter_header(None) is None

    def test_out_of_range(self):
        assert _parse_quarter_header("Q5-2024") is None
        assert _parse_quarter_header("Q0-2024") is None


class TestParseGdpXlsx:
    def test_basic(self):
        content = _make_sample_xlsx()
        result = parse_gdp_xlsx(content)

        assert len(result) == 3
        assert result[0].date == date(2024, 3, 1)
        assert result[0].value == 43268.6
        assert result[1].date == date(2024, 6, 1)
        assert result[1].value == 47114.7
        assert result[2].date == date(2024, 9, 1)
        assert result[2].value == 50699.4

    def test_dates_sorted(self):
        content = _make_sample_xlsx()
        result = parse_gdp_xlsx(content)
        dates = [p.date for p in result]
        assert dates == sorted(dates)

    def test_custom_row_index(self):
        """Test that row_index parameter selects the right data row."""
        content = _make_sample_xlsx()
        result = parse_gdp_xlsx(content, row_index=2)
        assert len(result) == 3
        assert result[0].value == 43268.6


class TestParseOfficialGdpQuarterGrid:
    def test_real_gdp_sheet(self):
        content = _make_official_quarter_grid_xlsx()
        result = parse_rosstat_gdp_quarter_grid_xlsx(content, "9")
        assert len(result) == 8
        assert result[0].date == date(2011, 3, 1)
        assert result[0].value == 26368.4
        assert result[3].date == date(2011, 12, 1)
        assert result[4].date == date(2012, 3, 1)
