"""Unit-тесты на backward chain исторических индексов цен на жильё.

Проверяют, что backward chain от anchor 2015-Q4 даёт согласованный chained
level для всех исторических точек, и что overlap-точка совпадает с тем,
что записано в БД (sanity-check на правильность extracted YoY-таблицы).
"""

from __future__ import annotations

import pytest

from app.data.housing_historical import (
    HISTORICAL_START_YEAR,
    PRIMARY_YOY_PCT,
    SECONDARY_YOY_PCT,
    SPECS,
    build_historical_levels,
)


# Известные anchor-значения 2015-Q4 в БД на 2026-05 (housing-price-primary,
# housing-price-secondary). Если splice вёл бы к другим anchor — тест бы упал.
PRIMARY_2015_Q4 = 130.5
SECONDARY_2015_Q4 = 126.3


def test_primary_chain_round_trip_anchor_year() -> None:
    """Forward chain от 1998 anchor должен вернуть 2014-Q4 close to 2015/yoy."""
    levels = build_historical_levels(PRIMARY_2015_Q4, PRIMARY_YOY_PCT)
    assert HISTORICAL_START_YEAR in levels
    assert 2014 in levels
    # 2014-Q4 backward: 130.5 / (99.7 / 100) = 130.892
    assert abs(levels[2014] - 130.5 / 0.997) < 0.01
    # 2010-Q4 (база нашего индекса) должно быть около 100 после полного chain
    assert abs(levels[2010] - 100.0) < 0.5, f"got {levels[2010]}"


def test_secondary_chain_round_trip_anchor_year() -> None:
    levels = build_historical_levels(SECONDARY_2015_Q4, SECONDARY_YOY_PCT)
    assert HISTORICAL_START_YEAR in levels
    # 2014-Q4: 126.3 / 0.968 ≈ 130.48
    assert abs(levels[2014] - 126.3 / 0.968) < 0.01


def test_build_returns_one_point_per_year() -> None:
    levels = build_historical_levels(PRIMARY_2015_Q4, PRIMARY_YOY_PCT)
    years = sorted(levels.keys())
    assert years == list(range(HISTORICAL_START_YEAR, 2015))
    assert len(years) == 17  # 1998..2014


def test_yoy_tables_cover_required_range() -> None:
    required = set(range(HISTORICAL_START_YEAR, 2016))  # need 1998..2015 (last yoy for backward step)
    assert required.issubset(PRIMARY_YOY_PCT.keys())
    assert required.issubset(SECONDARY_YOY_PCT.keys())


def test_levels_strictly_positive_and_growing_in_historical_part() -> None:
    levels = build_historical_levels(PRIMARY_2015_Q4, PRIMARY_YOY_PCT)
    for y, v in levels.items():
        assert v > 0, f"non-positive at {y}: {v}"
    # 2009 had price decline (yoy=92.4) — допускаем; 2014→2015 тоже декл.
    # Sanity: long-run growth from 1998 to 2014
    assert levels[2014] > levels[1998]


def test_specs_contain_both_indicators() -> None:
    codes = {spec.indicator_code for spec in SPECS}
    assert codes == {"housing-price-primary", "housing-price-secondary"}


def test_anchor_negative_raises() -> None:
    with pytest.raises(ValueError):
        build_historical_levels(-1.0, PRIMARY_YOY_PCT)


def test_missing_year_raises() -> None:
    truncated = {y: v for y, v in PRIMARY_YOY_PCT.items() if y >= 2010}
    with pytest.raises(KeyError):
        build_historical_levels(PRIMARY_2015_Q4, truncated)
