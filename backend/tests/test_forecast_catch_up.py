"""Авто-retrain при смене значений + gap-fill пустых прогнозов."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.services.base_parser import BaseParser
from app.services.forecast_pipeline import (
    catch_up_empty_forecasts,
    order_for_forecast_catch_up,
    values_changed_for_retrain,
)


def test_values_changed_for_retrain_gates_idempotent_upsert():
    assert values_changed_for_retrain(0, 0, 0) is False
    assert values_changed_for_retrain(1, 0, 0) is True
    assert values_changed_for_retrain(0, 1, 0) is True
    assert values_changed_for_retrain(0, 0, 1) is True
    assert values_changed_for_retrain(2, 3, 1) is True


def test_order_for_forecast_catch_up_puts_derived_last():
    src = SimpleNamespace(
        code="m2",
        model_config_json={"forecast_steps": 12, "forecast_strategy": "monthly_auto"},
    )
    der = SimpleNamespace(
        code="m2-yoy",
        model_config_json={
            "forecast_steps": 12,
            "forecast_strategy": "derived_from_source",
        },
    )
    other = SimpleNamespace(
        code="ipi",
        model_config_json={"forecast_steps": 12, "forecast_strategy": "monthly_auto"},
    )
    ordered = order_for_forecast_catch_up([der, src, other])
    assert [i.code for i in ordered] == ["m2", "ipi", "m2-yoy"]


class _StubParser(BaseParser):
    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        return [], ""


def test_handle_forecasts_skips_when_no_value_change(monkeypatch):
    calls: list[str] = []

    async def _fake_retrain(db, indicator):
        calls.append(indicator.code)

    monkeypatch.setattr(
        "app.services.base_parser.retrain_indicator_forecast",
        _fake_retrain,
    )
    parser = _StubParser()
    ind = SimpleNamespace(code="cpi", model_config_json={"forecast_steps": 12})

    asyncio.run(
        parser._handle_forecasts(
            db=None, indicator=ind, cfg=ind.model_config_json,
            records_added=0, records_updated=0, pruned=0,
        )
    )
    assert calls == []


def test_handle_forecasts_retrains_on_added_updated_or_pruned(monkeypatch):
    calls: list[str] = []

    async def _fake_retrain(db, indicator):
        calls.append(indicator.code)

    monkeypatch.setattr(
        "app.services.base_parser.retrain_indicator_forecast",
        _fake_retrain,
    )
    parser = _StubParser()
    ind = SimpleNamespace(code="cpi", model_config_json={"forecast_steps": 12})
    cfg = ind.model_config_json

    for kwargs in (
        {"records_added": 1, "records_updated": 0, "pruned": 0},
        {"records_added": 0, "records_updated": 2, "pruned": 0},
        {"records_added": 0, "records_updated": 0, "pruned": 3},
    ):
        calls.clear()
        asyncio.run(
            parser._handle_forecasts(db=None, indicator=ind, cfg=cfg, **kwargs)
        )
        assert calls == ["cpi"], kwargs


def test_handle_forecasts_skips_when_steps_zero(monkeypatch):
    calls: list[str] = []

    async def _fake_retrain(db, indicator):
        calls.append(indicator.code)

    monkeypatch.setattr(
        "app.services.base_parser.retrain_indicator_forecast",
        _fake_retrain,
    )
    parser = _StubParser()
    ind = SimpleNamespace(code="key-rate", model_config_json={"forecast_steps": 0})
    asyncio.run(
        parser._handle_forecasts(
            db=None, indicator=ind, cfg=ind.model_config_json,
            records_added=5, records_updated=1, pruned=0,
        )
    )
    assert calls == []


def test_catch_up_empty_forecasts_retrains_missing_only(monkeypatch):
    """Gap-fill зовёт retrain только для steps>0 без текущих forecast values."""

    src = SimpleNamespace(
        id=1,
        code="exports",
        is_active=True,
        model_config_json={"forecast_steps": 4, "forecast_strategy": "generic_quarterly"},
    )
    der = SimpleNamespace(
        id=2,
        code="exports-yoy",
        is_active=True,
        model_config_json={
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
        },
    )
    ok = SimpleNamespace(
        id=3,
        code="cpi",
        is_active=True,
        model_config_json={"forecast_steps": 12, "forecast_strategy": "cpi_combined"},
    )
    off = SimpleNamespace(
        id=4,
        code="key-rate",
        is_active=True,
        model_config_json={"forecast_steps": 0},
    )

    # counts: src empty, der empty, ok has values, off ignored by steps
    counts = {1: 0, 2: 0, 3: 12, 4: 0}
    retrained: list[str] = []

    async def _count(db, indicator_id):
        return counts[indicator_id]

    async def _fake_retrain(db, indicator, _retrain_chain=None):
        retrained.append(indicator.code)
        # Cascade from source fills derived — emulate for skip check.
        if indicator.code == "exports":
            counts[2] = 4
        counts[indicator.id] = 4

    monkeypatch.setattr(
        "app.services.forecast_pipeline._current_forecast_value_count",
        _count,
    )
    monkeypatch.setattr(
        "app.services.forecast_pipeline.retrain_indicator_forecast",
        _fake_retrain,
    )

    db = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalars.return_value.all.return_value = [der, ok, off, src]
    db.execute = AsyncMock(return_value=result_proxy)

    filled = asyncio.run(catch_up_empty_forecasts(db))

    # Source first; derived skipped after cascade filled counts[2].
    assert filled == ["exports"]
    assert retrained == ["exports"]
