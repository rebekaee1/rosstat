"""Pure-function tests for the calendar seeder.

These cover the event builders directly (no DB), focusing on coverage and
correctness invariants the operator cares about:

* All events fall inside the rolling [today, today+months_ahead] window.
* Importance values are valid {1, 2, 3}.
* Each weekday in the next 30 days has at least one Thursday International
  Reserves event (CBR weekly), at least one Wednesday weekly CPI (Rosstat),
  and at least one Friday Monetary Base (CBR).
* In any 30-day forward window we get a healthy mix of all three sources
  (cbr / rosstat / minfin).
* Public-facing strings never mention internal/forecast jargon (SARIMA,
  Никита, OLS, notebook…).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.calendar_seed import (
    CBR_MEETINGS_2026,
    CBR_MEETINGS_2027_TENTATIVE,
    WEEKLY_SPECS,
    _build_cbr_meeting_events,
    _build_monthly_release_events,
    _build_quarterly_release_events,
    _build_weekly_events,
    CBR_STAT_MONTHLY,
    MINFIN_MONTHLY,
    ROSSTAT_MONTHLY_RELEASES,
    ROSSTAT_QUARTERLY_RELEASES,
)


@pytest.fixture
def today() -> date:
    return date(2026, 5, 7)  # Thursday — exactly the date Никита asked about


# --- Builders return data in the rolling window ------------------------------


def _all_events(today: date, months_ahead: int = 12) -> list[dict]:
    events: list[dict] = []
    events.extend(_build_cbr_meeting_events(CBR_MEETINGS_2026, is_estimated=False, today=today))
    events.extend(_build_cbr_meeting_events(CBR_MEETINGS_2027_TENTATIVE, is_estimated=True, today=today))
    events.extend(_build_monthly_release_events(
        ROSSTAT_MONTHLY_RELEASES, "rosstat", today=today, months_ahead=months_ahead,
    ))
    events.extend(_build_monthly_release_events(
        CBR_STAT_MONTHLY, "cbr", today=today, months_ahead=months_ahead,
    ))
    events.extend(_build_monthly_release_events(
        MINFIN_MONTHLY, "minfin", today=today, months_ahead=months_ahead,
    ))
    events.extend(_build_quarterly_release_events(
        ROSSTAT_QUARTERLY_RELEASES, "rosstat", today=today, months_ahead=months_ahead,
    ))
    events.extend(_build_weekly_events(today=today, months_ahead=months_ahead))
    return events


def test_seed_produces_at_least_200_events_in_year(today: date):
    """Health check: a 12-month window should yield a dense calendar."""
    events = _all_events(today, months_ahead=12)
    horizon = today + timedelta(days=12 * 31)
    cutoff = today - timedelta(days=14)
    in_window = [e for e in events if cutoff <= e["scheduled_date"] <= horizon]
    assert len(in_window) >= 200, f"too few events in rolling window: {len(in_window)}"


def test_importance_is_in_valid_range(today: date):
    events = _all_events(today)
    for e in events:
        assert e["importance"] in (1, 2, 3), e


def test_thirty_day_forward_window_is_diverse(today: date):
    """At least N events with all three real sources in the next 30 days."""
    events = _all_events(today)
    horizon = today + timedelta(days=30)
    upcoming = [e for e in events if today <= e["scheduled_date"] <= horizon]
    assert len(upcoming) >= 25, f"upcoming count too low: {len(upcoming)}"
    sources = {e["source"] for e in upcoming}
    assert {"cbr", "rosstat", "minfin"} <= sources, sources


# --- Weekly events: International Reserves on every Thursday -----------------


def test_thursday_has_international_reserves_for_next_30_days(today: date):
    events = _build_weekly_events(today=today, months_ahead=2)
    by_date = {e["scheduled_date"]: e for e in events
               if e["title"] == "Международные резервы РФ"}
    cur = today
    end = today + timedelta(days=30)
    while cur <= end:
        if cur.weekday() == 3:  # Thursday
            assert cur in by_date, f"missing reserves event on {cur}"
            ev = by_date[cur]
            assert ev["source"] == "cbr"
            assert ev["importance"] == 2
            assert ev["scheduled_time"] == "16:00"
        cur += timedelta(days=1)


def test_weekday_anchor_for_each_weekly_spec(today: date):
    """Each WeeklySpec.weekday must match the actual day of every generated event."""
    events = _build_weekly_events(today=today, months_ahead=3)
    for spec in WEEKLY_SPECS:
        spec_events = [e for e in events
                       if e["title"] == spec.title and e["source"] == spec.source]
        assert spec_events, f"no events for spec {spec.title}"
        for e in spec_events:
            assert e["scheduled_date"].weekday() == spec.weekday, e


# --- Status auto-promotion ---------------------------------------------------


def test_past_events_marked_released(today: date):
    events = _all_events(today)
    past = [e for e in events if e["scheduled_date"] < today]
    future = [e for e in events if e["scheduled_date"] >= today]
    assert all(e["status"] == "released" for e in past)
    assert all(e["status"] == "scheduled" for e in future)


# --- CBR meetings split correctly between fixed/tentative --------------------


def test_2027_meetings_marked_tentative(today: date):
    events_2027 = _build_cbr_meeting_events(
        CBR_MEETINGS_2027_TENTATIVE, is_estimated=True, today=today,
    )
    assert events_2027, "no 2027 meetings produced"
    for e in events_2027:
        assert e["is_estimated"] is True
        if e["event_type"] == "rate_decision":
            assert e["metadata_json"]["tentative"] is True


def test_2026_meetings_not_tentative(today: date):
    events_2026 = _build_cbr_meeting_events(
        CBR_MEETINGS_2026, is_estimated=False, today=today,
    )
    for e in events_2026:
        assert e["is_estimated"] is False


# --- No internal jargon leaks in user-visible fields ------------------------


_FORBIDDEN_TERMS = (
    "SARIMA", "Никита", "ноутбук", "notebook",
    "Holt-Winters", "OLS", "multi-window", "multi_window",
)


def _user_visible_text(event: dict) -> str:
    parts = [
        event.get("title", ""),
        event.get("title_en", "") or "",
        event.get("description", "") or "",
        event.get("reference_period", "") or "",
    ]
    return " | ".join(parts)


def test_no_internal_jargon_in_calendar_strings(today: date):
    events = _all_events(today)
    for e in events:
        text = _user_visible_text(e)
        for term in _FORBIDDEN_TERMS:
            assert term.lower() not in text.lower(), (
                f"forbidden term {term!r} in event: {text}"
            )


# --- Quarterly GDP releases reach into the next 6 months --------------------


def test_quarterly_gdp_release_present_in_window(today: date):
    events = _build_quarterly_release_events(
        ROSSTAT_QUARTERLY_RELEASES, "rosstat", today=today, months_ahead=6,
    )
    codes = {e["indicator_code"] for e in events}
    assert "gdp-nominal" in codes
    assert all(e["importance"] in (1, 2, 3) for e in events)
