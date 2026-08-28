"""Unit tests for Bank of England IADB CSV adapter (mocked HTTP)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.world_adapters.boe_iadb import (
    DEFAULT_BOE_SERIES,
    BoeIadbAdapter,
    BoeIadbError,
    BoeSeriesSpec,
    create_adapter,
    format_boe_date_param,
    normalize_series_id,
    observations_url,
    parse_boe_date,
    parse_boe_iadb_csv,
)
from app.services.world_source_adapter import WorldDatasetVersion, WorldSeriesRef


BANK_RATE_CSV = """\
DATE,IUDBEDR
07 Aug 2025,4
18 Dec 2025,3.75
11 Aug 2026,3.75
"""

FX_CSV = """\
DATE,XUDLUSS
10 Aug 2026,1.3480
11 Aug 2026,1.3509
"""

BLANK_GAP_CSV = """\
DATE,IUDBEDR
10 Aug 2026,3.75
11 Aug 2026,
12 Aug 2026,3.75
"""


def _run(coro):
    return asyncio.run(coro)


async def _collect_datasets(adapter: BoeIadbAdapter) -> list[WorldDatasetVersion]:
    return [item async for item in adapter.list_datasets()]


async def _collect_series(
    adapter: BoeIadbAdapter, dataset: WorldDatasetVersion
) -> list[WorldSeriesRef]:
    return [item async for item in adapter.list_series(dataset)]


def _mock_session(text: str, *, status: int = 200, content_type: str = "application/csv") -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.headers = {"Content-Type": content_type}
    response.text = text
    response.content = text.encode("utf-8")
    session = MagicMock()
    session.get.return_value = response
    return session


def test_normalize_and_url_helpers():
    assert normalize_series_id(" iudbedr ") == "IUDBEDR"
    with pytest.raises(BoeIadbError):
        normalize_series_id("  ")
    assert format_boe_date_param(date(2020, 1, 2)) == "02/Jan/2020"
    url = observations_url("IUDBEDR", date_from=date(2020, 1, 1), date_to=date(2020, 1, 31))
    assert "SeriesCodes=IUDBEDR" in url
    assert "Datefrom=01/Jan/2020" in url


def test_parse_boe_date_variants():
    assert parse_boe_date("11 Aug 2026") == date(2026, 8, 11)
    assert parse_boe_date("02/01/2020") == date(2020, 1, 2)
    assert parse_boe_date("2026-08-11") == date(2026, 8, 11)


def test_parse_csv_skips_blank_and_sorts():
    obs = parse_boe_iadb_csv(BLANK_GAP_CSV, series_id="IUDBEDR")
    assert [o.period for o in obs] == [date(2026, 8, 10), date(2026, 8, 12)]
    assert obs[0].value == 3.75


def test_parse_csv_rejects_html_block():
    with pytest.raises(BoeIadbError, match="HTML|blocked"):
        parse_boe_iadb_csv("<html>Access Denied</html>", series_id="IUDBEDR")


def test_default_constructor_exposes_confirmed_series():
    adapter = BoeIadbAdapter()
    assert adapter.provider == "boe_iadb"
    assert adapter.public_source_name == "Bank of England"
    datasets = _run(_collect_datasets(adapter))
    ids = {d.dataset_id for d in datasets}
    assert "IUDBEDR" in ids
    assert "XUDLUSS" in ids
    assert {s.series_id for s in DEFAULT_BOE_SERIES} == {"IUDBEDR", "XUDLUSS"}


def test_list_series_for_bank_rate():
    adapter = BoeIadbAdapter()
    series = _run(
        _collect_series(
            adapter,
            WorldDatasetVersion(provider="boe_iadb", dataset_id="IUDBEDR"),
        )
    )
    assert len(series) == 1
    ref = series[0]
    assert ref.series_id == "IUDBEDR"
    assert ref.country_code == "UK"
    assert ref.frequency == "daily"
    assert ref.unit_code == "PERCENT"


def test_fetch_series_mocked():
    session = _mock_session(BANK_RATE_CSV)
    adapter = BoeIadbAdapter(session=session)
    ref = WorldSeriesRef(
        provider="boe_iadb",
        dataset_id="IUDBEDR",
        series_id="IUDBEDR",
        country_code="UK",
        frequency="daily",
        unit_code="PERCENT",
    )
    payload = _run(
        adapter.fetch_series(
            ref, date_from=date(2025, 1, 1), date_to=date(2026, 8, 12)
        )
    )
    assert len(payload.observations) == 3
    assert payload.observations[-1].value == 3.75
    assert payload.source_hash
    session.get.assert_called_once()
    params = session.get.call_args.kwargs["params"]
    assert params["SeriesCodes"] == "IUDBEDR"
    assert params["CSVF"] == "TN"


def test_fetch_fx_mocked():
    session = _mock_session(FX_CSV)
    adapter = BoeIadbAdapter(
        [
            BoeSeriesSpec(
                series_id="XUDLUSS",
                dataset_id="XUDLUSS",
                unit_code="USD_PER_GBP",
                frequency="daily",
            )
        ],
        session=session,
    )
    ref = WorldSeriesRef(
        provider="boe_iadb",
        dataset_id="XUDLUSS",
        series_id="XUDLUSS",
        country_code="UK",
        frequency="daily",
        unit_code="USD_PER_GBP",
    )
    payload = _run(adapter.fetch_series(ref))
    assert payload.observations[-1].period == date(2026, 8, 11)
    assert payload.observations[-1].value == 1.3509


def test_fetch_http_error():
    session = _mock_session("denied", status=403, content_type="text/html")
    adapter = BoeIadbAdapter(session=session)
    ref = WorldSeriesRef(
        provider="boe_iadb",
        dataset_id="IUDBEDR",
        series_id="IUDBEDR",
        country_code="UK",
        frequency="daily",
        unit_code="PERCENT",
    )
    with pytest.raises(BoeIadbError, match="HTTP 403"):
        _run(adapter.fetch_series(ref))


def test_create_adapter_from_national_like_rows():
    class Row:
        provider = "boe_iadb"
        series_id = "IUDBEDR"
        dataset_id = "IUDBEDR"
        frequency = "daily"
        unit = "PERCENT"
        name_en = "Official Bank Rate"
        source_url = None
        dimensions = {}

    adapter = create_adapter(series_specs=[Row()])
    datasets = _run(_collect_datasets(adapter))
    assert datasets[0].dataset_id == "IUDBEDR"
