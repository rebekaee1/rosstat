"""Unit tests for ABS Data API (SDMX 2.1) adapter — mocked HTTP."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.abs_data import (
    DEFAULT_ABS_SERIES,
    AbsDataAdapter,
    AbsDataError,
    AbsSeriesSpec,
    canonical_dataset_id,
    create_adapter,
    data_url,
    format_sdmx_period,
    infer_frequency_from_data_key,
    map_freq_code,
    normalize_data_key,
    parse_dataflow_ref,
    parse_sdmx_json_observations,
    parse_sdmx_period,
)
from app.services.world_source_adapter import WorldDatasetVersion, WorldSeriesRef


CPI_SDMX_FIXTURE = {
    "meta": {
        "schema": "https://raw.githubusercontent.com/sdmx-twg/sdmx-json/master/data-message/tools/schemas/2.0.0/sdmx-json-data-schema.json",
        "id": "IREF016112",
        "prepared": "2026-08-12T07:39:54Z",
        "test": True,
        "sender": {"id": "ABS"},
    },
    "data": {
        "dataSets": [
            {
                "structure": 0,
                "action": "Information",
                "series": {
                    "0:0:0:0:0": {
                        "attributes": [None],
                        "annotations": [],
                        "observations": {
                            "0": [81],
                            "1": [79.44],
                            # Missing cell — skip.
                            "2": [None],
                        },
                    }
                },
            }
        ],
        "structures": [
            {
                "name": "Consumer Price Index (CPI)",
                "dimensions": {
                    "dataSet": [],
                    "series": [
                        {
                            "id": "MEASURE",
                            "keyPosition": 0,
                            "values": [{"id": "1", "name": "Index numbers"}],
                        },
                        {
                            "id": "INDEX",
                            "keyPosition": 1,
                            "values": [{"id": "10001", "name": "All groups CPI"}],
                        },
                        {
                            "id": "TSEST",
                            "keyPosition": 2,
                            "values": [{"id": "10", "name": "Original"}],
                        },
                        {
                            "id": "REGION",
                            "keyPosition": 3,
                            "values": [{"id": "50", "name": "Australia"}],
                        },
                        {
                            "id": "FREQ",
                            "keyPosition": 4,
                            "values": [{"id": "Q", "name": "Quarterly"}],
                        },
                    ],
                    "observation": [
                        {
                            "id": "TIME_PERIOD",
                            "keyPosition": 5,
                            "values": [
                                {
                                    "start": "2020-01-01T00:00:00",
                                    "end": "2020-03-31T00:00:00",
                                    "id": "2020-Q1",
                                    "name": "2020-Q1",
                                },
                                {
                                    "start": "2020-04-01T00:00:00",
                                    "end": "2020-06-30T00:00:00",
                                    "id": "2020-Q2",
                                    "name": "2020-Q2",
                                },
                                {
                                    "start": "2020-07-01T00:00:00",
                                    "end": "2020-09-30T00:00:00",
                                    "id": "2020-Q3",
                                    "name": "2020-Q3",
                                },
                            ],
                        }
                    ],
                },
            }
        ],
    },
}


def _run(coro):
    return asyncio.run(coro)


async def _collect_datasets(adapter: AbsDataAdapter) -> list[WorldDatasetVersion]:
    return [item async for item in adapter.list_datasets()]


async def _collect_series(
    adapter: AbsDataAdapter, dataset: WorldDatasetVersion
) -> list[WorldSeriesRef]:
    return [item async for item in adapter.list_series(dataset)]


def _mock_session(payload: dict | str, *, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    if isinstance(payload, str):
        response.text = payload
        response.json.side_effect = ValueError("not json")
    else:
        response.text = "json"
        response.json.return_value = payload
    session = MagicMock()
    session.get.return_value = response
    return session


def test_normalize_and_dataflow_helpers():
    assert normalize_data_key(" 1.10001.10.50.Q ") == "1.10001.10.50.Q"
    with pytest.raises(AbsDataError):
        normalize_data_key("  ")
    assert parse_dataflow_ref("CPI") == ("ABS", "CPI", None)
    assert parse_dataflow_ref("ABS,CPI,2.0.0") == ("ABS", "CPI", "2.0.0")
    assert canonical_dataset_id("ABS,CPI,2.0.0") == "CPI"
    assert data_url("CPI", "1.10001.10.50.Q").endswith(
        "/data/ABS,CPI/1.10001.10.50.Q"
    )
    assert map_freq_code("Q") == "quarterly"
    assert infer_frequency_from_data_key("1.10001.10.50.M") == "monthly"
    assert format_sdmx_period(date(2020, 4, 15), "quarterly") == "2020-Q2"
    assert format_sdmx_period(date(2024, 3, 1), "monthly") == "2024-03"
    assert parse_sdmx_period("2020-Q1") == date(2020, 1, 1)
    assert parse_sdmx_period("2024-03") == date(2024, 3, 1)
    assert parse_sdmx_period("2019", start="2019-01-01T00:00:00") == date(2019, 1, 1)


def test_parse_sdmx_json_observations_sorts_and_skips_null():
    obs = parse_sdmx_json_observations(CPI_SDMX_FIXTURE)
    assert [o.period for o in obs] == [date(2020, 1, 1), date(2020, 4, 1)]
    assert obs[0].value == 81.0
    assert obs[1].value == 79.44


def test_parse_sdmx_json_rejects_empty_series():
    bad = {
        "data": {
            "dataSets": [{"series": {}}],
            "structures": [
                {
                    "dimensions": {
                        "observation": [
                            {"id": "TIME_PERIOD", "values": [{"id": "2020-Q1"}]}
                        ]
                    }
                }
            ],
        }
    }
    with pytest.raises(AbsDataError, match="no series"):
        parse_sdmx_json_observations(bad)


def test_default_constructor_exposes_cpi_seed():
    adapter = AbsDataAdapter()
    assert adapter.provider == "abs"
    assert adapter.public_source_name == "Australian Bureau of Statistics"
    datasets = _run(_collect_datasets(adapter))
    assert {d.dataset_id for d in datasets} == {"CPI"}
    assert DEFAULT_ABS_SERIES[0].series_id == "1.10001.10.50.Q"


def test_list_series_for_cpi_dataset():
    adapter = AbsDataAdapter()
    series = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="abs", dataset_id="CPI"),
        )
    )
    assert len(series) == 1
    ref = series[0]
    assert ref.provider == "abs"
    assert ref.series_id == "1.10001.10.50.Q"
    assert ref.country_code == "AU"
    assert ref.frequency == "quarterly"
    assert ref.unit_code == "INDEX"
    assert ref.source_url and "/data/ABS,CPI/1.10001.10.50.Q" in ref.source_url


def test_fetch_series_with_mocked_http():
    session = _mock_session(CPI_SDMX_FIXTURE)
    adapter = AbsDataAdapter(session=session)
    ref = WorldSeriesRef(
        provider="abs",
        dataset_id="CPI",
        series_id="1.10001.10.50.Q",
        country_code="AU",
        frequency="quarterly",
        unit_code="INDEX",
    )
    payload = _run(
        adapter.fetch_series(
            ref, date_from=date(2020, 1, 1), date_to=date(2020, 6, 30)
        )
    )
    assert payload.ref.provider == "abs"
    assert len(payload.observations) == 2
    assert payload.observations[0].period == date(2020, 1, 1)
    assert payload.observations[0].value == 81.0
    assert payload.observations[-1].value == 79.44
    assert payload.revision_token == "2026-08-12T07:39:54Z"
    assert payload.source_hash and len(payload.source_hash) == 64

    call_kwargs = session.get.call_args
    assert call_kwargs is not None
    url = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url")
    assert url.endswith("/data/ABS,CPI/1.10001.10.50.Q")
    params = call_kwargs.kwargs["params"]
    assert params["format"] == "jsondata"
    assert params["startPeriod"] == "2020-Q1"
    assert params["endPeriod"] == "2020-Q2"


def test_fetch_series_fails_on_http_error():
    session = _mock_session("boom", status=503)
    adapter = AbsDataAdapter(session=session)
    ref = WorldSeriesRef(
        provider="abs",
        dataset_id="CPI",
        series_id="1.10001.10.50.Q",
        country_code="AU",
        frequency="quarterly",
        unit_code="INDEX",
    )
    with pytest.raises(AbsDataError, match="HTTP 503"):
        _run(adapter.fetch_series(ref))


def test_fetch_series_fails_on_no_records_plain_text():
    session = _mock_session("NoRecordsFound", status=200)
    adapter = AbsDataAdapter(session=session)
    ref = WorldSeriesRef(
        provider="abs",
        dataset_id="CPI",
        series_id="1.10001.10.50.Q",
        country_code="AU",
        frequency="quarterly",
        unit_code="INDEX",
    )
    with pytest.raises(AbsDataError, match="NoRecordsFound"):
        _run(adapter.fetch_series(ref))


def test_fetch_series_rejects_provider_mismatch():
    adapter = AbsDataAdapter()
    ref = WorldSeriesRef(
        provider="statcan",
        dataset_id="CPI",
        series_id="1.10001.10.50.Q",
        country_code="AU",
        frequency="quarterly",
        unit_code="INDEX",
    )
    with pytest.raises(AbsDataError, match="Provider mismatch"):
        _run(adapter.fetch_series(ref))


def test_create_adapter_from_national_specs():
    class Row:
        provider = "abs"
        dataset_id = "ABS,CPI"
        series_id = "1.10001.10.50.Q"
        frequency = "quarterly"
        unit = "INDEX"
        name_en = "CPI All groups"
        name_ru = None
        dimensions = {"REGION": "50"}
        source_url = None

    adapter = create_adapter(series_specs=[Row()])
    assert adapter.provider == "abs"
    series = _run(
        _collect_series(
            adapter, WorldDatasetVersion(provider="abs", dataset_id="CPI")
        )
    )
    assert series[0].title == "CPI All groups"
    assert series[0].dimensions.get("REGION") == "50"


def test_curated_empty_falls_back_to_default_seed():
    # Explicit empty list still gets DEFAULT_ABS_SERIES (constructor contract).
    adapter = AbsDataAdapter(series=[])
    datasets = _run(_collect_datasets(adapter))
    assert datasets[0].dataset_id == "CPI"
