"""Unit tests for Japan e-Stat adapter (mocked HTTP; key-gated)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters import estat_api
from app.services.world_adapters.estat_api import (
    ENV_APP_ID,
    EstatApiAdapter,
    EstatApiError,
    EstatSeriesSpec,
    parse_estat_observations,
    parse_estat_time,
)
from app.services.world_national_ingest import AdapterUnavailable
from app.services.world_source_adapter import WorldSeriesRef

ESTAT_OK = {
    "GET_STATS_DATA": {
        "RESULT": {"STATUS": 0, "ERROR_MSG": "Normal termination."},
        "STATISTICAL_DATA": {
            "DATA_INF": {
                "VALUE": [
                    {"@time": "202401", "$": "105.2"},
                    {"@time": "202402", "$": "105.5"},
                    {"@time": "202403", "$": "*"},
                ]
            }
        },
    }
}


def _run(coro):
    return asyncio.run(coro)


def test_parse_estat_time_and_observations():
    assert parse_estat_time("202401", frequency="monthly") == date(2024, 1, 1)
    assert parse_estat_time("2024Q2", frequency="quarterly") == date(2024, 4, 1)
    obs = parse_estat_observations(ESTAT_OK, frequency="monthly")
    assert [o.period for o in obs] == [date(2024, 1, 1), date(2024, 2, 1)]
    assert obs[1].value == 105.5


def test_parse_estat_auth_failure():
    payload = {
        "GET_STATS_DATA": {
            "RESULT": {"STATUS": 100, "ERROR_MSG": "auth failed"},
        }
    }
    with pytest.raises(EstatApiError, match="authentication"):
        parse_estat_observations(payload, frequency="monthly")


def test_create_adapter_requires_app_id(monkeypatch):
    monkeypatch.delenv(ENV_APP_ID, raising=False)
    with pytest.raises(AdapterUnavailable, match=ENV_APP_ID):
        estat_api.create_adapter()


def test_create_adapter_and_fetch(monkeypatch):
    monkeypatch.setenv(ENV_APP_ID, "test-app-id")
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = ESTAT_OK
    response.text = "{}"
    session.get.return_value = response

    assert estat_api.create_adapter().provider == "estat"

    adapter = EstatApiAdapter(
        (
            EstatSeriesSpec(
                series_id="cpi-all-items",
                dataset_id="0003427113",
                frequency="monthly",
                unit_code="INDEX",
            ),
        ),
        app_id="test-app-id",
        session=session,
    )
    assert adapter.provider == "estat"
    ref = WorldSeriesRef(
        provider="estat",
        dataset_id="0003427113",
        series_id="cpi-all-items",
        country_code="JP",
        frequency="monthly",
        unit_code="INDEX",
    )
    payload = _run(adapter.fetch_series(ref))
    assert len(payload.observations) == 2
    assert payload.observations[0].value == 105.2


def test_resolve_estat_unavailable_without_key(monkeypatch):
    from app.services.world_national_ingest import resolve_adapter

    monkeypatch.delenv(ENV_APP_ID, raising=False)
    with pytest.raises(AdapterUnavailable, match=ENV_APP_ID):
        resolve_adapter("estat")
