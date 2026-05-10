from __future__ import annotations

from datetime import date, timedelta


WORKING_CALENDAR_SOURCES = {
    2026: "http://publication.pravo.gov.ru/document/0001202509240023",
}


NON_WORKING_DAYS = {
    2026: {
        # New year + transferred day from 2025-12-31 holiday stretch.
        date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3),
        date(2026, 1, 4), date(2026, 1, 5), date(2026, 1, 6),
        date(2026, 1, 7), date(2026, 1, 8), date(2026, 1, 9),
        # Federal holidays and observed long weekends.
        date(2026, 2, 23),
        date(2026, 3, 9),
        date(2026, 5, 1), date(2026, 5, 11),
        date(2026, 6, 12),
        date(2026, 11, 4),
        date(2026, 12, 31),
    },
}


def calendar_source_url(year: int) -> str | None:
    return WORKING_CALENDAR_SOURCES.get(year)


def is_working_day(day: date) -> bool:
    if day.year not in NON_WORKING_DAYS:
        raise ValueError(f"No official working calendar loaded for {day.year}")
    if day in NON_WORKING_DAYS[day.year]:
        return False
    return day.weekday() < 5


def nth_working_day(year: int, month: int, n: int) -> date:
    cur = date(year, month, 1)
    seen = 0
    while cur.month == month:
        if is_working_day(cur):
            seen += 1
            if seen == n:
                return cur
        cur += timedelta(days=1)
    raise ValueError(f"Month {year}-{month:02d} has fewer than {n} working days")


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1

