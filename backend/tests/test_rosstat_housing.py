"""Tests for Rosstat SDDS Housing Price Indices parser."""

import io
from datetime import date

import openpyxl

from app.services.rosstat_housing_parser import parse_housing_xlsx


def _make_housing_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Housing prices"

    ws.append(["SDDS", None, "Q1-2024", "Q2-2024", "Q3-2024"])
    ws.append(["Primary market", None, 245.0, 252.3, 258.1])
    ws.append(["Secondary market", None, 198.5, 201.2, 204.7])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseHousingXlsx:
    def test_primary(self):
        content = _make_housing_xlsx()
        result = parse_housing_xlsx(content)
        primary = result["housing-price-primary"]
        assert len(primary) == 3
        assert primary[0].date == date(2024, 3, 1)
        assert primary[0].value == 245.0

    def test_secondary(self):
        content = _make_housing_xlsx()
        result = parse_housing_xlsx(content)
        secondary = result["housing-price-secondary"]
        assert len(secondary) == 3
        assert secondary[0].date == date(2024, 3, 1)
        assert secondary[0].value == 198.5
