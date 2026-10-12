"""Дополнительные модели world-прогноза и вложенный выбор (круг 12)."""

from __future__ import annotations

import math
import random
from datetime import date

import pytest
from dateutil.relativedelta import relativedelta

from app.services import world_forecaster as wf
from app.services.world_forecast_candidates import (
    forecast_candidate,
    min_fit_points,
)


def _dates(start: date, count: int, months: int) -> list[date]:
    return [start + relativedelta(months=index * months) for index in range(count)]


def _failed_primary(reason: str = "mase_not_below_one") -> wf.WorldForecastGate:
    return wf.WorldForecastGate("failed", reason, "annual_auto", 1.3, 1.1, 4, None)


def test_drift_extrapolates_linear_trend_exactly():
    values = [10.0 + 2.0 * index for index in range(30)]
    forecast = forecast_candidate("drift", values, season=1, steps=3)
    assert forecast == pytest.approx([70.0, 72.0, 74.0])


def test_log_candidate_needs_positive_history():
    values = [float(index - 5) for index in range(30)]
    assert forecast_candidate("drift-log", values, season=1, steps=1) is None
    grow = [100.0 * 1.05 ** index for index in range(30)]
    result = forecast_candidate("drift-log", grow, season=1, steps=1)
    assert result is not None
    assert result[0] == pytest.approx(100.0 * 1.05 ** 30, rel=1e-6)


def test_seasonal_candidates_keep_the_seasonal_shape():
    season = [0.0, 10.0, 20.0, 5.0]
    values = [100.0 + 0.5 * index + season[index % 4] for index in range(80)]
    for name in ("drift", "theta", "holt-damped", "ses"):
        forecast = forecast_candidate(name, values, season=4, steps=4)
        assert forecast is not None and len(forecast) == 4
        # Фаза пика (третий квартал) остаётся самой высокой после возвращения сезонности.
        assert max(range(4), key=lambda i: forecast[i]) == (80 + 2) % 4 or forecast[2] > forecast[0]


def test_candidates_never_return_non_finite_or_too_short():
    short = [1.0] * (min_fit_points(1) - 1)
    assert forecast_candidate("theta", short, season=1, steps=1) is None
    wild = [math.exp(60 * index / 30) for index in range(30)]
    result = forecast_candidate("drift-log", wild, season=1, steps=5)
    assert result is None or all(math.isfinite(value) for value in result)


def test_candidate_path_publishes_trending_series_under_its_own_name(monkeypatch):
    dates = _dates(date(1990, 1, 1), 36, 12)
    rng = random.Random(7)
    values = [100.0 + 4.0 * index + rng.uniform(-0.5, 0.5) for index in range(36)]
    monkeypatch.setattr(wf, "_train_primary_gate", lambda *a, **k: _failed_primary())

    gate = wf.train_quality_gated_world_forecast(
        dates, values, frequency="annual", horizon=1, season=1, strategy="annual_auto",
    )

    assert gate.status == "passed"
    assert gate.strategy.startswith("candidate:")
    assert gate.reason == "beats_seasonal_naive"
    assert gate.mase is not None and gate.mase < 1
    assert gate.baseline_mase is not None and gate.mase < gate.baseline_mase * 0.98
    assert gate.result is not None and len(gate.result.points) == 1
    assert gate.result.points[0].date == date(2026, 1, 1)
    assert gate.result.model_name.startswith("World-")
    assert gate.details["candidate_set"] >= 1
    assert gate.details["candidate_model"] == gate.strategy.split(":", 1)[1]


def test_selection_windows_end_before_the_first_gate_window(monkeypatch):
    """Выбор модели не видит целевых значений окон гейта (нет утечки)."""
    dates = _dates(date(1990, 1, 1), 40, 12)
    values = [50.0 + 3.0 * index + (index % 3) for index in range(40)]
    monkeypatch.setattr(wf, "_train_primary_gate", lambda *a, **k: _failed_primary())
    calls: list[tuple[tuple[str, ...], list[int]]] = []
    real = wf._score_candidates

    def spy(names, vals, origins, **kwargs):
        calls.append((tuple(names), list(origins)))
        return real(names, vals, origins, **kwargs)

    monkeypatch.setattr(wf, "_score_candidates", spy)
    wf.train_quality_gated_world_forecast(
        dates, values, frequency="annual", horizon=1, season=1, strategy="annual_auto",
    )

    selection = calls[0][1]
    assert len(calls) <= 2
    if len(calls) == 2:
        gate_origins = calls[1][1]
        assert max(selection) + 1 <= min(gate_origins)  # целевые точки отбора раньше окон гейта
        assert len(calls[1][0]) == 1  # на гейт идёт ровно одна выбранная модель


