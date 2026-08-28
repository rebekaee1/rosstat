"""Unit tests for Reserve Bank of Australia statistical CSV adapter (mocked HTTP)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.rba_stats import (
    DEFAULT_RBA_SERIES,
    RbaSeriesSpec,
    RbaStatsAdapter,
    RbaStatsError,
    csv_filename_for_table,
    normalize_series_id,
    parse_rba_csv_series,
    parse_rba_date,
    table_csv_url,
)
from app.services.world_source_adapter import WorldDatasetVersion, WorldSeriesRef

F1_CASH_FIXTURE = """\
F1 INTEREST RATES AND YIELDS – MONEY MARKET – DAILY
Title,Cash Rate Target,Interbank Overnight Cash Rate
Description,Cash Rate Target; daily,Interbank Overnight Cash Rate; daily
Frequency,Daily,Daily
Type,Original,Original
Units,Per cent,Per cent


Source,RBA,RBA
Publication date,12-Aug-2026,12-Aug-2026
Series ID,FIRMMCRTD,FIRMMCRID
06-May-2026,4.35,4.34
07-May-2026,4.35,
08-May-2026,4.35,4.35
11-May-2026,,4.36
12-May-2026,4.35,4.34
"""

F11_1_FX_FIXTURE = """\
F11.1  EXCHANGE RATES
Title,A$1=USD,Trade-weighted Index May 1970 = 100
Description,AUD/USD Exchange Rate,Australian Dollar Trade-weighted Index
Frequency,Daily,Daily
Type,Indicative,Indicative
Units,USD,Index


Source,WM/Reuters,RBA
Publication date,11-Aug-2026,11-Aug-2026
Series ID,FXRUSD,FXRTWI
10-Aug-2026,0.6521,61.40
11-Aug-2026,0.6540,61.55
"""

F1_1_MONTHLY_SLASH_DATES = """\
F1.1 INTEREST RATES AND YIELDS – MONEY MARKET
Title,Cash Rate Target
Description,Cash Rate Target; monthly average
Frequency,Monthly
Type,Original
Units,Per cent


