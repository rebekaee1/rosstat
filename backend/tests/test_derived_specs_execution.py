"""Т-9 + Т-10: прямые тесты 4 непокрытых ops + execution-smoke ВСЕХ спеков.

Т-10: `DERIVED_SPECS` (включая ~757 сгенерированных generic-семей) до сих пор
тестировались только на уникальность dst-кодов — кривые kwargs пайплайна
(`гranularity="qurter"` и т.п.) взорвались бы только в проде. Здесь каждый op
каждого спека исполняется на синтетическом ряде: смок ловит TypeError/KeyError/
ValueError в самой формуле.
"""

from datetime import date

import pytest

from app.services.calculation_engine import DERIVED_SPECS
from app.services.derived_ops import (
    mom_abs,
    period_over_period_abs,
    qoq_abs,
    rebase_to_first,
)

# ── Т-9: юниты на знак / ноль / пропуски ─────────────────────────────


def test_mom_abs_sign_and_gap():
    series = [
        (date(2025, 1, 1), 10.0),
        (date(2025, 2, 1), 12.5),   # +2.5
        # март пропущен
        (date(2025, 4, 1), 11.0),   # нет пары (март) → точка не выйдет
        (date(2025, 5, 1), 9.0),    # −2.0 к апрелю
    ]
    out = dict(mom_abs(series))
    assert out[date(2025, 2, 1)] == 2.5
    assert date(2025, 4, 1) not in out, "дыра не сравнивается через пропуск"
    assert out[date(2025, 5, 1)] == -2.0


def test_mom_abs_year_boundary():
    out = dict(mom_abs([(date(2024, 12, 1), 5.0), (date(2025, 1, 1), 4.0)]))
    assert out[date(2025, 1, 1)] == -1.0


def test_qoq_abs_sign_change():
    series = [
        (date(2025, 1, 1), -3.0),
        (date(2025, 4, 1), 2.0),   # переход через ноль: +5.0 абсолютно
        (date(2025, 7, 1), 2.0),   # 0.0
    ]
    out = qoq_abs(series)
    assert out == [(date(2025, 4, 1), 5.0), (date(2025, 7, 1), 0.0)]


def test_period_over_period_abs_quarterly_last():
    # Месячная ставка: агрегат «last» внутри квартала, разница в п.п.
    series = [
        (date(2025, 1, 1), 16.0), (date(2025, 2, 1), 16.0), (date(2025, 3, 1), 15.0),
        (date(2025, 4, 1), 15.0), (date(2025, 5, 1), 14.0), (date(2025, 6, 1), 14.0),
    ]
    out = period_over_period_abs(series, "quarter", method="last")
    assert len(out) == 1
    assert out[0][1] == -1.0  # Q2 last 14.0 − Q1 last 15.0


def test_rebase_to_first_and_zero_base():
    out = rebase_to_first([(date(2000, 1, 1), 50.0), (date(2001, 1, 1), 75.0)])
    assert out == [(date(2000, 1, 1), 100.0), (date(2001, 1, 1), 150.0)]
    assert rebase_to_first([(date(2000, 1, 1), 0.0), (date(2001, 1, 1), 5.0)]) == []
    assert rebase_to_first([]) == []


# ── Т-10: execution-smoke всех спеков ────────────────────────────────


def _synthetic_series() -> list[tuple[date, float]]:
    """5 лет месячных положительных точек — «максимально безопасный» вход:
    покрывает monthly/quarterly/annual агрегации и YoY-глубину."""
    pts = []
    v = 100.0
    for year in range(2020, 2025):
        for month in range(1, 13):
            v *= 1.004
            pts.append((date(year, month, 1), round(v, 4)))
    return pts


@pytest.mark.parametrize(
    "spec", DERIVED_SPECS, ids=[s.dst_code for s in DERIVED_SPECS]
)
def test_spec_op_executes_on_synthetic(spec):
    series = _synthetic_series()
    inputs = [list(series) for _ in spec.src_codes]
    out = spec.op(*inputs)
    assert isinstance(out, list)
    for d, v in out:
        assert isinstance(d, date)
        assert isinstance(v, (int, float))
        assert v == v, f"{spec.dst_code}: NaN в выходе"
