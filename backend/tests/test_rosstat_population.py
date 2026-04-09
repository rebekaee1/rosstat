"""Tests for Rosstat Population parsers (SDDS + static XLSX)."""

import io
from datetime import date

import openpyxl

from app.services.rosstat_population_parser import (
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
