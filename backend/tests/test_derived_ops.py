"""Tests for pure derived-indicator operations.

These exercise the formulas directly, without the database layer. The numeric
expectations come from the legacy `_compute_*` functions in
`calculation_engine.py`, so the refactored engine must reproduce them
bit-for-bit.
"""

from __future__ import annotations

from datetime import date

from app.services.derived_ops import (
    annual_inflation,
    qoq,
    quarterly_avg,
    quarterly_index,
    rolling_avg,
    wages_real,
    yoy,
)


# --- quarterly_index ---------------------------------------------------------


def test_quarterly_index_three_months_chain():
    """Q1 2026 = product of Jan/Feb/Mar 2026 monthly CPI indices."""
    monthly = [
        (date(2026, 1, 1), 100.5),
        (date(2026, 2, 1), 100.3),
        (date(2026, 3, 1), 100.6),
    ]
    out = quarterly_index(monthly)
    assert len(out) == 1
    d, v = out[0]
    assert d == date(2026, 3, 1)
    expected = (100.5 / 100) * (100.3 / 100) * (100.6 / 100) * 100
    assert v == round(expected, 4)
    # sanity: value is just above 100 (sum of inflations)
    assert 101.3 < v < 101.5


def test_quarterly_index_skips_incomplete_quarter():
    monthly = [
        (date(2026, 1, 1), 100.5),
        (date(2026, 2, 1), 100.3),
        # March missing → Q1 skipped
        (date(2026, 4, 1), 100.4),
        (date(2026, 5, 1), 100.5),
        (date(2026, 6, 1), 100.6),
    ]
    out = quarterly_index(monthly)
    assert len(out) == 1
    assert out[0][0] == date(2026, 6, 1)


def test_quarterly_index_empty_input():
    assert quarterly_index([]) == []


# --- annual_inflation --------------------------------------------------------


def test_annual_inflation_steady_one_percent_per_month():
    """If every month is exactly 101 (1% mom), trailing 12-month inflation
    converges to (1.01)**12 - 1 = ~12.6825%."""
    monthly = [(date(2025, m, 1), 101.0) for m in range(1, 13)]
    monthly += [(date(2026, 1, 1), 101.0)]
    out = annual_inflation(monthly)
    assert len(out) == 2  # Dec 2025 and Jan 2026 both have 12 trailing months
    last_d, last_v = out[-1]
    assert last_d == date(2026, 1, 1)
    expected = (1.01 ** 12 - 1) * 100
    assert abs(last_v - round(expected, 4)) < 0.0001


def test_annual_inflation_skips_when_short_history():
    monthly = [(date(2025, m, 1), 100.5) for m in range(1, 12)]  # only 11 months
    assert annual_inflation(monthly) == []


# --- yoy ---------------------------------------------------------------------


def test_yoy_quarterly():
    series = [
        (date(2025, 3, 1), 100.0),
        (date(2025, 6, 1), 105.0),
        (date(2026, 3, 1), 110.0),
        (date(2026, 6, 1), 100.0),
    ]
    out = yoy(series)
    expected = {
        date(2026, 3, 1): round((110 / 100 - 1) * 100, 2),  # +10.0
        date(2026, 6, 1): round((100 / 105 - 1) * 100, 2),  # -4.76
    }
    assert dict(out) == expected


def test_yoy_handles_negative_denominator():
    """current-account-yoy: the prior-year value can be negative."""
    series = [
        (date(2025, 3, 1), -50.0),
        (date(2026, 3, 1), -20.0),
    ]
    out = yoy(series)
    expected = round((-20 / -50 - 1) * 100, 2)  # -60.0 (loss shrank by 60%)
    assert out == [(date(2026, 3, 1), expected)]


def test_yoy_skips_zero_denominator():
    series = [
        (date(2025, 3, 1), 0.0),
        (date(2026, 3, 1), 100.0),
    ]
    assert yoy(series) == []


# --- qoq ---------------------------------------------------------------------


def test_qoq_consecutive_points():
    series = [
        (date(2025, 3, 1), 100.0),
        (date(2025, 6, 1), 110.0),
        (date(2025, 9, 1), 99.0),
    ]
    out = qoq(series)
    assert out == [
        (date(2025, 6, 1), 10.0),
        (date(2025, 9, 1), -10.0),
    ]


def test_qoq_skips_zero_prev():
    series = [
        (date(2025, 3, 1), 0.0),
        (date(2025, 6, 1), 50.0),
    ]
    assert qoq(series) == []


# --- quarterly_avg -----------------------------------------------------------


def test_quarterly_avg_unemployment():
    monthly = [
        (date(2026, 1, 1), 2.4),
        (date(2026, 2, 1), 2.2),
        (date(2026, 3, 1), 2.0),
    ]
    out = quarterly_avg(monthly)
    assert out == [(date(2026, 3, 1), 2.2)]


def test_quarterly_avg_empty():
    assert quarterly_avg([]) == []


# --- rolling_avg -------------------------------------------------------------


def test_rolling_avg_window_12():
    monthly = [(date(2025, m, 1), float(m)) for m in range(1, 13)]
    monthly += [(date(2026, 1, 1), 100.0)]
    out = rolling_avg(monthly, window=12)
    # First eligible point: Dec 2025 — average of months 1..12 = 6.5
    # Second: Jan 2026 — average of Feb..Dec 2025 + Jan 2026 = (sum(2..12) + 100) / 12
    assert out[0] == (date(2025, 12, 1), 6.5)
    expected_jan = round((sum(range(2, 13)) + 100) / 12, 1)
    assert out[1] == (date(2026, 1, 1), expected_jan)


def test_rolling_avg_short_history():
    monthly = [(date(2025, m, 1), float(m)) for m in range(1, 12)]  # 11 months
    assert rolling_avg(monthly, window=12) == []


# --- wages_real --------------------------------------------------------------


def test_wages_real_constant_wages_against_inflation():
    """If nominal wages stay flat while CPI grows, real wages decline."""
    wages = [
        (date(2025, 1, 1), 100_000.0),
        (date(2025, 2, 1), 100_000.0),
        (date(2025, 3, 1), 100_000.0),
    ]
    cpi = [(date(2025, m, 1), 101.0) for m in range(1, 13)]  # 1% MoM, anchor month is Jan
    out = wages_real(wages, cpi)
    assert out
    # Base = (Jan 2025, 100000), base CPI cumulative = 1.01.
    # Feb cumulative = 1.01^2; real_feb = (100k/100k) / (1.01^2/1.01) * 100 = 1/1.01 * 100 ≈ 99.01
    feb_real = next(v for d, v in out if d == date(2025, 2, 1))
    assert abs(feb_real - round(100 / 1.01, 2)) < 0.01
    mar_real = next(v for d, v in out if d == date(2025, 3, 1))
    assert mar_real < feb_real  # purchasing power keeps shrinking


def test_wages_real_short_input():
    assert wages_real([(date(2025, 1, 1), 100.0)], []) == []
    assert wages_real([], [(date(2025, m, 1), 100.0) for m in range(1, 13)]) == []


def test_wages_real_zero_base_returns_empty():
    wages = [(date(2025, 1, 1), 0.0), (date(2025, 2, 1), 100.0)]
    cpi = [(date(2025, m, 1), 101.0) for m in range(1, 13)]
    assert wages_real(wages, cpi) == []
