"""Одна фраза «динамика» для SSR-карточки показателя (круг 13, SEO).

Карточки мировых рядов называли последнее значение и период, но не
говорили, куда движется показатель: запросы «как менялся …» и сниппеты
получали только таблицу. Фраза считается по тому же ряду, что и страница:
изменение к предыдущему периоду, к году назад и крайние значения истории.
Чистая функция: форматтеры и подписи периодов приходят снаружи.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, timedelta

_NEAR_DAYS = {"daily": 4, "weekly": 10, "monthly": 20, "quarterly": 50, "annual": 120}


def _year_ago_value(series: Sequence[tuple[date, float]], frequency: str | None) -> tuple[date, float] | None:
    """Точка ряда, ближайшая к дате последнего значения минус год (в допуске по частоте)."""
    last_date = series[-1][0]
    try:
        target = last_date.replace(year=last_date.year - 1)
    except ValueError:  # 29 февраля
        target = last_date - timedelta(days=365)
    tolerance = _NEAR_DAYS.get((frequency or "").lower(), 20)
    best = min(series[:-1], key=lambda item: abs((item[0] - target).days), default=None)
    if best is None or abs((best[0] - target).days) > tolerance:
        return None
    return best


def _delta_text(
    last: float,
    base: float,
    *,
    is_percent: bool,
    fmt: Callable[[float], str],
    en: bool,
) -> str | None:
    """«выше на 0,8 п.п.» / «ниже на 3,1 %» / «без изменений»; None — база непригодна."""
    if last == base:
        return "unchanged" if en else "без изменений"
    if is_percent:
        diff = abs(last - base)
        number = f"{fmt(diff)} {'pp' if en else 'п.п.'}"
    else:
        if base == 0:
            return None
        diff = abs(last / base - 1.0) * 100.0
        if diff >= 1000:
            return None
        number = f"{fmt(round(diff, 1))} %"
    if en:
        return f"{'up' if last > base else 'down'} {number}"
    return f"{'выше' if last > base else 'ниже'} на {number}"


def dynamics_note(
    series: Sequence[tuple[date, float]],
    frequency: str | None,
    *,
    unit: str,
    unit_sfx: str = "",
    fmt: Callable[[float], str],
    label: Callable[[date], str],
    en: bool = False,
    min_points: int = 3,
    fmt_value: Callable[[float], str] | None = None,
    extremes: bool = True,
) -> str:
    """Готовая фраза или пустая строка, если ряд слишком короткий.

    ``unit`` нужен только чтобы отличить проценты (разность в п.п.) от
    величин (относительное изменение в %). ``unit_sfx`` добавляется к значениям,
    но не к разностям.
    """
    if len(series) < min_points:
        return ""
    last_date, last = series[-1]
    prev_date, prev = series[-2]
    is_percent = "%" in (unit or "")

    def val(number: float) -> str:
        return fmt_value(number) if fmt_value else f"{fmt(number)}{unit_sfx}"

    parts: list[str] = []
    vs_prev = _delta_text(last, prev, is_percent=is_percent, fmt=fmt, en=en)
    # Дневной ряд, где вчера и сегодня совпали, — не динамика (ставка ЦБ, курс на выходных).
    if last == prev and (frequency or "").lower() in ("daily", "weekly"):
        vs_prev = None
    if vs_prev:
        parts.append(
            f"{'versus the previous period' if en else 'к предыдущему периоду'} "
            f"({label(prev_date)}, {val(prev)}) — {vs_prev}"
        )
    year_ago = _year_ago_value(series, frequency)
    if year_ago is not None and year_ago[0] != prev_date:
        vs_year = _delta_text(last, year_ago[1], is_percent=is_percent, fmt=fmt, en=en)
        if vs_year:
            parts.append(
                f"{'versus a year earlier' if en else 'к тому же периоду годом ранее'} "
                f"({label(year_ago[0])}, {val(year_ago[1])}) — {vs_year}"
            )
    lo = min(series, key=lambda item: item[1])
    hi = max(series, key=lambda item: item[1])
    tail = ""
    if extremes and lo[1] != hi[1] and len(series) >= 5:
        if en:
            tail = (
                f" Over the whole series the low is {val(lo[1])} ({label(lo[0])}) "
                f"and the high is {val(hi[1])} ({label(hi[0])})."
            )
        else:
            tail = (
                f" За весь период наблюдений минимум — {val(lo[1])} ({label(lo[0])}), "
                f"максимум — {val(hi[1])} ({label(hi[0])})."
            )
    if not parts:
        return tail.strip()
    head = "Change: " if en else "Динамика: "
    body = "; ".join(parts)
    if body and not body.endswith("."):
        body += "."
    return (head + body + (" " + tail.strip() if tail else "")).strip()