def test_candidate_path_skipped_for_hard_failures(monkeypatch):
    dates = _dates(date(1990, 1, 1), 36, 12)
    values = [100.0 + 4.0 * index for index in range(36)]
    monkeypatch.setattr(
        wf, "_train_primary_gate",
        lambda *a, **k: _failed_primary("history_too_short"),
    )
    gate = wf.train_quality_gated_world_forecast(
        dates, values, frequency="annual", horizon=1, season=1, strategy="annual_auto",
    )
    assert gate.status == "failed" and gate.reason == "history_too_short"


def test_candidate_path_rejects_random_walk(monkeypatch):
    """Случайное блуждание непредсказуемо: наивный прогноз оптимален, гейт закрыт."""
    dates = _dates(date(1990, 1, 1), 36, 12)
    rng = random.Random(3)
    values = [100.0]
    for _ in range(35):
        values.append(values[-1] + rng.gauss(0.0, 2.0))
    monkeypatch.setattr(wf, "_train_primary_gate", lambda *a, **k: _failed_primary())
    gate = wf.train_quality_gated_world_forecast(
        dates, values, frequency="annual", horizon=1, season=1, strategy="annual_auto",
    )
    assert gate.status == "failed"
    assert gate.result is None


def test_candidate_forecast_outside_bounds_is_not_published(monkeypatch):
    dates = _dates(date(1990, 1, 1), 36, 12)
    values = [50.0 + 1.5 * index for index in range(36)]  # тренд уходит за 100
    monkeypatch.setattr(wf, "_train_primary_gate", lambda *a, **k: _failed_primary())
    gate = wf.train_quality_gated_world_forecast(
        dates, values, frequency="annual", horizon=1, season=1,
        strategy="annual_auto", bounds=(0.0, 100.0),
    )
    assert gate.status == "failed"
    assert gate.reason == "out_of_range"
    assert gate.result is None


def test_primary_forecast_outside_bounds_is_rejected():
    dates = _dates(date(2018, 1, 1), 96, 1)
    values = [90.0 + 0.2 * index for index in range(96)]  # ~109 к концу
    gate = wf.train_quality_gated_world_forecast(
        dates, values, frequency="monthly", horizon=12, season=12,
        strategy="monthly_auto", bounds=(0.0, 100.0),
    )
    assert gate.result is None
    assert gate.status == "failed"


def test_regularize_tail_fills_short_gaps_and_cuts_after_long_ones():
    monthly = _dates(date(2020, 1, 1), 60, 1)
    one_missing = [*monthly[:30], *monthly[31:]]
    regular = wf._regularize_tail(one_missing, [float(i) for i in range(59)], 1)
    assert regular is not None and regular.imputed == 1 and not regular.cut
    assert len(regular.dates) == 60
    assert regular.observed.count(False) == 1
    filled = regular.observed.index(False)
    assert regular.dates[filled] == monthly[30]
    assert regular.values[filled] == pytest.approx((29.0 + 30.0) / 2)

    far = [*monthly[:20], *monthly[26:]]  # дыра в 6 месяцев
    cut = wf._regularize_tail(far, [float(i) for i in range(54)], 1)
    assert cut is not None and cut.cut and len(cut.dates) == 34 and cut.imputed == 0

    duplicated = [*monthly[:6], monthly[5], *monthly[6:10]]  # повторная дата: календарь неровный
    assert wf._regularize_tail(duplicated, [float(i) for i in range(11)], 1) is None


def test_imputed_targets_do_not_enter_backtest_errors():
    values = [10.0 + index for index in range(40)]
    observed = [True] * 40
    observed[30] = False
    values[30] = 9999.0  # заведомо неверная «интерполяция»: в ошибки попасть не должна
    names = ["drift"]
    masked = wf._score_candidates(names, values, [28, 29, 30], season=1, test_horizon=1, observed=observed)
    unmasked = wf._score_candidates(names, values, [28, 29, 30], season=1, test_horizon=1)
    assert masked is not None and unmasked is not None
    assert masked[0]["drift"][0] < 1.0 < unmasked[0]["drift"][0]


def test_gap_filling_never_takes_away_a_forecast_the_legacy_path_published(monkeypatch):
    """Если с интерполяцией ряд не прошёл, а по-старому (история после дыры) прошёл — берём прежний."""
    passed = wf.WorldForecastGate("passed", "beats_seasonal_naive", "monthly_auto", 0.4, 0.9, 6, object())
    failed = wf.WorldForecastGate(
        "failed", "not_better_than_seasonal_naive", "monthly_auto", 0.9, 0.9, 6, None,
        {"imputed_points": 1},
    )
    calls = []

    def fake(dates, values, **kwargs):
        calls.append(kwargs["fill_gaps"])
        return failed if kwargs["fill_gaps"] else passed

    monkeypatch.setattr(wf, "_gate_with_fallbacks", fake)
    dates = _dates(date(2018, 1, 1), 96, 1)
    gate = wf.train_quality_gated_world_forecast(
        dates, [float(i) for i in range(96)],
        frequency="monthly", horizon=12, season=12, strategy="monthly_auto",
    )
    assert gate is passed
    assert calls == [True, False]
