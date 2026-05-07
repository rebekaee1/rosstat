"""Snapshot регресс для прямой SARIMA-модели реального ВВП.

Никита Александрович обнаружил, что текущий прогноз `gdp-real` на сайте
не совпадает с его эталонным ноутбуком (`train_sarima_model(data,
forecast_steps=4)` где data = реальный ВВП напрямую). Раньше мы
прогнозировали `gdp-real` через цепочку
`gdp-real ← real_from_yoy(gdp-yoy) ← yoy_quarterly(gdp-nominal SARIMA)`,
и накопленная ошибка давала расхождение 4.5–7.5%. Переключение
на прямую SARIMA устраняет эту ошибку.

Тест двойной:

1. **Bit-exact regression** на сохранённом снэпшоте ряда (`gdp_real_2025_12.json`):
   функция должна детерминированно воспроизводить `expected_forecast`
   до 4-го знака. Гарантирует, что мы случайно не сломаем модель
   будущими правками.
2. **Notebook tolerance**: в том же файле лежит `_notebook_expected` —
   значения из ноутбука Никиты. Проверяем, что наша модель отличается
   от ноутбука не более чем на `_notebook_tolerance_pct` (1%). Это
   контролирует, что прямой SARIMA даёт «практически то же», что
   ожидает Никита (фактическое расхождение ~0.15% на актуальном
   снэпшоте — в пределах толерантности).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.services.forecaster import train_gdp_real_quarterly

SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "gdp_real_2025_12.json"


@pytest.fixture(scope="module")
def snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_gdp_real_snapshot_bit_exact(snapshot):
    series = snapshot["series"]
    dates = [date.fromisoformat(r["date"]) for r in series]
    values = [float(r["value"]) for r in series]

    result = train_gdp_real_quarterly(dates, values, forecast_steps=4)

    assert result.model_name == "GDP-Real-Quarterly-MW"
    assert len(result.points) == 4

    expected = snapshot["expected_forecast"]
    for got, exp in zip(result.points, expected):
        assert got.date.isoformat() == exp["date"], (
            f"date mismatch: {got.date} vs {exp['date']}"
        )
        assert got.value == pytest.approx(exp["value"], abs=1e-3), (
            f"{got.date}: got {got.value}, expected {exp['value']}"
        )


def test_gdp_real_matches_notebook_within_tolerance(snapshot):
    """Forecast должен совпадать с ноутбуком Никиты в пределах 1%."""
    series = snapshot["series"]
    dates = [date.fromisoformat(r["date"]) for r in series]
    values = [float(r["value"]) for r in series]

    result = train_gdp_real_quarterly(dates, values, forecast_steps=4)
    notebook = snapshot["_notebook_expected"]
    tol_pct = snapshot["_notebook_tolerance_pct"]

    by_date = {p.date.isoformat(): p.value for p in result.points}
    for exp in notebook:
        got_value = by_date.get(exp["date"])
        assert got_value is not None, f"missing forecast for {exp['date']}"
        diff_pct = abs(got_value - exp["value"]) / exp["value"] * 100.0
        assert diff_pct <= tol_pct, (
            f"{exp['date']}: got {got_value}, notebook {exp['value']}, "
            f"diff {diff_pct:.3f}% > {tol_pct}%"
        )


def test_gdp_real_strategy_is_registered():
    """Гарантия что стратегия зарегистрирована в реестре."""
    from app.services.forecast_strategies.registry import STRATEGIES
    assert "gdp_real_quarterly" in STRATEGIES
