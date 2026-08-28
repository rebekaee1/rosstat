"""Unit tests for Banco Central do Brasil SGS adapter (mocked HTTP)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.bcb_sgs import (
    DEFAULT_BCB_SERIES,
    BcbSeriesSpec,
    BcbSgsAdapter,
    BcbSgsError,
    format_br_date,
    normalize_series_id,
    observations_url,
    parse_observation_date,
    parse_sgs_observations,
)
from app.services.world_source_adapter import WorldDatasetVersion, WorldSeriesRef


IPCA_FIXTURE = [
    {"data": "01/05/2026", "valor": "0.58"},
    {"data": "01/07/2026", "valor": "0.07"},
    {"data": "01/06/2026", "valor": "0.16"},
    {"data": "01/04/2026", "valor": ""},
]

FX_FIXTURE = [
    {"data": "10/08/2026", "valor": "5.0963"},
    {"data": "11/08/2026", "valor": "5.1285"},
]


def _run(coro):
    return asyncio.run(coro)


async def _collect_datasets(adapter: BcbSgsAdapter) -> list[WorldDatasetVersion]:
    return [item async for item in adapter.list_datasets()]


async def _collect_series(
    adapter: BcbSgsAdapter, dataset: WorldDatasetVersion
) -> list[WorldSeriesRef]:
    return [item async for item in adapter.list_series(dataset)]


def test_normalize_and_url_helpers():
    assert normalize_series_id(" 433 ") == "433"
    with pytest.raises(BcbSgsError):
        normalize_series_id("  ")
    with pytest.raises(BcbSgsError):
        normalize_series_id("FXUSDBRL")
    assert observations_url("433") == (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados"
    )
    assert parse_observation_date("11/08/2026") == date(2026, 8, 11)
    assert format_br_date(date(2024, 1, 15)) == "15/01/2024"


def test_parse_sgs_observations_sorts_and_skips_blank():
    obs = parse_sgs_observations(IPCA_FIXTURE)
    assert [o.period for o in obs] == [
        date(2026, 5, 1),
        date(2026, 6, 1),
        date(2026, 7, 1),
    ]
    assert obs[0].value == 0.58
    assert obs[-1].value == 0.07


def test_parse_sgs_observations_rejects_empty_numeric():
    with pytest.raises(BcbSgsError, match="no numeric"):
        parse_sgs_observations([{"data": "01/05/2026", "valor": ""}])


def test_default_constructor_exposes_confirmed_series():
    adapter = BcbSgsAdapter()
    assert adapter.provider == "bcb_sgs"
    assert adapter.public_source_name == "Banco Central do Brasil"
    datasets = _run(_collect_datasets(adapter))
    ids = {d.dataset_id for d in datasets}
    assert {"433", "432", "1", "24369", "22109"}.issubset(ids)
    assert {s.series_id for s in DEFAULT_BCB_SERIES} >= {"433", "1", "432"}


def test_list_series_for_selic_dataset():
    adapter = BcbSgsAdapter()
    series = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="bcb_sgs", dataset_id="432"),
        )
    )
    assert len(series) == 1
    ref = series[0]
    assert ref.provider == "bcb_sgs"
    assert ref.series_id == "432"
    assert ref.country_code == "BR"
    assert ref.frequency == "daily"
    assert ref.unit_code == "PERCENT"


def test_fetch_series_recent_parses_values():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = IPCA_FIXTURE
    response.text = "[]"
    session.get.return_value = response

    adapter = BcbSgsAdapter(session=session, recent_n=100)
    ref = WorldSeriesRef(
        provider="bcb_sgs",
        dataset_id="433",
        series_id="433",
        country_code="BR",
        frequency="monthly",
        unit_code="PERCENT",
    )
    payload = _run(adapter.fetch_series(ref))
    assert len(payload.observations) == 3
    assert payload.observations[-1].value == 0.07
    assert payload.source_hash
    assert payload.revision_token and payload.revision_token.startswith("2026-05-01/")

    session.get.assert_called_once()
    args, kwargs = session.get.call_args
    assert args[0].endswith("/bcdata.sgs.433/dados")
    assert "/ultimos/" not in args[0]
    assert kwargs["params"]["formato"] == "json"
    assert "dataInicial" in kwargs["params"]
    assert "dataFinal" in kwargs["params"]


def test_fetch_series_date_window_uses_br_params():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = FX_FIXTURE
    response.text = "[]"
    session.get.return_value = response

    adapter = BcbSgsAdapter(session=session)
    ref = WorldSeriesRef(
        provider="bcb_sgs",
        dataset_id="1",
        series_id="1",
        country_code="BR",
        frequency="daily",
        unit_code="BRL",
    )
    payload = _run(
        adapter.fetch_series(
            ref,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 11),
        )
    )
    assert [o.value for o in payload.observations] == [5.0963, 5.1285]
    args, kwargs = session.get.call_args
    assert args[0].endswith("/bcdata.sgs.1/dados")
    assert kwargs["params"] == {
        "formato": "json",
        "dataInicial": "01/08/2026",
        "dataFinal": "11/08/2026",
    }


def test_fetch_series_rejects_provider_mismatch():
    adapter = BcbSgsAdapter()
    ref = WorldSeriesRef(
        provider="banxico_sie",
        dataset_id="433",
        series_id="433",
        country_code="BR",
        frequency="monthly",
        unit_code="PERCENT",
    )
    with pytest.raises(BcbSgsError, match="Provider mismatch"):
        _run(adapter.fetch_series(ref))


def test_empty_curated_catalog_rejected():
    with pytest.raises(BcbSgsError, match="at least one"):
        BcbSgsAdapter(series=())


def test_create_adapter_from_yaml_like_specs():
    from app.services.world_adapters.bcb_sgs import create_adapter

    adapter = create_adapter(
        [
            BcbSeriesSpec(series_id="432", title="Selic", unit_code="PERCENT", frequency="daily"),
        ]
    )
    assert adapter.provider == "bcb_sgs"
    datasets = _run(_collect_datasets(adapter))
    assert [d.dataset_id for d in datasets] == ["432"]
