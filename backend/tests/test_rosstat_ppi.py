"""Tests for Rosstat PPI parser (canonical русский Rosstat PDF)."""

from app.services.rosstat_ppi_parser import parse_ppi_mom_from_report


class TestParsePpiMomFromReport:
    def test_extracts_first_value(self):
        text = "Индекс цен производителей промышленных товаров   98,2 102,0  96,0 105,9  98,5 108,4"
        assert parse_ppi_mom_from_report(text) == 98.2

    def test_handles_extra_whitespace(self):
        text = "  Индекс  цен производителей  промышленных товаров     101,5    102,0"
        assert parse_ppi_mom_from_report(text) == 101.5

    def test_no_match_returns_none(self):
        assert parse_ppi_mom_from_report("nothing relevant here") is None

    def test_value_out_of_range_filtered(self):
        text = "Индекс цен производителей промышленных товаров   500,0 102,0"
        assert parse_ppi_mom_from_report(text) is None

    def test_decimal_with_comma(self):
        text = "Индекс цен производителей промышленных товаров   99,8 100,1"
        assert parse_ppi_mom_from_report(text) == 99.8

    def test_decimal_with_dot(self):
        text = "Индекс цен производителей промышленных товаров   99.8 100.1"
        assert parse_ppi_mom_from_report(text) == 99.8
