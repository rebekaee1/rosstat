"""Tests for Rosstat housing parser (canonical русский Rosstat PDF)."""

from datetime import date
from pathlib import Path

from app.services.rosstat_housing_parser import (
    has_housing_section,
    parse_housing_qoq_pair,
    parse_housing_reference_quarter,
    parse_housing_report_text,
    previous_quarter_end,
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


# --- регрессия 2026-09: pypdf «соотве тственно» → Q2 2026 потерян ------------

_OSN06 = (
    Path(__file__).parent / "fixtures" / "rosstat_osn" / "osn-06-2026_housing.txt"
).read_text(encoding="utf-8")


class TestRealOsn06Report:
    def test_qoq_pair_from_real_text(self):
        assert "соотве тственно" in _OSN06  # фикстура действительно «рваная»
        assert parse_housing_qoq_pair(_OSN06) == (101.1, 101.7)

    def test_reference_quarter_from_real_text(self):
        assert parse_housing_reference_quarter(_OSN06) == date(2026, 6, 1)

    def test_report_bundle(self):
        report = parse_housing_report_text(_OSN06)
        assert report.has_section
        assert report.reference_quarter == date(2026, 6, 1)
        assert report.qoq_pair == (101.1, 101.7)


class TestHousingSectionDetection:
    def test_monthly_report_without_section(self):
        text = "5.2. ЦЕНЫ ПРОИЗВОДИТЕЛЕЙ\nИндексы цен на первичном и вторичном рынках жилья (публикуется в докладах № 3, 6, 9, 12)"
        assert not has_housing_section(text)

    def test_toc_is_not_section(self):
        assert not has_housing_section("Рынок жилья ………………… 133")

    def test_section_number_may_vary(self):
        assert has_housing_section("5.3. РЫНОК  ЖИ ЛЬЯ\nВо II квартале")

    def test_split_word_in_pair(self):
        text = (
            "4.2. РЫНОК ЖИЛЬЯ\nВо II квартале 2026 г. индексы цен на перви чном и "
            "вторичном рынках жилья, по предварительным д анным, составили соотве "
            "тственно 101,1%   \nи 101,7%."
        )
        assert parse_housing_qoq_pair(text) == (101.1, 101.7)


def test_previous_quarter_end():
    assert previous_quarter_end(date(2026, 6, 1)) == date(2026, 3, 1)
    assert previous_quarter_end(date(2026, 3, 1)) == date(2025, 12, 1)
