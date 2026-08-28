"""Unit tests for Bank of Canada Valet adapter (mocked HTTP)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.boc_valet import (
    DEFAULT_BOC_SERIES,
    BocSeriesSpec,
    BocValetAdapter,
    BocValetError,
    normalize_series_id,
    observations_url,
    parse_observation_date,
    parse_valet_observations,
)
from app.services.world_source_adapter import WorldDatasetVersion, WorldSeriesRef


V39079_FIXTURE = {
    "terms": {"url": "https://www.bankofcanada.ca/terms/"},
    "seriesDetail": {
        "V39079": {
            "label": "Target for the overnight rate (business daily)",
            "description": "Also called the policy interest rate.",
            "dimension": {"key": "d", "name": "Date"},
        }
    },
    "observations": [
        {"d": "2026-08-10", "V39079": {"v": "2.25"}},
        {"d": "2026-08-07", "V39079": {"v": "2.25"}},
        {"d": "2026-08-06", "V39079": {"v": "2.50"}},
        # Blank holiday / unpublished cell — skip.
        {"d": "2026-08-05", "V39079": {"v": ""}},
    ],
}

FXUSDCAD_FIXTURE = {
    "terms": {"url": "https://www.bankofcanada.ca/terms/"},
    "seriesDetail": {
        "FXUSDCAD": {
            "label": "USD/CAD",
            "description": "Daily average exchange rate",
            "dimension": {"key": "d", "name": "Date"},
        }
    },
    "observations": [
        {"d": "2026-08-11", "FXUSDCAD": {"v": "1.3927"}},
        {"d": "2026-08-10", "FXUSDCAD": {"v": "1.3942"}},
    ],
}


def _run(coro):
    return asyncio.run(coro)


def _adapter_with_session(session: MagicMock, **kwargs) -> BocValetAdapter:
    return BocValetAdapter(session=session, **kwargs)


async def _collect_datasets(adapter: BocValetAdapter) -> list[WorldDatasetVersion]:
    return [item async for item in adapter.list_datasets()]


async def _collect_series(
    adapter: BocValetAdapter, dataset: WorldDatasetVersion
) -> list[WorldSeriesRef]:
    return [item async for item in adapter.list_series(dataset)]


def test_normalize_and_url_helpers():
    assert normalize_series_id(" V39079 ") == "V39079"
    with pytest.raises(BocValetError):
        normalize_series_id("  ")
    assert observations_url("FXUSDCAD") == (
        "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json"
    )
    assert parse_observation_date("2026-08-10") == date(2026, 8, 10)


def test_parse_valet_observations_sorts_and_skips_blank():
    obs = parse_valet_observations(V39079_FIXTURE, series_id="V39079")
    assert [o.period for o in obs] == [
        date(2026, 8, 6),
        date(2026, 8, 7),
        date(2026, 8, 10),
    ]
    assert obs[0].value == 2.50
    assert obs[-1].value == 2.25


def test_parse_valet_observations_rejects_empty_numeric():
    with pytest.raises(BocValetError, match="no numeric"):
        parse_valet_observations(
            {
                "observations": [
                    {"d": "2026-08-05", "V39079": {"v": ""}},
                ]
            },
            series_id="V39079",
        )


def test_default_constructor_exposes_confirmed_series():
    adapter = BocValetAdapter()
    assert adapter.provider == "boc_valet"
    assert adapter.public_source_name == "Bank of Canada"
    datasets = _run(_collect_datasets(adapter))
    ids = {d.dataset_id for d in datasets}
    assert "V39079" in ids
    assert "FX_RATES_DAILY" in ids
    assert {s.series_id for s in DEFAULT_BOC_SERIES} == {"V39079", "FXUSDCAD"}


def test_list_series_for_overnight_dataset():
    adapter = BocValetAdapter()
    series = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="boc_valet", dataset_id="V39079"),
        )
    )
    assert len(series) == 1
    ref = series[0]
    assert ref.provider == "boc_valet"
    assert ref.series_id == "V39079"
    assert ref.country_code == "CA"
    assert ref.frequency == "daily"
    assert ref.unit_code == "PERCENT"
    assert ref.source_url and ref.source_url.endswith("/observations/V39079/json")


def test_list_series_for_fx_group_dataset():
    adapter = BocValetAdapter()
    series = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="boc_valet", dataset_id="FX_RATES_DAILY"),
        )
    )
    assert len(series) == 1
    assert series[0].series_id == "FXUSDCAD"
    assert series[0].dataset_id == "FX_RATES_DAILY"
    assert series[0].country_code == "CA"
    assert series[0].frequency == "daily"


def test_curated_group_dataset_id_lists_member_series():
    """dataset_id may be a Valet group; series_id stays the series name."""
    adapter = BocValetAdapter(
        series=(
            BocSeriesSpec(
                series_id="FXUSDCAD",
                dataset_id="FX_RATES_DAILY",
                title="USD/CAD",
                unit_code="CAD",
                frequency="daily",
            ),
            BocSeriesSpec(
                series_id="FXEURCAD",
                dataset_id="FX_RATES_DAILY",
                title="EUR/CAD",
                unit_code="CAD",
                frequency="daily",
            ),
        )
    )
    datasets = _run(_collect_datasets(adapter))
    assert [d.dataset_id for d in datasets] == ["FX_RATES_DAILY"]
    series = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="boc_valet", dataset_id="FX_RATES_DAILY"),
        )
    )
    assert [s.series_id for s in series] == ["FXUSDCAD", "FXEURCAD"]
    assert all(s.dataset_id == "FX_RATES_DAILY" for s in series)
    assert all(s.country_code == "CA" for s in series)


def test_fetch_series_recent_parses_nested_values():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = V39079_FIXTURE
    response.text = "{}"
    session.get.return_value = response

    adapter = _adapter_with_session(session, recent_n=100)
    ref = WorldSeriesRef(
        provider="boc_valet",
        dataset_id="V39079",
        series_id="V39079",
        country_code="CA",
        frequency="daily",
        unit_code="PERCENT",
    )
    payload = _run(adapter.fetch_series(ref))
    assert payload.ref.provider == "boc_valet"
    assert len(payload.observations) == 3
    assert payload.observations[0].period == date(2026, 8, 6)
    assert payload.observations[-1].value == 2.25
    assert payload.source_hash
    assert payload.revision_token and payload.revision_token.startswith("2026-08-06/")
    assert payload.ref.title and "overnight" in payload.ref.title.lower()

    session.get.assert_called_once()
    args, kwargs = session.get.call_args
    assert args[0].endswith("/observations/V39079/json")
    assert kwargs["params"] == {"recent": "100"}


def test_fetch_series_date_window_uses_start_end_params():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = FXUSDCAD_FIXTURE
    response.text = "{}"
    session.get.return_value = response

    adapter = _adapter_with_session(session)
    ref = WorldSeriesRef(
        provider="boc_valet",
        dataset_id="FX_RATES_DAILY",
        series_id="FXUSDCAD",
        country_code="CA",
        frequency="daily",
        unit_code="CAD",
        title="USD/CAD",
    )
    payload = _run(
        adapter.fetch_series(
            ref,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 11),
        )
    )
    assert [o.value for o in payload.observations] == [1.3942, 1.3927]
    args, kwargs = session.get.call_args
    assert args[0].endswith("/observations/FXUSDCAD/json")
    assert kwargs["params"] == {
        "start_date": "2026-08-01",
        "end_date": "2026-08-11",
    }


def test_fetch_series_rejects_provider_mismatch():
    adapter = BocValetAdapter()
    ref = WorldSeriesRef(
        provider="statcan",
        dataset_id="V39079",
        series_id="V39079",
        country_code="CA",
        frequency="daily",
        unit_code="PERCENT",
    )
    with pytest.raises(BocValetError, match="Provider mismatch"):
        _run(adapter.fetch_series(ref))


def test_fetch_series_propagates_valet_error_message():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "message": "Series not found.",
        "docs": "https://www.bankofcanada.ca/valet/docs",
    }
    response.text = "{}"
    session.get.return_value = response

    adapter = _adapter_with_session(session)
    ref = WorldSeriesRef(
        provider="boc_valet",
        dataset_id="NOPE",
        series_id="NOPE",
        country_code="CA",
        frequency="daily",
        unit_code="UNIT",
    )
    with pytest.raises(BocValetError, match="Series not found"):
        _run(adapter.fetch_series(ref))


def test_empty_curated_catalog_rejected():
    with pytest.raises(BocValetError, match="at least one"):
        BocValetAdapter(series=())
