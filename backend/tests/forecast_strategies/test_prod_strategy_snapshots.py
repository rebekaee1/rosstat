"""Т-8: bit-exact снапшоты стратегий на РЕАЛЬНЫХ (prod-fixture) рядах.

До этого `ppi_monthly`/`gdp_nominal_quarterly` проверялись только на синтетике,
а `generic_quarterly`/`signed_quarterly`/`generic_ols` — только политикой
(whitelist). Обновление statsmodels/numpy могло тихо изменить прогнозные числа
на проде. Здесь каждая стратегия воспроизводит сохранённый прогноз до 1e-4.

Снапшоты генерирует `scripts/gen-forecast-snapshots.py` (см. docstring);
перегенерация ОСОЗНАННАЯ — после апгрейда numerical stack сначала объяснить
diff, потом коммитить новые файлы.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.services.forecast_strategies.base import StrategyContext
from app.services.forecast_strategies.registry import STRATEGIES

SNAP_DIR = Path(__file__).parent / "snapshots"
SNAPSHOTS = sorted(SNAP_DIR.glob("prod_*.json"))


def test_all_five_strategies_have_prod_snapshots():
    names = {p.stem.removeprefix("prod_") for p in SNAPSHOTS}
    assert {
        "ppi_monthly", "gdp_nominal_quarterly",
        "generic_quarterly", "signed_quarterly", "generic_ols",
    } <= names, f"не хватает снапшотов: {names}"


@pytest.mark.parametrize(
    "snap_path", SNAPSHOTS, ids=[p.stem for p in SNAPSHOTS]
)
def test_strategy_reproduces_snapshot(snap_path):
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    strategy = STRATEGIES[snap["strategy"]]

    dates = [date.fromisoformat(r["date"]) for r in snap["series"]]
    values = [float(r["value"]) for r in snap["series"]]
    cfg = snap["cfg"]
    ctx = StrategyContext(
        indicator_code=snap["code"],
        indicator_frequency=snap["frequency"],
        forecast_steps=int(cfg.get("forecast_steps") or 4),
        cfg=cfg,
    )

    outputs = strategy(dates, values, ctx)
    assert len(outputs) == len(snap["outputs"])

    for out, exp in zip(outputs, snap["outputs"]):
        assert out.result.model_name == exp["model_name"]
        assert len(out.result.points) == len(exp["points"])
        for got, want in zip(out.result.points, exp["points"]):
            assert got.date.isoformat() == want["date"]
            assert float(got.value) == pytest.approx(want["value"], abs=1e-4), (
                f"{snap['strategy']}/{want['date']}: {got.value} != {want['value']}"
            )
            if want["lower"] is not None:
                assert float(got.lower_bound) == pytest.approx(want["lower"], abs=1e-4)
            if want["upper"] is not None:
                assert float(got.upper_bound) == pytest.approx(want["upper"], abs=1e-4)
