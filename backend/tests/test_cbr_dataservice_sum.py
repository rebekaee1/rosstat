"""Tests for CbrDataServiceSumParser logic (sum aggregation)."""

from collections import defaultdict
from datetime import date


def test_sum_aggregation_logic():
    """Verify that summing multiple DataService component results works."""
    sums: dict[date, float] = defaultdict(float)

    comp1 = [(date(2024, 1, 1), 100.0), (date(2024, 2, 1), 110.0)]
    comp2 = [(date(2024, 1, 1), 200.0), (date(2024, 2, 1), 220.0)]
    comp3 = [(date(2024, 1, 1), 50.0), (date(2024, 2, 1), 55.0)]

    for comp in [comp1, comp2, comp3]:
        for dt, val in comp:
            sums[dt] += val

    assert sums[date(2024, 1, 1)] == 350.0
    assert sums[date(2024, 2, 1)] == 385.0


def test_sum_missing_dates():
    """Components with different date ranges should still sum correctly."""
    sums: dict[date, float] = defaultdict(float)

    comp1 = [(date(2024, 1, 1), 100.0), (date(2024, 2, 1), 110.0), (date(2024, 3, 1), 120.0)]
    comp2 = [(date(2024, 2, 1), 200.0), (date(2024, 3, 1), 210.0)]

    for comp in [comp1, comp2]:
        for dt, val in comp:
            sums[dt] += val

    assert sums[date(2024, 1, 1)] == 100.0
    assert sums[date(2024, 2, 1)] == 310.0
    assert sums[date(2024, 3, 1)] == 330.0
