"""Snapshot regression test для CPI-Monthly + Inflation-12M.

Эталон: `snapshots/cpi_2025_11.json` — выход моей реализации
`train_monthly_cpi`/`train_inflation_12m` на CSV-данных Никиты по
ноябрь 2025 (`snapshots/ipc_monthly_2025_11.csv`).

Тест ловит:
1. Случайные правки в `forecaster.py`, которые меняют numerical
   output (включая микро-правки знака/порядка операций).
2. Расхождение с эталоном Никиты — если Никита присылает новую версию
   блокнота, этот snapshot пересоздаётся, тест становится новым
   эталоном.

Допуск: 1e-3 для каждой точки. Хватает чтобы поймать любую содержательную
ошибку, но не реагирует на изменения round() / numerical drift в
библиотеках на 4-м знаке.
"""

import csv
import json
import math
from pathlib import Path

import pytest

from app.services.forecaster import train_inflation_12m, train_monthly_cpi


SNAP_DIR = Path(__file__).parent / "snapshots"


def _load_input():
    with open(SNAP_DIR / "ipc_monthly_2025_11.csv", encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))
    from datetime import date as date_t
    dates = [date_t.fromisoformat(r["date"]) for r in rows]
    values = [float(r["ipc"]) for r in rows]
    return dates, values


def _load_snapshot():
    with open(SNAP_DIR / "cpi_2025_11.json", encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture(scope="module")
def cpi_input():
    return _load_input()


def _assert_points_close(actual_points, expected_points, tol=1e-3):
    assert len(actual_points) == len(expected_points), \
        f"point count mismatch: {len(actual_points)} vs {len(expected_points)}"
    for ap, ep in zip(actual_points, expected_points):
        assert ap.date.isoformat() == ep["date"], \
            f"date mismatch: {ap.date.isoformat()} vs {ep['date']}"
        assert math.isclose(ap.value, ep["value"], abs_tol=tol), \
            f"value mismatch on {ep['date']}: {ap.value} vs {ep['value']} (tol={tol})"


def test_cpi_monthly_snapshot(cpi_input):
    dates, values = cpi_input
    snap = _load_snapshot()
    result = train_monthly_cpi(dates, values, forecast_steps=12)
    _assert_points_close(result.points, snap["cpi_monthly"])


def test_inflation_12m_snapshot(cpi_input):
    dates, values = cpi_input
    snap = _load_snapshot()
    result = train_inflation_12m(dates, values, forecast_steps=12)
    _assert_points_close(result.points, snap["inflation_12m"])
