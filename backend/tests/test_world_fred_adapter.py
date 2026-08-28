"""Unit tests for FRED St. Louis Fed adapter (mocked HTTP)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.fred_stlouis import (
    DEFAULT_FRED_SERIES,
    FredSeriesSpec,
    FredStLouisAdapter,
    FredStLouisError,
    graph_csv_url,
    normalize_series_id,
    parse_fred_api_observations,
    parse_fred_csv,
    parse_observation_date,
    series_page_url,
)
from app.services.world_source_adapter import WorldDatasetVersion, WorldSeriesRef

CPI_CSV = """\
observation_date,CPIAUCSL
2024-01-01,308.417
2024-02-01,310.326
2024-03-01,.
2024-04-01,313.207
"""

DFF_CSV = """\
observation_date,DFF
2026-08-08,3.63
2026-08-09,3.63
2026-08-10,3.63
"""

FRED_API_FIXTURE = {
    "observations": [
        {"date": "2024-01-01", "value": "308.417"},
        {"date": "2024-02-01", "value": "."},
        {"date": "2024-03-01", "value": "310.326"},
    ]
}


def _run(coro):
    return asyncio.run(coro)


def _adapter_with_session(session: MagicMock, **kwargs) -> FredStLouisAdapter:
    return FredStLouisAdapter(session=session, **kwargs)


async def _collect_datasets(adapter: FredStLouisAdapter) -> list[WorldDatasetVersion]:
    return [item async for item in adapter.list_datasets()]


async def _collect_series(
    adapter: FredStLouisAdapter, dataset: WorldDatasetVersion
) -> list[WorldSeriesRef]:
    return [item async for item in adapter.list_series(dataset)]


def test_normalize_and_url_helpers():
    assert normalize_series_id(" cpiaucsl ") == "CPIAUCSL"
    with pytest.raises(FredStLouisError):
        normalize_series_id("  ")
    assert series_page_url("UNRATE") == "https://fred.stlouisfed.org/series/UNRATE"
    assert graph_csv_url("DFF").endswith("id=DFF")
    assert parse_observation_date("2026-08-10") == date(2026, 8, 10)


def test_parse_fred_csv_skips_dot_and_sorts():
    obs = parse_fred_csv(CPI_CSV, series_id="CPIAUCSL")
    assert [o.period for o in obs] == [
        date(2024, 1, 1),
        date(2024, 2, 1),
        date(2024, 4, 1),
    ]
    assert obs[0].value == 308.417
    assert obs[-1].value == 313.207


def test_parse_fred_csv_date_window():
    obs = parse_fred_csv(
        CPI_CSV,
        series_id="CPIAUCSL",
        date_from=date(2024, 2, 1),
        date_to=date(2024, 2, 28),
    )
    assert len(obs) == 1
    assert obs[0].period == date(2024, 2, 1)


def test_parse_fred_api_observations():
    obs = parse_fred_api_observations(FRED_API_FIXTURE, series_id="CPIAUCSL")
    assert [o.value for o in obs] == [308.417, 310.326]


def test_default_constructor_exposes_passport_series():
    adapter = FredStLouisAdapter()
    assert adapter.provider == "fred"
    assert adapter.public_source_name == "Federal Reserve Bank of St. Louis"
    datasets = _run(_collect_datasets(adapter))
    ids = {d.dataset_id for d in datasets}
    assert "CPIAUCSL" in ids
    assert "FEDFUNDS" in ids
    assert "GDPC1" in ids
    series_ids = {s.series_id for s in DEFAULT_FRED_SERIES}
    assert {"CPIAUCSL", "UNRATE", "PAYEMS", "GDPC1", "RSAFS", "FEDFUNDS", "DTWEXBGS", "DEXUSEU", "INDPRO"} <= series_ids


def test_list_series_and_fetch_csv_mocked():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = DFF_CSV
    session.get.return_value = response

    adapter = _adapter_with_session(
        session,
        series=(
            FredSeriesSpec(
                series_id="FEDFUNDS",
                title="Federal Funds Effective Rate",
                unit_code="PERCENT",
                frequency="monthly",
            ),
        ),
    )
    datasets = _run(_collect_datasets(adapter))
    refs = _run(_collect_series(adapter, datasets[0]))
    assert refs[0].series_id == "FEDFUNDS"
    assert refs[0].country_code == "US"
    assert refs[0].frequency == "monthly"

    # Reuse DFF_CSV fixture text with FEDFUNDS header for parse path via HTTP mock.
    response.text = "observation_date,FEDFUNDS\n2026-05-01,4.33\n2026-06-01,4.33\n2026-07-01,3.63\n"
    payload = _run(adapter.fetch_series(refs[0]))
    assert len(payload.observations) == 3
    assert payload.observations[-1].value == 3.63
    assert payload.observations[-1].period == date(2026, 7, 1)
    assert payload.source_hash


def test_prefer_api_without_key_raises_unavailable():
    from app.services.world_national_ingest import AdapterUnavailable

    adapter = FredStLouisAdapter(
        series=(FredSeriesSpec(series_id="FEDFUNDS"),),
        prefer_api=True,
        api_key=None,
    )
    # prefer_api is only True when key present; force path via _prefer_api
    adapter._prefer_api = True
    adapter._api_key = None
    ref = WorldSeriesRef(
        provider="fred",
        dataset_id="FEDFUNDS",
        series_id="FEDFUNDS",
        country_code="US",
        frequency="monthly",
        unit_code="PERCENT",
    )
    with pytest.raises(AdapterUnavailable, match="RUSTATS_FRED_API_KEY"):
        _run(adapter.fetch_series(ref))


def test_create_adapter_from_national_specs():
    from app.services.world_adapters.fred_stlouis import create_adapter
    from app.services.world_national_ingest import load_national_core_yaml

    manifest = load_national_core_yaml("us")
    adapter = create_adapter(series_specs=manifest.series)
    assert adapter.provider == "fred"
    datasets = _run(_collect_datasets(adapter))
    assert len(datasets) >= 6