Source,RBA
Publication date,01-May-2026
Series ID,FIRMMCRT
31/03/2026,4.10
30/04/2026,4.10
"""


def _run(coro):
    return asyncio.run(coro)


def _adapter_with_session(session: MagicMock, **kwargs) -> RbaStatsAdapter:
    return RbaStatsAdapter(session=session, **kwargs)


async def _collect_datasets(adapter: RbaStatsAdapter) -> list[WorldDatasetVersion]:
    return [item async for item in adapter.list_datasets()]


async def _collect_series(
    adapter: RbaStatsAdapter, dataset: WorldDatasetVersion
) -> list[WorldSeriesRef]:
    return [item async for item in adapter.list_series(dataset)]


def test_normalize_and_url_helpers():
    assert normalize_series_id(" firmmcrtd ") == "FIRMMCRTD"
    with pytest.raises(RbaStatsError):
        normalize_series_id("  ")
    assert csv_filename_for_table("F1") == "f1-data.csv"
    assert csv_filename_for_table("F11.1") == "f11.1-data.csv"
    assert table_csv_url("F11.1") == (
        "https://www.rba.gov.au/statistics/tables/csv/f11.1-data.csv"
    )
    assert parse_rba_date("12-Aug-2026") == date(2026, 8, 12)
    assert parse_rba_date("31/03/2026") == date(2026, 3, 31)
    assert parse_rba_date("2026-05-06") == date(2026, 5, 6)


def test_parse_rba_csv_skips_blank_and_sorts():
    title, obs = parse_rba_csv_series(F1_CASH_FIXTURE, series_id="FIRMMCRTD")
    assert title == "Cash Rate Target"
    assert [o.period for o in obs] == [
        date(2026, 5, 6),
        date(2026, 5, 7),
        date(2026, 5, 8),
        date(2026, 5, 12),
    ]
    assert obs[0].value == 4.35
    assert all(o.value == 4.35 for o in obs)


def test_parse_rba_csv_slash_dates_and_fx():
    _, cash = parse_rba_csv_series(F1_1_MONTHLY_SLASH_DATES, series_id="FIRMMCRT")
    assert [o.period for o in cash] == [date(2026, 3, 31), date(2026, 4, 30)]
    title, fx = parse_rba_csv_series(F11_1_FX_FIXTURE, series_id="FXRUSD")
    assert "USD" in (title or "")
    assert [o.value for o in fx] == [0.6521, 0.6540]
    _, twi = parse_rba_csv_series(F11_1_FX_FIXTURE, series_id="FXRTWI")
    assert twi[-1].value == 61.55


def test_parse_rba_csv_rejects_missing_series():
    with pytest.raises(RbaStatsError, match="no column"):
        parse_rba_csv_series(F1_CASH_FIXTURE, series_id="NOPE")


def test_default_constructor_exposes_cash_and_fx():
    adapter = RbaStatsAdapter()
    assert adapter.provider == "rba"
    assert adapter.public_source_name == "Reserve Bank of Australia"
    datasets = _run(_collect_datasets(adapter))
    ids = {d.dataset_id for d in datasets}
    assert "F1" in ids
    assert "F11.1" in ids
    series_ids = {s.series_id for s in DEFAULT_RBA_SERIES}
    assert "FIRMMCRTD" in series_ids
    assert "FXRUSD" in series_ids
    assert "FXRTWI" in series_ids


def test_list_series_for_cash_and_fx_tables():
    adapter = RbaStatsAdapter()
    cash = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="rba", dataset_id="F1"),
        )
    )
    assert len(cash) == 1
    ref = cash[0]
    assert ref.provider == "rba"
    assert ref.series_id == "FIRMMCRTD"
    assert ref.country_code == "AU"
    assert ref.frequency == "daily"
    assert ref.unit_code == "PERCENT"
    assert ref.source_url and ref.source_url.endswith("/f1-data.csv")

    fx = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="rba", dataset_id="F11.1"),
        )
    )
    assert {s.series_id for s in fx} == {"FXRUSD", "FXRTWI"}
    assert all(s.dataset_id == "F11.1" for s in fx)
    assert all(s.country_code == "AU" for s in fx)


def test_fetch_series_parses_cash_rate_csv():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "text/csv"}
    response.content = F1_CASH_FIXTURE.encode("utf-8")
    response.text = F1_CASH_FIXTURE
    session.get.return_value = response

    adapter = _adapter_with_session(session)
    ref = WorldSeriesRef(
        provider="rba",
        dataset_id="F1",
        series_id="FIRMMCRTD",
        country_code="AU",
        frequency="daily",
        unit_code="PERCENT",
    )
    payload = _run(adapter.fetch_series(ref))
    assert payload.ref.provider == "rba"
    assert len(payload.observations) == 4
    assert payload.observations[0].period == date(2026, 5, 6)
    assert payload.observations[-1].value == 4.35
    assert payload.source_hash
    assert payload.revision_token and payload.revision_token.startswith("2026-05-06/")
    assert payload.ref.title and "cash" in payload.ref.title.lower()

    session.get.assert_called_once()
    args, kwargs = session.get.call_args
    assert args[0].endswith("/csv/f1-data.csv")
    assert "User-Agent" in kwargs["headers"]


def test_fetch_series_date_window_filters_client_side():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "text/csv"}
    response.content = F11_1_FX_FIXTURE.encode("utf-8")
    response.text = F11_1_FX_FIXTURE
    session.get.return_value = response

    adapter = _adapter_with_session(session)
    ref = WorldSeriesRef(
        provider="rba",
        dataset_id="F11.1",
        series_id="FXRUSD",
        country_code="AU",
        frequency="daily",
        unit_code="USD",
        title="AUD/USD",
    )
    payload = _run(
        adapter.fetch_series(
            ref,
            date_from=date(2026, 8, 11),
            date_to=date(2026, 8, 11),
        )
    )
    assert [o.value for o in payload.observations] == [0.6540]
    args, _kwargs = session.get.call_args
    assert args[0].endswith("/csv/f11.1-data.csv")


def test_fetch_series_rejects_provider_mismatch():
    adapter = RbaStatsAdapter()
    ref = WorldSeriesRef(
        provider="boc_valet",
        dataset_id="F1",
        series_id="FIRMMCRTD",
        country_code="AU",
        frequency="daily",
        unit_code="PERCENT",
    )
    with pytest.raises(RbaStatsError, match="Provider mismatch"):
        _run(adapter.fetch_series(ref))


def test_fetch_series_propagates_http_error():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 403
    response.headers = {"Content-Type": "text/html"}
    response.content = b"<html>Access Denied</html>"
    response.text = "<html>Access Denied</html>"
    session.get.return_value = response

    adapter = _adapter_with_session(session)
    ref = WorldSeriesRef(
        provider="rba",
        dataset_id="F1",
        series_id="FIRMMCRTD",
        country_code="AU",
        frequency="daily",
        unit_code="PERCENT",
    )
    with pytest.raises(RbaStatsError, match="HTTP 403"):
        _run(adapter.fetch_series(ref))


def test_empty_curated_catalog_rejected():
    with pytest.raises(RbaStatsError, match="at least one"):
        RbaStatsAdapter(series=())


def test_resolve_adapter_registry_points_at_rba_stats():
    from app.services.world_national_ingest import resolve_adapter

    adapter = resolve_adapter("rba")
    assert adapter.provider == "rba"
    assert adapter.public_source_name == "Reserve Bank of Australia"
    assert isinstance(adapter, RbaStatsAdapter)


def test_custom_curated_group_lists_members():
    adapter = RbaStatsAdapter(
        series=(
            RbaSeriesSpec(
                series_id="FXRUSD",
                dataset_id="F11.1",
                title="AUD/USD",
                unit_code="USD",
                frequency="daily",
            ),
            RbaSeriesSpec(
                series_id="FXRTWI",
                dataset_id="F11.1",
                title="TWI",
                unit_code="INDEX",
                frequency="daily",
            ),
        )
    )
    datasets = _run(_collect_datasets(adapter))
    assert [d.dataset_id for d in datasets] == ["F11.1"]
    series = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="rba", dataset_id="F11.1"),
        )
    )
    assert [s.series_id for s in series] == ["FXRUSD", "FXRTWI"]
