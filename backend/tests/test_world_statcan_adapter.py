"""Unit tests for Statistics Canada WDS adapter (mocked HTTP)."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.statcan_wds import (
    FREQUENCY_CODE_MAP,
    StatCanCubeSpec,
    StatCanVectorSpec,
    StatCanWdsAdapter,
    StatCanWdsError,
    map_frequency_code,
    normalize_vector_id,
    parse_ref_period,
    parse_vector_data_points,
)
from app.services.world_source_adapter import WorldSeriesRef


CUBE_META_FIXTURE = [
    {
        "status": "SUCCESS",
        "object": {
            "responseStatusCode": 0,
            "productId": 17100009,
            "cansimId": "051-0005",
            "cubeTitleEn": "Population estimates, quarterly",
            "cubeTitleFr": "Estimations de la population, trimestrielles",
            "cubeStartDate": "1971-01-01",
            "cubeEndDate": "2026-01-01",
            "frequencyCode": 9,
            "nbSeriesCube": 15,
            "nbDatapointsCube": 3000,
            "releaseTime": "2026-06-17T08:30",
            "archiveStatusCode": "2",
            "issueDate": "2021-04-13",
        },
    }
]

PERIOD_RANGE_FIXTURE = [
    {
        "status": "SUCCESS",
        "object": {
            "responseStatusCode": 0,
            "productId": 17100009,
            "coordinate": "1.0.0.0.0.0.0.0.0.0",
            "vectorId": 1,
            "vectorDataPoint": [
                {
                    "refPer": "2016-01-01",
                    "refPer2": "",
                    "refPerRaw": "2016-01-01",
                    "refPerRaw2": "",
                    "value": 35871136,
                    "decimals": 0,
                    "scalarFactorCode": 0,
                    "symbolCode": 0,
                    "statusCode": 0,
                    "securityLevelCode": 0,
                    "releaseTime": "2020-09-29T08:30",
                    "frequencyCode": 9,
                },
                {
                    "refPer": "2016-04-01",
                    "refPer2": "",
                    "refPerRaw": "2016-04-01",
                    "refPerRaw2": "",
                    "value": 35970303,
                    "decimals": 0,
                    "scalarFactorCode": 0,
                    "symbolCode": 0,
                    "statusCode": 0,
                    "securityLevelCode": 0,
                    "releaseTime": "2020-09-29T08:30",
                    "frequencyCode": 9,
                },
            ],
        },
    }
]

LATEST_N_FIXTURE = [
    {
        "status": "SUCCESS",
        "object": {
            "responseStatusCode": 0,
            "productId": 34100006,
            "coordinate": "1.2.7.0.0.0.0.0.0.0",
            "vectorId": 42076,
            "vectorDataPoint": [
                {
                    "refPer": "2017-07-01",
                    "refPer2": "",
                    "refPerRaw": "2017-01-01",
                    "refPerRaw2": "",
                    "value": "18381",
                    "decimals": 0,
                    "scalarFactorCode": 0,
                    "symbolCode": 0,
                    "statusCode": 0,
                    "securityLevelCode": 0,
                    "releaseTime": "2017-12-07T08:30",
                    "frequencyCode": 6,
                },
                {
                    "refPer": "2017-08-01",
                    "refPer2": "",
                    "refPerRaw": "2017-08-01",
                    "refPerRaw2": "",
                    "value": 18400.5,
                    "decimals": 1,
                    "scalarFactorCode": 0,
                    "symbolCode": 0,
                    "statusCode": 0,
                    "securityLevelCode": 0,
                    "releaseTime": "2018-01-07T08:30",
                    "frequencyCode": 6,
                },
            ],
        },
    }
]


def _run(coro):
    return asyncio.run(coro)


async def _collect(async_iter):
    return [item async for item in async_iter]


def _adapter(**kwargs) -> StatCanWdsAdapter:
    cubes = kwargs.pop(
        "cubes",
        [
            StatCanCubeSpec(
                product_id=17100009,
                title="Population estimates, quarterly",
                revision_token="seeded",
                data_updated_at=date(2026, 6, 17),
                vectors=(
                    StatCanVectorSpec(
                        vector_id=1,
                        title="Canada; Population estimate",
                        unit_code="PERSONS",
                        frequency_code=9,
                        coordinate="1.0.0.0.0.0.0.0.0.0",
                    ),
                    StatCanVectorSpec(
                        vector_id="v42076",
                        title="Monthly sample vector",
                        unit_code="INDEX",
                        frequency="monthly",
                    ),
                ),
            )
        ],
    )
    session = kwargs.pop("session", MagicMock())
    return StatCanWdsAdapter(cubes, session=session, fetch_cube_metadata=False, **kwargs)


def test_frequency_code_map_matches_wds_appendix():
    assert map_frequency_code(1) == "daily"
    assert map_frequency_code(2) == "weekly"
    assert map_frequency_code(6) == "monthly"
    assert map_frequency_code(9) == "quarterly"
    assert map_frequency_code(12) == "annual"
    assert FREQUENCY_CODE_MAP[2] == "weekly"


def test_normalize_vector_strips_v_prefix():
    assert normalize_vector_id("v42076") == "42076"
    assert normalize_vector_id(42076) == "42076"


def test_parse_ref_period_variants():
    assert parse_ref_period("2016-04-01") == date(2016, 4, 1)
    assert parse_ref_period("2016-04") == date(2016, 4, 1)
    assert parse_ref_period("2016") == date(2016, 1, 1)


def test_parse_vector_data_points_skips_null_values():
    points = [
        {
            "refPer": "2016-01-01",
            "value": None,
            "decimals": 0,
            "statusCode": 0,
        },
        {
            "refPer": "2016-04-01",
            "value": 10,
            "decimals": 0,
            "statusCode": 0,
        },
    ]
    obs = parse_vector_data_points(points)
    assert len(obs) == 1
    assert obs[0].value == 10.0


def test_parse_vector_data_points_rejects_empty():
    with pytest.raises(StatCanWdsError, match="empty"):
        parse_vector_data_points([])


def test_list_datasets_from_curated_without_http():
    adapter = _adapter()
    datasets = _run(_collect(adapter.list_datasets()))
    assert len(datasets) == 1
    assert datasets[0].provider == "statcan"
    assert datasets[0].dataset_id == "17100009"
    assert datasets[0].title == "Population estimates, quarterly"
    assert datasets[0].revision_token == "seeded"


def test_list_datasets_fetches_cube_metadata():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = "ok"
    response.json.return_value = CUBE_META_FIXTURE
    session.post.return_value = response

    adapter = StatCanWdsAdapter(
        [
            StatCanCubeSpec(
                product_id="17100009",
                vectors=(
                    StatCanVectorSpec(vector_id=1, frequency_code=9, unit_code="PERSONS"),
                ),
            )
        ],
        session=session,
        fetch_cube_metadata=True,
    )
    datasets = _run(_collect(adapter.list_datasets()))
    assert datasets[0].title == "Population estimates, quarterly"
    assert datasets[0].revision_token == "2026-06-17T08:30"
    assert isinstance(datasets[0].data_updated_at, datetime)
    session.post.assert_called_once()
    args, kwargs = session.post.call_args
    assert args[0].endswith("/getCubeMetadata")
    assert kwargs["json"] == [{"productId": 17100009}]


def test_list_series_yields_world_series_refs():
    adapter = _adapter()
    dataset = _run(_collect(adapter.list_datasets()))[0]
    series = _run(_collect(adapter.list_series(dataset)))
    assert len(series) == 2
    assert series[0].provider == "statcan"
    assert series[0].series_id == "1"
    assert series[0].country_code == "CA"
    assert series[0].frequency == "quarterly"
    assert series[0].unit_code == "PERSONS"
    assert series[0].dimensions["coordinate"] == "1.0.0.0.0.0.0.0.0.0"
    assert series[1].series_id == "42076"
    assert series[1].frequency == "monthly"
    assert adapter.public_source_name == "Statistics Canada"


def test_fetch_series_period_range_uses_get():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = "ok"
    response.json.return_value = PERIOD_RANGE_FIXTURE
    session.get.return_value = response

    adapter = _adapter(session=session)
    series = WorldSeriesRef(
        provider="statcan",
        dataset_id="17100009",
        series_id="1",
        country_code="CA",
        frequency="quarterly",
        unit_code="PERSONS",
    )
    payload = _run(
        adapter.fetch_series(
            series,
            date_from=date(2016, 1, 1),
            date_to=date(2016, 4, 1),
        )
    )
    assert len(payload.observations) == 2
    assert payload.observations[0].period == date(2016, 1, 1)
    assert payload.observations[0].value == 35871136.0
    assert payload.observations[1].period == date(2016, 4, 1)
    assert payload.revision_token == "2020-09-29T08:30"
    assert payload.source_hash
    session.get.assert_called_once()
    args, kwargs = session.get.call_args
    assert args[0].endswith("/getDataFromVectorByReferencePeriodRange")
    assert kwargs["params"]["vectorIds"] == '"1"'
    assert kwargs["params"]["startRefPeriod"] == "2016-01-01"
    assert kwargs["params"]["endReferencePeriod"] == "2016-04-01"
    session.post.assert_not_called()


def test_fetch_series_without_dates_uses_latest_n_post():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = "ok"
    response.json.return_value = LATEST_N_FIXTURE
    session.post.return_value = response

    adapter = _adapter(session=session, latest_n=500)
    series = WorldSeriesRef(
        provider="statcan",
        dataset_id="34100006",
        series_id="42076",
        country_code="CA",
        frequency="monthly",
        unit_code="INDEX",
    )
    payload = _run(adapter.fetch_series(series))
    assert [obs.period for obs in payload.observations] == [
        date(2017, 7, 1),
        date(2017, 8, 1),
    ]
    assert payload.observations[1].value == 18400.5
    assert payload.observations[1].decimals == 1
    session.post.assert_called_once()
    args, kwargs = session.post.call_args
    assert args[0].endswith("/getDataFromVectorsAndLatestNPeriods")
    assert kwargs["json"] == [{"vectorId": 42076, "latestN": 500}]


def test_fetch_series_failed_status_raises():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = "ok"
    response.json.return_value = [
        {"status": "FAILED", "object": {"responseStatusCode": 1}}
    ]
    session.post.return_value = response
    adapter = _adapter(session=session)
    series = WorldSeriesRef(
        provider="statcan",
        dataset_id="17100009",
        series_id="1",
        country_code="CA",
        frequency="quarterly",
        unit_code="PERSONS",
    )
    with pytest.raises(StatCanWdsError, match="FAILED"):
        _run(adapter.fetch_series(series))


def test_fetch_series_empty_points_raises():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = "ok"
    response.json.return_value = [
        {
            "status": "SUCCESS",
            "object": {
                "responseStatusCode": 0,
                "vectorId": 1,
                "vectorDataPoint": [],
            },
        }
    ]
    session.post.return_value = response
    adapter = _adapter(session=session)
    series = WorldSeriesRef(
        provider="statcan",
        dataset_id="17100009",
        series_id="1",
        country_code="CA",
        frequency="quarterly",
        unit_code="PERSONS",
    )
    with pytest.raises(StatCanWdsError, match="empty"):
        _run(adapter.fetch_series(series))


def test_adapter_requires_cubes():
    with pytest.raises(StatCanWdsError, match="at least one"):
        StatCanWdsAdapter([])
