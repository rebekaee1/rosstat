"""Unit tests for BLS and BEA world adapters (mocked; key-gate)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.bea_api import (
    BeaApiAdapter,
    BeaApiError,
    BeaSeriesSpec,
    parse_bea_data_rows,
    parse_bea_time,
    parse_series_id,
)
from app.services.world_adapters.bls_api import (
    BlsApiAdapter,
    BlsApiError,
    BlsSeriesSpec,
    parse_bls_period,
    parse_bls_series_payload,
)
from app.services.world_national_ingest import AdapterUnavailable
from app.services.world_source_adapter import WorldSeriesRef


def _run(coro):
    return asyncio.run(coro)


def test_bls_period_and_payload_parse():
    assert parse_bls_period(2024, "M03") == date(2024, 3, 1)
    assert parse_bls_period("2024", "Q02") == date(2024, 4, 1)
    assert parse_bls_period(2024, "A01") == date(2024, 1, 1)
    obs = parse_bls_series_payload(
        {
            "data": [
                {"year": "2024", "period": "M02", "value": "4.1"},
                {"year": "2024", "period": "M01", "value": "3.7"},
                {"year": "2024", "period": "M03", "value": ""},
            ]
        },
        series_id="LNS14000000",
    )
    assert [o.period for o in obs] == [date(2024, 1, 1), date(2024, 2, 1)]
    assert obs[-1].value == 4.1


def test_bls_fetch_mocked_with_key():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {
            "series": [
                {
                    "seriesID": "LNS14000000",
                    "data": [
                        {"year": "2026", "period": "M07", "value": "4.1"},
                        {"year": "2026", "period": "M06", "value": "4.1"},
                    ],
                }
            ]
        },
    }
    session.post.return_value = response

    adapter = BlsApiAdapter(
        series=(
            BlsSeriesSpec(
                series_id="LNS14000000",
                dataset_id="LN",
                unit_code="PERCENT",
                frequency="monthly",
            ),
        ),
        session=session,
        api_key="test-key",
    )
    ref = WorldSeriesRef(
        provider="bls",
        dataset_id="LN",
        series_id="LNS14000000",
        country_code="US",
        frequency="monthly",
        unit_code="PERCENT",
    )
    payload = _run(adapter.fetch_series(ref))
    assert payload.observations[-1].value == 4.1
    body = session.post.call_args.kwargs["json"]
    assert body["registrationkey"] == "test-key"


def test_bls_keyless_http_error_becomes_unavailable():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 403
    response.text = "Access Denied"
    session.post.return_value = response

    adapter = BlsApiAdapter(
        series=(BlsSeriesSpec(series_id="CUSR0000SA0", dataset_id="CU"),),
        session=session,
        api_key=None,
    )
    ref = WorldSeriesRef(
        provider="bls",
        dataset_id="CU",
        series_id="CUSR0000SA0",
        country_code="US",
        frequency="monthly",
        unit_code="INDEX",
    )
    with pytest.raises(AdapterUnavailable, match="RUSTATS_BLS_API_KEY"):
        _run(adapter.fetch_series(ref))


def test_bea_parse_helpers():
    assert parse_series_id("T10106:1") == ("T10106", "1")
    with pytest.raises(BeaApiError):
        parse_series_id("T10106")
    assert parse_bea_time("2024Q2", frequency="quarterly") == date(2024, 4, 1)
    assert parse_bea_time("2024M06", frequency="monthly") == date(2024, 6, 1)
    obs = parse_bea_data_rows(
        [
            {"LineNumber": "1", "TimePeriod": "2024Q1", "DataValue": "22,679.2"},
            {"LineNumber": "1", "TimePeriod": "2024Q2", "DataValue": "22,900.1"},
            {"LineNumber": "2", "TimePeriod": "2024Q2", "DataValue": "1.0"},
        ],
        line_number="1",
        frequency="quarterly",
    )
    assert len(obs) == 2
    assert obs[0].value == 22679.2


def test_bea_constructor_requires_key():
    with pytest.raises(AdapterUnavailable, match="RUSTATS_BEA_API_KEY"):
        BeaApiAdapter(api_key=None)


def test_bea_fetch_mocked():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "BEAAPI": {
            "Results": {
                "Data": [
                    {
                        "LineNumber": "1",
                        "TimePeriod": "2026Q1",
                        "DataValue": "24,180.419",
                    },
                    {
                        "LineNumber": "1",
                        "TimePeriod": "2026Q2",
                        "DataValue": "24,270.599",
                    },
                ]
            }
        }
    }
    session.get.return_value = response

    adapter = BeaApiAdapter(
        series=(
            BeaSeriesSpec(
                series_id="T10106:1",
                dataset_id="NIPA",
                table_name="T10106",
                line_number="1",
                unit_code="USD_BN_CHAINED",
                frequency="quarterly",
            ),
        ),
        session=session,
        api_key="bea-test-key",
    )
    ref = WorldSeriesRef(
        provider="bea",
        dataset_id="NIPA",
        series_id="T10106:1",
        country_code="US",
        frequency="quarterly",
        unit_code="USD_BN_CHAINED",
    )
    payload = _run(adapter.fetch_series(ref))
    assert payload.observations[-1].value == 24270.599
    assert session.get.call_args.kwargs["params"]["UserID"] == "bea-test-key"
