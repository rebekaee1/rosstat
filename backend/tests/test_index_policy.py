"""INDEX_POLICY: пороги, robots-meta, канон без ?mode=."""
from datetime import date

from app.services.index_policy import (
    RUSSIA_YEAR_MIN_POINTS,
    is_noindex_path,
    robots_for_path,
    strip_mode_query,
)


def test_russia_year_min_points_is_six():
    assert RUSSIA_YEAR_MIN_POINTS == 6


def test_old_regional_year_is_noindex():
    today = date(2026, 9, 3)
    assert is_noindex_path("/russia/region/moskva/chislennost-naseleniya/2018", today=today)
    assert not is_noindex_path("/russia/region/moskva/chislennost-naseleniya/2024", today=today)


def test_old_month_landing_is_noindex():
    today = date(2026, 9, 3)
    assert is_noindex_path("/russia/indicator/cpi/2023-04", today=today)
    assert not is_noindex_path("/russia/indicator/cpi/2026-01", today=today)


def test_old_world_year_is_noindex():
    today = date(2026, 9, 3)
    assert is_noindex_path("/germany/indicator/de-foo/2010", today=today)
    assert not is_noindex_path("/germany/indicator/de-cpi/2022", today=today)


def test_hubs_stay_indexable():
    assert not is_noindex_path("/russia/indicator/cpi")
    assert not is_noindex_path("/russia/region/moskva/chislennost-naseleniya")
    assert "index, follow" in robots_for_path("/")


def test_strip_mode_query():
    assert strip_mode_query("/russia/indicator/cpi?mode=weekly") == "/russia/indicator/cpi"
    assert strip_mode_query("/russia/indicator/cpi") == "/russia/indicator/cpi"
    assert strip_mode_query("/x?mode=a&utm_source=y") == "/x?utm_source=y"


def test_honeypot_noindex():
    assert is_noindex_path("/__honeypot__/trap")
