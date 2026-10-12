"""Веб-процесс не тянет pandas/scipy/statsmodels при старте (круг 12, SPEED3: −105 МБ на каждый из трёх воркеров)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def test_app_import_does_not_load_forecasting_stack():
    code = (
        "import sys, app.main\n"
        "heavy = [m for m in ('pandas', 'scipy', 'statsmodels') if m in sys.modules]\n"
        "assert not heavy, heavy\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def test_gate_names_are_reexported_from_old_modules():
    from app.services import world_forecast_gate, world_forecast_pipeline, world_forecaster

    assert world_forecaster.PUBLISHED_GATE_STATUSES is world_forecast_gate.PUBLISHED_GATE_STATUSES
    assert world_forecaster.WORLD_FORECAST_METHOD_VERSION == world_forecast_gate.WORLD_FORECAST_METHOD_VERSION
    assert world_forecaster.publishable_world_forecast is world_forecast_gate.publishable_world_forecast
    assert world_forecast_pipeline.world_forecast_source_ready is world_forecast_gate.world_forecast_source_ready


@pytest.mark.parametrize("status,version,expected", [("passed", 2, True), ("passed", 1, False), ("failed", 2, False)])
def test_publishable_world_forecast(status, version, expected):
    from types import SimpleNamespace

    from app.services.world_forecast_gate import publishable_world_forecast

    forecast = SimpleNamespace(gate_status=status, model_params={"method_version": version})
    assert publishable_world_forecast(forecast) is expected
