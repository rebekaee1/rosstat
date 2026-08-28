"""Unit tests for ONS time-series JSON adapter (mocked HTTP)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.ons_timeseries import (
    DEFAULT_ONS_SERIES,
    OnsSeriesSpec,
    OnsTimeseriesAdapter,
    OnsTimeseriesError,
    create_adapter,
    normalize_cdid,
    parse_ons_period,
    parse_ons_timeseries_payload,
    timeseries_data_url,
)
from app.services.world_source_adapter import WorldDatasetVersion, WorldSeriesRef


CPI_FIXTURE = {
    "description": {
        "title": "CPI INDEX 00: ALL ITEMS 2015=100",
        "cdid": "D7BT",
        "datasetId": "MM23",
        "unit": "Index, base year = 100",
    },
    "months": [
        {
            "date": "2026 APR",
            "value": "141.0",
            "year": "2026",
            "month": "April",
            "quarter": "",
        },
        {
            "date": "2026 MAY",
            "value": "",
            "year": "2026",
            "month": "May",
            "quarter": "",
        },
        {
            "date": "2026 JUN",
            "value": "142.5",
            "year": "2026",
            "month": "June",
            "quarter": "",
        },
    ],
    "quarters": [],
    "years": [
        {"date": "2025", "value": "138.0", "year": "2025", "month": "", "quarter": ""}
    ],
}

GDP_FIXTURE = {
    "description": {
        "title": "GDP chained volume SA £m",
        "cdid": "ABMI",
        "datasetId": "QNA",
    },
    "months": [],
    "quarters": [
        {
            "date": "2025 Q4",
            "value": "700000",
            "year": "2025",
            "month": "",
            "quarter": "Q4",
        },
        {
            "date": "2026 Q1",
            "value": "709598",
            "year": "2026",
            "month": "",
            "quarter": "Q1",
        },
    ],
    "years": [],
}


def _run(coro):
    return asyncio.run(coro)


async def _collect_datasets(adapter: OnsTimeseriesAdapter) -> list[WorldDatasetVersion]:
    return [item async for item in adapter.list_datasets()]


async def _collect_series(
    adapter: OnsTimeseriesAdapter, dataset: WorldDatasetVersion
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


def test_normalize_and_url_helpers():
    assert normalize_cdid(" d7bt ") == "D7BT"
    with pytest.raises(OnsTimeseriesError):
        normalize_cdid("  ")
    assert timeseries_data_url(
        "economy/inflationandpriceindices/timeseries/d7bt/mm23"
    ) == (
        "https://www.ons.gov.uk/economy/inflationandpriceindices/"
        "timeseries/d7bt/mm23/data"
    )


def test_parse_ons_period_variants():
    assert parse_ons_period(year="2026", month="June") == date(2026, 6, 1)
    assert parse_ons_period(year="2026", quarter="Q1") == date(2026, 1, 1)
    assert parse_ons_period(year="2025") == date(2025, 1, 1)
    assert parse_ons_period(date_token="2026 Q2") == date(2026, 4, 1)
    assert parse_ons_period(date_token="2026 JUN") == date(2026, 6, 1)


def test_parse_timeseries_skips_blank_and_sorts():
    obs = parse_ons_timeseries_payload(
        CPI_FIXTURE, frequency="monthly", series_id="D7BT"
    )
    assert [o.period for o in obs] == [date(2026, 4, 1), date(2026, 6, 1)]
    assert obs[-1].value == 142.5


def test_parse_timeseries_rejects_cdid_mismatch():
    with pytest.raises(OnsTimeseriesError, match="CDID mismatch"):
        parse_ons_timeseries_payload(
            CPI_FIXTURE, frequency="monthly", series_id="L522"
        )


def test_default_constructor_exposes_confirmed_series():
    adapter = OnsTimeseriesAdapter()
    assert adapter.provider == "ons"
    assert adapter.public_source_name == "Office for National Statistics"
    datasets = _run(_collect_datasets(adapter))
    assert {d.dataset_id for d in datasets} == {"MM23"}
    assert DEFAULT_ONS_SERIES[0].series_id == "D7BT"


def test_list_series_for_mm23():
    adapter = OnsTimeseriesAdapter()
    series = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="ons", dataset_id="MM23"),
        )
    )
    assert len(series) == 1
    ref = series[0]
    assert ref.series_id == "D7BT"
    assert ref.country_code == "UK"
    assert ref.frequency == "monthly"
    assert ref.dimensions["uri_path"].endswith("d7bt/mm23")
    assert ref.source_url and ref.source_url.endswith("/data")


def test_fetch_series_mocked():
    session = _mock_session(CPI_FIXTURE)
    adapter = OnsTimeseriesAdapter(session=session)
    ref = WorldSeriesRef(
        provider="ons",
        dataset_id="MM23",
        series_id="D7BT",
        country_code="UK",
        frequency="monthly",
        unit_code="INDEX",
        dimensions={
            "uri_path": "economy/inflationandpriceindices/timeseries/d7bt/mm23"
        },
    )
    payload = _run(adapter.fetch_series(ref))
    assert len(payload.observations) == 2
    assert payload.observations[-1].value == 142.5
    assert payload.source_hash
    session.get.assert_called_once()
    called_url = session.get.call_args.args[0]
    assert called_url.endswith("/d7bt/mm23/data")


def test_fetch_quarterly_gdp_mocked():
    session = _mock_session(GDP_FIXTURE)
    adapter = OnsTimeseriesAdapter(
        [
            OnsSeriesSpec(
                series_id="ABMI",
                dataset_id="QNA",
                uri_path="economy/grossdomesticproductgdp/timeseries/abmi/qna",
                frequency="quarterly",
                unit_code="GBP_MN",
            )
        ],
        session=session,
    )
    ref = WorldSeriesRef(
        provider="ons",
        dataset_id="QNA",
        series_id="ABMI",
        country_code="UK",
        frequency="quarterly",
        unit_code="GBP_MN",
        dimensions={
            "uri_path": "economy/grossdomesticproductgdp/timeseries/abmi/qna"
        },
    )
    payload = _run(adapter.fetch_series(ref))
    assert payload.observations[-1].period == date(2026, 1, 1)
    assert payload.observations[-1].value == 709598.0


def test_fetch_http_error():
    session = _mock_session("nope", status=404)
    adapter = OnsTimeseriesAdapter(session=session)
    ref = WorldSeriesRef(
        provider="ons",
        dataset_id="MM23",
        series_id="D7BT",
        country_code="UK",
        frequency="monthly",
        unit_code="INDEX",
        dimensions={
            "uri_path": "economy/inflationandpriceindices/timeseries/d7bt/mm23"
        },
    )
    with pytest.raises(OnsTimeseriesError, match="HTTP 404"):
        _run(adapter.fetch_series(ref))


def test_create_adapter_from_national_like_rows():
    class Row:
        provider = "ons"
        series_id = "MGSX"
        dataset_id = "LMS"
        frequency = "monthly"
        unit = "PERCENT"
        name_en = "Unemployment rate"
        source_url = None
        dimensions = {
            "uri_path": (
                "employmentandlabourmarket/peoplenotinwork/"
                "unemployment/timeseries/mgsx/lms"
            )
        }

    adapter = create_adapter(series_specs=[Row()])
    datasets = _run(_collect_datasets(adapter))
    assert datasets[0].dataset_id == "LMS"
