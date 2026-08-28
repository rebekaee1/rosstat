"""Unit tests for Banco de México SIE adapter (mocked HTTP)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.banxico_sie import (
    DEFAULT_BANXICO_SERIES,
    BanxicoSeriesSpec,
    BanxicoSieAdapter,
    BanxicoSieError,
    normalize_series_id,
    observations_oportuno_url,
    observations_range_url,
    parse_observation_date,
    parse_sie_observations,
)
from app.services.world_source_adapter import WorldDatasetVersion, WorldSeriesRef


SP1_FIXTURE = {
    "bmx": {
        "series": [
            {
                "idSerie": "SP1",
                "titulo": "Índice Nacional de Precios al Consumidor",
                "datos": [
                    {"fecha": "01/05/2026", "dato": "145.527"},
                    {"fecha": "01/06/2026", "dato": "145.131"},
                    {"fecha": "01/04/2026", "dato": "N/E"},
                ],
            }
        ]
    }
}

FX_FIXTURE = {
    "bmx": {
        "series": [
            {
                "idSerie": "SF43718",
                "titulo": "Tipo de cambio Pesos por dólar FIX",
                "datos": [
                    {"fecha": "10/08/2026", "dato": "18.5123"},
                    {"fecha": "11/08/2026", "dato": "18.4801"},
                ],
            }
        ]
    }
}


def _run(coro):
    return asyncio.run(coro)


async def _collect_datasets(adapter: BanxicoSieAdapter) -> list[WorldDatasetVersion]:
    return [item async for item in adapter.list_datasets()]


async def _collect_series(
    adapter: BanxicoSieAdapter, dataset: WorldDatasetVersion
) -> list[WorldSeriesRef]:
    return [item async for item in adapter.list_series(dataset)]


def test_normalize_and_url_helpers():
    assert normalize_series_id(" sp1 ") == "SP1"
    with pytest.raises(BanxicoSieError):
        normalize_series_id("  ")
    assert observations_oportuno_url("SF43718").endswith(
        "/series/SF43718/datos/oportuno"
    )
    assert observations_range_url(
        "SF61745", date(2024, 1, 1), date(2024, 1, 31)
    ).endswith("/series/SF61745/datos/2024-01-01/2024-01-31")
    assert parse_observation_date("11/08/2026") == date(2026, 8, 11)


def test_parse_sie_observations_sorts_and_skips_missing():
    obs = parse_sie_observations(SP1_FIXTURE, series_id="SP1")
    assert [o.period for o in obs] == [date(2026, 5, 1), date(2026, 6, 1)]
    assert obs[0].value == 145.527
    assert obs[-1].value == 145.131


def test_parse_sie_observations_rejects_empty_numeric():
    with pytest.raises(BanxicoSieError, match="no numeric"):
        parse_sie_observations(
            {
                "bmx": {
                    "series": [
                        {
                            "idSerie": "SP1",
                            "datos": [{"fecha": "01/05/2026", "dato": "N/E"}],
                        }
                    ]
                }
            },
            series_id="SP1",
        )


def test_default_constructor_exposes_confirmed_series():
    adapter = BanxicoSieAdapter(token="x" * 64)
    assert adapter.provider == "banxico_sie"
    assert adapter.public_source_name == "Banco de México"
    datasets = _run(_collect_datasets(adapter))
    ids = {d.dataset_id for d in datasets}
    # SR17493 (база 2018) сменил SR16620 в наборе; состав сверён с БД (7 рядов).
    assert {"SP1", "SL1", "SF61745", "SF43718", "SF60648", "SF43707", "SR17493"} == ids
    assert {s.series_id for s in DEFAULT_BANXICO_SERIES} >= {"SP1", "SF43718"}


def test_list_series_for_policy_rate():
    adapter = BanxicoSieAdapter(token="demo")
    series = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="banxico_sie", dataset_id="SF61745"),
        )
    )
    assert len(series) == 1
    ref = series[0]
    assert ref.series_id == "SF61745"
    assert ref.country_code == "MX"
    assert ref.frequency == "daily"
    assert ref.unit_code == "PERCENT"


def test_fetch_series_requires_token():
    adapter = BanxicoSieAdapter(token="")
    ref = WorldSeriesRef(
        provider="banxico_sie",
        dataset_id="SP1",
        series_id="SP1",
        country_code="MX",
        frequency="monthly",
        unit_code="INDEX",
    )
    with pytest.raises(BanxicoSieError, match="BANXICO_API_TOKEN"):
        _run(adapter.fetch_series(ref))


def test_fetch_series_range_parses_nested_values():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = SP1_FIXTURE
    response.text = "{}"
    session.get.return_value = response

    adapter = BanxicoSieAdapter(session=session, token="tok123")
    ref = WorldSeriesRef(
        provider="banxico_sie",
        dataset_id="SP1",
        series_id="SP1",
        country_code="MX",
        frequency="monthly",
        unit_code="INDEX",
    )
    payload = _run(
        adapter.fetch_series(
            ref,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 6, 30),
        )
    )
    assert len(payload.observations) == 2
    assert payload.observations[-1].value == 145.131
    assert payload.ref.title and "Precios" in payload.ref.title
    args, kwargs = session.get.call_args
    assert "/series/SP1/datos/2026-01-01/2026-06-30" in args[0]
    assert kwargs["headers"]["Bmx-Token"] == "tok123"
    # Token must stay in header only (never query — leaks into error URLs).
    assert kwargs["headers"]["Bmx-Token"] == "tok123"
    assert not (kwargs.get("params") or {}).get("token")


def test_fetch_series_full_history_uses_wide_window():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = FX_FIXTURE
    response.text = "{}"
    session.get.return_value = response

    adapter = BanxicoSieAdapter(session=session, token="tok")
    ref = WorldSeriesRef(
        provider="banxico_sie",
        dataset_id="SF43718",
        series_id="SF43718",
        country_code="MX",
        frequency="daily",
        unit_code="MXN",
    )
    payload = _run(adapter.fetch_series(ref))
    assert [o.value for o in payload.observations] == [18.5123, 18.4801]
    args, _kwargs = session.get.call_args
    assert "/series/SF43718/datos/1960-01-01/" in args[0]


def test_fetch_series_rejects_provider_mismatch():
    adapter = BanxicoSieAdapter(token="tok")
    ref = WorldSeriesRef(
        provider="bcb_sgs",
        dataset_id="SP1",
        series_id="SP1",
        country_code="MX",
        frequency="monthly",
        unit_code="INDEX",
    )
    with pytest.raises(BanxicoSieError, match="Provider mismatch"):
        _run(adapter.fetch_series(ref))


def test_empty_curated_catalog_rejected():
    with pytest.raises(BanxicoSieError, match="at least one"):
        BanxicoSieAdapter(series=(), token="tok")


def test_create_adapter_from_specs():
    from app.services.world_adapters.banxico_sie import create_adapter

    adapter = create_adapter(
        [
            BanxicoSeriesSpec(
                series_id="SF61745",
                title="Target rate",
                unit_code="PERCENT",
                frequency="daily",
            ),
        ]
    )
    assert adapter.provider == "banxico_sie"
    datasets = _run(_collect_datasets(adapter))
    assert [d.dataset_id for d in datasets] == ["SF61745"]
