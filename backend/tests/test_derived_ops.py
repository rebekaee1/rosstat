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
    annual_sum,
    cpi_mom_qoq,
    cpi_mom_yoy,
    cumulative_level_from_mom,
    december_to_december,
    mom,
    period_avg,
    period_last,
    period_over_period,
    period_sum,
    qoq,
    quarterly_avg,
    quarterly_index,
    rolling_avg,
    wages_real,
    weekly_inflation_by_calendar_month,
    weekly_mtd_in_calendar_month,
    yoy,
    yoy_abs,
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


# --- december_to_december ----------------------------------------------------


def test_december_to_december_one_point_per_complete_year():
    """Year 2024: 12 months @ 101 → ∏(1.01)¹² × 100 − 100 ≈ 12.6825%.
    Year 2025: only 11 months → skipped (no point)."""
    monthly = [(date(2024, m, 1), 101.0) for m in range(1, 13)]
    monthly += [(date(2025, m, 1), 101.0) for m in range(1, 12)]
    out = december_to_december(monthly)
    assert len(out) == 1
    d, v = out[0]
    assert d == date(2024, 1, 1)
    expected = (1.01 ** 12 - 1) * 100
    assert abs(v - round(expected, 4)) < 0.0001


def test_december_to_december_anchors_on_january_1():
    """Anchor date is always Jan 1 of the year, regardless of input month order."""
    # Mix months out of natural order (sometimes parsers drop them randomly).
    monthly = [(date(2023, m, 1), 100.5) for m in (3, 1, 12, 5, 8, 2, 4, 6, 7, 9, 10, 11)]
    out = december_to_december(monthly)
    assert [d for d, _ in out] == [date(2023, 1, 1)]
    expected = (1.005 ** 12 - 1) * 100
    assert abs(out[0][1] - round(expected, 4)) < 0.0001


def test_december_to_december_skips_year_with_missing_month():
    """If even one month of the year is absent, the entire year is dropped."""
    monthly = [(date(2024, m, 1), 100.5) for m in range(1, 13) if m != 7]  # July missing
    monthly += [(date(2025, m, 1), 100.5) for m in range(1, 13)]  # 2025 is complete
    out = december_to_december(monthly)
    assert [d for d, _ in out] == [date(2025, 1, 1)]


def test_december_to_december_empty_input():
    assert december_to_december([]) == []


def test_december_to_december_handles_level_format_via_dec_yoy():
    """For PPI-style level series (median 200+), use Dec_Y / Dec_{Y-1} ratio.
    Year 2024 ends at 318.9, 2023 at 304.9 → annual = (318.9/304.9 - 1)*100 ≈ 4.59%.
    """
    monthly = [(date(2023, m, 1), 300.0 + m * 0.4) for m in range(1, 13)]  # ends at 304.8
    monthly += [(date(2024, m, 1), 314.0 + m * 0.4) for m in range(1, 13)]  # ends at 318.8
    out = december_to_december(monthly)
    assert len(out) == 1
    d, v = out[0]
    assert d == date(2024, 1, 1)
    expected = (318.8 / 304.8 - 1) * 100
    assert abs(v - round(expected, 4)) < 0.01


def test_december_to_december_level_format_skips_first_year():
    """Without the previous December, year 2023 has no anchor → skipped."""
    monthly = [(date(2023, m, 1), 300.0 + m) for m in range(1, 13)]
    out = december_to_december(monthly)
    assert out == []


# --- annual_sum --------------------------------------------------------------


def test_annual_sum_quarterly_series_full_year():
    """Standard ВВП-real case: sum of 4 quarterly values per year."""
    series = [
        (date(2024, 3, 1), 30000.0),
        (date(2024, 6, 1), 31000.0),
        (date(2024, 9, 1), 32000.0),
        (date(2024, 12, 1), 35000.0),
    ]
    out = annual_sum(series)
    assert out == [(date(2024, 1, 1), 128000.0)]


