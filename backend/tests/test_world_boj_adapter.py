"""Unit tests for Bank of Japan Time-Series adapter (mocked HTTP)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.boj_stat import (
    DEFAULT_BOJ_SERIES,
    BojSeriesSpec,
    BojStatAdapter,
    BojStatError,
    format_boj_period,
    normalize_series_id,
    parse_boj_resultset,
    parse_boj_survey_date,
)
from app.services.world_source_adapter import WorldDatasetVersion, WorldSeriesRef

CALL_RATE_PAYLOAD = {
    "STATUS": 200,
    "MESSAGEID": "M181000I",
    "MESSAGE": "Successfully completed",
    "RESULTSET": [
        {
            "SERIES_CODE": "STRDCLUCON",
            "NAME_OF_TIME_SERIES": "Call Rate, Uncollateralized Overnight, Average (Daily)",
            "UNIT": "percent per annum",
            "FREQUENCY": "DAILY",
            "VALUES": {
                "SURVEY_DATES": [20240801, 20240802, 20240803, 20240805],
                "VALUES": [0.227, 0.227, None, 0.228],
            },
        }
    ],
}


def _run(coro):
    return asyncio.run(coro)


async def _collect_datasets(adapter: BojStatAdapter):
    return [item async for item in adapter.list_datasets()]


def test_normalize_and_period_helpers():
    assert normalize_series_id("STRDCLUCON") == "STRDCLUCON"
    assert normalize_series_id("FM01'STRDCLUCON") == "STRDCLUCON"
    with pytest.raises(BojStatError):
        normalize_series_id("  ")
    assert format_boj_period(date(2024, 8, 12), frequency="daily") == "202408"
    assert format_boj_period(date(2024, 8, 12), frequency="monthly") == "202408"
    assert format_boj_period(date(2024, 4, 1), frequency="quarterly") == "202402"
    assert format_boj_period(date(2024, 1, 1), frequency="annual") == "2024"
    assert parse_boj_survey_date(20240805, frequency="daily") == date(2024, 8, 5)
    assert parse_boj_survey_date("202408", frequency="monthly") == date(2024, 8, 1)


def test_parse_boj_resultset_skips_nulls():
    title, obs = parse_boj_resultset(
        CALL_RATE_PAYLOAD, series_id="STRDCLUCON", frequency="daily"
    )
    assert "Call Rate" in (title or "")
    assert [o.period for o in obs] == [
        date(2024, 8, 1),
        date(2024, 8, 2),
        date(2024, 8, 5),
    ]
    assert obs[-1].value == 0.228


def test_default_catalog_has_core_passport_series():
    adapter = BojStatAdapter()
    assert adapter.provider == "boj"
    ids = {s.series_id for s in DEFAULT_BOJ_SERIES}
    assert "STRDCLUCON" in ids
    assert "FXERD04" in ids
    assert "MAM1NAM2M2MO" in ids
    datasets = _run(_collect_datasets(adapter))
    assert {d.dataset_id for d in datasets} >= {"FM01", "FM08", "MD02"}


def test_fetch_series_mocked():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = CALL_RATE_PAYLOAD
    response.text = "{}"
    session.get.return_value = response

    adapter = BojStatAdapter(
        series=(
            BojSeriesSpec(
                series_id="STRDCLUCON",
                dataset_id="FM01",
                frequency="daily",
                unit_code="PERCENT",
            ),
        ),
        session=session,
    )
    ref = WorldSeriesRef(
        provider="boj",
        dataset_id="FM01",
        series_id="STRDCLUCON",
        country_code="JP",
        frequency="daily",
        unit_code="PERCENT",
    )
    payload = _run(adapter.fetch_series(ref, date_from=date(2024, 8, 1), date_to=date(2024, 8, 31)))
    assert len(payload.observations) == 3
    assert payload.observations[0].value == 0.227
    assert session.get.called


def test_fetch_rejects_provider_mismatch():
    adapter = BojStatAdapter()
    ref = WorldSeriesRef(
        provider="estat",
        dataset_id="FM01",
        series_id="STRDCLUCON",
        country_code="JP",
        frequency="daily",
        unit_code="PERCENT",
    )
    with pytest.raises(BojStatError, match="Provider mismatch"):
        _run(adapter.fetch_series(ref))


def test_resolve_boj_adapter_registry():
    from app.services.world_national_ingest import resolve_adapter

    adapter = resolve_adapter("boj")
    assert adapter.provider == "boj"
