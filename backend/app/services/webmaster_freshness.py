"""Свежесть данных Яндекс Вебмастера: от какого дня число «в поиске» и с чем его сравнивать.

Вебмастер публикует число страниц в поиске точками по обновлениям поисковой базы (раз в 2–3 дня).
После аварий в дата-центрах Яндекса (8–11.10.2026) точек не было с 07.10 по 13.11, обход в истории
остановился на 10.10, а `summary` до 16.11 отдавал замороженные 105 480. Первая точка после перерыва
(29 306 на 13.11) — пересчёт базы Яндекса за пять недель, а не падение «за день»: события того же
обновления называют только 658 исключённых. Сравнение через такой перерыв подписываем, а не тревожим.
Разбор — docs/backlog.md#yandex-in-search-2026-11-18.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

# Обычный шаг обновлений базы — 2–3 дня; неделя без точки — перерыв данных Яндекса.
IN_SEARCH_GAP_DAYS = 7
# История обхода в норме отстаёт на 1–2 суток (см. COMPLETE_DAY_AFTER_DAYS в webmaster_indexing_daily).
CRAWL_STALE_DAYS = 3

_MSK = timezone(timedelta(hours=3))


def _point_date(point: Any) -> date | None:
    try:
        ts = datetime.fromisoformat(str(point["date"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return None
    if ts.tzinfo is not None:
        ts = ts.astimezone(_MSK)
    return ts.date()


def in_search_points(payload: Any) -> list[tuple[date, int]]:
    """Точки `search-urls/in-search/history` по возрастанию даты; ноль — тоже наблюдение."""
    if not isinstance(payload, dict):
        return []
    by_day: dict[date, int] = {}
    for point in payload.get("history") or []:
        if not isinstance(point, dict) or point.get("value") is None:
            continue
        d = _point_date(point)
        if d is not None:
            by_day[d] = int(point["value"])
    return sorted(by_day.items())


def in_search_freshness(payload: Any, today: date) -> dict[str, Any] | None:
    """Последняя и предыдущая точки «в поиске», перерыв между ними и возраст последней.

    data_gap=True — между точками больше IN_SEARCH_GAP_DAYS дней: разница копилась весь перерыв
    и не является изменением за день. None у data_gap — одна точка, сравнивать не с чем.
    """
    points = in_search_points(payload)
    if not points:
        return None
    last_day, last_value = points[-1]
    out: dict[str, Any] = {
        "date": last_day.isoformat(),
        "value": last_value,
        "age_days": (today - last_day).days,
        "previous_date": None,
        "previous_value": None,
        "gap_days": None,
        "data_gap": None,
    }
    if len(points) >= 2:
        prev_day, prev_value = points[-2]
        gap = (last_day - prev_day).days
        out.update(previous_date=prev_day.isoformat(), previous_value=prev_value,
                   gap_days=gap, data_gap=gap > IN_SEARCH_GAP_DAYS)
    return out


def last_crawl_day(payload: Any) -> date | None:
    """Последний день с наблюдением в `indexing/history` (любой класс HTTP-кодов)."""
    if not isinstance(payload, dict):
        return None
    indicators = payload.get("indicators") or {}
    if isinstance(indicators, dict):
        series = indicators.values()
    elif isinstance(indicators, list):
        series = (s.get("history", []) for s in indicators if isinstance(s, dict))
    else:
        return None
    days = [d for points in series for p in points or []
            if isinstance(p, dict) and p.get("value") is not None and (d := _point_date(p)) is not None]
    return max(days) if days else None


def freshness_lines(fresh: dict[str, Any] | None, crawl_day: date | None, today: date) -> list[str]:
    """Строки недельного отчёта о свежести данных Вебмастера (пусто — данные свежие)."""
    lines: list[str] = []
    if fresh:
        when = date.fromisoformat(fresh["date"]).strftime("%d.%m")
        if fresh.get("data_gap"):
            prev = date.fromisoformat(fresh["previous_date"]).strftime("%d.%m")
            lines.append(
                f"«В поиске» от {when}; предыдущая точка {prev} ({fresh['previous_value']}), "
                f"перерыв данных Яндекса {fresh['gap_days']} дн. — разница накоплена за перерыв, "
                "это не изменение за неделю")
        elif fresh.get("age_days") is not None and fresh["age_days"] > IN_SEARCH_GAP_DAYS:
            lines.append(f"«В поиске» не обновлялось Яндексом с {when} ({fresh['age_days']} дн.)")
    if crawl_day is not None and (today - crawl_day).days > CRAWL_STALE_DAYS:
        lines.append(f"История обхода в Вебмастере остановилась {crawl_day.strftime('%d.%m')}: "
                     "числа обхода ниже — за прежний период, сторона Яндекса")
    return lines
