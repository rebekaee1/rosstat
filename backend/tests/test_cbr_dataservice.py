"""Tests for CbrDataServiceParser date parsing."""

from datetime import date
from app.services.cbr_dataservice_parser import _parse_ds_date


def test_parse_ds_date_from_iso():
    d = _parse_ds_date("", "2026-02-01T00:00:00")
    assert d == date(2026, 1, 1)


def test_parse_ds_date_from_iso_january():
    d = _parse_ds_date("", "2026-01-01T00:00:00")
    assert d == date(2025, 12, 1)


def test_parse_ds_date_from_text():
    d = _parse_ds_date("Март 2025", None)
    assert d == date(2025, 3, 1)


def test_parse_ds_date_from_text_lower():
    d = _parse_ds_date("декабрь 2024", None)
    assert d == date(2024, 12, 1)


def test_parse_ds_date_iso_preferred_over_text():
    d = _parse_ds_date("Январь 2020", "2026-02-01T00:00:00")
    assert d == date(2026, 1, 1)


def test_parse_ds_date_none():
    d = _parse_ds_date("", None)
    assert d is None


def test_parse_ds_date_invalid():
    d = _parse_ds_date("foo bar", None)
    assert d is None
