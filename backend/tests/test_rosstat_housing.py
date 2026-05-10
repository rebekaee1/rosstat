"""Tests for Rosstat housing parser (canonical русский Rosstat PDF)."""

from datetime import date

from app.services.rosstat_housing_parser import (
    parse_housing_qoq_pair,
    parse_housing_reference_quarter,
)


class TestParseHousingQoqPair:
    def test_extracts_pair(self):
        text = (
            "4.2. РЫНОК ЖИЛЬЯ\n"
            "В I квартале 2026 г. индексы цен на первичном и вторичном "
            "рынках жилья составили соответственно 103,9% и 101,8%."
        )
        result = parse_housing_qoq_pair(text)
        assert result == (103.9, 101.8)

    def test_handles_pdf_extraction_artefacts(self):
        """PDF extraction вносит лишние пробелы в слова: 'перви чном'."""
        text = (
            "4.2. РЫНОК ЖИЛЬЯ\n"
            "В I квартале 202 6 г. индексы цен на перви чном  и вторичном "
            "рынках жилья,  составили соответственно 103,9%   \nи 101,8%."
        )
        assert parse_housing_qoq_pair(text) == (103.9, 101.8)

    def test_skips_toc_match(self):
        """Section regex must skip table-of-contents 'Рынок жилья ... 133'."""
        text = (
            "Рынок жилья ………………………………… 133\n"
            "(other PDF content) "
        )
        assert parse_housing_qoq_pair(text) is None

    def test_no_match_returns_none(self):
        assert parse_housing_qoq_pair("nothing relevant") is None

    def test_out_of_range_filtered(self):
        text = "РЫНОК ЖИЛЬЯ ... составили соответственно 500,0% и 101,8%"
        assert parse_housing_qoq_pair(text) is None

    def test_other_section_does_not_leak(self):
        """'составили соответственно' from other sections must not leak in."""
        text = (
            "Доля рынков и ярмарок составила 2,8% (в марте - 97,0% и 3,0% "
            "соответственно)."
        )
        assert parse_housing_qoq_pair(text) is None


class TestParseHousingReferenceQuarter:
    def test_q1(self):
        text = (
            "ИНДЕКСЫ ЦЕН НА РЫНКЕ ЖИЛЬЯ\n"
            "I квартал 2026 г. в % к IV кварталу 2025 г."
        )
        assert parse_housing_reference_quarter(text) == date(2026, 3, 1)

    def test_q3(self):
        text = (
            "ИНДЕКСЫ ЦЕН НА РЫНКЕ ЖИЛЬЯ\n"
            "III квартал 2025 г. в % к II кварталу 2025 г."
        )
        assert parse_housing_reference_quarter(text) == date(2025, 9, 1)

    def test_handles_split_year(self):
        """Rosstat PDF text extraction sometimes splits year: '202 6' → '2026'."""
        text = (
            "ИНДЕКСЫ ЦЕН НА РЫНКЕ ЖИЛЬЯ\n"
            "I квартал 202 6 г. в % к IV кварталу 202 5 г."
        )
        assert parse_housing_reference_quarter(text) == date(2026, 3, 1)

    def test_no_section(self):
        assert parse_housing_reference_quarter("nothing here") is None
