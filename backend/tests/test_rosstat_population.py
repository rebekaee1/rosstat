"""Tests for Rosstat Population parsers (SDDS + static XLSX)."""

import io
from datetime import date

import openpyxl

from app.services.rosstat_population_parser import (
    merge_population_history_with_sdds,
    parse_population_history_xlsx,
    parse_sdds_population_xlsx,
    parse_popul_components_xlsx,
)


def _make_sdds_population_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Population"

    ws.append(["SDDS", None, 2020, 2021, 2022])
    ws.append(["Label", None, None, None, None])
    ws.append(["Population", None, 146748.6, 145478.1, 144236.9])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_popul_components_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cover"
    ws2 = wb.create_sheet("1")

    for _ in range(7):
        ws2.append([None])

    ws2.append([2019, 146794.0, -31.1, -316.2, 285.1])
    ws2.append([2020, 146749.0, -596.3, -702.8, 106.5])
    ws2.append([2021, 145478.0, -669.8, -1038.8, 369.0])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_population_history_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Лист1"

    for _ in range(6):
        ws.append([None])
    ws.append([1897, None, None])
    ws.append(["в границах Российской империи", 128.2])
    ws.append(["в современных границах", 67.5])
    ws.append([1914, None, None])
    ws.append(["в границах Российской империи", 165.7])
    ws.append(["в современных границах", 89.9])
    ws.append([1970, 129.9])
    ws.append([1971, 130.6])
    ws.append(["20242)", 146.1])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseSddsPopulation:
    def test_basic(self):
        content = _make_sdds_population_xlsx()
        result = parse_sdds_population_xlsx(content)
        assert len(result) == 3
        assert result[0].date == date(2020, 1, 1)
        assert result[0].value == 146748.6

    def test_sorted(self):
        content = _make_sdds_population_xlsx()
        result = parse_sdds_population_xlsx(content)
        dates = [p.date for p in result]
        assert dates == sorted(dates)


class TestParsePopulationHistory:
    def test_modern_borders_and_annual_rows(self):
        content = _make_population_history_xlsx()
        result = parse_population_history_xlsx(content)
        assert [p.date for p in result] == [
            date(1897, 1, 1),
            date(1914, 1, 1),
            date(1970, 1, 1),
            date(1971, 1, 1),
            date(2024, 1, 1),
        ]
        assert result[0].value == 67.5
        assert result[1].value == 89.9
        assert result[-1].value == 146.1

    def test_merge_prefers_sdds_on_overlap(self):
        history = [type("P", (), {"date": date(2024, 1, 1), "value": 146.1})()]
        sdds = [type("P", (), {"date": date(2024, 1, 1), "value": 146.2})()]
        result = merge_population_history_with_sdds(history, sdds)
        assert result[0].value == 146.2


class TestParsePopulComponents:
    def test_population(self):
        content = _make_popul_components_xlsx()
        result = parse_popul_components_xlsx(content)
        pop = result["population"]
        assert len(pop) == 3
        assert pop[0].date == date(2019, 1, 1)
        assert pop[0].value == 146.79  # 146794 / 1000

    def test_natural_growth(self):
        content = _make_popul_components_xlsx()
        result = parse_popul_components_xlsx(content)
        natural = result["natural-growth"]
        assert len(natural) == 3
        assert natural[0].value == -316.2
        assert natural[2].value == -1038.8

    def test_migration(self):
        content = _make_popul_components_xlsx()
        result = parse_popul_components_xlsx(content)
        migration = result["migration"]
        assert len(migration) == 3
        assert migration[0].value == 285.1

    def test_total_growth(self):
        content = _make_popul_components_xlsx()
        result = parse_popul_components_xlsx(content)
        total = result["total-growth"]
        assert len(total) == 3
        assert total[0].value == -31.1