def test_annual_sum_skips_incomplete_year():
    """Year with only 3 of 4 quarters is dropped — we don't extrapolate."""
    series = [
        (date(2024, 3, 1), 30000.0),
        (date(2024, 6, 1), 31000.0),
        (date(2024, 9, 1), 32000.0),
        # Q4 2024 missing → year 2024 dropped
        (date(2025, 3, 1), 33000.0),
        (date(2025, 6, 1), 34000.0),
        (date(2025, 9, 1), 35000.0),
        (date(2025, 12, 1), 36000.0),
    ]
    out = annual_sum(series)
    assert out == [(date(2025, 1, 1), 138000.0)]


def test_annual_sum_monthly_source_requires_12_months():
    """For a monthly source the threshold is 12 unique months/year."""
    series = [(date(2024, m, 1), 100.0) for m in range(1, 13)]
    series += [(date(2025, m, 1), 50.0) for m in range(1, 8)]  # only 7 months
    out = annual_sum(series)
    assert out == [(date(2024, 1, 1), 1200.0)]


def test_annual_sum_empty_input():
    assert annual_sum([]) == []


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


# --- yoy_abs (звонок 2026-05-22, для balances со знаком) --------------------


def test_yoy_abs_positive_growth():
    """Trade-balance вырос с 30 000 до 50 000 млн $ — YoY-абсолют = +20 000."""
    series = [
        (date(2025, 3, 1), 30_000.0),
        (date(2026, 3, 1), 50_000.0),
    ]
    out = yoy_abs(series)
    assert out == [(date(2026, 3, 1), 20_000.0)]


def test_yoy_abs_sign_crossover_keeps_units():
    """Сальдо текущего счёта перешло с +3 594 до −4 356: разница = −7 950 млн $.

    Это и есть смысл yoy_abs: процент тут бессмыслен (база разнознаковая),
    единица сохраняется. Регрессия — фиксирует, что op возвращает дельту в
    единицах источника, а не падает на знаке.
    """
    series = [
        (date(2025, 3, 1), 3_594.0),
        (date(2026, 3, 1), -4_356.0),
    ]
    out = yoy_abs(series)
    assert out == [(date(2026, 3, 1), -7_950.0)]


def test_yoy_abs_skips_missing_prior_year():
    """Если t-1y нет в ряду — точка пропускается."""
    series = [
        (date(2025, 6, 1), 100.0),
        (date(2026, 3, 1), 50.0),  # нет (2025-03-01) — пропустим
        (date(2026, 6, 1), 80.0),
    ]
    out = yoy_abs(series)
    assert out == [(date(2026, 6, 1), -20.0)]


def test_yoy_abs_allows_zero_denominator():
    """В отличие от yoy() — нулевая база не приводит к division: просто 0 → val_t."""
    series = [
        (date(2025, 3, 1), 0.0),
        (date(2026, 3, 1), 42.0),
    ]
    assert yoy_abs(series) == [(date(2026, 3, 1), 42.0)]


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


# --- CPI view-mode ops -------------------------------------------------------


def test_cumulative_level_from_mom_starts_at_2000():
    monthly = [
        (date(1999, 12, 1), 110.0),
        (date(2000, 1, 1), 101.0),
        (date(2000, 2, 1), 101.0),
    ]
    out = cumulative_level_from_mom(monthly)
    assert out[0] == (date(2000, 1, 1), 100.0)
    assert out[1][0] == date(2000, 2, 1)
    assert out[1][1] == 101.0


def test_cpi_mom_yoy_needs_year_gap():
    monthly = [(date(2025, m, 1), 101.0) for m in range(1, 13)]
    monthly += [(date(2026, 1, 1), 101.0)]
    out = cpi_mom_yoy(monthly)
    assert len(out) >= 1
    assert out[0][0] == date(2026, 1, 1)


def test_weekly_inflation_by_calendar_month_products_weeks():
    weekly = [
        (date(2026, 1, 5), 100.5),
        (date(2026, 1, 12), 100.3),
        (date(2026, 2, 2), 100.2),
    ]
    out = weekly_inflation_by_calendar_month(weekly)
    assert len(out) == 2
    jan = next(v for d, v in out if d.month == 1)
    expected_jan = (100.5 / 100) * (100.3 / 100) * 100 - 100
    assert abs(jan - round(expected_jan, 4)) < 0.0001


