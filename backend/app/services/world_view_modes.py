"""Чистые операции режимов отображения мирового блока.

По духу ADR-0001: без db/async/I/O. Материализация в БД запрещена —
режимы считаются на лету в API из базового ряда. Прогнозов нет.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

Series = list[tuple[date, float]]

def _sorted(series: Series) -> Series:
    return sorted(((d, float(v)) for d, v in series), key=lambda p: p[0])


def is_signed_or_zero_crossing(series: Iterable[tuple[date, float]]) -> bool:
    """Ряд со знаком / пересекает ноль → процентный YoY запрещён (AGENTS п. 5)."""
    vals = [float(v) for _, v in series]
    if not vals:
        return False
    return min(vals) <= 0 <= max(vals) or any(v < 0 for v in vals)


def transform_level(series: Series) -> Series:
    return _sorted(series)


def transform_mom(series: Series) -> Series:
    by_ym = {(d.year, d.month): float(v) for d, v in series}
    out: Series = []
    for y, m in sorted(by_ym):
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        prev = by_ym.get((py, pm))
        if prev is None or prev == 0:
            continue
        out.append((date(y, m, 1), round((by_ym[(y, m)] / prev - 1.0) * 100.0, 2)))
    return out


def transform_qoq(series: Series) -> Series:
    pts = _sorted(series)
    out: Series = []
    for i in range(1, len(pts)):
        d_cur, v_cur = pts[i]
        d_prev, v_prev = pts[i - 1]
        if v_prev == 0 or (d_cur - d_prev).days > 110:
            continue
        out.append((d_cur, round((v_cur / v_prev - 1.0) * 100.0, 2)))
    return out


def transform_mom_abs(series: Series) -> Series:
    """Изменение к прошлому месяцу в единицах ряда (для знакопеременных)."""
    by_ym = {(d.year, d.month): float(v) for d, v in series}
    out: Series = []
    for y, m in sorted(by_ym):
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        prev = by_ym.get((py, pm))
        if prev is None:
            continue
        out.append((date(y, m, 1), round(by_ym[(y, m)] - prev, 4)))
    return out


def transform_qoq_abs(series: Series) -> Series:
    """Изменение к прошлому кварталу в единицах ряда (для знакопеременных)."""
    pts = _sorted(series)
    out: Series = []
    for i in range(1, len(pts)):
        d_cur, v_cur = pts[i]
        d_prev, v_prev = pts[i - 1]
        if (d_cur - d_prev).days > 110:
            continue
        out.append((d_cur, round(v_cur - v_prev, 4)))
    return out


def transform_yoy(series: Series) -> Series:
    by_date = {d: float(v) for d, v in series}
    out: Series = []
    for d in sorted(by_date):
        try:
            prev_d = date(d.year - 1, d.month, d.day)
        except ValueError:
            continue
        denom = by_date.get(prev_d)
        if denom is None or denom == 0:
            continue
        out.append((d, round((by_date[d] / denom - 1.0) * 100.0, 2)))
    return out


def transform_yoy_abs(series: Series) -> Series:
    by_date = {d: float(v) for d, v in series}
    out: Series = []
    for d in sorted(by_date):
        try:
            prev_d = date(d.year - 1, d.month, d.day)
        except ValueError:
            continue
        prev = by_date.get(prev_d)
        if prev is None:
            continue
        out.append((d, round(by_date[d] - prev, 4)))
    return out


def transform_index_first(series: Series) -> Series:
    pts = _sorted(series)
    if not pts or pts[0][1] == 0:
        return []
    base = pts[0][1]
    return [(d, round(v / base * 100.0, 2)) for d, v in pts]


def transform_avg_quarter(series: Series) -> Series:
    buckets: dict[tuple[int, int], list[float]] = {}
    for d, v in series:
        q = (d.month - 1) // 3 + 1
        buckets.setdefault((d.year, q), []).append(float(v))
    out: Series = []
    for (y, q), vals in sorted(buckets.items()):
        out.append((date(y, (q - 1) * 3 + 1, 1), round(sum(vals) / len(vals), 4)))
    return out


def transform_avg_year(series: Series) -> Series:
    buckets: dict[int, list[float]] = {}
    for d, v in series:
        buckets.setdefault(d.year, []).append(float(v))
    return [
        (date(y, 1, 1), round(sum(vals) / len(vals), 4))
        for y, vals in sorted(buckets.items())
    ]


_TRANSFORMS = {
    "level": transform_level,
    "mom": transform_mom,
    "mom_abs": transform_mom_abs,
    "qoq": transform_qoq,
    "qoq_abs": transform_qoq_abs,
    "yoy": transform_yoy,
    "yoy_abs": transform_yoy_abs,
    "index_first": transform_index_first,
    "avg_quarter": transform_avg_quarter,
    "avg_year": transform_avg_year,
}


def apply_mode(series: Series, mode: str) -> Series:
    fn = _TRANSFORMS.get(mode)
    if fn is None:
        raise ValueError(f"unknown mode: {mode}")
    return fn(series)


def mode_unit(mode: str, base_unit: str, *, locale: str | None = None) -> str:
    if mode in ("mom", "qoq", "yoy"):
        return "%"
    if mode == "index_first":
        loc = locale
        if loc is None:
            from app.services.locale import get_locale

            loc = get_locale()
        return "index" if loc == "en" else "индекс"
    return base_unit or ""
