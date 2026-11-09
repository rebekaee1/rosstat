"""Просрочки рядов с особым ритмом выпуска (09.11.2026)."""

from datetime import date, datetime


def test_weekly_published_daily_series_is_not_stale_after_nine_days():
    """08.11.2026: `usd-index` (ФРС H.10, выход раз в неделю) с последней точкой 30.10 был в «новых просрочках»."""
    from app.services.staleness import StaleRow, build_report, find_stale

    today = date(2026, 11, 8)
    row = StaleRow("usd-index", "daily", date(2026, 10, 30), parser_type="fred_csv", last_status="no_new_data",
                   last_fetch_at=datetime(2026, 11, 8, 7, 0))
    report = build_report([row], {}, today=today)
    assert report.total_stale == 0
    assert find_stale([("usd-index", "daily", date(2026, 10, 30))], today=today) == []
    # три недели без точки - уже просрочка
    assert find_stale([("usd-index", "daily", date(2026, 10, 15))], today=today) == [("usd-index", 24)]
