"""Snapshot регресс для квартальной модели цен на жильё.

После рефакторинга 2026-05 (1:1 port of `Прогнозы_цены_на_жилье (1).ipynb`)
`train_quarterly_housing` воспроизводит ноутбук Никиты byte-exact.

Тест двойной:

1. **Bit-exact regression** на сохранённом снэпшоте ряда
   (`housing_primary_2026_q1.json`): функция должна детерминированно
   воспроизводить `expected_forecast` до 4-го знака.
2. **Notebook tolerance**: в том же файле лежит `_notebook_expected` —
   фактические значения из ноутбука Никиты. Различие — только в
   последнем округлении (мы режем до 4-х знаков, ноутбук до 6-ти),
   поэтому толерантность 0.01%.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.services.forecaster import train_quarterly_housing

SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "housing_primary_2026_q1.json"


@pytest.fixture(scope="module")
def snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_housing_primary_snapshot_bit_exact(snapshot):
    series = snapshot["series"]
    dates = [date.fromisoformat(r["date"]) for r in series]
    values = [float(r["value"]) for r in series]

    result = train_quarterly_housing(dates, values, forecast_steps=4)

    assert result.model_name == "Quarterly-Housing-MW"
    assert len(result.points) == 4

    expected = snapshot["expected_forecast"]
    for got, exp in zip(result.points, expected):
        assert got.date.isoformat() == exp["date"], (
            f"date mismatch: {got.date} vs {exp['date']}"
        )
        assert got.value == pytest.approx(exp["value"], abs=1e-3), (
            f"{got.date}: got {got.value}, expected {exp['value']}"
        )


def test_housing_primary_matches_notebook_within_tolerance(snapshot):
    """Forecast должен совпадать с ноутбуком Никиты в пределах 0.01%."""
    series = snapshot["series"]
    dates = [date.fromisoformat(r["date"]) for r in series]
    values = [float(r["value"]) for r in series]

    result = train_quarterly_housing(dates, values, forecast_steps=4)
    notebook = snapshot["_notebook_expected"]
    tol_pct = snapshot["_notebook_tolerance_pct"]

    by_date = {p.date.isoformat(): p.value for p in result.points}
    for exp in notebook:
        got_value = by_date.get(exp["date"])
        assert got_value is not None, f"missing forecast for {exp['date']}"
        diff_pct = abs(got_value - exp["value"]) / exp["value"] * 100.0
        assert diff_pct <= tol_pct, (
            f"{exp['date']}: got {got_value}, notebook {exp['value']}, "
            f"diff {diff_pct:.4f}% > {tol_pct}%"
        )


def test_housing_quarterly_strategy_is_registered():
    """Гарантия что стратегия зарегистрирована в реестре."""
    from app.services.forecast_strategies.registry import STRATEGIES
    assert "housing_quarterly" in STRATEGIES
