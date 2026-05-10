"""Tests for Rosstat SDDS GDP parser."""

import io
from datetime import date

import openpyxl
import pytest

from app.services.rosstat_gdp_parser import (
    _parse_quarter_header,
    parse_gdp_xlsx,
    parse_rosstat_gdp_quarter_grid_xlsx,
    parse_rosstat_gdp_use_xls,
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

    def test_nominal_gdp_sheet_2(self):
        """Sheet '2' of VVP_kvartal_s_1995-2025.xlsx — nominal GDP в текущих ценах
        (ОКВЭД2, с 2011). Same row layout as sheet 9, configurable via gdp_sheet."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "2"
        ws.append(["К содержанию"])
        ws.append(["Валовой внутрений продукт1) (в текущих ценах, млрд.руб.)"])
        ws.append([2024, None, None, None, "20252)", None, None, None])
        ws.append(["I квартал", "II квартал", "III квартал", "IV квартал", "I квартал", "II квартал", "III квартал", "IV квартал"])
        ws.append([41410.7, 44389.2, 45606.9, 52079.4, 47950.4, 49284.8, 54671.8, 62354.1])

        buf = io.BytesIO()
        wb.save(buf)
        result = parse_rosstat_gdp_quarter_grid_xlsx(buf.getvalue(), "2")
        assert len(result) == 8
        assert result[7].date == date(2025, 12, 1)
        assert result[7].value == 62354.1
        assert result[4].date == date(2025, 3, 1)
        assert result[4].value == 47950.4


def _make_gdp_use_xls() -> bytes:
    """Build legacy .xls (OLE2) sample with ВВП-by-use multi-row layout.

    Mirrors `GDP-quarters-of-use-*.xls` sheet '2' (ОКВЭД2, 2011+):
    rows 4/7/8/11 = ВВП / consumption-HH / government / GFCF.
    """
    import xlwt

    wb = xlwt.Workbook()
    ws = wb.add_sheet("2")

    ws.write(0, 0, "К содержанию")
    ws.write(1, 0, "Элементы использования валового внутреннего продукта")
    for i, year in enumerate([2024, 2025]):
        ws.write(2, 1 + i * 4, year)
    quarters = ["I квартал", "II квартал", "III квартал", "IV квартал"]
    for offset in (0, 1):
        for j, q in enumerate(quarters):
            ws.write(3, 1 + offset * 4 + j, q)

    ws.write(4, 0, "Валовой внутренний продукт")
    for col, val in enumerate([41410.7, 44389.2, 45606.9, 52079.4, 47950.4, 49284.8, 54671.8, 62354.1]):
        ws.write(4, 1 + col, val)

    ws.write(7, 0, "домашних хозяйств")
    for col, val in enumerate([22803.0, 23891.7, 25694.3, 26660.6, 25265.0, 26174.9, 28038.6, 29281.1]):
        ws.write(7, 1 + col, val)

    ws.write(8, 0, "государственного управления")
    for col, val in enumerate([9101.9, 9119.5, 9249.3, 9592.6, 10114.7, 10034.8, 10327.7, 10448.3]):
        ws.write(8, 1 + col, val)

    ws.write(11, 0, "валовое накопление основного капитала")
    for col, val in enumerate([7397.1, 9843.4, 11056.0, 17091.4, 8530.3, 10599.8, 12165.1, 18176.8]):
        ws.write(11, 1 + col, val)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseRosstatGdpUseXls:
    def test_consumption_row(self):
        try:
            content = _make_gdp_use_xls()
        except ImportError:
            pytest.skip("xlwt not installed (legacy .xls writer for tests only)")
        result = parse_rosstat_gdp_use_xls(content, sheet_name="2", value_row_index=7)
        assert len(result) == 8
        assert result[7].date == date(2025, 12, 1)
        assert result[7].value == 29281.1
        assert result[0].date == date(2024, 3, 1)
        assert result[0].value == 22803.0

    def test_government_row(self):
        try:
            content = _make_gdp_use_xls()
        except ImportError:
            pytest.skip("xlwt not installed")
        result = parse_rosstat_gdp_use_xls(content, sheet_name="2", value_row_index=8)
        assert len(result) == 8
        assert result[7].value == 10448.3

    def test_investment_row(self):
        try:
            content = _make_gdp_use_xls()
        except ImportError:
            pytest.skip("xlwt not installed")
        result = parse_rosstat_gdp_use_xls(content, sheet_name="2", value_row_index=11)
        assert len(result) == 8
        assert result[7].value == 18176.8
        assert result[3].value == 17091.4

    def test_dates_sorted(self):
        try:
            content = _make_gdp_use_xls()
        except ImportError:
            pytest.skip("xlwt not installed")
        result = parse_rosstat_gdp_use_xls(content, sheet_name="2", value_row_index=4)
        dates = [p.date for p in result]
        assert dates == sorted(dates)
