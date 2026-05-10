"""Tests for Rosstat labor parser (canonical русский Rosstat PDF, без SDDS)."""

from datetime import date

from app.services.rosstat_labor_parser import (
    DataPoint,
    _parse_labor_force_table,
    _parse_wages_summary,
    parse_report_month_from_url,
)


class TestParseReportMonthFromUrl:
    def test_basic_t_plus_1_lag(self):
        """`osn-03-2026.pdf` (опубликован март) содержит данные за февраль 2026."""
        url = "https://rosstat.gov.ru/storage/mediabank/osn-03-2026.pdf"
        assert parse_report_month_from_url(url) == date(2026, 2, 1)

    def test_january_publication_wraps_to_prev_year(self):
        """`osn-01-2025.pdf` (опубликован январь 2025) → данные за декабрь 2024."""
        url = "https://rosstat.gov.ru/storage/mediabank/osn-01-2025.pdf"
        assert parse_report_month_from_url(url) == date(2024, 12, 1)

    def test_no_match(self):
        assert parse_report_month_from_url("https://example.com/file.pdf") is None

    def test_invalid_month(self):
        url = "https://rosstat.gov.ru/storage/mediabank/osn-13-2026.pdf"
        assert parse_report_month_from_url(url) is None


class TestParseLaborForceTable:
    def test_extracts_three_series(self):
        text = """
        ДИНАМИКА ЧИСЛЕННОСТИ РАБОЧЕЙ СИЛЫ
        2026 г.
        Январь 76,2 101,2 74,5 101,4 1,7 91,8 2,2 0,3 103,3 0,4
        Февраль 76,3 101,0 74,6 101,2 1,6 91,6 2,1 0,3 106,6 0,4
        Мар т 76,2 100,6 74,6 100,7 1,7 96,8 2,2 0,3 107,0 0,4
        Занятость населения.
        """

        result = _parse_labor_force_table(text)

        assert result["labor_force"][-1].date == date(2026, 3, 1)
        assert result["labor_force"][-1].value == 76.2
        assert result["employment"][-1].value == 74.6
        assert result["unemployment_rate"][-1].value == 2.2

    def test_handles_multiple_years(self):
        text = """
        ДИНАМИКА ЧИСЛЕННОСТИ РАБОЧЕЙ СИЛЫ
        2025 г.
        Декабрь 76,5 100,5 74,8 100,5 1,7 95,8 2,2 0,3 105,3 0,4
        2026 г.
        Январь 76,2 101,2 74,5 101,4 1,7 91,8 2,2 0,3 103,3 0,4
        Занятость населения.
        """
        result = _parse_labor_force_table(text)
        assert len(result["labor_force"]) == 2
        assert result["labor_force"][0].date == date(2025, 12, 1)
        assert result["labor_force"][1].date == date(2026, 1, 1)


class TestParseWagesSummary:
    def test_extracts_current_month_wage(self):
        text = """
        Среднемесячная начисленная заработная плата
         работников организаций:
           номинальная, рублей  103 900  115,0  115,4  113,6  115,7
           реальная   108,6  108,9  103,2  105,2
        """
        result = _parse_wages_summary(text, date(2026, 2, 1))
        assert len(result) == 1
        assert result[0].date == date(2026, 2, 1)
        assert result[0].value == 103900.0

    def test_no_reference_month_returns_empty(self):
        text = "Среднемесячная начисленная ... номинальная, рублей  103 900  115"
        assert _parse_wages_summary(text, None) == []

    def test_section_not_found(self):
        assert _parse_wages_summary("nothing here", date(2026, 2, 1)) == []

    def test_value_outside_range_filtered(self):
        text = """
        Среднемесячная начисленная заработная плата
           номинальная, рублей  5  115,0  115,4
        """
        assert _parse_wages_summary(text, date(2026, 2, 1)) == []
