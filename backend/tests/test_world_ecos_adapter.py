"""Unit tests for Bank of Korea ECOS adapter (mocked HTTP; key-gated)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters import ecos_bok
from app.services.world_adapters.ecos_bok import (
    ENV_API_KEY,
    EcosBokAdapter,
    EcosBokError,
    EcosSeriesSpec,
    format_ecos_time,
    parse_ecos_search_payload,
    parse_ecos_time,
    split_item_path,
    statistic_search_url,
)
from app.services.world_national_ingest import AdapterUnavailable
from app.services.world_source_adapter import WorldSeriesRef

ECOS_OK = {
    "StatisticSearch": {
        "list_total_count": 2,
        "row": [
            {
                "STAT_CODE": "722Y001",
                "ITEM_CODE1": "0101000",
                "TIME": "20240701",
                "DATA_VALUE": "3.5",
            },
            {
                "STAT_CODE": "722Y001",
                "ITEM_CODE1": "0101000",
                "TIME": "20240702",
                "DATA_VALUE": "3.5",
            },
        ],
    }
}


def _run(coro):
    return asyncio.run(coro)


def test_helpers_cycle_and_items():
    assert format_ecos_time(date(2024, 7, 2), cycle="D") == "20240702"
    assert format_ecos_time(date(2024, 7, 2), cycle="M") == "202407"
    assert format_ecos_time(date(2024, 4, 1), cycle="Q") == "2024Q2"
    assert parse_ecos_time("2024Q1", cycle="Q") == date(2024, 1, 1)
    assert split_item_path("I61BC/I28B") == ["I61BC", "I28B"]
    url = statistic_search_url(
        api_key="sample",
        stat_code="722Y001",
        cycle="D",
        start_time="20240701",
        end_time="20240710",
        item_codes=["0101000"],
    )
    assert "/StatisticSearch/sample/json/en/1/1000/722Y001/D/" in url


def test_parse_ecos_payload():
    obs = parse_ecos_search_payload(ECOS_OK, cycle="D")
    assert [o.period for o in obs] == [date(2024, 7, 1), date(2024, 7, 2)]
    assert obs[0].value == 3.5


def test_parse_ecos_error_result():
    with pytest.raises(EcosBokError, match="ERROR-301"):
        parse_ecos_search_payload(
            {"RESULT": {"CODE": "ERROR-301", "MESSAGE": "sample cap"}},
            cycle="D",
        )


def test_create_adapter_requires_key(monkeypatch):
    monkeypatch.delenv(ENV_API_KEY, raising=False)
    monkeypatch.delenv("RUSTATS_ECOS_ALLOW_SAMPLE", raising=False)
    with pytest.raises(AdapterUnavailable, match=ENV_API_KEY):
        ecos_bok.create_adapter()


def test_sample_key_rejected_by_default(monkeypatch):
    monkeypatch.setenv(ENV_API_KEY, "sample")
    monkeypatch.delenv("RUSTATS_ECOS_ALLOW_SAMPLE", raising=False)
    with pytest.raises(AdapterUnavailable, match="sample"):
        ecos_bok.create_adapter()


def test_fetch_series_mocked(monkeypatch):
    monkeypatch.setenv(ENV_API_KEY, "real-test-key")
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = ECOS_OK
    response.text = "{}"
    session.get.return_value = response

    adapter = EcosBokAdapter(
        (
            EcosSeriesSpec(
                series_id="0101000",
                dataset_id="722Y001",
                frequency="daily",
                unit_code="PERCENT",
            ),
        ),
        api_key="real-test-key",
        session=session,
    )
    ref = WorldSeriesRef(
        provider="ecos",
        dataset_id="722Y001",
        series_id="0101000",
        country_code="KR",
        frequency="daily",
        unit_code="PERCENT",
    )
    payload = _run(
        adapter.fetch_series(ref, date_from=date(2024, 7, 1), date_to=date(2024, 7, 10))
    )
    assert len(payload.observations) == 2
    assert payload.observations[0].value == 3.5


def test_resolve_ecos_unavailable_without_key(monkeypatch):
    from app.services.world_national_ingest import resolve_adapter

    monkeypatch.delenv(ENV_API_KEY, raising=False)
    with pytest.raises(AdapterUnavailable, match=ENV_API_KEY):
        resolve_adapter("ecos")