def test_weekly_mtd_emits_point_per_week_and_differs_from_wow():
    weekly = [
        (date(2026, 1, 5), 100.5),
        (date(2026, 1, 12), 100.3),
        (date(2026, 2, 2), 100.2),
    ]
    mtd = weekly_mtd_in_calendar_month(weekly)
    assert len(mtd) == 3
    assert mtd[0][1] == round(100.5 - 100, 4)
    expected_w2 = (100.5 / 100) * (100.3 / 100) * 100 - 100
    assert abs(mtd[1][1] - round(expected_w2, 4)) < 0.0001
    assert mtd[1][1] != round(100.3 - 100, 4)


def test_cpi_mom_qoq_on_quarter_ends():
    monthly = [(date(2025, m, 1), 101.0) for m in range(1, 13)]
    monthly += [(date(2026, m, 1), 101.0) for m in range(1, 4)]
    out = cpi_mom_qoq(monthly)
    assert len(out) >= 1
    assert out[0][0].month in (3, 6, 9, 12)


# --- generic bucketing: period_last / period_avg / period_sum ----------------


def test_period_last_quarter_takes_end_of_quarter_value():
    monthly = [(date(2025, m, 1), float(m)) for m in range(1, 13)]
    out = period_last(monthly, "quarter")
    # 4 quarters anchored on the third month, value = last month of quarter.
    assert out == [
        (date(2025, 3, 1), 3.0),
        (date(2025, 6, 1), 6.0),
        (date(2025, 9, 1), 9.0),
        (date(2025, 12, 1), 12.0),
    ]


def test_period_last_year_takes_december():
    monthly = [(date(2024, m, 1), 10.0) for m in range(1, 13)]
    monthly += [(date(2025, m, 1), 20.0) for m in range(1, 13)]
    out = period_last(monthly, "year")
    assert out == [(date(2024, 1, 1), 10.0), (date(2025, 1, 1), 20.0)]


def test_period_avg_quarter_mean():
    monthly = [(date(2025, m, 1), float(m)) for m in range(1, 7)]
    out = period_avg(monthly, "quarter")
    assert out == [(date(2025, 3, 1), 2.0), (date(2025, 6, 1), 5.0)]


def test_period_sum_year_adds_flow():
    monthly = [(date(2025, m, 1), 100.0) for m in range(1, 13)]
    out = period_sum(monthly, "year")
    assert out == [(date(2025, 1, 1), 1200.0)]


def test_period_last_week_uses_last_observation_date():
    # ISO week of 2025-01-06..2025-01-12 — Mon..Sun; last obs is the 12th.
    daily = [(date(2025, 1, 6), 1.0), (date(2025, 1, 8), 2.0), (date(2025, 1, 12), 3.0)]
    out = period_last(daily, "week")
    assert out == [(date(2025, 1, 12), 3.0)]


def test_aggregate_rejects_unknown_granularity():
    import pytest

    with pytest.raises(ValueError):
        period_last([(date(2025, 1, 1), 1.0)], "decade")


# --- mom / period_over_period ------------------------------------------------


def test_mom_percent_vs_previous_month():
    monthly = [(date(2025, 1, 1), 100.0), (date(2025, 2, 1), 110.0), (date(2025, 3, 1), 99.0)]
    out = mom(monthly)
    assert out == [(date(2025, 2, 1), 10.0), (date(2025, 3, 1), -10.0)]


def test_mom_skips_gap_across_missing_month():
    monthly = [(date(2025, 1, 1), 100.0), (date(2025, 3, 1), 120.0)]
    # February missing -> March has no immediate prior month, skipped.
    assert mom(monthly) == []


def test_period_over_period_quarter_on_monthly_stock():
    # Monthly stock; quarter-end levels 3,6 -> QoQ = +100%.
    monthly = [(date(2025, m, 1), float(m)) for m in range(1, 7)]
    out = period_over_period(monthly, "quarter", method="last")
    assert out == [(date(2025, 6, 1), 100.0)]
