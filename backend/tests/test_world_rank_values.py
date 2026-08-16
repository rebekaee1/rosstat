"""Сопоставимость баз индекса и режим рейтинга/карты."""

from __future__ import annotations

from datetime import date

from app.services.world_rank_values import (
    index_base_key,
    index_bases_mixed,
    latest_rank_point,
    ranking_value_mode,
    resolve_default_coverage_year,
    yearly_last_points,
)


class _Ind:
    def __init__(self, unit="", unit_ru="", slice_json=None):
        self.unit = unit
        self.unit_ru = unit_ru
        self.slice_json = slice_json or {}


def test_index_base_key_from_unit_and_slice():
    assert index_base_key("I15", "индекс (2015 = 100)") == "2015"
    assert index_base_key("INDEX", "индекс (1982–84 = 100)") == "1982-1984"
    assert index_base_key("INDEX", "индекс (2002 = 100)") == "2002"
    assert index_base_key(
        "INDEX", "индекс", {"base_year": "2012"}
    ) == "2012"
    assert index_base_key("INDEX", "индекс") == "__unknown__"
    assert index_base_key("PC_ACT", "% экономически активного населения") is None


def test_mixed_index_bases_force_yoy_and_catch_unknown():
    euro = _Ind("I15", "индекс (2015 = 100)")
    us = _Ind("INDEX", "индекс (1982–84 = 100)")
    au = _Ind("INDEX", "индекс")
    rate = _Ind("PC_ACT", "% экономически активного населения")

    assert index_bases_mixed([(None, euro), (None, euro)]) is False
    assert index_bases_mixed([(None, euro), (None, us)]) is True
    assert index_bases_mixed([(None, euro), (None, au)]) is True
    assert index_bases_mixed([(None, rate), (None, rate)]) is False

    assert ranking_value_mode("unemployment-rate", [(None, rate)]) == "level"
    assert ranking_value_mode("budget-balance-gdp", [(None, euro), (None, us)]) == "yoy"
    # Цены всегда в изменении за год, даже при одинаковой базе.
    assert ranking_value_mode("hicp-index", [(None, euro), (None, euro)]) == "yoy"


def test_yoy_rank_points_cancel_index_base():
    # Одна база 100 vs другая база 200 — уровни несравнимы, YoY одинаков.
    series_a = [
        (date(2024, 1, 1), 100.0),
        (date(2025, 1, 1), 110.0),
    ]
    series_b = [
        (date(2024, 1, 1), 200.0),
        (date(2025, 1, 1), 220.0),
    ]
    assert latest_rank_point(series_a, "yoy") == (date(2025, 1, 1), 10.0)
    assert latest_rank_point(series_b, "yoy") == (date(2025, 1, 1), 10.0)
    assert yearly_last_points(series_a, "yoy")[2025][1] == 10.0


def test_default_year_uses_coverage_share():
    years = [2024, 2025, 2026]
    values = {
        "2024": {f"C{i}": {} for i in range(40)},
        "2025": {f"C{i}": {} for i in range(40)},
        "2026": {"US": {}, "CA": {}, "IN": {}, "AU": {}, "MX": {}},
    }
    assert resolve_default_coverage_year(years, values) == 2025
