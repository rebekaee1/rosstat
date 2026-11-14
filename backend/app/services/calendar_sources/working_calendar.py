from __future__ import annotations

from datetime import date, timedelta


WORKING_CALENDAR_SOURCES = {
    2026: "http://publication.pravo.gov.ru/document/0001202509240023",
    # Постановление Правительства РФ от 17.09.2026 № 1187 «О переносе выходных дней в 2027 году».
    2027: "http://government.ru/docs/59913/",
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
    # Статья 112 ТК РФ и постановление № 1187 от 17.09.2026: 2 января → 5 ноября,
    # 3 января → 31 декабря, 20 февраля → 22 февраля. Ниже — только будни: выходные
    # субботы и воскресенья отсекает weekday().
    2027: {
        date(2027, 1, 1), date(2027, 1, 4), date(2027, 1, 5),
        date(2027, 1, 6), date(2027, 1, 7), date(2027, 1, 8),
        date(2027, 2, 22), date(2027, 2, 23),
        date(2027, 3, 8),
        date(2027, 5, 3), date(2027, 5, 10),
        date(2027, 6, 14),
        date(2027, 11, 4), date(2027, 11, 5),
        date(2027, 12, 31),
    },
}


# Субботы и воскресенья, ставшие рабочими по переносу (постановление о переносе выходных).
WORKING_WEEKENDS = {
    2026: set(),
    2027: {date(2027, 2, 20)},  # суббота 20 февраля — рабочая, выходной перенесён на 22 февраля
}


def calendar_source_url(year: int) -> str | None:
    return WORKING_CALENDAR_SOURCES.get(year)


def is_working_day(day: date) -> bool:
    if day.year not in NON_WORKING_DAYS:
        raise ValueError(f"No official working calendar loaded for {day.year}")
    if day in NON_WORKING_DAYS[day.year]:
        return False
    if day in WORKING_WEEKENDS.get(day.year, set()):
        return True
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

