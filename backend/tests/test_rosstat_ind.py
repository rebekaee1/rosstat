"""Tests for Rosstat ind_MM-YYYY.xlsx parser helpers."""

from datetime import date

from app.services.rosstat_ind_parser import DataPoint, collapse_flow_to_quarterly


def test_collapse_flow_to_quarterly_sums_monthly_within_quarter():
    points = [
        DataPoint(date(2015, 1, 1), 516.9),
        DataPoint(date(2015, 2, 1), 681.7),
        DataPoint(date(2015, 3, 1), 762.1),
    ]
    out = collapse_flow_to_quarterly(points)
    assert len(out) == 1
    assert out[0].date == date(2015, 1, 1)
    assert out[0].value == round(516.9 + 681.7 + 762.1, 2)


def test_collapse_flow_to_quarterly_keeps_quarterly_only_rows():
    points = [
        DataPoint(date(2015, 1, 1), 1960.7),
        DataPoint(date(2016, 1, 1), 2047.3),
        DataPoint(date(2016, 4, 1), 3103.3),
    ]
    out = collapse_flow_to_quarterly(points)
    assert [p.date for p in out] == [date(2015, 1, 1), date(2016, 1, 1), date(2016, 4, 1)]
    assert [p.value for p in out] == [1960.7, 2047.3, 3103.3]


def test_collapse_flow_to_quarterly_yoy_base_not_spike():
    """Mixed monthly (2015) + quarterly (2016) must not compare Q1 to January."""
    monthly_2015 = [
        DataPoint(date(2015, 1, 1), 516.9),
        DataPoint(date(2015, 2, 1), 681.7),
        DataPoint(date(2015, 3, 1), 762.1),
    ]
    quarterly_2016 = [DataPoint(date(2016, 1, 1), 2047.3)]
    collapsed = collapse_flow_to_quarterly(monthly_2015 + quarterly_2016)
    q1_2015 = next(p for p in collapsed if p.date == date(2015, 1, 1)).value
    q1_2016 = next(p for p in collapsed if p.date == date(2016, 1, 1)).value
    yoy_pct = round((q1_2016 / q1_2015 - 1) * 100, 2)
    assert yoy_pct == round((2047.3 / (516.9 + 681.7 + 762.1) - 1) * 100, 2)
    assert yoy_pct < 10
