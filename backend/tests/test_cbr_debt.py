"""Tests for CBR External Debt XLSX parser."""

import io
from datetime import date, datetime

import openpyxl
import pytest

from app.services.cbr_debt_parser import parse_debt_xlsx


def _make_debt_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "2003-2026"

    for _ in range(3):
        ws.append([None])
    ws.append([
        None,
        datetime(2024, 1, 1),
        datetime(2024, 4, 1),
        datetime(2024, 7, 1),
        datetime(2024, 10, 1),
    ])
    ws.append(["Всего", 300000.0, 305000.0, 310000.0, 315000.0])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseDebtXlsx:
    def test_basic(self):
        content = _make_debt_xlsx()
        result = parse_debt_xlsx(content)
        assert len(result) == 4
        assert result[0].date == date(2024, 1, 1)
        assert result[0].value == 300000.0
        assert result[-1].date == date(2024, 10, 1)
        assert result[-1].value == 315000.0

    def test_sorted(self):
        content = _make_debt_xlsx()
        result = parse_debt_xlsx(content)
        dates = [r.date for r in result]
        assert dates == sorted(dates)
